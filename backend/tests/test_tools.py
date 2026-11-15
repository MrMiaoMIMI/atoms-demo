import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import agents
import db
from tools import Toolbox, ToolContext


class ToolboxTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch.object(db, "DB_PATH", Path(self._tmp.name) / "test.db")
        self._patch.start()
        await db.init_db()
        self.pid = "project-1"
        self.events: list[tuple[str, dict]] = []

        async def emit(event: str, payload: dict) -> None:
            self.events.append((event, payload))

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

    async def test_write_read_edit_delete(self) -> None:
        toolbox = self._toolbox()
        created = await toolbox.invoke(
            "write_file",
            {
                "path": "frontend/src/App.tsx",
                "content": "const a = 1;\n",
            },
        )
        self.assertTrue(created["ok"], created)
        data = created["data"]
        self.assertEqual(data["change_type"], "created")
        self.assertIsNotNone(data["change_id"])
        self.assertEqual(
            await db.latest_artifacts(self.pid),
            {"frontend/src/App.tsx": "const a = 1;\n"},
        )
        self.assertEqual([event for event, _ in self.events], ["file_change", "artifact"])

        read = await toolbox.invoke("read_file", {"path": "frontend/src/App.tsx"})
        self.assertTrue(read["ok"])
        self.assertEqual(read["data"]["content"], "const a = 1;")
        self.assertIn("1  const a = 1;", read["data"]["numbered"])

        blocked = await toolbox.invoke(
            "write_file",
            {
                "path": "frontend/src/App.tsx",
                "content": "const a = 2;\n",
            },
        )
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["error"]["code"], "overwrite_required")

        edited = await toolbox.invoke(
            "edit_file",
            {
                "path": "frontend/src/App.tsx",
                "old_string": "const a = 1;",
                "new_string": "const a = 3;",
            },
        )
        self.assertTrue(edited["ok"], edited)
        self.assertEqual(edited["data"]["change_type"], "modified")
        self.assertEqual(
            await db.latest_artifacts(self.pid),
            {"frontend/src/App.tsx": "const a = 3;\n"},
        )

        deleted = await toolbox.invoke(
            "delete_file", {"path": "frontend/src/App.tsx"}
        )
        self.assertTrue(deleted["ok"], deleted)
        self.assertEqual(deleted["data"]["change_type"], "deleted")
        self.assertEqual(await db.latest_artifacts(self.pid), {})

    async def test_list_and_grep(self) -> None:
        toolbox = self._toolbox()
        await toolbox.invoke(
            "write_file",
            {
                "path": "frontend/src/components/Foo.tsx",
                "content": "const Foo = () => useState(0);\n",
            },
        )
        listing = await toolbox.invoke("list_files", {"pattern": "frontend/**/*.tsx"})
        self.assertTrue(listing["ok"])
        self.assertEqual(
            [item["path"] for item in listing["data"]["files"]],
            ["frontend/src/components/Foo.tsx"],
        )

        found = await toolbox.invoke(
            "grep",
            {"pattern": "useState", "glob": "frontend/**/*.tsx"},
        )
        self.assertTrue(found["ok"])
        self.assertEqual(found["data"]["total"], 1)
        self.assertEqual(found["data"]["matches"][0]["line"], 1)

    async def test_path_denied(self) -> None:
        toolbox = self._toolbox()
        denied = await toolbox.invoke(
            "write_file",
            {"path": "../escape.tsx", "content": "x\n"},
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["error"]["code"], "path_denied")

        protected = await toolbox.invoke(
            "write_file",
            {"path": "backend/data/app.db", "content": "x"},
        )
        self.assertFalse(protected["ok"])
        self.assertEqual(protected["error"]["code"], "path_denied")

    async def test_role_isolation(self) -> None:
        bob = self._toolbox("bob")
        denied = await bob.invoke(
            "write_file",
            {"path": "frontend/src/App.tsx", "content": "x\n"},
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["error"]["code"], "permission_denied")

        read = await bob.invoke("list_files", {})
        self.assertTrue(read["ok"])

    async def test_specs_only_expose_allowed_tools(self) -> None:
        bob_names = {
            spec["function"]["name"] for spec in self._toolbox("bob").specs()
        }
        self.assertIn("read_file", bob_names)
        self.assertIn("grep", bob_names)
        self.assertNotIn("write_file", bob_names)
        self.assertNotIn("delete_file", bob_names)

        alex_names = {
            spec["function"]["name"] for spec in self._toolbox("alex").specs()
        }
        self.assertIn("edit_file", alex_names)
        self.assertIn("delete_file", alex_names)
        self.assertIn("build_preview", alex_names)


if __name__ == "__main__":
    unittest.main()
