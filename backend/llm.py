"""LLM access with a single streaming interface.

RealLLM  -> DeepSeek (OpenAI-compatible) streaming endpoint.
MockLLM  -> demo placeholder used only when no API key is configured; it is
            never a runtime fallback for a failing real model.
"""
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import httpx

import config
from mocks import agents as agent_mocks
from mocks import templates

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """One function call requested by the model."""

    id: str
    name: str
    arguments: str  # raw JSON string, validated by the tool loop


@dataclass
class AssistantTurn:
    """One model turn, with optional native tool calls."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    truncated: bool = False


class MockLLM:
    label = "mock"

    async def stream(self, *, role: str, system: str, user: str, meta: dict | None = None) -> AsyncIterator[str]:
        meta = meta or {}
        if role == "mike":
            text = agent_mocks.mike_reply(meta)
        elif role == "title":
            text = agent_mocks.title_reply(meta)
        elif role == "consult":
            text = agent_mocks.consult_reply(meta)
        elif role == "planner":
            text = templates.mock_plan(
                meta.get("prompt", ""),
                meta.get("existing"),
                meta.get("existing_mode"),
            )
        else:
            text = templates.mock_file(
                meta.get("prompt", ""),
                meta.get("filename", "frontend/src/App.tsx"),
                meta.get("existing"),
                mode=meta.get("mode"),
                title=meta.get("title"),
            )

        step = 48
        for i in range(0, len(text), step):
            yield text[i : i + step]

    async def turn(
        self,
        *,
        messages: list[dict],
        tools: list[dict] | None = None,
        meta: dict | None = None,
        on_text=None,
    ) -> AssistantTurn:
        """Deterministic tool sequence so the loop and diff UI work without a key."""
        meta = meta or {}
        mode = str(meta.get("mode") or "frontend")
        title = str(meta.get("title") or "Mock 演示项目")
        prompt = str(meta.get("prompt") or "")
        existing = meta.get("existing") or {}
        iteration = bool(meta.get("iteration"))
        step = sum(1 for message in messages if message.get("role") == "assistant")

        def call(name: str, arguments: dict) -> AssistantTurn:
            return AssistantTurn(
                text="",
                tool_calls=[
                    ToolCall(
                        id=f"mock-{step}-{name}",
                        name=name,
                        arguments=json.dumps(arguments, ensure_ascii=False),
                    )
                ],
                finish_reason="tool_calls",
            )

        if not iteration:
            script: list[tuple[str, dict]] = []
            if mode in ("frontend", "fullstack"):
                script.append(
                    (
                        "write_file",
                        {
                            "path": "frontend/src/App.tsx",
                            "content": templates.mock_file(
                                prompt,
                                "frontend/src/App.tsx",
                                existing,
                                mode=mode,
                                title=title,
                            ),
                            # The scaffold seeds a starter App.tsx.
                            "overwrite": True,
                        },
                    )
                )
                script.append(
                    (
                        "write_file",
                        {
                            "path": "frontend/src/styles.css",
                            "content": templates.mock_file(
                                prompt,
                                "frontend/src/styles.css",
                                existing,
                                mode=mode,
                                title=title,
                            ),
                            # The scaffold seeds starter styles.
                            "overwrite": True,
                        },
                    )
                )
            if mode in ("backend", "fullstack"):
                script.append(
                    (
                        "write_file",
                        {
                            "path": "backend/main.py",
                            "content": templates.mock_file(
                                prompt,
                                "backend/main.py",
                                existing,
                                mode=mode,
                                title=title,
                            ),
                        },
                    )
                )
            # Backend-only builds also need the static API console entry so the
            # preview iframe and publish have something to serve.
            script.append(("build_preview", {}))
            if mode in ("backend", "fullstack"):
                script.append(("start_runtime", {}))
            if step < len(script):
                name, arguments = script[step]
                return call(name, arguments)
            return AssistantTurn(
                text="Mock 模式：已完成占位项目的工具循环。配置 LLM_API_KEY 后会按需求生成真实应用。",
                finish_reason="stop",
            )

        # Iteration: read one file, append a clearly-labelled mock line, then
        # build. This exercises the same tool path as a real edit.
        target = (
            "frontend/src/App.tsx"
            if "frontend/src/App.tsx" in existing
            else "backend/main.py"
            if "backend/main.py" in existing
            else "frontend/src/App.tsx"
        )
        if step == 0:
            return call("read_file", {"path": target})
        if step == 1:
            content = ""
            last_tool = next(
                (m for m in reversed(messages) if m.get("role") == "tool"), None
            )
            if last_tool:
                try:
                    payload = json.loads(last_tool.get("content") or "{}")
                    content = str(payload.get("data", {}).get("content") or "")
                except (TypeError, ValueError):
                    content = ""
            marker = (
                "# mock iteration: 未配置 LLM_API_KEY"
                if target.endswith(".py")
                else "/* mock iteration: 未配置 LLM_API_KEY */"
            )
            if content:
                return call(
                    "edit_file",
                    {
                        "path": target,
                        "old_string": content,
                        "new_string": f"{content}\n{marker}\n",
                    },
                )
            return call(
                "write_file",
                {
                    "path": target,
                    "content": f"{marker}\n",
                    "overwrite": True,
                },
            )
        if step == 2:
            return call("build_preview", {})
        if step == 3 and mode in ("backend", "fullstack"):
            return call("start_runtime", {})
        return AssistantTurn(
            text="Mock 模式：已完成一次占位修改。配置 LLM_API_KEY 后会按需求真实修改代码。",
            finish_reason="stop",
        )


class DeepSeekLLM:
    label = "deepseek"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=config.LLM_TIMEOUT, write=30.0, pool=10.0)
        )
        # Per-request output budget. If the provider rejects the configured
        # value we permanently fall back to DeepSeek's classic 8K ceiling.
        self._max_tokens = config.LLM_MAX_TOKENS

    async def stream(self, *, role: str, system: str, user: str, meta: dict | None = None) -> AsyncIterator[str]:
        import json

        url = f"{config.LLM_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.LLM_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        collected: list[str] = []

        # One completion may end with finish_reason=length (model/request
        # output budget). Continue from the cut point instead of shipping a
        # half-written file. The budget and pass count are configurable.
        for pass_index in range(config.LLM_CONTINUATION_PASSES):
            finish = {"reason": None}
            while True:
                payload = {
                    "model": config.LLM_MODEL,
                    "messages": messages,
                    "stream": True,
                    "temperature": config.LLM_TEMPERATURE,
                    "max_tokens": self._max_tokens,
                }
                async with self._client.stream("POST", url, json=payload, headers=headers) as resp:
                    if resp.status_code >= 400:
                        body = await resp.aread()
                        detail = body.decode("utf-8", "ignore")
                        if resp.status_code == 400 and self._max_tokens > 8192:
                            logger.warning(
                                "provider returned 400 with max_tokens=%s; "
                                "retrying with 8192: %s",
                                self._max_tokens,
                                detail[:200],
                            )
                            self._max_tokens = 8192
                            continue
                        raise RuntimeError(
                            f"LLM HTTP {resp.status_code}: {detail[:300]}"
                        )
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                            choice = obj["choices"][0]
                            delta = choice.get("delta", {}).get("content")
                            if choice.get("finish_reason"):
                                finish["reason"] = choice["finish_reason"]
                        except (ValueError, KeyError, IndexError):
                            continue
                        if delta:
                            collected.append(delta)
                            yield delta
                break

            if finish["reason"] != "length":
                return
            logger.info(
                "LLM output hit max_tokens=%s (pass %s/%s); requesting continuation",
                self._max_tokens,
                pass_index + 1,
                config.LLM_CONTINUATION_PASSES,
            )
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "assistant", "content": "".join(collected)},
                {
                    "role": "user",
                    "content": (
                        "上一条输出因长度限制被截断。请从中断处继续输出剩余内容，"
                        "不要重复已输出的任何内容，不要添加解释或代码围栏，直到文件完整闭合。"
                    ),
                },
            ]

        raise RuntimeError(
            "LLM output still truncated after "
            f"{config.LLM_CONTINUATION_PASSES} continuation passes"
        )

    async def _deltas(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        """Stream text/tool-call deltas from an OpenAI-compatible endpoint."""
        url = f"{config.LLM_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.LLM_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        while True:
            payload: dict = {
                "model": config.LLM_MODEL,
                "messages": messages,
                "stream": True,
                "temperature": config.LLM_TEMPERATURE,
                "max_tokens": self._max_tokens,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            async with self._client.stream(
                "POST", url, json=payload, headers=headers
            ) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    detail = body.decode("utf-8", "ignore")
                    if resp.status_code == 400 and self._max_tokens > 8192:
                        logger.warning(
                            "provider returned 400 with max_tokens=%s; "
                            "retrying with 8192: %s",
                            self._max_tokens,
                            detail[:200],
                        )
                        self._max_tokens = 8192
                        continue
                    raise RuntimeError(
                        f"LLM HTTP {resp.status_code}: {detail[:300]}"
                    )
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                        choice = obj["choices"][0]
                    except (ValueError, KeyError, IndexError):
                        continue
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield {"type": "text", "text": content}
                    for item in delta.get("tool_calls") or []:
                        function = item.get("function") or {}
                        yield {
                            "type": "tool_call",
                            "index": int(item.get("index") or 0),
                            "id": item.get("id"),
                            "name": function.get("name"),
                            "arguments": function.get("arguments"),
                        }
                    if choice.get("finish_reason"):
                        yield {"type": "finish", "reason": choice["finish_reason"]}
            break

    async def _collect_turn(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        on_text,
    ) -> AssistantTurn:
        text_parts: list[str] = []
        slots: dict[int, dict[str, str]] = {}
        finish_reason: str | None = None
        async for event in self._deltas(messages, tools):
            kind = event["type"]
            if kind == "text":
                text_parts.append(event["text"])
                if on_text is not None:
                    await on_text(event["text"])
            elif kind == "tool_call":
                slot = slots.setdefault(
                    event["index"],
                    {"id": "", "name": "", "arguments": ""},
                )
                if event["id"]:
                    slot["id"] = event["id"]
                if event["name"]:
                    slot["name"] = event["name"]
                if event["arguments"]:
                    slot["arguments"] += event["arguments"]
            elif kind == "finish":
                finish_reason = event["reason"]

        calls: list[ToolCall] = []
        for index in sorted(slots):
            slot = slots[index]
            if not slot["name"]:
                continue
            calls.append(
                ToolCall(
                    id=slot["id"] or f"call_{index}",
                    name=slot["name"],
                    arguments=slot["arguments"] or "{}",
                )
            )
        return AssistantTurn(
            text="".join(text_parts),
            tool_calls=calls,
            finish_reason=finish_reason,
            truncated=finish_reason == "length" and bool(calls),
        )

    async def turn(
        self,
        *,
        messages: list[dict],
        tools: list[dict] | None = None,
        meta: dict | None = None,
        on_text=None,
    ) -> AssistantTurn:
        """One native-function-calling turn, with text continuation."""
        current = list(messages)
        text_parts: list[str] = []
        for _ in range(config.LLM_CONTINUATION_PASSES):
            result = await self._collect_turn(current, tools, on_text)
            text_parts.append(result.text)
            if result.tool_calls or result.finish_reason != "length":
                result.text = "".join(text_parts)
                return result
            current = current + [
                {"role": "assistant", "content": result.text},
                {
                    "role": "user",
                    "content": (
                        "上一条输出因长度限制被截断。请从中断处继续输出剩余内容，"
                        "不要重复已输出的任何内容，不要添加解释或代码围栏。"
                    ),
                },
            ]
        return AssistantTurn(
            text="".join(text_parts),
            finish_reason="length",
            truncated=True,
        )


_shared: DeepSeekLLM | None = None


def get_llm():
    global _shared
    if config.LLM_MODE != "deepseek":
        return MockLLM()
    if _shared is None:
        _shared = DeepSeekLLM()
    return _shared


async def complete(
    *,
    role: str,
    system: str,
    user: str,
    meta: dict | None = None,
    max_chars: int = 200,
) -> str:
    """Collect a short completion without streaming it to a client.

    Used for lightweight side calls such as project naming; stops reading as
    soon as ``max_chars`` arrived so a chatty model cannot stall creation.
    """
    parts: list[str] = []
    size = 0
    async for chunk in get_llm().stream(role=role, system=system, user=user, meta=meta):
        parts.append(chunk)
        size += len(chunk)
        if size >= max_chars:
            break
    return "".join(parts)
