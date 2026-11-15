"""Deterministic tools used by the agents, plus a per-role Toolbox.

Tools are plain async Python functions. No MCP or agent framework is needed:
the orchestrator passes a role-scoped ``Toolbox`` to each agent, so e.g. Bob
cannot write files and Mike cannot build a preview.
"""
from __future__ import annotations

import asyncio
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

import config
import db
import frontend_builder
import runtime
import scaffold

Emit = Callable[[str, dict], Awaitable[Any]]


@dataclass
class ToolContext:
    pid: str
    run_id: str
    agent: str
    emit: Emit
    version: int = 1
    files: dict[str, str] = field(default_factory=dict)


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
