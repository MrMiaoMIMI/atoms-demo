import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import agent
import db
import scaffold
import tools
import workspace


class ScaffoldDesignTests(unittest.TestCase):
    def test_frontend_files_include_design_system(self) -> None:
        files = scaffold.frontend_files("测试项目")
        for path in (
            "frontend/src/design-system.css",
            "frontend/src/styles.css",
            "frontend/src/App.tsx",
            "frontend/src/ui/index.ts",
            "frontend/src/ui/Button.tsx",
            "frontend/src/ui/Field.tsx",
            "frontend/src/ui/Icon.tsx",
            "frontend/src/ui/Navigation.tsx",
            "frontend/src/ui/Overlay.tsx",
            "frontend/src/ui/Surface.tsx",
        ):
            with self.subTest(path=path):
                self.assertIn(path, files)
                self.assertTrue(files[path].strip())

        self.assertIn('import "./design-system.css";', files["frontend/src/main.tsx"])
        self.assertIn("测试项目", files["frontend/src/App.tsx"])
        self.assertIn("--ds-accent", files["frontend/src/styles.css"])
        self.assertIn("lucide-react", files["frontend/package.json"])
        self.assertIn("react-router-dom", files["frontend/package.json"])

    def test_ui_kit_exports(self) -> None:
        files = scaffold.frontend_files("Test")
        self.assertIn("export const Button", files["frontend/src/ui/Button.tsx"])
        self.assertIn("export const Input", files["frontend/src/ui/Field.tsx"])
        self.assertIn("export function EmptyState", files["frontend/src/ui/Surface.tsx"])
        self.assertIn("export function AppShell", files["frontend/src/ui/Navigation.tsx"])
        self.assertIn("export function Dialog", files["frontend/src/ui/Overlay.tsx"])

    def test_svg_is_allowed_but_other_assets_are_not(self) -> None:
        self.assertIn(".svg", scaffold.ALLOWED_EXT)
        self.assertEqual(
            workspace.normalize_path("frontend/src/logo.svg"),
            "frontend/src/logo.svg",
        )
        with self.assertRaises(workspace.PathDenied):
            workspace.normalize_path("frontend/src/photo.png")


class DesignContractTests(unittest.TestCase):
    def test_defaults_by_mode(self) -> None:
        self.assertEqual(agent._normalize_design(None, "backend"), {})
        frontend = agent._normalize_design(None, "frontend")
        self.assertEqual(frontend["archetype"], "landing")
        self.assertEqual(frontend["layout"], "hero+sections")
        fullstack = agent._normalize_design(None, "fullstack")
        self.assertEqual(fullstack["archetype"], "saas-tool")
        self.assertEqual(fullstack["layout"], "topbar+content")

    def test_clamps_model_values(self) -> None:
        design = agent._normalize_design(
            {
                "archetype": "dashboard",
                "style": "editorial",
                "palette": {"accent": "#123456", "bg": "not-a-color"},
                "typography": {"display": "serif", "scale": "huge"},
                "layout": "topbar+sidebar",
                "sections": ["hero", "hero", "pricing"],
                "interactions": ["tabs", "unknown"],
                "density": "compact",
            },
            "fullstack",
        )
        self.assertEqual(design["archetype"], "dashboard")
        self.assertEqual(design["style"], "editorial")
        self.assertEqual(design["palette"]["accent"], "#123456")
        self.assertEqual(design["palette"]["bg"], agent.DEFAULT_PALETTE["bg"])
        self.assertEqual(design["typography"], {"display": "serif", "scale": "regular"})
        self.assertEqual(design["layout"], "topbar+sidebar")
        self.assertEqual(design["sections"], ["hero", "pricing"])
        self.assertEqual(design["interactions"], ["tabs"])
        self.assertEqual(design["density"], "compact")

    def test_design_brief_mentions_tokens(self) -> None:
        plan = {
            "mode": "frontend",
            "design": agent._normalize_design(
                {"palette": {"accent": "#112233"}}, "frontend"
            ),
        }
        brief = agent._design_brief(plan)
        self.assertIn("#112233", brief)
        self.assertIn("--ds-", brief)
        self.assertIn("hero+sections", brief)

    def test_design_brief_is_empty_for_backend(self) -> None:
        self.assertIn(
            "没有前端界面",
            agent._design_brief({"mode": "backend", "design": {}}),
        )

    def test_planner_cannot_plan_scaffold_managed_files(self) -> None:
        files = agent._normalize_files(
            [
                {"path": "frontend/src/App.tsx"},
                {"path": "frontend/src/design-system.css"},
                {"path": "frontend/src/ui/Button.tsx"},
                {"path": "frontend/src/components/Card.tsx"},
            ],
            "frontend",
        )
        paths = {item["path"] for item in files}
        self.assertIn("frontend/src/App.tsx", paths)
        self.assertIn("frontend/src/components/Card.tsx", paths)
        self.assertNotIn("frontend/src/design-system.css", paths)
        self.assertNotIn("frontend/src/ui/Button.tsx", paths)

    def test_design_brief_falls_back_for_legacy_plans(self) -> None:
        brief = agent._design_brief({"mode": "fullstack"})
        self.assertIn("topbar+content", brief)
        self.assertIn("--ds-", brief)


class ReviewTests(unittest.TestCase):
    def _files(self, **overrides: str) -> dict[str, str]:
        files = {
            "frontend/src/App.tsx": (
                "export default function App() {\n"
                '  return <main className="app">hi</main>;\n'
                "}\n"
            ),
            "frontend/src/styles.css": (
                ".app { color: #111; }\n"
                "@media (max-width: 768px) { .app { color: #222; } }\n"
            ),
            "frontend/src/main.tsx": 'import "./styles.css";\n',
            "frontend/src/design-system.css": ":root { --ds-accent: #4267ff; }\n",
        }
        files.update(overrides)
        return files

    def test_requires_design_system_import(self) -> None:
        files = self._files()
        files.pop("frontend/src/design-system.css")
        issues = agent._review(files, "frontend")
        self.assertIn("frontend/src/design-system.css 缺失（设计系统底座）", issues)
        self.assertIn("main.tsx 未引入 design-system.css", issues)

    def test_clean_frontend_passes_structure(self) -> None:
        files = self._files(
            **{
                "frontend/src/main.tsx": (
                    'import "./design-system.css";\n'
                    'import "./styles.css";\n'
                )
            }
        )
        self.assertEqual(agent._review(files, "frontend"), [])

    def test_design_review_reports_missing_tokens_and_states(self) -> None:
        files = self._files(
            **{
                "frontend/src/styles.css": ".app { color: #111; }\n",
                "frontend/src/main.tsx": (
                    'import "./design-system.css";\n'
                    'import "./styles.css";\n'
                ),
            }
        )
        notes = agent._design_review(files, "frontend")
        self.assertTrue(any("--ds-" in note for note in notes))
        self.assertTrue(any("断点" in note for note in notes))
        self.assertTrue(any("加载态" in note for note in notes))


class WriteScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_design_system_and_ui_kit_are_read_only(self) -> None:
        ctx = tools.ToolContext(
            pid="p1",
            run_id="r1",
            agent="alex",
            emit=lambda *args, **kwargs: None,  # type: ignore[arg-type]
        )
        with self.assertRaises(workspace.PathDenied):
            await tools.llm_write_file(
                ctx,
                "frontend/src/design-system.css",
                "x\n",
                overwrite=True,
            )
        with self.assertRaises(workspace.PathDenied):
            await tools.llm_edit_file(
                ctx,
                "frontend/src/ui/Button.tsx",
                "a",
                "b",
            )

    async def test_design_pass_cannot_write_backend(self) -> None:
        ctx = tools.ToolContext(
            pid="p1",
            run_id="r1",
            agent="alex",
            emit=lambda *args, **kwargs: None,  # type: ignore[arg-type]
            write_allowlist=("frontend/src/App.tsx", "frontend/src/styles.css"),
        )
        with self.assertRaises(workspace.PathDenied):
            await tools.llm_write_file(
                ctx,
                "backend/main.py",
                "print('x')\n",
                overwrite=True,
            )


class ScaffoldMigrationTests(unittest.TestCase):
    def test_main_tsx_gets_design_import(self) -> None:
        old = 'import App from "./App";\nimport "./styles.css";\n'
        migrated = agent._with_design_import(old)
        self.assertIn('import "./design-system.css";', migrated)
        self.assertLess(
            migrated.index("design-system.css"),
            migrated.index("./styles.css"),
        )

    def test_tsconfig_loses_vite_client_types(self) -> None:
        old = '{"compilerOptions": {"strict": true, "types": ["vite/client"]}}'
        migrated = agent._migrate_tsconfig(old)
        self.assertNotIn("vite/client", migrated)
        self.assertIn('"types": []', migrated)

        mixed = '{"compilerOptions": {"types": ["node", "vite/client"]}}'
        migrated_mixed = agent._migrate_tsconfig(mixed)
        self.assertNotIn("vite/client", migrated_mixed)
        self.assertIn('"node"', migrated_mixed)

    def test_vite_env_becomes_minimal_import_meta(self) -> None:
        migrated = agent._migrate_vite_env('/// <reference types="vite/client" />\n')
        self.assertIn("interface ImportMetaEnv", migrated)
        self.assertNotIn("vite/client", migrated)

    def test_package_json_merges_curated_dependencies(self) -> None:
        old = (
            '{\n  "name": "demo",\n  "scripts": {"dev": "vite"},\n'
            '  "dependencies": {"react": "^18.3.1", "react-dom": "^18.3.1"},\n'
            '  "devDependencies": {"vite": "^5.4.11"}\n}\n'
        )
        migrated = agent._migrate_package_json(old, "Demo")
        self.assertIn("lucide-react", migrated)
        self.assertIn("react-router-dom", migrated)
        self.assertIn('"dev": "vite"', migrated)
        self.assertIn('"name": "demo"', migrated)


class DesignArtifactReconcileTests(unittest.IsolatedAsyncioTestCase):
    async def test_reconcile_restores_files_and_tombstones_new_ones(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(db, "DB_PATH", Path(tmp) / "test.db"):
                await db.init_db()
                project = await db.create_project("测试", "user-1")
                pid = project["id"]
                before = {
                    "frontend/src/App.tsx": "changed\n",
                    "frontend/src/components/Extra.tsx": "extra\n",
                }
                after = {"frontend/src/App.tsx": "original\n"}
                await agent._reconcile_design_artifacts(pid, 1, before, after)
                files = await db.latest_artifacts(pid)
                self.assertEqual(
                    files["frontend/src/App.tsx"], "original\n"
                )
                self.assertNotIn(
                    "frontend/src/components/Extra.tsx", files
                )


class DesignRestoreTests(unittest.TestCase):
    def test_restore_snapshot_keeps_functional_tree(self) -> None:
        original = {
            "frontend/src/App.tsx": "const a = 1;\n",
            "frontend/src/styles.css": ".a { color: red; }\n",
        }
        ws = workspace.Workspace(dict(original))
        snapshot = dict(ws.files)
        ws.write("frontend/src/App.tsx", "const a = 2;\n", overwrite=True)
        ws.write("frontend/src/components/Extra.tsx", "export const x = 1;\n")
        agent._restore_design_snapshot(ws, snapshot, set())
        self.assertEqual(ws.files, original)


if __name__ == "__main__":
    unittest.main()
