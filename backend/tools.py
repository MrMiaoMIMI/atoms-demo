"""Deterministic tools used by the agents, plus a per-role Toolbox.

Tools are plain async Python functions. No MCP or agent framework is needed:
the orchestrator passes a role-scoped ``Toolbox`` to each agent, so e.g. Bob
cannot write files and Mike cannot build a preview.
"""
from __future__ import annotations

import asyncio
import shutil
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

import config
import db
import diffing
import frontend_builder
import runtime
import scaffold
import views
from workspace import Workspace, WorkspaceError

Emit = Callable[[str, dict], Awaitable[Any]]


@dataclass
class ToolContext:
    pid: str
    run_id: str
    agent: str
    emit: Emit
    version: int = 1
    files: dict[str, str] = field(default_factory=dict)
    # Populated by the tool loop. ``execution_id`` links a mutation to the
    # timeline step the user can click; ``plan`` lets build tools reuse the
    # planner contract.
    execution_id: int | None = None
    plan: dict | None = None
    workspace: Workspace | None = None
    # Set by ``Toolbox.invoke`` so the tool loop can attach the view kind to
    # the execution event the UI renders.
    last_view_type: str | None = None


def _project_mode(paths: set[str]) -> str:
    has_frontend = any(path.startswith("frontend/") for path in paths)
    has_backend = any(path.startswith("backend/") for path in paths)
    if has_frontend and has_backend:
        return "fullstack"
    if has_backend:
        return "backend"
    return "frontend"


async def read_project_state(ctx: ToolContext) -> dict:
    project = await db.get_project(ctx.pid)
    files = await db.latest_artifacts(ctx.pid)
    return {
        "project": project,
        "files": files,
        "mode": _project_mode(set(files)),
    }


async def read_file(ctx: ToolContext, path: str) -> str | None:
    files = ctx.files or await db.latest_artifacts(ctx.pid)
    return files.get(path)


async def write_file(ctx: ToolContext, path: str, content: str) -> None:
    await db.add_artifact(ctx.pid, path, content, ctx.version)
    ctx.files[path] = content
    await ctx.emit(
        "artifact",
        {"filename": path, "content": content, "version": ctx.version, "run_id": ctx.run_id},
    )


async def publish_files(ctx: ToolContext, files: dict[str, str]) -> None:
    """Replace the project tree while preserving its SQLite data directory."""
    await runtime.runtime.stop(ctx.pid)
    target = config.APPS_DIR / ctx.pid

    def write() -> None:
        target.mkdir(parents=True, exist_ok=True)
        backend = target / "backend"
        backend.mkdir(parents=True, exist_ok=True)
        # Keep the published snapshot and the project SQLite data in place.
        # Moving data aside would also briefly dangle the published runtime's
        # symlink, so both are preserved rather than recreated.
        keep = {".published", "backend"}
        for child in target.iterdir():
            if child.name in keep:
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        for child in backend.iterdir():
            if child.name == "data":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        (backend / "data").mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            dest = target / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

    await asyncio.to_thread(write)


async def build_preview(ctx: ToolContext, plan: dict) -> None:
    if plan["mode"] in ("frontend", "fullstack"):
        await frontend_builder.build(ctx.pid, plan["title"])
    if plan["mode"] == "backend":
        await asyncio.to_thread(
            frontend_builder.publish_api_page, ctx.pid, plan["title"], plan["api"]
        )


async def start_runtime(ctx: ToolContext) -> int:
    return await runtime.runtime.ensure(ctx.pid)


async def check_health(ctx: ToolContext, port: int) -> None:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.get(f"http://127.0.0.1:{port}/api/health")
    except httpx.HTTPError as exc:
        raise RuntimeError(f"健康检查失败：{type(exc).__name__}: {exc}") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"健康检查返回 HTTP {response.status_code}")


async def validate_plan(ctx: ToolContext, plan: dict) -> bool:
    if not isinstance(plan, dict):
        return False
    if plan.get("mode") not in scaffold.MODES:
        return False
    if not isinstance(plan.get("files"), list) or not plan["files"]:
        return False
    if plan["mode"] in ("frontend", "fullstack") and not any(
        item.get("path") == "frontend/src/App.tsx" for item in plan["files"]
    ):
        return False
    if plan["mode"] in ("backend", "fullstack") and not any(
        item.get("path") == "backend/main.py" for item in plan["files"]
    ):
        return False
    return True


TOOL_REGISTRY = {
    "read_project_state": read_project_state,
    "read_file": read_file,
    "write_file": write_file,
    "publish_files": publish_files,
    "build_preview": build_preview,
    "start_runtime": start_runtime,
    "check_health": check_health,
    "validate_plan": validate_plan,
}


# ---------------------------------------------------------------------------
# LLM-facing tools (native function calling)
#
# These are separate from TOOL_REGISTRY so the still-existing deterministic
# pipeline keeps its old call semantics until the tool loop replaces it. The
# final loop invokes these through ``Toolbox.invoke``.
# ---------------------------------------------------------------------------


async def _workspace(ctx: ToolContext) -> Workspace:
    if ctx.workspace is None:
        files = ctx.files if ctx.files else await db.latest_artifacts(ctx.pid)
        ctx.workspace = Workspace(dict(files))
    return ctx.workspace


async def _record_change(ctx: ToolContext, change) -> int | None:
    """Persist and broadcast one tool mutation."""
    if change is None:
        return None
    change_id = await db.add_file_change(
        ctx.pid,
        version=ctx.version,
        filename=change.path,
        change_type=change.change_type,
        diff=change.diff.diff,
        additions=change.additions,
        deletions=change.deletions,
        run_id=ctx.run_id,
        agent=ctx.agent,
        execution_id=ctx.execution_id,
        truncated=change.diff.truncated,
    )
    await ctx.emit(
        "file_change",
        {
            "id": change_id,
            "filename": change.path,
            "change_type": change.change_type,
            "diff": change.diff.diff,
            "additions": change.additions,
            "deletions": change.deletions,
            "truncated": change.diff.truncated,
            "execution_id": ctx.execution_id,
            "run_id": ctx.run_id,
            "agent": ctx.agent,
            "version": ctx.version,
        },
    )
    return change_id


async def record_change(ctx: ToolContext, change) -> int | None:
    """Public wrapper used by deterministic steps such as scaffolding."""
    return await _record_change(ctx, change)


def _change_data(change, change_id: int | None) -> dict:
    if change is None:
        return {"changed": False, "change_id": None}
    return {
        "changed": True,
        "change_id": change_id,
        "filename": change.path,
        "change_type": change.change_type,
        "additions": change.additions,
        "deletions": change.deletions,
    }


async def llm_list_files(ctx: ToolContext, pattern: str | None = None) -> dict:
    ws = await _workspace(ctx)
    infos = ws.list_files(pattern)
    return {
        "ok": True,
        "data": {
            "files": [
                {"path": item.path, "bytes": item.bytes, "lines": item.lines}
                for item in infos
            ],
            "total": len(infos),
        },
    }


async def llm_read_file(
    ctx: ToolContext,
    path: str,
    offset: int = 1,
    limit: int = 400,
) -> dict:
    ws = await _workspace(ctx)
    result = ws.read(path, offset=offset, limit=limit)
    lines = result.content.splitlines()
    numbered = "\n".join(
        f"{result.start_line + index:>5}  {line}"
        for index, line in enumerate(lines)
    )
    return {
        "ok": True,
        "data": {
            "path": result.path,
            "content": result.content,
            "numbered": numbered,
            "start_line": result.start_line,
            "end_line": result.end_line,
            "total_lines": result.total_lines,
            "truncated": result.truncated,
        },
    }


async def llm_grep(
    ctx: ToolContext,
    pattern: str,
    glob: str | None = None,
    max_results: int = 30,
) -> dict:
    ws = await _workspace(ctx)
    result = ws.grep(pattern, glob=glob, max_results=max_results)
    return {
        "ok": True,
        "data": {
            "matches": [
                {"path": item.path, "line": item.line, "text": item.text}
                for item in result.matches
            ],
            "total": result.total,
            "truncated": result.truncated,
        },
    }


async def llm_write_file(
    ctx: ToolContext,
    path: str,
    content: str,
    overwrite: bool = False,
) -> dict:
    ws = await _workspace(ctx)
    change = ws.write(path, content, overwrite=bool(overwrite))
    if change is None:
        return {"ok": True, "data": {"path": path, **_change_data(None, None)}}
    await db.add_artifact(ctx.pid, change.path, change.new or "", ctx.version)
    change_id = await _record_change(ctx, change)
    await ctx.emit(
        "artifact",
        {
            "filename": change.path,
            "content": change.new or "",
            "version": ctx.version,
            "run_id": ctx.run_id,
        },
    )
    return {"ok": True, "data": _change_data(change, change_id)}


async def llm_edit_file(
    ctx: ToolContext,
    path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> dict:
    ws = await _workspace(ctx)
    change = ws.edit(
        path,
        old_string,
        new_string,
        replace_all=bool(replace_all),
    )
    if change is None:
        return {"ok": True, "data": {"path": path, **_change_data(None, None)}}
    await db.add_artifact(ctx.pid, change.path, change.new or "", ctx.version)
    change_id = await _record_change(ctx, change)
    await ctx.emit(
        "artifact",
        {
            "filename": change.path,
            "content": change.new or "",
            "version": ctx.version,
            "run_id": ctx.run_id,
        },
    )
    return {"ok": True, "data": _change_data(change, change_id)}


async def llm_delete_file(ctx: ToolContext, path: str) -> dict:
    ws = await _workspace(ctx)
    change = ws.delete(path)
    await db.add_artifact_deleted(ctx.pid, change.path, ctx.version)
    change_id = await _record_change(ctx, change)
    return {"ok": True, "data": _change_data(change, change_id)}


async def _runtime_log_text(pid: str) -> str:
    path = config.APPS_DIR / pid / ".runtime.log"
    if not path.is_file():
        return ""
    return await asyncio.to_thread(
        path.read_text, encoding="utf-8", errors="replace"
    )


async def llm_build_preview(ctx: ToolContext) -> dict:
    if not ctx.plan:
        raise RuntimeError("缺少项目计划，无法构建预览")
    mode = ctx.plan.get("mode")
    command = (
        "esbuild src/main.tsx --bundle --outdir=dist --format=iife"
        if mode in ("frontend", "fullstack")
        else "生成内置 API 控制台"
    )
    started = time.monotonic()
    ws = await _workspace(ctx)
    try:
        # Build tools see the staged tree; only the build step materialises it.
        await asyncio.to_thread(
            ws.apply_to, config.APPS_DIR / ctx.pid, reconcile_source=True
        )
        await build_preview(ctx, ctx.plan)
    except frontend_builder.BuildError as exc:
        message = str(exc)
        return {
            "ok": False,
            "error": {"code": "build_failed", "message": message},
            "data": {
                "mode": mode,
                "command": command,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "exit_code": 1,
                "output": message,
            },
        }
    return {
        "ok": True,
        "data": {
            "mode": mode,
            "command": command,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "exit_code": 0,
            "output": "构建成功",
        },
    }


async def llm_start_runtime(ctx: ToolContext) -> dict:
    command = "python -m uvicorn main:app --host 127.0.0.1"
    started = time.monotonic()
    ws = await _workspace(ctx)
    try:
        await asyncio.to_thread(
            ws.apply_to, config.APPS_DIR / ctx.pid, reconcile_source=True
        )
        # The process must pick up the staged backend source, not the previous one.
        await runtime.runtime.stop(ctx.pid)
        port = await start_runtime(ctx)
    except runtime.AppRuntimeError as exc:
        message = str(exc)
        return {
            "ok": False,
            "error": {"code": "runtime_failed", "message": message},
            "data": {
                "command": command,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "exit_code": 1,
                "log": message,
            },
        }
    tail = (await _runtime_log_text(ctx.pid)).splitlines()[-40:]
    log_text = "\n".join(tail)
    if not log_text:
        # uvicorn runs at warning level, so a clean start often has no output.
        log_text = f"✓ 服务已启动，监听 127.0.0.1:{port}"
    return {
        "ok": True,
        "data": {
            "port": port,
            "command": f"{command} --port {port}",
            "duration_ms": int((time.monotonic() - started) * 1000),
            "exit_code": 0,
            "log": log_text,
        },
    }


async def llm_check_health(ctx: ToolContext, port: int) -> dict:
    url = f"http://127.0.0.1:{port}/api/health"
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        message = f"健康检查失败：{type(exc).__name__}: {exc}"
        return {
            "ok": False,
            "error": {"code": "health_failed", "message": message},
            "data": {
                "method": "GET",
                "url": "/api/health",
                "status": None,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "body": "",
            },
        }
    data = {
        "method": "GET",
        "url": "/api/health",
        "status": response.status_code,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "body": response.text[:16000],
    }
    if response.status_code >= 400:
        return {
            "ok": False,
            "error": {
                "code": "health_failed",
                "message": f"健康检查返回 HTTP {response.status_code}",
            },
            "data": data,
        }
    return {"ok": True, "data": data}


async def llm_read_runtime_log(ctx: ToolContext, lines: int = 80) -> dict:
    all_lines = (await _runtime_log_text(ctx.pid)).splitlines()
    limit = max(1, min(int(lines), 400))
    tail = all_lines[-limit:]
    return {
        "ok": True,
        "data": {
            "lines": tail,
            "text": "\n".join(tail),
            "truncated": len(all_lines) > len(tail),
        },
    }


async def llm_validate_plan(ctx: ToolContext, plan: dict) -> dict:
    return {"ok": True, "data": {"valid": await validate_plan(ctx, plan)}}


async def llm_read_project_state(ctx: ToolContext) -> dict:
    return {"ok": True, "data": await read_project_state(ctx)}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict
    read_only: bool = False

    def openai(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


_EMPTY_PARAMS = {"type": "object", "properties": {}, "additionalProperties": False}

LLM_TOOL_SPECS: dict[str, ToolSpec] = {
    "list_files": ToolSpec(
        name="list_files",
        description="列出项目内可编辑的源文件（路径、字节数、行数）。可用 pattern 过滤，如 frontend/src/**/*.tsx。",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "可选的 glob，例如 frontend/src/**/*.tsx",
                }
            },
            "additionalProperties": False,
        },
        read_only=True,
    ),
    "read_file": ToolSpec(
        name="read_file",
        description="读取项目文件的一段内容。返回 raw content 和带行号的 numbered 版本；修改前先读文件。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "项目相对路径"},
                "offset": {
                    "type": "integer",
                    "description": "起始行，1-based，默认 1",
                    "minimum": 1,
                },
                "limit": {
                    "type": "integer",
                    "description": "最多读取行数，默认 400，上限 800",
                    "minimum": 1,
                    "maximum": 800,
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        read_only=True,
    ),
    "grep": ToolSpec(
        name="grep",
        description="用正则搜索项目源码，返回文件、行号和该行内容。",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Python 正则"},
                "glob": {
                    "type": "string",
                    "description": "可选文件过滤，例如 frontend/src/**/*.tsx",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最多返回条数，默认 30，上限 50",
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
        read_only=True,
    ),
    "write_file": ToolSpec(
        name="write_file",
        description=(
            "创建新文件，或显式 overwrite=true 整文件重写。修改已有文件优先用 edit_file。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "项目相对路径"},
                "content": {"type": "string", "description": "完整文件内容"},
                "overwrite": {
                    "type": "boolean",
                    "description": "已存在文件必须显式设为 true",
                },
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    ),
    "edit_file": ToolSpec(
        name="edit_file",
        description=(
            "对已有文件做精确字符串替换。old_string 必须在文件中唯一命中，"
            "否则请求失败；多处替换请设置 replace_all=true。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "项目相对路径"},
                "old_string": {
                    "type": "string",
                    "description": "要替换的原文，必须精确匹配",
                },
                "new_string": {"type": "string", "description": "替换后的内容"},
                "replace_all": {
                    "type": "boolean",
                    "description": "是否替换所有命中，默认 false",
                },
            },
            "required": ["path", "old_string", "new_string"],
            "additionalProperties": False,
        },
    ),
    "delete_file": ToolSpec(
        name="delete_file",
        description="删除项目文件；删除后应重新构建并处理引用错误。",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "项目相对路径"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    ),
    "build_preview": ToolSpec(
        name="build_preview",
        description="用 esbuild 构建前端预览（或生成纯后端 API 页面），返回真实构建错误。",
        parameters=_EMPTY_PARAMS,
    ),
    "start_runtime": ToolSpec(
        name="start_runtime",
        description="启动/重启项目自己的 FastAPI 运行时，返回端口。",
        parameters=_EMPTY_PARAMS,
    ),
    "check_health": ToolSpec(
        name="check_health",
        description="检查项目后端的 /api/health。",
        parameters={
            "type": "object",
            "properties": {"port": {"type": "integer"}},
            "required": ["port"],
            "additionalProperties": False,
        },
    ),
    "read_runtime_log": ToolSpec(
        name="read_runtime_log",
        description="读取项目后端运行时日志尾部，用于修复启动错误。",
        parameters={
            "type": "object",
            "properties": {
                "lines": {
                    "type": "integer",
                    "description": "读取尾部行数，默认 80",
                    "minimum": 1,
                    "maximum": 400,
                }
            },
            "additionalProperties": False,
        },
        read_only=True,
    ),
    "read_project_state": ToolSpec(
        name="read_project_state",
        description="读取项目形态、文件列表和当前版本。",
        parameters=_EMPTY_PARAMS,
        read_only=True,
    ),
    "validate_plan": ToolSpec(
        name="validate_plan",
        description="校验 Planner 输出是否包含必需文件与合法形态。",
        parameters={
            "type": "object",
            "properties": {"plan": {"type": "object"}},
            "required": ["plan"],
            "additionalProperties": False,
        },
        read_only=True,
    ),
}

LLM_TOOL_REGISTRY = {
    "list_files": llm_list_files,
    "read_file": llm_read_file,
    "grep": llm_grep,
    "write_file": llm_write_file,
    "edit_file": llm_edit_file,
    "delete_file": llm_delete_file,
    "build_preview": llm_build_preview,
    "start_runtime": llm_start_runtime,
    "check_health": llm_check_health,
    "read_runtime_log": llm_read_runtime_log,
    "read_project_state": llm_read_project_state,
    "validate_plan": llm_validate_plan,
}


class Toolbox:
    def __init__(self, ctx: ToolContext, allowed: frozenset[str]):
        self.ctx = ctx
        self.allowed = allowed

    async def call(self, name: str, **kwargs) -> Any:
        if name not in self.allowed:
            raise PermissionError(f"工具 {name} 不属于角色 {self.ctx.agent}")
        tool = TOOL_REGISTRY.get(name)
        if tool is None:
            raise KeyError(f"未知工具：{name}")
        return await tool(self.ctx, **kwargs)

    def specs(self) -> list[dict]:
        """OpenAI-compatible function schemas for this role's tools."""
        return [
            spec.openai()
            for name, spec in LLM_TOOL_SPECS.items()
            if name in self.allowed
        ]

    async def invoke(self, name: str, arguments: dict | None = None) -> dict:
        """Execute one LLM tool call and always return a JSON-serialisable result."""
        self.ctx.last_view_type = None
        if name not in self.allowed:
            return _tool_error(
                "permission_denied",
                f"工具 {name} 不属于角色 {self.ctx.agent}",
            )
        spec = LLM_TOOL_SPECS.get(name)
        tool = LLM_TOOL_REGISTRY.get(name)
        if spec is None or tool is None:
            return _tool_error("unknown_tool", f"未知工具：{name}")
        kwargs = arguments or {}
        try:
            result = await tool(self.ctx, **kwargs)
        except WorkspaceError as exc:
            result = exc.to_result()
        except frontend_builder.BuildError as exc:
            result = _tool_error("build_failed", str(exc))
        except runtime.AppRuntimeError as exc:
            result = _tool_error("runtime_failed", str(exc))
        except asyncio.TimeoutError:
            result = _tool_error("timeout", f"工具 {name} 执行超时")
        except TypeError as exc:
            result = _tool_error("invalid_args", f"{name} 参数不正确：{exc}")
        except Exception as exc:  # noqa: BLE001 - tool errors must reach the model
            result = _tool_error("internal", f"{type(exc).__name__}: {exc}")
        if not (isinstance(result, dict) and "ok" in result):
            result = {"ok": True, "data": result}
        await self._record_view(name, kwargs, result)
        return result

    async def _record_view(
        self, name: str, arguments: dict, result: dict
    ) -> None:
        """Persist this step's read-only view; a failure must not fail the tool."""
        try:
            view = views.build_view(name, arguments, result)
        except Exception:  # noqa: BLE001 - views are best-effort presentation
            return
        if view is None:
            return
        view_type, payload, truncated = view
        if view_type == "diff":
            # The diff itself lives in file_changes; only mark the step so the
            # live SSE event and history agree on the view kind.
            self.ctx.last_view_type = "diff"
            return
        if self.ctx.execution_id is None:
            return
        try:
            await db.add_execution_view(
                self.ctx.pid,
                self.ctx.execution_id,
                view_type,
                payload,
                truncated,
            )
        except Exception:  # noqa: BLE001 - keep the tool result usable
            return
        self.ctx.last_view_type = view_type


def _tool_error(code: str, message: str) -> dict:
    return {"ok": False, "error": {"code": code, "message": message}}
