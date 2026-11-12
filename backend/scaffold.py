"""Deterministic scaffolding for generated projects.

The LLM only writes app-specific code (React components / FastAPI routes).
Everything that must be byte-for-byte correct for the project to build and
run — package.json, tsconfig, Vite config, SQLite helpers, README, preview
shells — is produced here by plain Python.
"""
from __future__ import annotations

import html
import re
from typing import Any

MODES = ("frontend", "fullstack", "backend")
SAFE_PATH = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._/-]{0,119}$")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,30}$")
ALLOWED_EXT = {".tsx", ".ts", ".jsx", ".js", ".css", ".py", ".json", ".md", ".html", ".txt", ".sql"}

FRONTEND_PACKAGE = """{
  "name": "__NAME__",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "typecheck": "tsc --noEmit",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "~5.6.3",
    "vite": "^5.4.11"
  }
}
"""

FRONTEND_INDEX = """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>__TITLE__</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
"""

FRONTEND_VITE_CONFIG = """import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
"""

FRONTEND_TSCONFIG = """{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "types": ["vite/client"]
  },
  "include": ["src"]
}
"""

FRONTEND_MAIN = """import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
"""

FRONTEND_ENV_TYPES = """/// <reference types="vite/client" />
"""

BACKEND_REQUIREMENTS = """fastapi==0.115.6
uvicorn[standard]==0.34.0
aiosqlite==0.20.0
"""

BACKEND_DB = '''"""SQLite helpers for this generated project.

The database lives inside this project at ``backend/data/app.db`` and is never
shared with the Atoms demo database.
"""
import re
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "app.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"

_TABLE_RE = re.compile(
    r"CREATE\\s+TABLE\\s+IF\\s+NOT\\s+EXISTS\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*\\(([^;]*)\\)\\s*;",
    re.I | re.S,
)


async def connect() -> aiosqlite.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.execute("PRAGMA busy_timeout=5000")
    return conn


@asynccontextmanager
async def connection():
    conn = await connect()
    try:
        yield conn
    finally:
        await conn.close()


def _column_defs(body: str):
    """Yield (name, declaration) for plain columns in a CREATE TABLE body."""
    parts: list[str] = []
    depth = 0
    buf = ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf)

    for part in parts:
        decl = " ".join(part.split())
        if not decl:
            continue
        upper = decl.upper()
        if upper.startswith(("PRIMARY ", "FOREIGN ", "UNIQUE", "CHECK ", "CONSTRAINT ")):
            continue
        name = decl.split()[0].strip('"`[]')
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            continue
        rest = decl[len(name):].strip()
        if "PRIMARY KEY" in rest.upper():
            continue
        yield name, rest


async def _add_missing_columns(conn: aiosqlite.Connection) -> None:
    """Cheap additive migration so follow-up edits can add fields safely."""
    if not SCHEMA_PATH.exists():
        return
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    for table, body in _TABLE_RE.findall(sql):
        cur = await conn.execute(f'PRAGMA table_info("{table}")')
        existing = {row[1] for row in await cur.fetchall()}
        for name, decl in _column_defs(body):
            if name in existing:
                continue
            try:
                await conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {decl}')
            except Exception:
                # SQLite cannot add NOT NULL/non-constant defaults via ALTER.
                await conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}"')


async def init_db() -> None:
    async with connection() as conn:
        if SCHEMA_PATH.exists():
            await conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            await _add_missing_columns(conn)
            await conn.commit()
'''

FRONTEND_ONLY_NOTES = "本项目是纯前端应用，不需要后端服务。"


def safe_project_path(path: str) -> bool:
    return bool(SAFE_PATH.match(path)) and ".." not in path.split("/")


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _package_name(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:40] or "atoms-app"


def frontend_files(title: str) -> dict[str, str]:
    return {
        "frontend/package.json": FRONTEND_PACKAGE.replace("__NAME__", _package_name(title)),
        "frontend/index.html": FRONTEND_INDEX.replace("__TITLE__", _esc(title)),
        "frontend/vite.config.ts": FRONTEND_VITE_CONFIG,
        "frontend/tsconfig.json": FRONTEND_TSCONFIG,
        "frontend/src/main.tsx": FRONTEND_MAIN,
        "frontend/src/vite-env.d.ts": FRONTEND_ENV_TYPES,
    }


def backend_common_files() -> dict[str, str]:
    return {
        "backend/requirements.txt": BACKEND_REQUIREMENTS,
        "backend/db.py": BACKEND_DB,
    }


def gitignore() -> str:
    return """# Generated app runtime files
frontend/node_modules/
frontend/dist/
.preview/
.runtime.log
backend/data/*.db
backend/data/*.db-wal
backend/data/*.db-shm
__pycache__/
*.pyc
.DS_Store
"""


def _sql_default(value: Any) -> str | None:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str) and re.match(r"^[A-Za-z0-9_ .,:+-]{0,40}$", value):
        return "'" + value.replace("'", "''") + "'"
    return None


FIELD_TYPES = {"INTEGER", "TEXT", "REAL", "NUMERIC", "BLOB"}


def schema_sql(entities: list[dict]) -> str:
    """Render CREATE TABLE statements from normalized planner entities."""
    chunks = ["-- Per-project SQLite schema. Safe to execute repeatedly.\n"]
    for entity in entities:
        table = str(entity.get("table") or "").strip()
        if not IDENT.match(table):
            continue
        lines: list[str] = []
        has_created_at = False
        for field in entity.get("fields") or []:
            name = str(field.get("name") or "").strip()
            if not IDENT.match(name):
                continue
            ftype = str(field.get("type") or "TEXT").upper()
            if ftype not in FIELD_TYPES:
                ftype = "TEXT"
            decl = f"    {name} {ftype}"
            if field.get("primary_key"):
                decl += " PRIMARY KEY"
                if field.get("autoincrement") and ftype == "INTEGER":
                    decl += " AUTOINCREMENT"
            elif field.get("not_null"):
                decl += " NOT NULL"
            default = _sql_default(field.get("default"))
            if default is not None and not field.get("primary_key"):
                decl += f" DEFAULT {default}"
            if name == "created_at":
                has_created_at = True
            lines.append(decl)
        if not lines:
            continue
        if not has_created_at:
            lines.append("    created_at TEXT NOT NULL DEFAULT (datetime('now'))")
        chunks.append(
            f"CREATE TABLE IF NOT EXISTS {table} (\n" + ",\n".join(lines) + "\n);\n"
        )
    return "\n".join(chunks)


def readme(title: str, mode: str, api: list[dict]) -> str:
    lines = [
        f"# {title}",
        "",
        "由 Atoms Demo 生成的 Web 项目。",
        "",
        f"- 形态：**{ {'frontend': '纯前端', 'fullstack': '前后端一体', 'backend': '纯后端 API'}[mode] }**",
        "",
    ]
    if mode in ("frontend", "fullstack"):
        lines += [
            "## 前端（Vite + React 18 + TypeScript）",
            "",
            "```bash",
            "cd frontend",
            "npm install",
            "npm run dev       # http://127.0.0.1:5173",
            "npm run build     # 产物输出到 frontend/dist",
            "```",
            "",
        ]
    if mode in ("backend", "fullstack"):
        lines += [
            "## 后端（FastAPI + SQLite）",
            "",
            "```bash",
            "cd backend",
            "python3.11 -m venv .venv",
            ".venv/bin/pip install -r requirements.txt",
            ".venv/bin/uvicorn main:app --reload --port 8000",
            "```",
            "",
            "数据库文件位于 `backend/data/app.db`，随本项目的目录一起保存，"
            "与 Atoms Demo 自己的数据库完全隔离。首次启动会自动建表。",
            "",
            f"- API 文档：http://127.0.0.1:8000/docs",
            "",
        ]
        if api:
            lines += ["### API", "", "| 方法 | 路径 | 说明 |", "| --- | --- | --- |"]
            for item in api:
                lines.append(
                    f"| {item['method']} | `{item['path']}` | {item.get('description') or ''} |"
                )
            lines.append("")
    if mode == "fullstack":
        lines += [
            "## 本地联调",
            "",
            "后端跑在 8000，前端 Vite 已把 `/api` 代理到 8000；"
            "前端请求统一使用相对路径 `api/...`，因此部署到任意子路径也能工作。",
            "",
        ]
    lines += [
        "## 说明",
        "",
        "- 本目录是完整源码，可独立于 Atoms Demo 运行。",
        "- `.preview/`、`.runtime.log`、`backend/data/*.db*` 是运行产物，已在 `.gitignore` 中忽略。",
        "",
    ]
    return "\n".join(lines)


PREVIEW_SHELL = """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <base href="/apps/__PID__/" />
    <title>__TITLE__</title>
    __CSS__
  </head>
  <body>
    <div id="root"></div>
    <script defer src="app.js"></script>
  </body>
</html>
"""


def preview_shell(pid: str, title: str, has_css: bool) -> str:
    css = '<link rel="stylesheet" href="app.css" />' if has_css else ""
    return (
        PREVIEW_SHELL.replace("__PID__", _esc(pid))
        .replace("__TITLE__", _esc(title))
        .replace("__CSS__", css)
    )


API_PREVIEW_CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; min-height: 100vh; padding: 48px 20px; color: #e8edf9;
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  background: radial-gradient(800px 500px at 80% -10%, rgba(108,140,255,.2), transparent 60%), #080d18;
}
.wrap { width: min(760px, 100%); margin: 0 auto; }
.eyebrow { margin: 0 0 10px; font-size: 11px; letter-spacing: .26em; color: #6c8cff; font-weight: 700; }
h1 { margin: 0 0 10px; font-size: clamp(26px, 5vw, 38px); letter-spacing: -.03em; }
.lead { margin: 0 0 26px; color: #98a2bd; line-height: 1.7; font-size: 14px; }
.status { display: inline-flex; align-items: center; gap: 8px; padding: 8px 14px; border-radius: 999px;
  border: 1px solid rgba(255,255,255,.1); background: rgba(255,255,255,.03); font-size: 12px; color: #aab4cf; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #ffd166; }
.dot.ok { background: #38e1c6; box-shadow: 0 0 12px rgba(56,225,198,.6); }
.dot.bad { background: #ff7a8f; }
table { width: 100%; margin-top: 26px; border-collapse: collapse; overflow: hidden; border-radius: 14px;
  border: 1px solid rgba(255,255,255,.08); background: rgba(255,255,255,.02); }
th, td { padding: 12px 14px; text-align: left; border-bottom: 1px solid rgba(255,255,255,.06); font-size: 13px; }
th { color: #7c87a4; font-size: 11px; letter-spacing: .08em; }
tr:last-child td { border-bottom: 0; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: #c7d4ff; }
.links { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 22px; }
.links a { padding: 9px 16px; border-radius: 10px; border: 1px solid rgba(255,255,255,.12);
  color: #dfe4f5; text-decoration: none; font-size: 13px; background: rgba(255,255,255,.03); }
.links a:hover { border-color: rgba(108,140,255,.5); background: rgba(108,140,255,.1); }
.note { margin-top: 26px; font-size: 12px; line-height: 1.8; color: #66708c; }
"""


def api_preview_page(pid: str, title: str, api: list[dict]) -> str:
    rows = "\n".join(
        f"<tr><td><code>{_esc(item['method'])}</code></td>"
        f"<td><code>{_esc(item['path'])}</code></td>"
        f"<td>{_esc(item.get('description') or '')}</td></tr>"
        for item in api
    )
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <base href="/apps/{_esc(pid)}/" />
    <title>{_esc(title)} · API</title>
    <style>{API_PREVIEW_CSS}</style>
  </head>
  <body>
    <main class="wrap">
      <p class="eyebrow">FASTAPI · SQLITE · PYTHON 3.11</p>
      <h1>{_esc(title)}</h1>
      <p class="lead">这是一个纯后端项目。FastAPI 服务已经按项目隔离启动，数据保存在
        <code>backend/data/app.db</code>，与 Atoms Demo 的数据库互不影响。</p>
      <span class="status"><span class="dot" id="dot"></span><span id="status">正在检查服务…</span></span>

      <table>
        <thead><tr><th>方法</th><th>路径</th><th>说明</th></tr></thead>
        <tbody>{rows or "<tr><td colspan='3'>该服务由生成代码自行定义路由。</td></tr>"}</tbody>
      </table>

      <div class="links">
        <a href="docs">Swagger 文档</a>
        <a href="redoc">ReDoc</a>
        <a href="api/health">健康检查</a>
      </div>
      <p class="note">提示：在 Atoms 工作台继续对话即可修改接口或增加数据表；刷新页面不会丢数据。</p>
    </main>
    <script>
      const dot = document.getElementById("dot");
      const label = document.getElementById("status");
      fetch("api/health").then(function (res) {{
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      }}).then(function () {{
        dot.classList.add("ok"); label.textContent = "服务运行中";
      }}).catch(function () {{
        dot.classList.add("bad"); label.textContent = "服务暂未响应，请稍后刷新";
      }});
    </script>
  </body>
</html>
"""
