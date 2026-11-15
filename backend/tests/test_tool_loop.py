import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import agents
import db
from llm import AssistantTurn, ToolCall
from tool_loop import run_tool_loop
from tools import Toolbox, ToolContext


class ScriptedLLM:
    label = "scripted"

    def __init__(self, turns: list[AssistantTurn]) -> None:
        self.turns = list(turns)
        self.calls: list[list[dict]] = []

    async def turn(self, *, messages, tools=None, meta=None, on_text=None):
        self.calls.append([dict(message) for message in messages])
        if not self.turns:
            return AssistantTurn(text="完成", finish_reason="stop")
        return self.turns.pop(0)


def call(name: str, arguments: dict, call_id: str = "call-1") -> AssistantTurn:
    import json

    return AssistantTurn(
        text="",
        tool_calls=[
            ToolCall(
                id=call_id,
                name=name,
                arguments=json.dumps(arguments, ensure_ascii=False),
            )
        ],
        finish_reason="tool_calls",
    )


class ToolLoopTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch.object(db, "DB_PATH", Path(self._tmp.name) / "test.db")
        self._patch.start()
        await db.init_db()
        self.pid = "project-1"
        self.events: list[tuple[str, dict]] = []
        self._next_execution = 0

        async def emit(event: str, payload: dict):
            self.events.append((event, dict(payload)))
            if event == "execution" and not payload.get("id"):
                self._next_execution += 1
                return self._next_execution
            return None

        self.emit = emit

    async def asyncTearDown(self) -> None:
        self._patch.stop()
        self._tmp.cleanup()

    def _toolbox(self, agent: str = "alex") -> Toolbox:
        ctx = ToolContext(
            pid=self.pid,
            run_id="run-1",
            agent=agent,
            emit=self.emit,
            version=1,
        )
        return Toolbox(ctx, agents.AGENTS[agent].tools)

    async def test_write_edit_then_finish(self) -> None:
        llm = ScriptedLLM(
            [
                call(
                    "write_file",
                    {
                        "path": "frontend/src/App.tsx",
                        "content": "const a = 1;\n",
                    },
                ),
                call(
                    "edit_file",
                    {
                        "path": "frontend/src/App.tsx",
                        "old_string": "const a = 1;",
                        "new_string": "const a = 2;",
                    },
                ),
                AssistantTurn(text="完成", finish_reason="stop"),
            ]
        )
        result = await run_tool_loop(
            llm=llm,
            toolbox=self._toolbox(),
            system="system",
            user="user",
            meta={},
            emit=self.emit,
            max_steps=5,
            timeout_seconds=30,
        )
        self.assertTrue(result.completed)
        self.assertEqual(result.text, "完成")
        self.assertEqual(result.tool_calls, 2)
        self.assertEqual(result.steps, 3)
        self.assertEqual(
            await db.latest_artifacts(self.pid),
            {"frontend/src/App.tsx": "const a = 2;\n"},
        )
        changes = await db.list_file_changes(self.pid)
        self.assertEqual([item["change_type"] for item in changes], ["created", "modified"])
        self.assertTrue(all(item["execution_id"] for item in changes))

        event_names = [name for name, _ in self.events]
        self.assertEqual(event_names.count("file_change"), 2)
        self.assertEqual(event_names.count("artifact"), 2)
        # The second model turn must contain the first tool result.
        self.assertTrue(
            any(
                message.get("role") == "tool"
                for message in llm.calls[1]
            )
        )

    async def test_invalid_arguments_are_returned_to_model(self) -> None:
        llm = ScriptedLLM(
            [
                AssistantTurn(
                    text="",
                    tool_calls=[
                        ToolCall(
                            id="call-1",
                            name="edit_file",
                            arguments="{not json",
                        )
                    ],
                    finish_reason="tool_calls",
                ),
                AssistantTurn(text="已修正", finish_reason="stop"),
            ]
        )
        result = await run_tool_loop(
            llm=llm,
            toolbox=self._toolbox(),
            system="system",
            user="user",
            meta={},
            emit=self.emit,
            max_steps=5,
            timeout_seconds=30,
        )
        self.assertTrue(result.completed)
        self.assertEqual(result.tool_calls, 1)
        tool_messages = [
            message
            for message in llm.calls[1]
            if message.get("role") == "tool"
        ]
        self.assertEqual(len(tool_messages), 1)
        self.assertIn("invalid_args", tool_messages[0]["content"])

    async def test_role_isolation(self) -> None:
        llm = ScriptedLLM(
            [
                call(
                    "write_file",
                    {
                        "path": "frontend/src/App.tsx",
                        "content": "x\n",
                    },
                ),
                AssistantTurn(text="完成", finish_reason="stop"),
            ]
        )
        result = await run_tool_loop(
            llm=llm,
            toolbox=self._toolbox("bob"),
            system="system",
            user="user",
            meta={},
            emit=self.emit,
            max_steps=5,
            timeout_seconds=30,
        )
        self.assertTrue(result.completed)
        self.assertEqual(await db.latest_artifacts(self.pid), {})
        tool_messages = [
            message for message in llm.calls[1] if message.get("role") == "tool"
        ]
        self.assertIn("permission_denied", tool_messages[0]["content"])

    async def test_truncated_tool_call_is_not_executed(self) -> None:
        llm = ScriptedLLM(
            [
                AssistantTurn(
                    text="",
                    tool_calls=[
                        ToolCall(
                            id="call-1",
                            name="write_file",
                            arguments='{"path": "frontend/src/App.tsx", "content": "half',
                        )
                    ],
                    finish_reason="length",
                    truncated=True,
                ),
                AssistantTurn(text="完成", finish_reason="stop"),
            ]
        )
        result = await run_tool_loop(
            llm=llm,
            toolbox=self._toolbox(),
            system="system",
            user="user",
            meta={},
            emit=self.emit,
            max_steps=5,
            timeout_seconds=30,
        )
        self.assertTrue(result.completed)
        self.assertEqual(result.tool_calls, 0)
        self.assertEqual(await db.latest_artifacts(self.pid), {})
        self.assertNotIn("execution", [name for name, _ in self.events])

    async def test_no_progress_stops_the_loop(self) -> None:
        await db.add_artifact(self.pid, "frontend/src/App.tsx", "const a = 1;\n", 1)
        turns = [
            call("read_file", {"path": "frontend/src/App.tsx"}, f"call-{i}")
            for i in range(10)
        ]
        result = await run_tool_loop(
            llm=ScriptedLLM(turns),
            toolbox=self._toolbox(),
            system="system",
            user="user",
            meta={},
            emit=self.emit,
            max_steps=10,
            timeout_seconds=30,
            no_progress_limit=2,
        )
        self.assertEqual(result.stopped_reason, "no_progress")
        self.assertEqual(result.steps, 2)

    async def test_max_steps(self) -> None:
        await db.add_artifact(self.pid, "frontend/src/App.tsx", "const a = 1;\n", 1)
        turns = [
            call("read_file", {"path": "frontend/src/App.tsx"}, f"call-{i}")
            for i in range(10)
        ]
        result = await run_tool_loop(
            llm=ScriptedLLM(turns),
            toolbox=self._toolbox(),
            system="system",
            user="user",
            meta={},
            emit=self.emit,
            max_steps=3,
            timeout_seconds=30,
            no_progress_limit=10,
        )
        self.assertEqual(result.stopped_reason, "max_steps")
        self.assertEqual(result.steps, 3)


if __name__ == "__main__":
    unittest.main()
