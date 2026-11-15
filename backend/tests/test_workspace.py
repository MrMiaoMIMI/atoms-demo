import os
import tempfile
import unittest
from pathlib import Path

import workspace


class PathPolicyTests(unittest.TestCase):
    def test_allowed_paths(self) -> None:
        for path in (
            "frontend/src/App.tsx",
            "frontend/src/components/Foo.tsx",
            "frontend/src/styles.css",
            "frontend/package.json",
            "backend/main.py",
            "backend/schema.sql",
            "README.md",
            ".gitignore",
        ):
            with self.subTest(path=path):
                self.assertEqual(workspace.normalize_path(path), path)

    def test_denied_paths(self) -> None:
        for path in (
            "../secret.py",
            "/etc/passwd",
            "frontend/../../secret.tsx",
            "C:\\temp\\x.tsx",
            ".env",
            "frontend/.env",
            "frontend/src/.hidden.tsx",
            ".published/source.json",
            ".preview/index.html",
            "backend/data/app.db",
            "frontend/dist/app.js",
            "frontend/node_modules/pkg/index.js",
            "backend/__pycache__/x.py",
            "script.sh",
            "frontend/src/App.exe",
            "frontend/src/App",
        ):
            with self.subTest(path=path):
                with self.assertRaises(workspace.PathDenied):
                    workspace.normalize_path(path)


class WorkspaceEditTests(unittest.TestCase):
    def test_write_create_and_overwrite_guard(self) -> None:
        ws = workspace.Workspace()
        change = ws.write("frontend/src/App.tsx", "const a = 1;\n")
        self.assertIsNotNone(change)
        assert change is not None
        self.assertEqual(change.change_type, "created")
        self.assertEqual(change.additions, 1)

        with self.assertRaises(workspace.OverwriteRequired):
            ws.write("frontend/src/App.tsx", "const a = 2;\n")

        change = ws.write("frontend/src/App.tsx", "const a = 2;\n", overwrite=True)
        self.assertIsNotNone(change)
        assert change is not None
        self.assertEqual(change.change_type, "modified")
        self.assertEqual(change.additions, 1)
        self.assertEqual(change.deletions, 1)

    def test_write_noop_returns_none(self) -> None:
        ws = workspace.Workspace({"frontend/src/App.tsx": "same\n"})
        self.assertIsNone(
            ws.write("frontend/src/App.tsx", "same\n", overwrite=True)
        )

    def test_write_size_limit(self) -> None:
        ws = workspace.Workspace()
        with self.assertRaises(workspace.TooLarge):
            ws.write("frontend/src/App.tsx", "x" * (workspace.MAX_WRITE_BYTES + 1))

    def test_edit_unique_match(self) -> None:
        ws = workspace.Workspace(
            {"frontend/src/App.tsx": "const a = 1;\nconst b = 2;\n"}
        )
        change = ws.edit(
            "frontend/src/App.tsx", "const b = 2;", "const b = 3;"
        )
        self.assertIsNotNone(change)
        assert change is not None
        self.assertEqual(change.change_type, "modified")
        self.assertEqual(
            ws.files["frontend/src/App.tsx"],
            "const a = 1;\nconst b = 3;\n",
        )

    def test_edit_no_match(self) -> None:
        ws = workspace.Workspace({"frontend/src/App.tsx": "const a = 1;\n"})
        with self.assertRaises(workspace.NoMatch) as ctx:
            ws.edit("frontend/src/App.tsx", "missing", "x")
        self.assertEqual(ctx.exception.details.get("match_count"), 0)

    def test_edit_ambiguous_match(self) -> None:
        ws = workspace.Workspace(
            {"frontend/src/App.tsx": "const a = 1;\nconst b = 2;\n"}
        )
        with self.assertRaises(workspace.AmbiguousMatch) as ctx:
            ws.edit("frontend/src/App.tsx", "const", "let")
        self.assertEqual(ctx.exception.details.get("match_count"), 2)

    def test_edit_replace_all(self) -> None:
        ws = workspace.Workspace(
            {"frontend/src/App.tsx": "const a = 1;\nconst b = 2;\n"}
        )
        ws.edit("frontend/src/App.tsx", "const", "let", replace_all=True)
        self.assertEqual(
            ws.files["frontend/src/App.tsx"], "let a = 1;\nlet b = 2;\n"
        )

    def test_delete(self) -> None:
        ws = workspace.Workspace({"frontend/src/App.tsx": "x\n"})
        change = ws.delete("frontend/src/App.tsx")
        self.assertEqual(change.change_type, "deleted")
        self.assertNotIn("frontend/src/App.tsx", ws.files)
        self.assertIn("frontend/src/App.tsx", ws.deleted)
        with self.assertRaises(workspace.NotFound):
            ws.delete("frontend/src/App.tsx")


class WorkspaceReadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = workspace.Workspace(
            {
                "frontend/src/App.tsx": "one\ntwo\nthree\nfour\nfive\n",
                "frontend/src/components/Foo.tsx": "const Foo = () => useState(0);\n",
                "backend/main.py": "print('hello')\n",
            }
        )

    def test_read_slice(self) -> None:
        result = self.ws.read("frontend/src/App.tsx", offset=2, limit=2)
        self.assertEqual(result.content, "two\nthree")
        self.assertEqual(result.start_line, 2)
        self.assertEqual(result.end_line, 3)
        self.assertEqual(result.total_lines, 5)
        self.assertTrue(result.truncated)

    def test_read_full(self) -> None:
        result = self.ws.read("frontend/src/App.tsx", offset=1, limit=5)
        self.assertEqual(result.content, "one\ntwo\nthree\nfour\nfive")
        self.assertFalse(result.truncated)

    def test_list_glob(self) -> None:
        infos = self.ws.list_files("frontend/**/*.tsx")
        self.assertEqual(
            [item.path for item in infos],
            ["frontend/src/App.tsx", "frontend/src/components/Foo.tsx"],
        )

    def test_grep(self) -> None:
        result = self.ws.grep("useState", glob="frontend/**/*.tsx", max_results=1)
        self.assertEqual(result.total, 1)
        self.assertFalse(result.truncated)
        self.assertEqual(result.matches[0].path, "frontend/src/components/Foo.tsx")

    def test_commit_plan(self) -> None:
        ws = workspace.Workspace({"a.tsx": "1\n", "b.tsx": "2\n"})
        ws.write("a.tsx", "1x\n", overwrite=True)
        ws.write("c.tsx", "3\n")
        ws.delete("b.tsx")
        changed, deleted = ws.commit_plan()
        self.assertEqual(set(changed), {"a.tsx", "c.tsx"})
        self.assertEqual(deleted, ["b.tsx"])


class WorkspaceApplyTests(unittest.TestCase):
    def test_apply_writes_changed_and_reconciles_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "frontend/src").mkdir(parents=True)
            (root / "frontend/src/App.tsx").write_text("old\n", encoding="utf-8")
            (root / "frontend/src/Stale.tsx").write_text("stale\n", encoding="utf-8")
            (root / "backend/data").mkdir(parents=True)
            (root / "backend/main.py").write_text("print('old')\n", encoding="utf-8")
            (root / "backend/data/app.db").write_text("db", encoding="utf-8")
            (root / "frontend/node_modules").mkdir(parents=True)
            (root / "frontend/node_modules/x.js").write_text("dep", encoding="utf-8")
            (root / ".published/site").mkdir(parents=True)
            (root / ".published/site/index.html").write_text("pub", encoding="utf-8")

            ws = workspace.Workspace(
                {
                    "frontend/src/App.tsx": "old\n",
                    "backend/main.py": "print('old')\n",
                }
            )
            ws.write("frontend/src/App.tsx", "new\n", overwrite=True)
            ws.write("frontend/src/New.tsx", "new file\n")
            ws.delete("backend/main.py")

            stats = ws.apply_to(root, reconcile_source=True)
            self.assertEqual(stats["written"], 2)
            self.assertGreaterEqual(stats["removed"], 2)
            self.assertEqual(
                (root / "frontend/src/App.tsx").read_text(encoding="utf-8"), "new\n"
            )
            self.assertTrue((root / "frontend/src/New.tsx").is_file())
            self.assertFalse((root / "frontend/src/Stale.tsx").exists())
            self.assertFalse((root / "backend/main.py").exists())
            self.assertTrue((root / "backend/data/app.db").is_file())
            self.assertTrue((root / "frontend/node_modules/x.js").is_file())
            self.assertTrue((root / ".published/site/index.html").is_file())

    def test_apply_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            (root / "frontend").mkdir(parents=True)
            try:
                os.symlink(outside, root / "frontend/link")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            ws = workspace.Workspace({"frontend/link/x.tsx": "x\n"})
            ws.write("frontend/link/x.tsx", "y\n", overwrite=True)
            with self.assertRaises(workspace.PathDenied):
                ws.apply_to(root)


if __name__ == "__main__":
    unittest.main()
