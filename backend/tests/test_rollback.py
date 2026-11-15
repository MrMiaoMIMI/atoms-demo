import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import agent
import db


class FakeToolbox:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call(self, name: str, **kwargs):
        self.calls.append((name, kwargs))
        if name == "start_runtime":
            return 12345
        return None


class RollbackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch.object(db, "DB_PATH", Path(self._tmp.name) / "test.db")
        self._patch.start()
        await db.init_db()
        project = await db.create_project("回滚测试", "user-1")
        self.pid = project["id"]
        self.events: list[tuple[str, dict]] = []

        async def emit(event: str, payload: dict):
            self.events.append((event, dict(payload)))
            return len(self.events)

        self.emit = emit

    async def asyncTearDown(self) -> None:
        self._patch.stop()
        self._tmp.cleanup()

    async def test_rollback_marks_changes_and_restores_previous_version(self) -> None:
        await db.add_artifact(
            self.pid, "frontend/src/App.tsx", "export default function App() {}\n", 1
        )
        await db.add_artifact(
            self.pid, "frontend/src/App.tsx", "broken\n", 2
        )
        change_id = await db.add_file_change(
            self.pid,
            version=2,
            filename="frontend/src/App.tsx",
            change_type="modified",
            diff="+broken\n",
            additions=1,
            run_id="run-2",
            agent="alex",
        )
        toolbox = FakeToolbox()
        previous = {"frontend/src/App.tsx": "export default function App() {}\n"}
        build = AsyncMock(return_value=True)
        with patch.object(agent.frontend_builder, "build", build):
            await agent._rollback_round(
                self.pid,
                2,
                previous,
                "回滚测试",
                self.emit,
                toolbox,
                True,
            )

        change = await db.get_file_change(self.pid, change_id)
        assert change is not None
        self.assertEqual(change["rolled_back"], 1)
        self.assertEqual(
            await db.latest_artifacts(self.pid),
            {"frontend/src/App.tsx": "export default function App() {}\n"},
        )
        self.assertIn("publish_files", [name for name, _ in toolbox.calls])
        build.assert_awaited()
        self.assertTrue(
            any(name == "changes_reset" for name, _ in self.events)
        )

    async def test_rollback_without_published_tree_only_cleans_artifacts(self) -> None:
        await db.add_artifact(self.pid, "frontend/src/App.tsx", "draft\n", 1)
        change_id = await db.add_file_change(
            self.pid,
            version=1,
            filename="frontend/src/App.tsx",
            change_type="created",
            diff="+draft\n",
            additions=1,
            run_id="run-1",
            agent="alex",
        )
        toolbox = FakeToolbox()
        await agent._rollback_round(
            self.pid,
            1,
            {},
            "回滚测试",
            self.emit,
            toolbox,
            False,
        )
        change = await db.get_file_change(self.pid, change_id)
        assert change is not None
        self.assertEqual(change["rolled_back"], 1)
        self.assertEqual(await db.latest_artifacts(self.pid), {})
        self.assertNotIn("publish_files", [name for name, _ in toolbox.calls])


if __name__ == "__main__":
    unittest.main()
