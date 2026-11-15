import unittest

import diffing


class UnifiedDiffTests(unittest.TestCase):
    def test_no_change(self) -> None:
        result = diffing.unified_diff(path="a.tsx", old="a\nb\n", new="a\nb\n")
        self.assertFalse(result.has_changes)
        self.assertEqual(result.additions, 0)
        self.assertEqual(result.deletions, 0)

    def test_modified(self) -> None:
        result = diffing.unified_diff(
            path="frontend/src/App.tsx",
            old="const a = 1;\nconst b = 2;\n",
            new="const a = 1;\nconst b = 3;\n",
        )
        self.assertTrue(result.has_changes)
        self.assertEqual(result.additions, 1)
        self.assertEqual(result.deletions, 1)
        self.assertIn("@@", result.diff)
        self.assertIn("-const b = 2;", result.diff)
        self.assertIn("+const b = 3;", result.diff)

    def test_created(self) -> None:
        result = diffing.unified_diff(path="new.tsx", old=None, new="a\nb\n")
        self.assertEqual(result.additions, 2)
        self.assertEqual(result.deletions, 0)
        self.assertIn("--- /dev/null", result.diff)
        self.assertIn("+++ after/new.tsx", result.diff)

    def test_deleted(self) -> None:
        result = diffing.unified_diff(path="old.tsx", old="a\nb\n", new=None)
        self.assertEqual(result.additions, 0)
        self.assertEqual(result.deletions, 2)
        self.assertIn("+++ /dev/null", result.diff)

    def test_truncated(self) -> None:
        old = "\n".join(f"old-{i}" for i in range(100))
        new = "\n".join(f"new-{i}" for i in range(100))
        result = diffing.unified_diff(path="a.tsx", old=old, new=new, max_chars=80)
        self.assertTrue(result.truncated)
        self.assertIn("diff truncated", result.diff)


class DiffTreesTests(unittest.TestCase):
    def test_created_modified_deleted(self) -> None:
        published = {"a.tsx": "one\n", "b.tsx": "two\n"}
        current = {"a.tsx": "one\nmore\n", "c.tsx": "three\n"}
        changes = diffing.diff_trees(published, current)
        by_path = {change.path: change for change in changes}
        self.assertEqual(set(by_path), {"a.tsx", "b.tsx", "c.tsx"})
        self.assertEqual(by_path["a.tsx"].change_type, "modified")
        self.assertEqual(by_path["b.tsx"].change_type, "deleted")
        self.assertEqual(by_path["c.tsx"].change_type, "created")
        self.assertEqual(
            diffing.summarize(changes),
            {"created": 1, "modified": 1, "deleted": 1},
        )

    def test_identical_trees(self) -> None:
        self.assertEqual(diffing.diff_trees({"a": "1"}, {"a": "1"}), [])


if __name__ == "__main__":
    unittest.main()
