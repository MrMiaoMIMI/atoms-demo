import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db


class DbChangesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch.object(db, "DB_PATH", Path(self._tmp.name) / "test.db")
        self._patch.start()
        await db.init_db()
        project = await db.create_project("测试项目", "user-1")
        self.pid = project["id"]

    async def asyncTearDown(self) -> None:
        self._patch.stop()
        self._tmp.cleanup()

    async def test_tombstone_hides_latest_version(self) -> None:
        await db.add_artifact(
            self.pid, "frontend/src/App.tsx", "v1\n", 1
        )
        self.assertEqual(
            await db.latest_artifacts(self.pid),
            {"frontend/src/App.tsx": "v1\n"},
        )

        await db.add_artifact_deleted(self.pid, "frontend/src/App.tsx", 2)
        self.assertEqual(await db.latest_artifacts(self.pid), {})
        self.assertEqual(await db.latest_artifact_names(self.pid), [])
        state = await db.get_state(self.pid)
        assert state is not None
        self.assertEqual(state["artifacts"], [])

        projects = await db.list_projects("user-1")
        self.assertEqual(projects[0]["has_frontend"], 0)
        self.assertEqual(projects[0]["artifact_count"], 0)

        await db.add_artifact(self.pid, "frontend/src/App.tsx", "v3\n", 3)
        self.assertEqual(
            await db.latest_artifacts(self.pid),
            {"frontend/src/App.tsx": "v3\n"},
        )
        self.assertEqual(await db.next_version(self.pid), 4)
        projects = await db.list_projects("user-1")
        self.assertEqual(projects[0]["has_frontend"], 1)
        self.assertEqual(projects[0]["artifact_count"], 1)

    async def test_old_frontend_does_not_survive_newer_tombstone(self) -> None:
        await db.add_artifact(self.pid, "frontend/src/App.tsx", "v1\n", 1)
        await db.add_artifact_deleted(self.pid, "frontend/src/App.tsx", 2)
        projects = await db.list_projects("user-1")
        self.assertEqual(projects[0]["has_frontend"], 0)

    async def test_file_change_lifecycle(self) -> None:
        exec_id = await db.add_execution(
            self.pid,
            "alex",
            "编辑 frontend/src/App.tsx",
            "success",
            "+1 -1",
            run_id="run-1",
            tool="edit_file",
            target="frontend/src/App.tsx",
        )
        change_id = await db.add_file_change(
            self.pid,
            version=5,
            filename="frontend/src/App.tsx",
            change_type="modified",
            diff="--- a\n+++ b\n",
            additions=1,
            deletions=1,
            run_id="run-1",
            agent="alex",
            execution_id=exec_id,
        )
        row = await db.get_file_change(self.pid, change_id)
        assert row is not None
        self.assertEqual(row["change_type"], "modified")
        self.assertEqual(row["execution_id"], exec_id)
        self.assertEqual(row["rolled_back"], 0)

        rows = await db.list_file_changes(self.pid, execution_id=exec_id)
        self.assertEqual([item["id"] for item in rows], [change_id])
        self.assertEqual(
            await db.list_file_changes(self.pid, version=5, include_rolled_back=False),
            rows,
        )

        state = await db.get_state(self.pid)
        assert state is not None
        execution = next(item for item in state["executions"] if item["id"] == exec_id)
        self.assertEqual(execution["tool"], "edit_file")
        self.assertEqual(execution["target"], "frontend/src/App.tsx")
        self.assertEqual(execution["change_count"], 1)

        await db.mark_file_changes_rolled_back(self.pid, 5)
        rolled = await db.get_file_change(self.pid, change_id)
        assert rolled is not None
        self.assertEqual(rolled["rolled_back"], 1)
        self.assertEqual(
            await db.list_file_changes(
                self.pid, version=5, include_rolled_back=False
            ),
            [],
        )
        state = await db.get_state(self.pid)
        assert state is not None
        execution = next(item for item in state["executions"] if item["id"] == exec_id)
        self.assertEqual(execution["change_count"], 1)

        await db.delete_file_changes_version(self.pid, 5)
        self.assertEqual(await db.list_file_changes(self.pid, version=5), [])

    async def test_delete_project_removes_file_changes(self) -> None:
        await db.add_file_change(
            self.pid,
            version=1,
            filename="frontend/src/App.tsx",
            change_type="created",
            diff="+x\n",
            additions=1,
            deletions=0,
            run_id="run-1",
            agent="alex",
        )
        await db.delete_project(self.pid)
        self.assertIsNone(await db.get_state(self.pid))
        self.assertEqual(await db.list_file_changes(self.pid), [])


if __name__ == "__main__":
    unittest.main()
