import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import agent
import db
import publisher
from llm import AssistantTurn, ToolCall


class ScriptedLLM:
    label = "scripted"

    def __init__(self, turns: list[AssistantTurn]) -> None:
        self.turns = list(turns)

    async def turn(self, *, messages, tools=None, meta=None, on_text=None):
        if not self.turns:
            return AssistantTurn(text="完成", finish_reason="stop")
        return self.turns.pop(0)


def call(name: str, arguments: dict, call_id: str = "call-1") -> AssistantTurn:
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


APP = """import { useEffect } from "react";

export default function App() {
  useEffect(() => {
    fetch("api/health");
  }, []);
  return <main className="app">hi</main>;
}
"""

CSS = """.app { color: #111; }

@media (max-width: 768px) {
  .app { color: #222; }
}
"""

BACKEND = '''import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import connection, init_db


@asynccontextmanager
async def lifespan(app):
    await init_db()
    yield


app = FastAPI(root_path=os.getenv("APP_ROOT_PATH", ""), lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"ok": True}
'''

PLAN = {
    "summary": "测试全栈应用",
    "title": "测试应用",
    "mode": "fullstack",
    "entities": [
        {
            "table": "items",
            "fields": [
                {
                    "name": "id",
                    "type": "INTEGER",
                    "primary_key": True,
                    "autoincrement": True,
                },
                {"name": "title", "type": "TEXT", "not_null": True},
            ],
        }
    ],
    "api": [{"method": "GET", "path": "/api/items", "description": "列表"}],
    "files": [
        {"path": "frontend/src/App.tsx", "purpose": "页面"},
        {"path": "frontend/src/styles.css", "purpose": "样式"},
        {"path": "backend/main.py", "purpose": "后端"},
    ],
}


class BuildToolLoopTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._patches = [
            patch.object(db, "DB_PATH", self.root / "test.db"),
            patch.object(agent.config, "APPS_DIR", self.root / "apps"),
        ]
        for item in self._patches:
            item.start()
        (self.root / "apps").mkdir(parents=True)
        await db.init_db()
        project = await db.create_project("测试应用", "user-1")
        self.pid = project["id"]
        self.events: list[tuple[str, dict]] = []
        self._next_execution = 0

        async def base_emit(event: str, payload: dict):
            self.events.append((event, dict(payload)))
            if event == "execution" and not payload.get("id"):
                self._next_execution += 1
                return self._next_execution
            return None

        self.base_emit = base_emit
        self.build = AsyncMock(return_value=True)
        self.ensure = AsyncMock(return_value=12345)
        self.stop = AsyncMock()
        self.health = AsyncMock()
        self._patches += [
            patch.object(agent.frontend_builder, "build", self.build),
            patch.object(agent.runtime.runtime, "ensure", self.ensure),
            patch.object(agent.runtime.runtime, "stop", self.stop),
            patch.object(agent, "check_runtime_health", self.health),
        ]
        for item in self._patches[2:]:
            item.start()

    async def asyncTearDown(self) -> None:
        for item in reversed(self._patches):
            item.stop()
        self._tmp.cleanup()

    def emitter(self, version: int) -> agent.RoleEmitter:
        return agent.RoleEmitter(
            self.pid,
            f"run-{version}",
            "alex",
            self.base_emit,
            version,
            0,
        )

    async def test_first_build_then_iteration_then_noop(self) -> None:
        first = ScriptedLLM(
            [
                call(
                    "write_file",
                    {
                        "path": "frontend/src/App.tsx",
                        "content": APP,
                        "overwrite": True,
                    },
                ),
                call(
                    "write_file",
                    {
                        "path": "frontend/src/styles.css",
                        "content": CSS,
                        "overwrite": True,
                    },
                ),
                call(
                    "write_file",
                    {
                        "path": "backend/main.py",
                        "content": BACKEND,
                    },
                ),
                AssistantTurn(text="首建完成", finish_reason="stop"),
            ]
        )
        progress = {"published": False}
        answer = await agent._build_project_tools(
            self.pid,
            "做一个全栈应用",
            PLAN,
            self.emitter(1),
            existing={},
            version=1,
            llm=first,
            progress=progress,
        )
        self.assertIn("已完成 v1", answer)
        self.assertTrue(progress["published"])
        self.build.assert_awaited()
        self.ensure.assert_awaited()

        project = await db.get_project(self.pid)
        assert project is not None
        self.assertEqual(project["built_version"], 1)

        files = await db.latest_artifacts(self.pid)
        self.assertIn("frontend/src/App.tsx", files)
        self.assertIn("frontend/src/styles.css", files)
        self.assertIn("backend/main.py", files)
        self.assertIn("frontend/package.json", files)
        self.assertIn("backend/schema.sql", files)
        self.assertEqual(files["frontend/src/App.tsx"], APP)

        changes = await db.list_file_changes(self.pid, version=1)
        changed_paths = {item["filename"] for item in changes}
        self.assertIn("frontend/src/App.tsx", changed_paths)
        self.assertIn("frontend/src/styles.css", changed_paths)
        self.assertIn("backend/main.py", changed_paths)
        self.assertIn("frontend/package.json", changed_paths)

        event_names = [name for name, _ in self.events]
        self.assertIn("file_change", event_names)
        self.assertIn("artifact", event_names)
        self.assertIn("preview", event_names)

        # Iteration: one precise edit, no scaffolding churn.
        existing = await db.latest_artifacts(self.pid)
        second = ScriptedLLM(
            [
                call(
                    "edit_file",
                    {
                        "path": "frontend/src/App.tsx",
                        "old_string": "hi",
                        "new_string": "hello",
                    },
                ),
                AssistantTurn(text="迭代完成", finish_reason="stop"),
            ]
        )
        answer2 = await agent._build_project_tools(
            self.pid,
            "把 hi 改成 hello",
            {
                **PLAN,
                "files": [{"path": "frontend/src/App.tsx", "purpose": "页面"}],
            },
            self.emitter(2),
            existing=existing,
            version=2,
            llm=second,
            progress={"published": False},
        )
        self.assertIn("已完成 v2", answer2)
        files2 = await db.latest_artifacts(self.pid)
        self.assertIn("hello", files2["frontend/src/App.tsx"])
        project = await db.get_project(self.pid)
        assert project is not None
        self.assertEqual(project["built_version"], 2)
        changes2 = await db.list_file_changes(self.pid, version=2)
        self.assertEqual(
            [(item["filename"], item["change_type"]) for item in changes2],
            [("frontend/src/App.tsx", "modified")],
        )

        # No-op: no new artifacts, no built_version bump.
        third = ScriptedLLM([AssistantTurn(text="没有需要改的", finish_reason="stop")])
        answer3 = await agent._build_project_tools(
            self.pid,
            "看看就好",
            PLAN,
            self.emitter(3),
            existing=files2,
            version=3,
            llm=third,
            progress={"published": False},
        )
        self.assertEqual(answer3, "没有需要改的")
        project = await db.get_project(self.pid)
        assert project is not None
        self.assertEqual(project["built_version"], 2)
        self.assertEqual(await db.next_version(self.pid), 3)

    async def test_backend_only_build_generates_api_preview(self) -> None:
        """A backend-only build must ship a static entry for preview/publish."""
        plan = {
            "summary": "测试纯后端 API",
            "title": "记账 API",
            "mode": "backend",
            "entities": [
                {
                    "table": "items",
                    "fields": [
                        {
                            "name": "id",
                            "type": "INTEGER",
                            "primary_key": True,
                            "autoincrement": True,
                        }
                    ],
                }
            ],
            "api": [
                {"method": "GET", "path": "/api/items", "description": "列表"},
                {"method": "GET", "path": "/api/health", "description": "健康检查"},
            ],
            "files": [{"path": "backend/main.py", "purpose": "后端"}],
        }
        llm = ScriptedLLM(
            [
                call(
                    "write_file",
                    {"path": "backend/main.py", "content": BACKEND},
                ),
                AssistantTurn(text="API 完成", finish_reason="stop"),
            ]
        )
        progress = {"published": False}
        answer = await agent._build_project_tools(
            self.pid,
            "只做后端 API",
            plan,
            self.emitter(1),
            existing={},
            version=1,
            llm=llm,
            progress=progress,
        )
        self.assertIn("已完成 v1", answer)
        # The API console is generated deterministically; no esbuild/frontend.
        self.build.assert_not_awaited()
        preview = self.root / "apps" / self.pid / ".preview" / "index.html"
        self.assertTrue(preview.is_file())
        html = preview.read_text(encoding="utf-8")
        self.assertIn("记账 API", html)
        self.assertIn("/api/items", html)

        manifest = publisher.snapshot(self.pid, 1, "backend", "记账 API")
        self.assertEqual(manifest["mode"], "backend")
        self.assertTrue(
            (
                self.root
                / "apps"
                / self.pid
                / ".published"
                / "site"
                / "index.html"
            ).is_file()
        )


if __name__ == "__main__":
    unittest.main()
