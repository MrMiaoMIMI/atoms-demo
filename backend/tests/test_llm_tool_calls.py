import json
import unittest

from llm import DeepSeekLLM, MockLLM


def tool_message(content: str) -> dict:
    return {
        "role": "tool",
        "tool_call_id": "mock-tool",
        "content": json.dumps({"ok": True, "data": {"content": content}}),
    }


def assistant_message() -> dict:
    return {"role": "assistant", "content": None, "tool_calls": []}


class MockToolTurnTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_frontend_script(self) -> None:
        llm = MockLLM()
        meta = {
            "mode": "frontend",
            "title": "测试页面",
            "prompt": "做一个展示页面",
            "existing": {},
        }
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ]

        first = await llm.turn(messages=messages, tools=[], meta=meta)
        self.assertEqual(first.tool_calls[0].name, "write_file")
        first_args = json.loads(first.tool_calls[0].arguments)
        self.assertEqual(first_args["path"], "frontend/src/App.tsx")
        self.assertIn("MOCK PREVIEW", first_args["content"])

        messages += [assistant_message(), tool_message("")]
        second = await llm.turn(messages=messages, tools=[], meta=meta)
        second_args = json.loads(second.tool_calls[0].arguments)
        self.assertEqual(second_args["path"], "frontend/src/styles.css")
        self.assertIn(".demo", second_args["content"])

        messages += [assistant_message(), tool_message("")]
        third = await llm.turn(messages=messages, tools=[], meta=meta)
        self.assertEqual(third.tool_calls[0].name, "build_preview")

        messages += [assistant_message(), tool_message("")]
        fourth = await llm.turn(messages=messages, tools=[], meta=meta)
        self.assertEqual(fourth.finish_reason, "stop")
        self.assertIn("Mock", fourth.text)

    async def test_new_backend_script(self) -> None:
        llm = MockLLM()
        meta = {
            "mode": "backend",
            "title": "测试 API",
            "prompt": "只要后端",
            "existing": {},
        }
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ]
        first = await llm.turn(messages=messages, tools=[], meta=meta)
        self.assertEqual(
            json.loads(first.tool_calls[0].arguments)["path"],
            "backend/main.py",
        )
        messages += [assistant_message(), tool_message("")]
        second = await llm.turn(messages=messages, tools=[], meta=meta)
        self.assertEqual(second.tool_calls[0].name, "build_preview")

        messages += [assistant_message(), tool_message("")]
        third = await llm.turn(messages=messages, tools=[], meta=meta)
        self.assertEqual(third.tool_calls[0].name, "start_runtime")

    async def test_iteration_read_then_edit(self) -> None:
        llm = MockLLM()
        meta = {
            "mode": "frontend",
            "title": "测试页面",
            "prompt": "改一下标题",
            "existing": {"frontend/src/App.tsx": "const a = 1;\n"},
            "iteration": True,
        }
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ]
        first = await llm.turn(messages=messages, tools=[], meta=meta)
        self.assertEqual(first.tool_calls[0].name, "read_file")
        self.assertEqual(
            json.loads(first.tool_calls[0].arguments)["path"],
            "frontend/src/App.tsx",
        )

        messages += [assistant_message(), tool_message("const a = 1;\n")]
        second = await llm.turn(messages=messages, tools=[], meta=meta)
        self.assertEqual(second.tool_calls[0].name, "edit_file")
        args = json.loads(second.tool_calls[0].arguments)
        self.assertEqual(args["old_string"], "const a = 1;\n")
        self.assertIn("mock iteration", args["new_string"])


class FakeDeepSeek(DeepSeekLLM):
    def __init__(self, sequences: list[list[dict]]) -> None:
        super().__init__()
        self.sequences = sequences
        self.calls = 0
        self.text_calls: list[str] = []

    async def _deltas(self, messages, tools=None):
        sequence = self.sequences[min(self.calls, len(self.sequences) - 1)]
        self.calls += 1
        for event in sequence:
            yield event


class DeepSeekTurnParsingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        if hasattr(self, "llm"):
            await self.llm._client.aclose()

    async def test_accumulates_tool_call_fragments(self) -> None:
        self.llm = FakeDeepSeek(
            [
                [
                    {"type": "text", "text": "我先看一下。"},
                    {
                        "type": "tool_call",
                        "index": 0,
                        "id": "call-1",
                        "name": "read_file",
                        "arguments": '{"path": ',
                    },
                    {
                        "type": "tool_call",
                        "index": 0,
                        "id": None,
                        "name": None,
                        "arguments": '"frontend/src/App.tsx"}',
                    },
                    {"type": "finish", "reason": "tool_calls"},
                ]
            ]
        )
        seen: list[str] = []

        async def on_text(delta: str) -> None:
            seen.append(delta)

        turn = await self.llm._collect_turn([], None, on_text)
        self.assertEqual(turn.text, "我先看一下。")
        self.assertEqual(seen, ["我先看一下。"])
        self.assertEqual(turn.finish_reason, "tool_calls")
        self.assertFalse(turn.truncated)
        self.assertEqual(len(turn.tool_calls), 1)
        self.assertEqual(turn.tool_calls[0].name, "read_file")
        self.assertEqual(
            json.loads(turn.tool_calls[0].arguments),
            {"path": "frontend/src/App.tsx"},
        )

    async def test_length_with_tool_call_is_truncated(self) -> None:
        self.llm = FakeDeepSeek(
            [
                [
                    {
                        "type": "tool_call",
                        "index": 0,
                        "id": "call-1",
                        "name": "write_file",
                        "arguments": '{"path": "a.tsx", "content": "half',
                    },
                    {"type": "finish", "reason": "length"},
                ]
            ]
        )
        turn = await self.llm._collect_turn([], None, None)
        self.assertTrue(turn.truncated)
        self.assertEqual(len(turn.tool_calls), 1)

    async def test_text_continuation(self) -> None:
        self.llm = FakeDeepSeek(
            [
                [
                    {"type": "text", "text": "前半段"},
                    {"type": "finish", "reason": "length"},
                ],
                [
                    {"type": "text", "text": "后半段"},
                    {"type": "finish", "reason": "stop"},
                ],
            ]
        )
        turn = await self.llm.turn(messages=[], tools=None, meta={})
        self.assertEqual(turn.text, "前半段后半段")
        self.assertEqual(turn.finish_reason, "stop")
        self.assertEqual(self.llm.calls, 2)


if __name__ == "__main__":
    unittest.main()
