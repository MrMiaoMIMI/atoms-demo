"""Bounded native-function-calling loop shared by Bob and Alex.

The loop owns the conversation with the model, executes tool calls through the
role-scoped ``Toolbox``, and emits one execution step per tool call. It never
writes the final project state itself: the caller decides what to commit based
on the returned ``LoopResult`` and the build/health outcome.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import config
from llm import AssistantTurn, MockLLM, ToolCall
from tools import Toolbox

Emit = Callable[[str, dict], Awaitable[Any]]


class ToolLoopError(RuntimeError):
    """The loop could not complete because the model repeatedly failed."""


@dataclass
class LoopResult:
    text: str
    steps: int
    tool_calls: int
    stopped_reason: str  # done | max_steps | timeout | no_progress | max_tool_calls | truncated
    truncated: bool = False
    messages: list[dict] = field(default_factory=list)

    @property
    def completed(self) -> bool:
        return self.stopped_reason == "done"


async def run_tool_loop(
    *,
    llm,
    toolbox: Toolbox,
    system: str | None = None,
    user: str | None = None,
    initial_messages: list[dict] | None = None,
    meta: dict,
    emit: Emit,
    max_steps: int,
    timeout_seconds: float,
    max_tool_calls: int = 320,
    max_tool_calls_per_step: int = 8,
    no_progress_limit: int = 5,
) -> LoopResult:
    if initial_messages is not None:
        messages: list[dict] = [dict(message) for message in initial_messages]
    else:
        messages = [
            {"role": "system", "content": system or ""},
            {"role": "user", "content": user or ""},
        ]
    started = time.monotonic()
    total_calls = 0
    no_progress = 0
    last_text = ""

    def finish(
        reason: str,
        steps: int,
        *,
        truncated: bool = False,
    ) -> LoopResult:
        return LoopResult(
            text=last_text,
            steps=steps,
            tool_calls=total_calls,
            stopped_reason=reason,
            truncated=truncated,
            messages=list(messages),
        )

    for step in range(1, max_steps + 1):
        if time.monotonic() - started > timeout_seconds:
            return finish("timeout", step - 1)

        turn = await _call_llm(llm, messages, toolbox.specs(), meta, emit)
        last_text = turn.text or last_text

        # A truncated tool-call argument is never executed: running half a JSON
        # object would create a bogus edit. Ask the model to retry the call.
        if turn.tool_calls and turn.truncated:
            messages.append({"role": "assistant", "content": turn.text or ""})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "上一步工具调用参数因长度限制被截断，未执行。"
                        "请重新发起完整的工具调用，不要省略参数。"
                    ),
                }
            )
            no_progress += 1
            if no_progress >= no_progress_limit:
                return finish("truncated", step, truncated=True)
            continue

        if not turn.tool_calls:
            return finish("done", step, truncated=turn.truncated)

        messages.append(_assistant_message(turn))
        step_progress = False
        for call in turn.tool_calls[:max_tool_calls_per_step]:
            if total_calls >= max_tool_calls:
                messages.append(
                    _tool_message(
                        call,
                        _error("max_tool_calls", "本轮工具调用次数已达上限"),
                    )
                )
                return finish("max_tool_calls", step)
            total_calls += 1
            result, progressed = await _execute_call(toolbox, emit, call)
            step_progress = step_progress or progressed
            messages.append(_tool_message(call, result))

        if step_progress:
            no_progress = 0
        else:
            no_progress += 1
            if no_progress >= no_progress_limit:
                return finish("no_progress", step)

    return finish("max_steps", max_steps)


async def _call_llm(
    llm,
    messages: list[dict],
    tools: list[dict] | None,
    meta: dict,
    emit: Emit,
) -> AssistantTurn:
    attempts = 1 if isinstance(llm, MockLLM) else config.LLM_MAX_RETRIES + 1
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return await llm.turn(messages=messages, tools=tools, meta=meta)
        except Exception as exc:  # noqa: BLE001 - transport/model errors are retried
            last_error = exc
            if attempt + 1 >= attempts:
                break
            await emit(
                "execution",
                {
                    "step": "重试 LLM 调用",
                    "status": "warning",
                    "log": (
                        f"第 {attempt + 1}/{attempts - 1} 次重试："
                        f"{type(exc).__name__}: {str(exc)[:140]}"
                    ),
                },
            )
            delay = min(
                config.LLM_RETRY_BACKOFF * (2**attempt),
                config.LLM_RETRY_BACKOFF_MAX,
            )
            if delay > 0:
                await asyncio.sleep(delay)
    assert last_error is not None
    raise ToolLoopError(
        f"LLM 调用失败（已尝试 {attempts} 次）："
        f"{type(last_error).__name__}: {str(last_error)[:200]}"
    )


async def _execute_call(
    toolbox: Toolbox,
    emit: Emit,
    call: ToolCall,
) -> tuple[dict, bool]:
    arguments = _parse_arguments(call.arguments)
    target = (
        arguments.get("path")
        if isinstance(arguments, dict) and isinstance(arguments.get("path"), str)
        else None
    )
    label = _step_label(call.name, target, arguments)
    execution_id = await emit(
        "execution",
        {
            "step": label,
            "status": "running",
            "log": f"调用工具 {call.name}",
            "kind": "tool",
            "tool": call.name,
            "target": target,
        },
    )
    if isinstance(execution_id, int):
        toolbox.ctx.execution_id = execution_id
    else:
        toolbox.ctx.execution_id = None

    if arguments is None:
        result = _error(
            "invalid_args",
            f"{call.name} 的参数不是合法的 JSON 对象",
        )
    else:
        result = await toolbox.invoke(call.name, arguments)

    data = result.get("data") if isinstance(result, dict) else None
    ok = bool(result.get("ok")) if isinstance(result, dict) else False
    change_id = data.get("change_id") if isinstance(data, dict) else None
    await emit(
        "execution",
        {
            "id": execution_id,
            "step": label,
            "status": "success" if ok else "error",
            "log": _summary(result),
            "kind": "tool",
            "tool": call.name,
            "target": target,
            "change_id": change_id,
            "change_count": 1 if change_id else 0,
        },
    )
    progressed = ok and (
        (isinstance(data, dict) and bool(data.get("changed")))
        or call.name in {"build_preview", "start_runtime", "check_health"}
    )
    return result, bool(progressed)


def _assistant_message(turn: AssistantTurn) -> dict:
    return {
        "role": "assistant",
        "content": turn.text or None,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in turn.tool_calls
        ],
    }


def _tool_message(call: ToolCall, result: dict) -> dict:
    return {
        "role": "tool",
        "tool_call_id": call.id,
        "content": json.dumps(result, ensure_ascii=False, default=str),
    }


def _parse_arguments(raw: str | None) -> dict | None:
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _error(code: str, message: str) -> dict:
    return {"ok": False, "error": {"code": code, "message": message}}


_STEP_LABELS = {
    "list_files": "列出文件",
    "read_file": "读取",
    "grep": "搜索",
    "write_file": "写入",
    "edit_file": "编辑",
    "delete_file": "删除",
    "build_preview": "构建预览",
    "start_runtime": "启动后端",
    "check_health": "检查后端",
    "read_runtime_log": "读取运行时日志",
    "read_project_state": "读取项目状态",
    "validate_plan": "校验方案",
}


def _step_label(name: str, target: str | None, arguments: dict | None) -> str:
    base = _STEP_LABELS.get(name, name)
    if name in {"read_file", "write_file", "edit_file", "delete_file"} and target:
        return f"{base} {target}"
    if name in {"grep", "list_files"} and isinstance(arguments, dict):
        pattern = arguments.get("pattern") or arguments.get("glob")
        if isinstance(pattern, str) and pattern:
            return f"{base} {pattern}"
    return base


def _summary(result: dict) -> str:
    if not isinstance(result, dict):
        return "完成"
    if not result.get("ok"):
        error = result.get("error") or {}
        message = str(error.get("message") or "工具执行失败")
        return message[:180]
    data = result.get("data") or {}
    if not isinstance(data, dict):
        return "完成"
    if "additions" in data or "deletions" in data:
        return f"+{int(data.get('additions') or 0)} -{int(data.get('deletions') or 0)}"
    if "files" in data:
        return f"{data.get('total', len(data.get('files') or []))} 个文件"
    if "matches" in data:
        return f"{data.get('total', len(data.get('matches') or []))} 处命中"
    if "total_lines" in data:
        lines = int(data.get("total_lines") or 0)
        return f"{lines} 行" + ("（已截断）" if data.get("truncated") else "")
    if "port" in data:
        return f"端口 {data['port']}"
    if "valid" in data:
        return "方案有效" if data["valid"] else "方案无效"
    if data.get("changed") is False:
        return "内容无变化"
    return "完成"
