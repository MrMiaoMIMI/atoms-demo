"""LLM access with a single streaming interface.

RealLLM  -> DeepSeek (OpenAI-compatible) streaming endpoint.
MockLLM  -> demo placeholder used only when no API key is configured; it is
            never a runtime fallback for a failing real model.
"""
import logging
from collections.abc import AsyncIterator

import httpx

import config
from mocks import agents as agent_mocks
from mocks import templates

logger = logging.getLogger(__name__)


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
