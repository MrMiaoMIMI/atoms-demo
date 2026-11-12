"""LLM access with a single streaming interface.

RealLLM  -> DeepSeek (OpenAI-compatible) streaming endpoint.
MockLLM  -> canned, chunk-by-chunk output so the UI behaves identically.
"""
from collections.abc import AsyncIterator

import httpx

import config
from mocks import agents as agent_mocks
from mocks import templates


class MockLLM:
    label = "mock"

    async def stream(self, *, role: str, system: str, user: str, meta: dict | None = None) -> AsyncIterator[str]:
        meta = meta or {}
        if role == "mike":
            text = agent_mocks.mike_reply(meta)
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

        # DeepSeek caps a single completion at 8K output tokens. Large HTML
        # files regularly hit that cap, so continue from the cut point instead
        # of shipping a half-written file.
        for _ in range(3):
            payload = {
                "model": config.LLM_MODEL,
                "messages": messages,
                "stream": True,
                "temperature": config.LLM_TEMPERATURE,
                "max_tokens": 8192,
            }
            finish = {"reason": None}
            async with self._client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    raise RuntimeError(
                        f"LLM HTTP {resp.status_code}: {body.decode('utf-8', 'ignore')[:300]}"
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

            if finish["reason"] != "length":
                return
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

        raise RuntimeError("LLM output still truncated after continuation passes")


_shared: DeepSeekLLM | None = None


def get_llm():
    global _shared
    if config.LLM_MODE != "deepseek":
        return MockLLM()
    if _shared is None:
        _shared = DeepSeekLLM()
    return _shared
