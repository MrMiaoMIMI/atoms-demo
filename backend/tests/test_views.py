import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db
import views


class ViewPresenterTests(unittest.TestCase):
    def test_list_files_becomes_files_view(self) -> None:
        view = views.build_view(
            "list_files",
            {"pattern": "frontend/**/*.tsx"},
            {
                "ok": True,
                "data": {
                    "files": [
                        {"path": "frontend/src/App.tsx", "bytes": 120, "lines": 8}
                    ],
                    "total": 1,
                },
            },
        )
        assert view is not None
        view_type, payload, truncated = view
        self.assertEqual(view_type, "files")
        self.assertEqual(payload["pattern"], "frontend/**/*.tsx")
        self.assertEqual(payload["files"][0]["path"], "frontend/src/App.tsx")
        self.assertEqual(payload["total"], 1)
        self.assertFalse(truncated)

    def test_read_file_becomes_file_view(self) -> None:
        view = views.build_view(
            "read_file",
            {"path": "frontend/src/App.tsx", "offset": 1, "limit": 400},
            {
                "ok": True,
                "data": {
                    "path": "frontend/src/App.tsx",
                    "content": "export default function App() {}\n",
                    "start_line": 1,
                    "end_line": 1,
                    "total_lines": 1,
                    "truncated": False,
                },
            },
        )
        assert view is not None
        view_type, payload, _ = view
        self.assertEqual(view_type, "file")
        self.assertEqual(payload["path"], "frontend/src/App.tsx")
        self.assertIn("export default", payload["content"])
        self.assertEqual(payload["end_line"], 1)

    def test_read_file_content_is_capped(self) -> None:
        view = views.build_view(
            "read_file",
            {"path": "big.ts"},
            {
                "ok": True,
                "data": {
                    "path": "big.ts",
                    "content": "x" * (views.MAX_CONTENT + 100),
                    "start_line": 1,
                    "end_line": 10,
                    "total_lines": 10,
                },
            },
        )
        assert view is not None
        _, payload, truncated = view
        self.assertTrue(truncated)
        self.assertLessEqual(len(payload["content"]), views.MAX_CONTENT + 20)

    def test_grep_becomes_search_view(self) -> None:
        view = views.build_view(
            "grep",
            {"pattern": "useState", "glob": "frontend/**/*.tsx"},
            {
                "ok": True,
                "data": {
                    "matches": [
                        {
                            "path": "frontend/src/App.tsx",
                            "line": 3,
                            "text": "import { useState } from 'react'",
                        }
                    ],
                    "total": 1,
                    "truncated": False,
                },
            },
        )
        assert view is not None
        view_type, payload, _ = view
        self.assertEqual(view_type, "search")
        self.assertEqual(payload["pattern"], "useState")
        self.assertEqual(payload["matches"][0]["line"], 3)

    def test_diff_tools_reuse_file_change(self) -> None:
        view = views.build_view(
            "edit_file",
            {"path": "frontend/src/App.tsx", "old_string": "a", "new_string": "b"},
            {"ok": True, "data": {"changed": True, "change_id": 7}},
        )
        self.assertEqual(view, ("diff", {}, False))

    def test_unchanged_write_has_no_view(self) -> None:
        view = views.build_view(
            "write_file",
            {"path": "frontend/src/App.tsx", "content": "same"},
            {"ok": True, "data": {"changed": False, "change_id": None}},
        )
        self.assertIsNone(view)

    def test_failed_write_hides_file_contents(self) -> None:
        view = views.build_view(
            "write_file",
            {
                "path": "frontend/src/App.tsx",
                "content": "secret body",
                "overwrite": False,
            },
            {
                "ok": False,
                "error": {"code": "workspace", "message": "文件已存在"},
            },
        )
        assert view is not None
        view_type, payload, _ = view
        self.assertEqual(view_type, "json")
        self.assertNotIn("content", payload["arguments"])
        self.assertEqual(payload["arguments"]["path"], "frontend/src/App.tsx")
        self.assertIn("文件已存在", payload["error"]["message"])

    def test_build_preview_success_becomes_terminal_view(self) -> None:
        view = views.build_view(
            "build_preview",
            {},
            {
                "ok": True,
                "data": {
                    "mode": "frontend",
                    "command": "esbuild src/main.tsx",
                    "duration_ms": 321,
                    "exit_code": 0,
                    "output": "构建成功",
                },
            },
        )
        assert view is not None
        view_type, payload, _ = view
        self.assertEqual(view_type, "terminal")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["duration_ms"], 321)
        self.assertEqual(payload["command"], "esbuild src/main.tsx")

    def test_build_preview_failure_keeps_compiler_output(self) -> None:
        view = views.build_view(
            "build_preview",
            {},
            {
                "ok": False,
                "error": {
                    "code": "build_failed",
                    "message": 'error: Could not resolve "./Missing"',
                },
                "data": {"mode": "frontend", "exit_code": 1, "duration_ms": 12},
            },
        )
        assert view is not None
        view_type, payload, _ = view
        self.assertEqual(view_type, "terminal")
        self.assertFalse(payload["ok"])
        self.assertIn("Could not resolve", payload["output"])

    def test_start_runtime_keeps_port_and_log(self) -> None:
        view = views.build_view(
            "start_runtime",
            {},
            {
                "ok": True,
                "data": {
                    "port": 43210,
                    "command": "python -m uvicorn main:app --port 43210",
                    "duration_ms": 800,
                    "exit_code": 0,
                    "log": "INFO: Application startup complete.",
                },
            },
        )
        assert view is not None
        view_type, payload, _ = view
        self.assertEqual(view_type, "terminal")
        self.assertEqual(payload["port"], 43210)
        self.assertIn("startup complete", payload["output"])

    def test_check_health_becomes_http_view(self) -> None:
        view = views.build_view(
            "check_health",
            {"port": 43210},
            {
                "ok": False,
                "error": {"code": "health_failed", "message": "HTTP 500"},
                "data": {
                    "method": "GET",
                    "url": "/api/health",
                    "status": 500,
                    "duration_ms": 9,
                    "body": '{"detail":"boom"}',
                },
            },
        )
        assert view is not None
        view_type, payload, _ = view
        self.assertEqual(view_type, "http")
        self.assertEqual(payload["status"], 500)
        self.assertIn("boom", payload["body"])

    def test_read_runtime_log_becomes_terminal_view(self) -> None:
        view = views.build_view(
            "read_runtime_log",
            {"lines": 10},
            {
                "ok": True,
                "data": {
                    "lines": ["line one", "line two"],
                    "text": "line one\nline two",
                    "truncated": False,
                },
            },
        )
        assert view is not None
        view_type, payload, _ = view
        self.assertEqual(view_type, "terminal")
        self.assertEqual(payload["lines"], ["line one", "line two"])
        self.assertIn("line two", payload["output"])

    def test_validate_plan_becomes_json_view(self) -> None:
        view = views.build_view(
            "validate_plan",
            {"plan": {"mode": "frontend", "files": [{"path": "frontend/src/App.tsx"}]}},
            {"ok": True, "data": {"valid": True}},
        )
        assert view is not None
        view_type, payload, _ = view
        self.assertEqual(view_type, "json")
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["plan"]["mode"], "frontend")

    def test_read_project_state_has_no_view_for_now(self) -> None:
        view = views.build_view(
            "read_project_state",
            {},
            {"ok": True, "data": {"mode": "frontend", "files": []}},
        )
        self.assertIsNone(view)


class ExecutionViewDbTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch.object(db, "DB_PATH", Path(self._tmp.name) / "test.db")
        self._patch.start()
        await db.init_db()
        project = await db.create_project("视图测试", "user-1")
        self.pid = project["id"]

    async def asyncTearDown(self) -> None:
        self._patch.stop()
        self._tmp.cleanup()

    async def test_view_round_trip_and_state(self) -> None:
        exec_id = await db.add_execution(
            self.pid, "alex", "读取 frontend/src/App.tsx", "success", "12 行"
        )
        await db.add_execution_view(
            self.pid,
            exec_id,
            "file",
            {"path": "frontend/src/App.tsx", "content": "hello"},
        )
        row = await db.get_execution_view(self.pid, exec_id)
        assert row is not None
        self.assertEqual(row["view_type"], "file")
        self.assertIn("hello", row["payload"])
        self.assertEqual(row["truncated"], 0)

        state = await db.get_state(self.pid)
        assert state is not None
        execution = next(item for item in state["executions"] if item["id"] == exec_id)
        self.assertEqual(execution["view_type"], "file")

    async def test_diff_view_is_derived_from_file_changes(self) -> None:
        exec_id = await db.add_execution(
            self.pid, "alex", "编辑 App.tsx", "success", "+1 -1"
        )
        await db.add_file_change(
            self.pid,
            version=1,
            filename="frontend/src/App.tsx",
            change_type="modified",
            diff="--- a\n+++ b\n",
            additions=1,
            deletions=1,
            execution_id=exec_id,
        )
        state = await db.get_state(self.pid)
        assert state is not None
        execution = next(item for item in state["executions"] if item["id"] == exec_id)
        self.assertEqual(execution["change_count"], 1)
        self.assertEqual(execution["view_type"], "diff")

    async def test_delete_project_removes_views(self) -> None:
        exec_id = await db.add_execution(self.pid, "alex", "读取", "success", "")
        await db.add_execution_view(self.pid, exec_id, "file", {"path": "a.ts"})
        await db.delete_project(self.pid)
        self.assertIsNone(await db.get_execution_view(self.pid, exec_id))

    async def test_prune_keeps_the_most_recent_runs(self) -> None:
        ids: list[int] = []
        for index in range(5):
            exec_id = await db.add_execution(
                self.pid,
                "alex",
                f"读取 {index}",
                "success",
                "",
                run_id=f"run-{index}",
            )
            ids.append(exec_id)
            await db.add_execution_view(
                self.pid,
                exec_id,
                "file",
                {"path": f"file-{index}.ts", "content": "x"},
            )

        result = await db.prune_execution_views(
            self.pid, keep_runs=2, max_bytes=0
        )
        self.assertEqual(result["removed"], 3)
        self.assertIsNone(await db.get_execution_view(self.pid, ids[0]))
        self.assertIsNone(await db.get_execution_view(self.pid, ids[2]))
        self.assertIsNotNone(await db.get_execution_view(self.pid, ids[3]))
        self.assertIsNotNone(await db.get_execution_view(self.pid, ids[4]))

        # Step rows remain: only the payload is dropped.
        state = await db.get_state(self.pid)
        assert state is not None
        self.assertEqual(len(state["executions"]), 5)

    async def test_prune_caps_total_payload_bytes(self) -> None:
        ids: list[int] = []
        for index in range(3):
            exec_id = await db.add_execution(
                self.pid, "alex", f"构建 {index}", "success", ""
            )
            ids.append(exec_id)
            await db.add_execution_view(
                self.pid,
                exec_id,
                "terminal",
                {"output": "x" * 1000},
            )

        result = await db.prune_execution_views(
            self.pid, keep_runs=0, max_bytes=2500
        )
        self.assertEqual(result["removed"], 1)
        self.assertIsNone(await db.get_execution_view(self.pid, ids[0]))
        self.assertIsNotNone(await db.get_execution_view(self.pid, ids[1]))
        self.assertIsNotNone(await db.get_execution_view(self.pid, ids[2]))

    async def test_prune_with_no_views_is_a_noop(self) -> None:
        result = await db.prune_execution_views(
            self.pid, keep_runs=2, max_bytes=1000
        )
        self.assertEqual(result["removed"], 0)


if __name__ == "__main__":
    unittest.main()
