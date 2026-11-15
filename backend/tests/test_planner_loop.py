import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import agent
import db
from llm import AssistantTurn, MockLLM, ToolCall


PLAN = {
    "summary": "给列表加搜索框",
    "title": "测试应用",
    "mode": "fullstack",
    "reason": "已有全栈项目",
    "entities": [
        {
            "table": "items",
            "fields": [
                {"name": "id", "type": "INTEGER", "primary_key": True},
                {"name": "title", "type": "TEXT", "not_null": True},
            ],
        }
    ],
    "api": [{"method": "GET", "path": "/api/items", "description": "列表"}],
    "files": [{"path": "frontend/src/App.tsx", "purpose": "页面"}],
}


class ScriptedPlannerLLM:
    label = "scripted"

    def __init__(self, turns: list[AssistantTurn], fallback_text: str) -> None:
        self.turns = list(turns)
        self.fallback_text = fallback_text
        self.calls: list[list[dict]] = []
        self.stream_calls = 0

    async def turn(self, *, messages, tools=None, meta=None, on_text=None):
        self.calls.append([dict(message) for message in messages])
        if not self.turns:
            return AssistantTurn(text=json.dumps(PLAN), finish_reason="stop")
        return self.turns.pop(0)

    async def stream(self, *, role, system, user, meta=None):
        self.stream_calls += 1
        text = self.fallback_text
        for index in range(0, len(text), 32):
            yield text[index : index + 32]


def read_call() -> AssistantTurn:
    return AssistantTurn(
        text="",
        tool_calls=[
            ToolCall(
                id="read-1",
                name="read_file",
                arguments=json.dumps({"path": "frontend/src/App.tsx"}),
            )
        ],
        finish_reason="tool_calls",
    )


class PlannerLoopTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch.object(db, "DB_PATH", Path(self._tmp.name) / "test.db")
        self._patch.start()
        await db.init_db()
        project = await db.create_project("测试应用", "user-1")
        self.pid = project["id"]
        await db.add_artifact(
            self.pid,
            "frontend/src/App.tsx",
            'export default function App() { return <main className="app">hi</main>; }\n',
            1,
        )
        await db.add_artifact(
            self.pid,
            "backend/main.py",
            "from db import connection\n",
            1,
        )
        self.events: list[tuple[str, dict]] = []
        self._next_execution = 0

        async def base_emit(event: str, payload: dict):
            self.events.append((event, dict(payload)))
            if event == "execution" and not payload.get("id"):
                self._next_execution += 1
                return self._next_execution
            return None

        self.emitter = agent.RoleEmitter(
            self.pid, "run-1", "bob", base_emit, 1, 0
        )

    async def asyncTearDown(self) -> None:
        self._patch.stop()
        self._tmp.cleanup()

    async def test_bob_reads_then_plans(self) -> None:
        llm = ScriptedPlannerLLM(
            [
                read_call(),
                AssistantTurn(text=json.dumps(PLAN), finish_reason="stop"),
            ],
            fallback_text=json.dumps(PLAN),
        )
        with patch.object(agent, "get_llm", lambda: llm):
            plan = await agent._call_planner(
                "给列表加搜索框",
                self.emitter,
                project_name="测试应用",
                existing=await db.latest_artifacts(self.pid),
                existing_mode="fullstack",
            )
        self.assertEqual(plan["mode"], "fullstack")
        self.assertEqual(len(llm.calls), 2)
        tool_messages = [
            message for message in llm.calls[1] if message.get("role") == "tool"
        ]
        self.assertEqual(len(tool_messages), 1)
        self.assertIn("App.tsx", tool_messages[0]["content"])
        steps = [
            payload.get("step")
            for name, payload in self.events
            if name == "execution"
        ]
        self.assertTrue(any("读取" in (step or "") for step in steps))

    async def test_invalid_loop_output_falls_back(self) -> None:
        llm = ScriptedPlannerLLM(
            [AssistantTurn(text="我先看看，然后再说。", finish_reason="stop")],
            fallback_text=json.dumps(PLAN),
        )
        with patch.object(agent, "get_llm", lambda: llm):
            plan = await agent._call_planner(
                "给列表加搜索框",
                self.emitter,
                project_name="测试应用",
                existing=await db.latest_artifacts(self.pid),
                existing_mode="fullstack",
            )
        self.assertEqual(plan["mode"], "fullstack")
        self.assertEqual(llm.stream_calls, 1)

    async def test_new_project_uses_single_shot_planner(self) -> None:
        llm = ScriptedPlannerLLM([], fallback_text=json.dumps(PLAN))
        with patch.object(agent, "get_llm", lambda: llm):
            plan = await agent._call_planner(
                "做一个新项目",
                self.emitter,
                project_name="新项目",
                existing={},
                existing_mode=None,
            )
        self.assertEqual(plan["mode"], "fullstack")
        self.assertEqual(llm.calls, [])
        self.assertEqual(llm.stream_calls, 1)

    async def test_mock_mode_skips_tool_loop(self) -> None:
        llm = MockLLM()
        with patch.object(agent, "get_llm", lambda: llm):
            plan = await agent._call_planner(
                "给列表加搜索框",
                self.emitter,
                project_name="测试应用",
                existing=await db.latest_artifacts(self.pid),
                existing_mode="fullstack",
            )
        self.assertIn(plan["mode"], {"frontend", "fullstack", "backend"})
        self.assertIn("summary", plan)


if __name__ == "__main__":
    unittest.main()
