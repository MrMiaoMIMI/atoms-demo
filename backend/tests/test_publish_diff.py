import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import config
import db
import main
import publisher


class PublisherBaselineTests(unittest.TestCase):
    def test_snapshot_writes_source_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            apps = Path(tmp) / "apps"
            with patch.object(config, "APPS_DIR", apps):
                pid = "project-1"
                root = apps / pid
                (root / ".preview").mkdir(parents=True)
                (root / ".preview/index.html").write_text(
                    f'<html><head><base href="/apps/{pid}/" /></head></html>',
                    encoding="utf-8",
                )
                (root / "backend").mkdir(parents=True)
                (root / "backend/main.py").write_text("print('x')\n", encoding="utf-8")

                source = {
                    "frontend/src/App.tsx": "export default function App() {}\n",
                    "backend/main.py": "print('x')\n",
                }
                publisher.snapshot(pid, 1, "fullstack", "测试", source)

                payload = publisher.read_source(pid)
                assert payload is not None
                self.assertEqual(payload["version"], 1)
                self.assertEqual(payload["files"], source)
                published_index = (
                    root / ".published/site/index.html"
                ).read_text(encoding="utf-8")
                self.assertIn(f'href="/s/{pid}/"', published_index)

    def test_read_source_missing_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(config, "APPS_DIR", Path(tmp) / "apps"):
                self.assertIsNone(publisher.read_source("missing"))


class ChangesApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.apps = self.root / "apps"
        self.apps.mkdir(parents=True)
        self._patches = [
            patch.object(db, "DB_PATH", self.root / "test.db"),
            patch.object(config, "APPS_DIR", self.apps),
        ]
        for item in self._patches:
            item.start()
        await db.init_db()
        project = await db.create_project("测试项目", "user-1")
        self.pid = project["id"]
        self.user = {"id": "user-1"}

    async def asyncTearDown(self) -> None:
        for item in reversed(self._patches):
            item.stop()
        self._tmp.cleanup()

    def _write_baseline(self, files: dict[str, str]) -> None:
        target = self.apps / self.pid / ".published"
        target.mkdir(parents=True, exist_ok=True)
        (target / publisher.SOURCE_FILE).write_text(
            json.dumps({"version": 1, "mode": "fullstack", "files": files}),
            encoding="utf-8",
        )

    async def test_unpublished_tree_diff(self) -> None:
        await db.add_artifact(self.pid, "frontend/src/App.tsx", "one\n", 1)
        await db.add_artifact(self.pid, "backend/main.py", "x\n", 1)
        await db.mark_published(self.pid, 1)
        self._write_baseline(
            {
                "frontend/src/App.tsx": "one\n",
                "backend/main.py": "x\n",
            }
        )
        await db.add_artifact(self.pid, "frontend/src/App.tsx", "one\ntwo\n", 2)

        result = await main.get_project_changes(self.pid, self.user)
        self.assertTrue(result["has_published"])
        self.assertTrue(result["baseline_ok"])
        self.assertEqual(result["published_version"], 1)
        self.assertEqual(result["current_version"], 2)
        self.assertEqual(result["summary"], {"created": 0, "modified": 1, "deleted": 0})
        self.assertEqual(len(result["files"]), 1)
        change = result["files"][0]
        self.assertEqual(change["filename"], "frontend/src/App.tsx")
        self.assertEqual(change["additions"], 1)
        self.assertEqual(change["deletions"], 0)
        self.assertIn("+two", change["diff"])

        await db.add_artifact(self.pid, "frontend/src/New.tsx", "new\n", 2)
        result = await main.get_project_changes(self.pid, self.user)
        self.assertEqual(result["summary"]["created"], 1)

        await db.add_artifact_deleted(self.pid, "backend/main.py", 3)
        result = await main.get_project_changes(self.pid, self.user)
        self.assertEqual(result["summary"]["deleted"], 1)
        self.assertEqual(result["current_version"], 3)

    async def test_draft_lists_all_files_as_created(self) -> None:
        await db.add_artifact(self.pid, "frontend/src/App.tsx", "one\n", 1)
        result = await main.get_project_changes(self.pid, self.user)
        self.assertFalse(result["has_published"])
        self.assertEqual(result["summary"]["created"], 1)
        self.assertEqual(result["files"][0]["change_type"], "created")

    async def test_missing_baseline_is_reported(self) -> None:
        await db.add_artifact(self.pid, "frontend/src/App.tsx", "one\n", 1)
        await db.mark_published(self.pid, 1)
        result = await main.get_project_changes(self.pid, self.user)
        self.assertTrue(result["has_published"])
        self.assertFalse(result["baseline_ok"])
        self.assertEqual(result["files"], [])

    async def test_change_and_execution_endpoints(self) -> None:
        execution_id = await db.add_execution(
            self.pid,
            "alex",
            "编辑 frontend/src/App.tsx",
            "success",
            "+1 -0",
            run_id="run-1",
            tool="edit_file",
            target="frontend/src/App.tsx",
        )
        change_id = await db.add_file_change(
            self.pid,
            version=1,
            filename="frontend/src/App.tsx",
            change_type="modified",
            diff="+x\n",
            additions=1,
            deletions=0,
            run_id="run-1",
            agent="alex",
            execution_id=execution_id,
        )
        single = await main.get_project_change(self.pid, change_id, self.user)
        self.assertEqual(single["id"], change_id)
        self.assertEqual(single["execution_id"], execution_id)

        grouped = await main.get_execution_changes(
            self.pid, execution_id, self.user
        )
        self.assertEqual([item["id"] for item in grouped["changes"]], [change_id])

    async def test_other_user_gets_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            await main.get_project_changes(self.pid, {"id": "user-2"})
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
