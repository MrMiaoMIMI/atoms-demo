"""Multi-role orchestration on top of a single LLM.

Planner -> scaffold -> Coder (per app file) -> Reviewer -> Deployer.

The Planner decides whether the request needs a frontend, a backend, or both.
Scaffolding (Vite config, package.json, SQLite helpers, preview shell) is
generated deterministically; the LLM only writes app-specific React and
FastAPI source. Full-stack projects run as a dedicated uvicorn process with
their own SQLite file under ``apps/{pid}/backend/data/app.db``.
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import uuid
from collections import Counter, deque
from collections.abc import Awaitable, Callable
from typing import Any

import agents as agent_roster
import config
import db
import frontend_builder
import runtime
import scaffold
from llm import MockLLM, get_llm
from mocks import templates
from tool_loop import LoopResult, ToolLoopError, run_tool_loop
from tools import Toolbox, ToolContext, check_health as check_runtime_health, record_change
from workspace import Workspace

Emit = Callable[[str, dict], Awaitable[Any]]

PLANNER_SYSTEM = """你是 "Planner" Agent，负责把用户的自然语言需求拆解为一个可运行的 Web 项目。
只输出 JSON，不要 markdown 代码围栏，不要任何解释。
JSON 结构：
{
  "summary": "一句话说明要做什么",
  "title": "2-20 字的应用名",
  "mode": "frontend | fullstack | backend",
  "reason": "为什么选择这个形态",
  "entities": [
    {"table": "items", "fields": [
      {"name": "id", "type": "INTEGER", "primary_key": true, "autoincrement": true},
      {"name": "title", "type": "TEXT", "not_null": true},
      {"name": "created_at", "type": "TEXT", "not_null": true}
    ]}
  ],
  "api": [{"method": "GET", "path": "/api/items", "description": "获取列表"}],
  "files": [{"path": "frontend/src/App.tsx", "purpose": "该文件的职责"}]
}

形态判断：
1. 纯展示/营销/落地页/个人主页 → frontend，不需要 entities 和 api。
2. 需要保存数据、增删改查、账号、订单、留言、评论、记账等刷新后仍在的数据 → fullstack。
3. 用户明确只要后端/API，不需要页面 → backend。
4. 模糊时优先 frontend；但只要需求涉及“保存/持久化/数据库/后端”，就必须 fullstack。

文件规则：
1. 只允许这些路径：
   - 前端：frontend/src/**，扩展名 .tsx/.ts/.css
   - 后端：backend/**，扩展名 .py
2. 不要规划 package.json、vite.config.ts、tsconfig.json、index.html、src/main.tsx、
   backend/db.py、backend/schema.sql、backend/requirements.txt、README.md，这些由系统生成。
3. frontend 形态必须规划 frontend/src/App.tsx 与 frontend/src/styles.css。
   fullstack 形态还必须规划 backend/main.py。
4. 前端只能 import react / react-dom 和本轮规划中的本地文件；禁止第三方库。
5. 前端所有后端请求使用相对路径 "api/..."（不要以 / 开头），例如 fetch("api/items")。
6. 后端只能使用 fastapi、pydantic、aiosqlite、uvicorn 与 Python 标准库。
7. 用户是在续改已有项目时，列出所有需要新增或修改的文件；不要重复列出不需要改的文件。
8. 如果已有项目是 fullstack，除非用户明确要求去掉后端，否则继续保持 fullstack。
"""

BOB_TOOL_SYSTEM = (
    "你是 Bob，架构师。你可以使用只读工具查看现有项目，但绝不能修改文件。\n"
    "在给出方案前，先用 list_files / read_file / grep 确认现有文件、数据模型和 API；"
    "不要凭文件名猜测。\n"
    "最终答复必须只输出一个 JSON 对象，不要 markdown 围栏、不要解释、"
    "不要在 JSON 前后写文字。\n\n" + PLANNER_SYSTEM
)

FRONTEND_SYSTEM = """你是 "Coder" Agent，负责写出一个 React + TypeScript 文件的完整内容。
只输出文件内容本身：不要 markdown 代码围栏，不要任何解释、标题或前后缀。

要求：
- React 18 函数组件 + hooks，TypeScript，单文件可独立被 Vite/esbuild 编译。
- 只 import react / react-dom 以及本轮文件清单中的本地文件；禁止任何第三方库。
- 不要 import CSS（样式统一写在 frontend/src/styles.css，由 main.tsx 引入）。
- 所有 className 使用字面量字符串（条件样式用 "a" + (cond ? " b" : "")），不要在运行时拼出未定义的类名。
- 全栈项目必须调用后端 API：所有请求使用相对路径 "api/..."，例如 fetch("api/items")，禁止以 / 开头。
- fetch 后必须检查 res.ok；要有加载中、空数据、错误三种状态。
- 禁止 localStorage / sessionStorage；持久化只能走后端 SQLite。
- 视觉现代、精致、响应式，文案使用真实内容，不要 Lorem ipsum 占位。
- 单个文件尽量控制在 8,000 字符以内；结构完整闭合，绝不能写到一半停止。
- 如果提供了当前文件内容，在保留原有可用功能的基础上修改。
"""

STYLES_SYSTEM = """你是 "Coder" Agent，负责写出前端样式文件 frontend/src/styles.css 的完整内容。
只输出 CSS 本身：不要 markdown 代码围栏，不要任何解释。

要求：
- 覆盖 React 代码中出现的所有 className；布局容器必须有明确的 display / grid / flex 规则。
- 现代、精致、一致的视觉语言；使用 React 代码里的真实类名，不要臆造。
- 必须包含至少一个 @media (max-width: 768px) 媒体查询，保证窄屏可用。
- 禁止 @import 外部字体之外的远程依赖；不要依赖构建工具。
- 单个文件尽量控制在 8,000 字符以内；结构完整闭合。
- 如果提供了当前文件内容，在保留原有设计的基础上修改。
"""

BACKEND_SYSTEM = """你是 "Coder" Agent，负责写出一个 FastAPI 后端文件的完整内容。
只输出文件内容本身：不要 markdown 代码围栏，不要任何解释、标题或前后缀。

硬性约束：
- Python 3.11 + FastAPI + aiosqlite；只允许 fastapi、pydantic、aiosqlite 和标准库。
- 必须从 db 模块导入数据库能力：`from db import connection, init_db`。
- app 必须使用 lifespan，在启动时 `await init_db()`；不要自己创建 sqlite 连接或数据库文件。
- app = FastAPI(title=..., root_path=os.getenv("APP_ROOT_PATH", ""), lifespan=lifespan)
- 必须添加 CORSMiddleware，allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]。
- 必须实现 GET /api/health，返回 {"ok": true} 之类的 JSON。
- 严格按给定的 API 合约与 SQL 表结构实现路由；SQL 必须参数绑定。
- 数据库路径由 db.py 固定在 backend/data/app.db，禁止引用其他数据库。
- 不要启动 uvicorn、不要写 __main__ 监听端口。
- 单个文件尽量控制在 8,000 字符以内；语法完整，绝不能写到一半停止。
- 如果提供了当前文件内容或启动报错，在保留原有可用功能的基础上修复。
"""

SPLIT_SYSTEM = """你是 "Coder" Agent，负责把一个过大的前端文件拆分为多个可编译的文件。
只输出 JSON，不要 markdown 代码围栏，不要任何解释。

JSON 结构：
{"files":[{"path":"frontend/src/App.tsx","content":"完整文件内容"},{"path":"frontend/src/components/Foo.tsx","content":"完整文件内容"}]}

规则：
1. 必须包含原文件路径；如果原文件是 App.tsx，必须保留 `export default`。
2. 新文件只能放在 frontend/src/components/ 或 frontend/src/hooks/，扩展名 .tsx/.ts/.jsx/.js。
3. 保留现有功能、文案、className 与样式依赖；拆出的组件通过 import 使用。
4. 每个文件尽量控制在 6,000 字符以内；结构完整闭合，不要省略实现。
5. 不要输出 package.json、main.tsx、styles.css 或任何解释。
"""

RETRY_HINT = (
    "\n\n重要：上一次输出被截断或不完整。请重新输出完整文件，"
    "确保所有标签与括号闭合，不要省略任何部分，也不要加解释。"
)
PLANNER_RETRY_HINT = (
    "\n\n重要：上一次输出不是合法 JSON 或缺少 mode / files。"
    "请只输出一个完整 JSON 对象，不要 markdown 代码围栏或解释。"
)
ANSWER_RETRY_HINT = (
    "\n\n重要：上一次回答为空或不完整。请重新完整回答，不要重复已输出内容。"
)
SPLIT_RETRY_HINT = (
    "\n\n重要：上一次输出不是合法 JSON，或没有同时包含原文件与新组件。"
    '请只输出 {"files":[{"path":"...","content":"..."}]}，并保留原文件路径。'
)


class GenerationError(RuntimeError):
    """A generation round failed; the project keeps its last good version."""

FENCE = re.compile(r"^```[a-zA-Z0-9]*\s*\n?")
REMOVE_BACKEND = ("不要后端", "去掉后端", "纯前端", "只做前端", "只要前端")
REMOVE_FRONTEND = ("只做后端", "只要后端", "纯后端", "只写后端", "不要前端", "没有前端", "只提供api")
# Models occasionally concatenate several planned files into one reply, each
# introduced by a comment such as ``// frontend/src/App.tsx`` or
# ``/* frontend/src/styles.css */``. Appending CSS to a .tsx file breaks esbuild.
FILE_MARKER = re.compile(
    r"^[ \t]*(?://|/\*)[ \t]*((?:frontend|backend)/[\w./-]+\.(?:tsx|ts|jsx|js|css|py))"
    r"[ \t]*(?:\*/)?[ \t]*$",
    re.M,
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _clean_file_content(text: str) -> str:
    content = text.strip()
    content = FENCE.sub("", content)
    content = re.sub(r"\n?```\s*$", "", content)
    return content.strip()


def _extract_requested_file(text: str, path: str) -> str:
    """Keep only the block that belongs to ``path`` when the model emits more
    than one file in a single reply.

    The requested block starts at its own file marker; everything from the next
    foreign file marker onward is dropped. Without markers the text is returned
    unchanged, so this is safe for models that answer with bare file content.
    """
    cleaned = _clean_file_content(text)
    markers = list(FILE_MARKER.finditer(cleaned))
    own = [m for m in markers if m.group(1) == path]
    if not own:
        return cleaned
    start = own[0].end()
    end = len(cleaned)
    for marker in markers:
        if marker.start() >= start and marker.group(1) != path:
            end = marker.start()
            break
    body = cleaned[start:end].strip()
    return body or cleaned


def _existing_mode(existing: dict[str, str]) -> str | None:
    has_backend = any(path.startswith("backend/") for path in existing)
    has_frontend = any(path.startswith("frontend/") for path in existing)
    if has_backend and has_frontend:
        return "fullstack"
    if has_backend:
        return "backend"
    if has_frontend:
        return "frontend"
    return None


def _existing_title(existing: dict[str, str]) -> str | None:
    html = existing.get("frontend/index.html", "")
    match = re.search(r"<title>(.*?)</title>", html, re.S)
    if match and match.group(1).strip():
        return match.group(1).strip()[:60]
    return None


def _resolve_mode(planned: str, message: str, existing_mode: str | None) -> str:
    p = message.lower()
    planned = planned if planned in scaffold.MODES else "frontend"
    if existing_mode == "fullstack":
        if any(key in p for key in REMOVE_BACKEND):
            return "frontend"
        if any(key in p for key in REMOVE_FRONTEND):
            return "backend"
        return "fullstack"
    if existing_mode == "frontend" and planned == "backend":
        if any(key in p for key in REMOVE_BACKEND):
            return "frontend"
        if any(key in p for key in REMOVE_FRONTEND):
            return "backend"
        return "fullstack"
    if existing_mode == "backend" and planned == "frontend":
        if any(key in p for key in REMOVE_FRONTEND):
            return "backend"
        if any(key in p for key in REMOVE_BACKEND):
            return "frontend"
        return "fullstack"
    return planned


def _safe_ident(value: Any) -> str | None:
    text = str(value or "").strip()
    return text if scaffold.IDENT.match(text) else None


def _default_entity() -> dict:
    return {
        "table": "items",
        "fields": [
            {"name": "id", "type": "INTEGER", "primary_key": True, "autoincrement": True},
            {"name": "name", "type": "TEXT", "not_null": True},
        ],
    }


def _normalize_entities(raw: Any) -> list[dict]:
    entities: list[dict] = []
    if not isinstance(raw, list):
        return entities
    for item in raw[:4]:
        if not isinstance(item, dict):
            continue
        table = _safe_ident(item.get("table"))
        if not table:
            continue
        fields: list[dict] = []
        raw_fields = item.get("fields") if isinstance(item.get("fields"), list) else []
        for field in raw_fields[:16]:
            if not isinstance(field, dict):
                continue
            name = _safe_ident(field.get("name"))
            if not name:
                continue
            ftype = str(field.get("type") or "TEXT").upper()
            if ftype not in scaffold.FIELD_TYPES:
                ftype = "TEXT"
            normalized = {"name": name, "type": ftype}
            if field.get("primary_key"):
                normalized["primary_key"] = True
                if field.get("autoincrement") and ftype == "INTEGER":
                    normalized["autoincrement"] = True
            elif field.get("not_null"):
                normalized["not_null"] = True
            if field.get("default") is not None:
                normalized["default"] = field["default"]
            fields.append(normalized)
        if not fields:
            continue
        if not any(f.get("primary_key") for f in fields):
            fields.insert(
                0,
                {"name": "id", "type": "INTEGER", "primary_key": True, "autoincrement": True},
            )
        entity = {"table": table, "fields": fields}
        if entity not in entities:
            entities.append(entity)
    return entities


def _normalize_api(raw: Any, entities: list[dict], mode: str) -> list[dict]:
    if mode == "frontend":
        return []
    api: list[dict] = []
    seen: set[tuple[str, str]] = set()
    if isinstance(raw, list):
        for item in raw[:24]:
            if not isinstance(item, dict):
                continue
            method = str(item.get("method") or "GET").upper()
            path = str(item.get("path") or "").strip()
            if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            if not path.startswith("/api/"):
                continue
            key = (method, path)
            if key in seen:
                continue
            seen.add(key)
            api.append(
                {
                    "method": method,
                    "path": path,
                    "description": str(item.get("description") or "").strip()[:100],
                }
            )
    if not any(item["path"] == "/api/health" for item in api):
        api.append({"method": "GET", "path": "/api/health", "description": "健康检查"})
    if len(api) == 1 and entities:
        table = entities[0]["table"]
        api[0:0] = [
            {"method": "GET", "path": f"/api/{table}", "description": f"获取 {table} 列表"},
            {"method": "POST", "path": f"/api/{table}", "description": f"新增 {table} 记录"},
            {"method": "PUT", "path": f"/api/{table}/{{id}}", "description": f"更新 {table} 记录"},
            {"method": "DELETE", "path": f"/api/{table}/{{id}}", "description": f"删除 {table} 记录"},
        ]
    return api


def _required_files(mode: str) -> list[dict]:
    files: list[dict] = []
    if mode in ("frontend", "fullstack"):
        files += [
            {"path": "frontend/src/App.tsx", "purpose": "根组件与页面交互"},
            {"path": "frontend/src/styles.css", "purpose": "视觉样式与响应式布局"},
        ]
    if mode in ("backend", "fullstack"):
        files.append({"path": "backend/main.py", "purpose": "FastAPI 路由与 SQLite 读写"})
    return files


def _normalize_files(raw: Any, mode: str) -> list[dict]:
    files: list[dict] = []
    seen: set[str] = set()
    blocked = {
        "backend/db.py",
        "backend/schema.sql",
        "backend/requirements.txt",
        "frontend/src/main.tsx",
        "frontend/src/vite-env.d.ts",
    }
    if isinstance(raw, list):
        for item in raw[:16]:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "").strip().replace("\\", "/")
            if not path or path in blocked or not scaffold.safe_project_path(path):
                continue
            ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
            frontend_ok = path.startswith("frontend/src/") and ext in {".tsx", ".ts", ".jsx", ".js", ".css"}
            backend_ok = path.startswith("backend/") and ext == ".py"
            if not (frontend_ok or backend_ok):
                continue
            if mode == "frontend" and not frontend_ok:
                continue
            if mode == "backend" and not backend_ok:
                continue
            if path in seen:
                continue
            seen.add(path)
            files.append(
                {
                    "path": path,
                    "purpose": str(item.get("purpose") or "项目文件").strip()[:100],
                }
            )
    for required in _required_files(mode):
        if required["path"] not in seen:
            files.append(required)
            seen.add(required["path"])
    return files


def _parse_plan_json(text: str) -> dict | None:
    """Parse the first JSON object in a model reply, tolerating prose around it."""
    start = text.find("{")
    if start < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(text[start:])
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _planner_text_valid(text: str) -> bool:
    """Reject prose / broken JSON so the planner call is retried."""
    data = _parse_plan_json(text)
    return bool(
        data
        and str(data.get("mode") or "").strip().lower() in scaffold.MODES
    )


def _plan_from_text(
    text: str,
    message: str,
    existing: dict[str, str],
    existing_mode: str | None,
    project_name: str,
) -> dict:
    data: dict = _parse_plan_json(text) or {}

    planned_mode = str(data.get("mode") or "").strip().lower()
    if planned_mode not in scaffold.MODES:
        planned_mode = templates.pick_mode(message, existing_mode)
    mode = _resolve_mode(planned_mode, message, existing_mode)

    entities = _normalize_entities(data.get("entities"))
    if mode in ("backend", "fullstack") and not entities:
        entities = [_default_entity()]
    if mode == "frontend":
        entities = []

    api = _normalize_api(data.get("api"), entities, mode)
    files = _normalize_files(data.get("files"), mode)

    title = _existing_title(existing)
    if not title:
        candidate = str(data.get("title") or "").strip()
        title = candidate[:24] if 2 <= len(candidate) <= 24 else ""
    if not title:
        title = (project_name or "")[:24].strip() or templates.extract_title(message, mode)

    summary = str(data.get("summary") or "").strip() or f"生成一个{mode}形态的 Web 项目。"
    return {
        "summary": summary[:200],
        "title": title,
        "mode": mode,
        "entities": entities,
        "api": api,
        "files": files,
    }


def _scaffold_files(
    plan: dict, existing: dict[str, str]
) -> dict[str, str]:
    mode = plan["mode"]
    files: dict[str, str] = {
        ".gitignore": scaffold.gitignore(),
        "README.md": scaffold.readme(plan["title"], mode, plan["api"]),
    }
    if mode in ("frontend", "fullstack"):
        for path, content in scaffold.frontend_files(plan["title"]).items():
            if path not in existing:
                files[path] = content
    if mode in ("backend", "fullstack"):
        for path, content in scaffold.backend_common_files().items():
            if path not in existing:
                files[path] = content
        files["backend/schema.sql"] = scaffold.schema_sql(plan["entities"])
    return files


def _prune(files: dict[str, str], mode: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for path, content in files.items():
        if path.startswith("backend/") and mode == "frontend":
            continue
        if path.startswith("frontend/") and mode == "backend":
            continue
        out[path] = content
    return out


# ---------------------------------------------------------------------------
# Validation / review
# ---------------------------------------------------------------------------

def _valid_content(filename: str, content: str) -> bool:
    text = content.strip()
    if len(text) < 24:
        return False
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("html", "htm"):
        lower = text.lower()
        return "<html" in lower and "</body>" in lower and "</html>" in lower
    if ext == "css":
        return text.count("{") == text.count("}")
    if ext in ("tsx", "jsx", "ts", "js"):
        # esbuild is the real validator for TS/JSX; only enforce the App contract.
        return not filename.endswith("App.tsx") or "export default" in text
    if ext == "py":
        try:
            compile(text, filename, "exec")
        except SyntaxError:
            return False
    return True


def _review(files: dict[str, str], mode: str) -> list[str]:
    issues: list[str] = []
    if mode in ("frontend", "fullstack"):
        app = files.get("frontend/src/App.tsx", "")
        css = files.get("frontend/src/styles.css", "")
        frontend_source = "\n".join(
            content
            for name, content in files.items()
            if name.startswith("frontend/src/")
        )
        if not app:
            issues.append("frontend/src/App.tsx 缺失")
        elif "export default" not in app:
            issues.append("App.tsx 缺少默认导出")
        if not css:
            issues.append("frontend/src/styles.css 缺失")
        else:
            if css.count("{") != css.count("}"):
                issues.append("styles.css 括号不完整")
            if "@media" not in css:
                issues.append("styles.css 缺少移动端媒体查询")
            used: set[str] = set()
            for value in re.findall(r'className\s*=\s*"([^"]+)"', app):
                used.update(token for token in value.split() if token)
            for value in re.findall(r"className\s*=\s*'([^']+)'", app):
                used.update(token for token in value.split() if token)
            defined = set(re.findall(r"\.([A-Za-z_][\w-]*)", css))
            missing = sorted(used - defined)
            if missing:
                issues.append("样式缺口：" + "、".join("." + name for name in missing[:6]))
        if (
            "localstorage" in frontend_source.lower()
            or "sessionstorage" in frontend_source.lower()
        ):
            issues.append("前端代码使用了 localStorage/sessionStorage，沙箱预览不可用")
        if mode == "fullstack":
            if re.search(r"""["'`]/api/""", frontend_source):
                issues.append("前端 API 路径不能以 / 开头（预览挂在子路径下）")
            elif "api/" not in frontend_source:
                issues.append("前端尚未调用后端 API")
    if mode in ("backend", "fullstack"):
        main = files.get("backend/main.py", "")
        if not main:
            issues.append("backend/main.py 缺失")
        else:
            try:
                compile(main, "backend/main.py", "exec")
            except SyntaxError as exc:
                issues.append(f"backend/main.py 语法错误：line {exc.lineno}")
            if "FastAPI(" not in main:
                issues.append("main.py 未创建 FastAPI 应用")
            if "/api/health" not in main:
                issues.append("main.py 缺少 /api/health")
            if "from db import" not in main:
                issues.append("main.py 未使用项目内的 db.py")
            if "root_path" not in main:
                issues.append("backend/main.py 缺少 root_path=os.getenv('APP_ROOT_PATH')")
            lower = main.lower()
            if any(
                token in lower
                for token in ("psycopg", "postgres", "mysql", "sqlalchemy", "redis", "pymongo")
            ):
                issues.append("backend/main.py 只能使用 SQLite，禁止其他数据库依赖")
    return issues


def _needs_style_repair(issues: list[str]) -> bool:
    return any(
        issue.startswith("样式缺口") or issue.startswith("styles.css 缺少") for issue in issues
    )


def _needs_app_repair(issues: list[str]) -> bool:
    return any(
        "前端 API 路径" in issue
        or "前端尚未调用" in issue
        or "localStorage" in issue
        for issue in issues
    )


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def _contract(plan: dict) -> str:
    if plan["mode"] == "frontend":
        return "本项目没有后端。"
    schema = scaffold.schema_sql(plan["entities"])
    api_lines = "\n".join(
        f"- {item['method']} {item['path']} — {item.get('description') or ''}"
        for item in plan["api"]
    )
    return f"SQLite 表结构（由系统自动建表）：\n{schema}\nAPI 合约：\n{api_lines}"


def _coder_user(
    path: str,
    purpose: str,
    plan: dict,
    message: str,
    existing: dict[str, str],
) -> str:
    blocks = [
        f"用户需求：\n{message}",
        f"项目概述：{plan['summary']}",
        f"项目形态：{plan['mode']}（title: {plan['title']}）",
        f"需要生成的文件：{path}（{purpose}）",
        f"本轮文件清单：{', '.join(item['path'] for item in plan['files'])}",
        f"注意：本轮只输出 {path} 这一个文件的完整内容；清单中的其他文件会在后续单独生成，"
        "不要把它们拼进同一个回复里。",
        _contract(plan),
    ]
    if path in existing:
        blocks.append(
            f"当前 {path} 的内容（在此基础上修改）：\n<current>\n{existing[path][:8000]}\n</current>"
        )
    siblings = [(name, content) for name, content in existing.items() if name != path][:2]
    if siblings:
        joined = "\n\n".join(f"--- {name} ---\n{content[:2400]}" for name, content in siblings)
        blocks.append(f"其他已有文件（供保持命名/风格一致参考）：\n{joined}")
    if path == "frontend/src/App.tsx":
        blocks.append("这是根组件：必须使用 `export default function App()`。")
    if plan["mode"] == "fullstack" and path.startswith("frontend/"):
        blocks.append(
            "这是全栈项目：必须通过相对路径 api/... 调用后端，"
            "数据必须来自后端而不是写死在组件里。"
        )
    if path.endswith(".py"):
        blocks.append(
            "后端文件必须：from db import connection, init_db；lifespan 中 await init_db()；"
            "FastAPI(root_path=os.getenv('APP_ROOT_PATH',''))；CORS 全开；实现 /api/health。"
        )
    return "\n\n".join(blocks)


def _system_for(path: str) -> str:
    if path.endswith(".css"):
        return STYLES_SYSTEM
    if path.endswith(".py"):
        return BACKEND_SYSTEM
    return FRONTEND_SYSTEM


def _repair_styles_user(files: dict[str, str], issues: list[str]) -> str:
    return "\n\n".join(
        [
            "Reviewer 发现以下样式问题，请修复 frontend/src/styles.css：\n- "
            + "\n- ".join(issues),
            "frontend/src/App.tsx（供参考）：\n" + files.get("frontend/src/App.tsx", "")[:16000],
            "当前 frontend/src/styles.css：\n" + files.get("frontend/src/styles.css", "")[:16000],
            "要求：保留现有设计语言与全部已有样式；补齐缺失 class 的样式；"
            "文件末尾添加 @media (max-width: 768px) 移动端规则；只输出 styles.css 完整内容。",
        ]
    )


def _offending_frontend_file(files: dict[str, str], issues: list[str]) -> str:
    if any("localStorage" in issue for issue in issues):
        for name, content in files.items():
            if name.startswith("frontend/src/") and (
                "localstorage" in content.lower() or "sessionstorage" in content.lower()
            ):
                return name
    if any("API 路径" in issue for issue in issues):
        for name, content in files.items():
            if name.startswith("frontend/src/") and re.search(r"""["'`]/api/""", content):
                return name
    return "frontend/src/App.tsx"


def _repair_build_user(
    message: str, plan: dict, target: str, error: str, files: dict[str, str]
) -> str:
    return "\n\n".join(
        [
            f"用户需求：\n{message}",
            f"项目概述：{plan['summary']}",
            _contract(plan),
            f"前端构建失败，错误如下：\n{error[:3000]}",
            f"当前 {target} 的完整内容（必须在此基础上修复，不要重写业务内容）：\n"
            f"<current>\n{files.get(target, '')[:16000]}\n</current>",
            f"要求：只修复导致构建失败的语法/结构问题；保留现有页面主题、文案、布局与交互；"
            f"只输出 {target} 的完整内容，不要输出其他文件、代码围栏或解释。",
        ]
    )


def _repair_app_user(
    files: dict[str, str], issues: list[str], plan: dict, target: str
) -> str:
    return "\n\n".join(
        [
            f"Reviewer 发现以下前后端联调问题，请修复 {target}：\n- "
            + "\n- ".join(issues),
            _contract(plan),
            f"当前 {target}：\n" + files.get(target, "")[:16000],
            "要求：所有后端请求使用相对路径 api/...（不要以 / 开头）；"
            "删除 localStorage/sessionStorage（沙箱预览不可用，持久化只能走后端）；"
            + (
                "根组件必须使用 `export default function App()`；"
                if target == "frontend/src/App.tsx"
                else ""
            )
            + f"保留现有 UI 与交互；只输出 {target} 完整内容。",
        ]
    )


# ---------------------------------------------------------------------------
# LLM call with retry + degradation
# ---------------------------------------------------------------------------

def _repair_backend_user(files: dict[str, str], issues: list[str], plan: dict) -> str:
    return "\n\n".join(
        [
            "Reviewer 发现以下后端问题，请修复 backend/main.py：\n- "
            + "\n- ".join(issues),
            _contract(plan),
            "当前 backend/main.py：\n" + files.get("backend/main.py", "")[:16000],
            "要求：保留现有 API 合约；必须 from db import connection, init_db；"
            "lifespan 中 await init_db()；实现 /api/health；只输出 main.py 完整内容。",
        ]
    )


async def _llm_text(
    llm,
    *,
    role: str,
    system: str,
    user: str,
    meta: dict,
    emit: Emit,
    emit_tokens: bool,
    validator: Callable[[str], bool] | None = None,
    retry_hint: str = RETRY_HINT,
) -> str:
    """One LLM call with bounded retries and no silent Mock fallback.

    MockLLM is used only when the deployment has no API key, so it is never
    retried. A real model gets ``LLM_MAX_RETRIES`` extra attempts; when every
    attempt fails the round raises ``GenerationError`` and the caller keeps
    the project's last published version.
    """

    async def run(current, prompt_user: str) -> str:
        parts: list[str] = []
        async for chunk in current.stream(role=role, system=system, user=prompt_user, meta=meta):
            parts.append(chunk)
            if emit_tokens:
                await emit("token", {"filename": meta.get("filename"), "delta": chunk})
        text = "".join(parts)
        if not text.strip():
            raise RuntimeError("LLM returned empty content")
        return text

    attempts = 1 if isinstance(llm, MockLLM) else config.LLM_MAX_RETRIES + 1
    last_error: Exception | None = None
    for attempt in range(attempts):
        prompt_user = user if attempt == 0 else user + retry_hint
        try:
            text = await run(llm, prompt_user)
            candidate = _clean_file_content(text) if validator else text
            if validator is None or validator(candidate):
                return text
            last_error = RuntimeError("LLM output incomplete")
        except Exception as exc:
            last_error = exc

        if emit_tokens:
            await emit("token_reset", {"filename": meta.get("filename")})
        if attempt + 1 >= attempts:
            break

        delay = min(
            config.LLM_RETRY_BACKOFF * (2 ** attempt),
            config.LLM_RETRY_BACKOFF_MAX,
        )
        assert last_error is not None
        await emit(
            "execution",
            {
                "agent": "Coder" if role == "coder" else "Orchestrator",
                "step": f"重试 {meta.get('filename') or role}",
                "status": "warning",
                "log": (
                    f"第 {attempt + 1}/{attempts - 1} 次重试："
                    f"{type(last_error).__name__}: {str(last_error)[:140]}"
                ),
            },
        )
        if delay > 0:
            await asyncio.sleep(delay)

    assert last_error is not None
    raise GenerationError(
        f"LLM 调用失败（已尝试 {attempts} 次）："
        f"{type(last_error).__name__}: {str(last_error)[:200]}"
    )


# ---------------------------------------------------------------------------
# Role orchestration
# ---------------------------------------------------------------------------

MAX_TOTAL_RUNS = 5
MAX_RUNS_PER_AGENT = 2

MODE_LABEL = {
    "frontend": "纯前端",
    "fullstack": "前后端一体",
    "backend": "纯后端 API",
}


class RoleEmitter:
    """Adds agent + run_id to every event emitted by one agent run."""

    def __init__(
        self,
        pid: str,
        run_id: str,
        agent: str,
        emit: Emit,
        version: int,
        index: int = 0,
    ) -> None:
        self.pid = pid
        self.run_id = run_id
        self.agent = agent
        self.base_emit = emit
        self.version = version
        self.index = index

    async def __call__(self, event: str, payload: dict) -> Any:
        data = dict(payload)
        if event in {"execution", "message", "agent_start", "agent_end"}:
            data["agent"] = self.agent
            data["run_id"] = self.run_id
            data["run_index"] = self.index
        elif event in {"artifact", "file_change", "file_start", "token", "token_reset"}:
            data.setdefault("run_id", self.run_id)
            data.setdefault("agent", self.agent)
        return await self.base_emit(event, data)

    def toolbox(self) -> Toolbox:
        spec = agent_roster.AGENTS[self.agent]
        return Toolbox(
            ToolContext(
                pid=self.pid,
                run_id=self.run_id,
                agent=self.agent,
                emit=self.base_emit,
                version=self.version,
            ),
            spec.tools,
        )


def _new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def _project_context(
    project_name: str,
    existing: dict[str, str],
    mode: str | None,
    version: int,
) -> str:
    files = ", ".join(sorted(existing)[:30]) or "（空）"
    return (
        f"项目：{project_name}\n"
        f"当前形态：{mode or '空项目'}\n"
        f"当前版本：v{version}\n"
        f"文件（{len(existing)}）：{files}"
    )


def _fallback_route(message: str, existing_mode: str | None) -> str:
    """Deterministic fallback when Mike omits the trailing @mention."""
    text = (message or "").lower()
    backend_need = any(
        token in text
        for token in (
            "登录",
            "支付",
            "订单",
            "数据库",
            "数据保存",
            "持久化",
            "存储",
            "sqlite",
            "多表",
            "权限",
            "购物车",
            "后台",
            "库存",
            "api",
            "后端",
            "全栈",
            "webhook",
            "用户",
            "fullstack",
        )
    )
    frontend_only = any(
        token in text
        for token in (
            "颜色",
            "配色",
            "样式",
            "字体",
            "文案",
            "按钮",
            "布局",
            "间距",
            "圆角",
            "图片",
            "动效",
            "首页",
            "落地页",
        )
    )
    if backend_need:
        return "bob"
    if existing_mode in ("fullstack", "backend") and not frontend_only:
        return "bob"
    if len(message or "") > 240:
        return "bob"
    return "alex"


async def _run_mike(
    pid: str,
    message: str,
    emit: RoleEmitter,
    *,
    project_name: str,
    existing: dict[str, str],
    existing_mode: str | None,
    current_version: int,
) -> str:
    ex = await emit(
        "execution",
        {"step": "理解需求", "status": "running", "log": "分析目标、约束与现有项目…"},
    )
    context = _project_context(project_name, existing, existing_mode, current_version)
    user = (
        f"用户请求：\n{message}\n\n"
        f"项目上下文：\n{context}\n\n"
        "请按角色要求输出；最后一行给出 @Bob 或 @Alex。"
    )
    try:
        text = await _llm_text(
            get_llm(),
            role="mike",
            system=agent_roster.MIKE_SYSTEM,
            user=user,
            meta={
                "prompt": message,
                "project_name": project_name,
                "mode": existing_mode,
                "files": sorted(existing),
                "version": current_version,
            },
            emit=emit,
            emit_tokens=False,
            retry_hint=ANSWER_RETRY_HINT,
        )
    except Exception as exc:
        await emit(
            "execution",
            {
                "id": ex,
                "step": "理解需求",
                "status": "error",
                "log": f"{type(exc).__name__}: {str(exc)[:160]}",
            },
        )
        raise
    text = text.strip()
    if not text:
        target = _fallback_route(message, existing_mode)
        text = f"需求理解：{message[:80]}\n\n复杂度：待评估\n\n@{agent_roster.AGENT_NAMES[target]}"

    tail = agent_roster.parse_mentions(text, tail_only=True)
    if not tail:
        target = _fallback_route(message, existing_mode)
        text = text.rstrip() + f"\n\n@{agent_roster.AGENT_NAMES[target]}"
        tail = [target]
    await emit(
        "execution",
        {
            "id": ex,
            "step": "理解需求",
            "status": "success",
            "log": f"{len(message)} 字符需求 · {len(existing)} 个已有文件",
        },
    )
    ex2 = await emit(
        "execution",
        {
            "step": "拆解与分配",
            "status": "running",
            "log": "判断复杂度并选择下一位…",
        },
    )
    await emit(
        "execution",
        {
            "id": ex2,
            "step": "拆解与分配",
            "status": "success",
            "log": "交接给 " + "、".join(
                f"@{agent_roster.AGENT_NAMES[key]}" for key in tail
            ),
        },
    )
    return text


async def _call_planner(
    message: str,
    emit: RoleEmitter,
    *,
    project_name: str,
    existing: dict[str, str],
    existing_mode: str | None,
    extra_context: str = "",
) -> dict:
    planner_user = (
        f"用户需求：\n{message}\n\n"
        + (f"{extra_context}\n\n" if extra_context else "")
        + f"当前项目文件：{', '.join(existing) if existing else '（空项目）'}\n"
        + f"当前形态：{existing_mode or '（空项目）'}\n\n"
        + "输出 JSON。"
    )
    llm = get_llm()

    # Bob gets a short read-only loop only when there is an existing project to
    # inspect. New projects have nothing to read, and Mock mode uses the
    # deterministic single-shot planner.
    if config.AGENT_TOOL_LOOP and existing and not isinstance(llm, MockLLM):
        ctx = ToolContext(
            pid=emit.pid,
            run_id=emit.run_id,
            agent="bob",
            emit=emit,
            version=emit.version,
        )
        toolbox = Toolbox(ctx, agent_roster.AGENTS["bob"].tools)
        try:
            result = await run_tool_loop(
                llm=llm,
                toolbox=toolbox,
                system=BOB_TOOL_SYSTEM,
                user=(
                    planner_user
                    + "\n\n你可以先用只读工具查看项目文件，确认结构与 API；"
                    "最终只输出 JSON。"
                ),
                meta={
                    "prompt": message,
                    "existing": existing,
                    "existing_mode": existing_mode,
                    "role": "bob",
                },
                emit=emit,
                max_steps=6,
                timeout_seconds=180.0,
                max_tool_calls=24,
                max_tool_calls_per_step=4,
                no_progress_limit=6,
            )
            if _planner_text_valid(result.text):
                return _plan_from_text(
                    result.text, message, existing, existing_mode, project_name
                )
            await emit(
                "execution",
                {
                    "step": "读取项目上下文",
                    "status": "warning",
                    "log": "Bob 的工具循环没有输出合法 JSON，回退到一次性规划",
                },
            )
        except Exception as exc:  # noqa: BLE001 - planning must fall back, not fail
            await emit(
                "execution",
                {
                    "step": "读取项目上下文",
                    "status": "warning",
                    "log": f"{type(exc).__name__}: {str(exc)[:160]}",
                },
            )

    plan_text = await _llm_text(
        llm,
        role="planner",
        system=PLANNER_SYSTEM,
        user=planner_user,
        meta={
            "prompt": message,
            "existing": existing,
            "existing_mode": existing_mode,
        },
        emit=emit,
        emit_tokens=False,
        validator=_planner_text_valid,
        retry_hint=PLANNER_RETRY_HINT,
    )
    return _plan_from_text(plan_text, message, existing, existing_mode, project_name)


async def _run_bob(
    pid: str,
    message: str,
    emit: RoleEmitter,
    *,
    project_name: str,
    existing: dict[str, str],
    existing_mode: str | None,
    mike_text: str,
) -> tuple[dict, str]:
    ex = await emit(
        "execution",
        {
            "step": "分析项目形态",
            "status": "running",
            "log": "阅读现有结构，判断前端 / 全栈 / 后端…",
        },
    )
    try:
        plan = await _call_planner(
            message,
            emit,
            project_name=project_name,
            existing=existing,
            existing_mode=existing_mode,
            extra_context=(f"Mike 的计划：\n{mike_text}" if mike_text else ""),
        )
    except Exception as exc:
        await emit(
            "execution",
            {
                "id": ex,
                "step": "分析项目形态",
                "status": "error",
                "log": f"{type(exc).__name__}: {str(exc)[:160]}",
            },
        )
        raise
    await emit(
        "execution",
        {
            "id": ex,
            "step": "分析项目形态",
            "status": "success",
            "log": f"{plan['summary']} → {plan['mode']}",
        },
    )

    ex2 = await emit(
        "execution",
        {
            "step": "设计数据模型与接口",
            "status": "running",
            "log": "校验表结构、API 合约与文件清单…",
        },
    )
    toolbox = emit.toolbox()
    try:
        valid = await toolbox.call("validate_plan", plan=plan)
    except Exception:  # noqa: BLE001 - validation must never block the plan
        valid = True
    if not valid:
        raise GenerationError("架构方案校验失败：缺少必需文件或形态不合法")
    tables = "、".join(item["table"] for item in plan["entities"]) or "无"
    api_count = len(plan["api"])
    files = "、".join(item["path"] for item in plan["files"][:6])
    await emit(
        "execution",
        {
            "id": ex2,
            "step": "设计数据模型与接口",
            "status": "success",
            "log": f"{len(plan['entities'])} 张表 · {api_count} 个 API · {len(plan['files'])} 个文件",
        },
    )
    text = (
        f"技术方案：{plan['summary']}\n"
        f"形态：{MODE_LABEL.get(plan['mode'], plan['mode'])}（{plan['mode']}）\n"
        f"数据表：{tables}\n"
        f"API：{api_count} 个\n"
        f"文件：{files}\n\n"
        "@Alex"
    )
    return plan, text


async def _run_alex(
    pid: str,
    message: str,
    emit: RoleEmitter,
    *,
    project_name: str,
    existing: dict[str, str],
    existing_mode: str | None,
    version: int,
    plan: dict | None,
    bob_text: str = "",
) -> str:
    if plan is None:
        ex = await emit(
            "execution",
            {
                "step": "分析需求与形态",
                "status": "running",
                "log": "读取现有项目并规划应用结构…",
            },
        )
        try:
            plan = await _call_planner(
                message,
                emit,
                project_name=project_name,
                existing=existing,
                existing_mode=existing_mode,
            )
        except Exception as exc:
            await emit(
                "execution",
                {
                    "id": ex,
                    "step": "分析需求与形态",
                    "status": "error",
                    "log": f"{type(exc).__name__}: {str(exc)[:160]}",
                },
            )
            raise
        await emit(
            "execution",
            {
                "id": ex,
                "step": "分析需求与形态",
                "status": "success",
                "log": f"{plan['summary']} → {plan['mode']}",
            },
        )
        ex2 = await emit(
            "execution",
            {
                "step": "规划数据与接口",
                "status": "running",
                "log": "确定表结构、API 与文件范围…",
            },
        )
        await emit(
            "execution",
            {
                "id": ex2,
                "step": "规划数据与接口",
                "status": "success",
                "log": f"{len(plan['entities'])} 张表 · {len(plan['api'])} 个 API",
            },
        )
    else:
        ex = await emit(
            "execution",
            {
                "step": "接收架构方案",
                "status": "running",
                "log": "读取 Bob 的技术方案…",
            },
        )
        await emit(
            "execution",
            {
                "id": ex,
                "step": "接收架构方案",
                "status": "success",
                "log": f"{plan['mode']} · {len(plan['files'])} 个文件",
            },
        )

    progress = {"published": False}
    try:
        return await _build_project(
            pid,
            message,
            plan,
            emit,
            existing=existing,
            version=version,
            llm=get_llm(),
            progress=progress,
            bob_text=bob_text,
        )
    except Exception:
        await _rollback_round(
            pid,
            version,
            existing,
            project_name,
            emit,
            emit.toolbox(),
            progress["published"],
        )
        raise


async def _rollback_round(
    pid: str,
    version: int,
    previous: dict[str, str],
    project_name: str,
    emit: RoleEmitter,
    toolbox: Toolbox,
    had_published: bool,
) -> None:
    """Restore the last good source tree after a failed build round.

    The project's SQLite data directory is preserved by ``publish_files``. Any
    artifacts written for the failed version are discarded so a refresh shows
    the same code that is on disk.
    """
    restore_error: Exception | None = None
    try:
        if had_published:
            await toolbox.call("publish_files", files=previous)
            title = _existing_title(previous) or project_name
            # Drop any preview written by the failed round before restoring the
            # previous one; a failed rebuild must not leave the failed preview.
            shutil.rmtree(config.APPS_DIR / pid / ".preview", ignore_errors=True)
            try:
                if any(path.startswith("frontend/") for path in previous):
                    await frontend_builder.build(pid, title)
                elif any(path.startswith("backend/") for path in previous):
                    await toolbox.call(
                        "build_preview",
                        plan={"mode": "backend", "title": title, "api": []},
                    )
            except Exception as exc:  # noqa: BLE001 - preview restore is best effort
                await emit(
                    "execution",
                    {
                        "step": "恢复预览",
                        "status": "warning",
                        "log": f"{type(exc).__name__}: {str(exc)[:140]}",
                    },
                )
            if any(path.startswith("backend/") for path in previous):
                try:
                    await toolbox.call("start_runtime")
                except Exception as exc:  # noqa: BLE001 - best effort
                    await emit(
                        "execution",
                        {
                            "step": "恢复后端运行时",
                            "status": "warning",
                            "log": f"{type(exc).__name__}: {str(exc)[:140]}",
                        },
                    )
            else:
                # publish_files already stopped the runtime; a project with no
                # previous backend must not leave a runtime from the failed round.
                await runtime.runtime.stop(pid)
    except Exception as exc:  # noqa: BLE001 - rollback must not mask the cause
        restore_error = exc
    try:
        await db.delete_artifacts_version(pid, version)
    except Exception as exc:  # noqa: BLE001
        restore_error = restore_error or exc
    try:
        # Keep the attempted diffs visible in the timeline, but mark them so the
        # UI can say "本轮已回滚" and aggregate queries ignore them.
        await db.mark_file_changes_rolled_back(pid, version)
    except Exception as exc:  # noqa: BLE001
        restore_error = restore_error or exc
    if restore_error is not None:
        await emit(
            "execution",
            {
                "step": "回滚本轮改动",
                "status": "error",
                "log": f"回滚失败：{type(restore_error).__name__}: {str(restore_error)[:160]}",
            },
        )
    else:
        await emit(
            "execution",
            {
                "step": "回滚本轮改动",
                "status": "warning",
                "log": (
                    "已恢复上一个可用版本"
                    if had_published
                    else "本轮尚未发布，已清理生成的草稿文件"
                ),
            },
        )
    # Tell the UI to drop in-flight file_change state and refetch the aggregate
    # diff; the per-step rows remain queryable with rolled_back=1.
    await emit("changes_reset", {"version": version})


def _build_error_path(error: str, published: dict[str, str]) -> str | None:
    match = re.search(r"((?:src/)[^\s:]+\.(?:tsx|ts|jsx|js|css))", error)
    if not match:
        return None
    path = "frontend/" + match.group(1)
    return path if path in published else None


# ---------------------------------------------------------------------------
# Large-file guard: warn at 12K chars, split frontend TS/TSX at 20K
# ---------------------------------------------------------------------------

_SPLIT_EXTS = {".tsx", ".ts", ".jsx", ".js"}


def _split_path_allowed(path: str, original: str) -> bool:
    if path == original:
        return True
    if not path.startswith(("frontend/src/components/", "frontend/src/hooks/")):
        return False
    ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext in _SPLIT_EXTS and scaffold.safe_project_path(path)


def _split_manifest(text: str, original: str) -> dict[str, str] | None:
    """Validate a split reply; the original path must be present and valid."""
    data = _parse_plan_json(text)
    if not data:
        return None
    raw_files = data.get("files")
    if (
        not isinstance(raw_files, list)
        or not 2 <= len(raw_files) <= config.FILE_SPLIT_MAX_FILES
    ):
        return None
    files: dict[str, str] = {}
    for item in raw_files:
        if not isinstance(item, dict):
            return None
        path = str(item.get("path") or "").strip().replace("\\", "/")
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            return None
        if not _split_path_allowed(path, original):
            return None
        if not _valid_content(path, content):
            return None
        files[path] = content
    return files if len(files) >= 2 and original in files else None


def _split_user(path: str, content: str, plan: dict) -> str:
    return "\n\n".join(
        [
            f"项目概述：{plan['summary']}",
            f"项目形态：{plan['mode']}（title: {plan['title']}）",
            f"需要拆分的前端文件：{path}（{len(content):,} 字符，"
            f"超过单文件上限 {config.FILE_SIZE_SPLIT_CHARS:,} 字符）",
            f"当前完整内容：\n<current>\n{content[:60000]}\n</current>",
            f"要求：拆成 2-{config.FILE_SPLIT_MAX_FILES} 个文件，"
            "保持功能与视觉不变；只输出 JSON。",
        ]
    )


def _splittable(path: str) -> bool:
    if not path.startswith("frontend/src/"):
        return False
    ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext in _SPLIT_EXTS


async def _split_large_file(
    path: str,
    content: str,
    plan: dict,
    message: str,
    llm,
    emit: RoleEmitter,
    toolbox: Toolbox,
) -> dict[str, str] | None:
    step = await emit(
        "execution",
        {
            "step": f"拆分超大文件：{path}",
            "status": "running",
            "log": f"{len(content):,} 字符超过 {config.FILE_SIZE_SPLIT_CHARS:,}",
        },
    )
    try:
        raw = await _llm_text(
            llm,
            role="coder",
            system=SPLIT_SYSTEM,
            user=_split_user(path, content, plan),
            meta={
                "prompt": message,
                "filename": path,
                "existing": {},
                "mode": plan["mode"],
                "title": plan["title"],
            },
            emit=emit,
            emit_tokens=False,
            validator=lambda text: _split_manifest(text, path) is not None,
            retry_hint=SPLIT_RETRY_HINT,
        )
    except GenerationError as exc:
        await emit(
            "execution",
            {
                "id": step,
                "step": f"拆分超大文件：{path}",
                "status": "warning",
                "log": f"拆分失败，保留原文件：{str(exc)[:120]}",
            },
        )
        return None

    files = _split_manifest(raw, path)
    if not files:
        await emit(
            "execution",
            {
                "id": step,
                "step": f"拆分超大文件：{path}",
                "status": "warning",
                "log": "拆分结果不合法，保留原文件",
            },
        )
        return None

    for new_path, new_content in files.items():
        await toolbox.call("write_file", path=new_path, content=new_content)
    await emit(
        "execution",
        {
            "id": step,
            "step": f"拆分超大文件：{path}",
            "status": "success",
            "log": f"{len(content):,} 字符 → {len(files)} 个文件",
        },
    )
    return files


async def _guard_large_files(
    contents: dict[str, str],
    plan: dict,
    message: str,
    llm,
    emit: RoleEmitter,
    toolbox: Toolbox,
) -> None:
    """Warn on large files and split frontend TS/TSX before review/build."""
    for path, content in list(contents.items()):
        size = len(content)
        over_warn = bool(
            config.FILE_SIZE_WARN_CHARS and size > config.FILE_SIZE_WARN_CHARS
        )
        over_split = bool(
            config.FILE_SPLIT
            and config.FILE_SIZE_SPLIT_CHARS > 0
            and size > config.FILE_SIZE_SPLIT_CHARS
        )
        if not over_warn and not over_split:
            continue
        if over_split and not _splittable(path):
            await emit(
                "execution",
                {
                    "step": "文件较大",
                    "status": "warning",
                    "log": (
                        f"{path} · {size:,} 字符，超过 "
                        f"{config.FILE_SIZE_SPLIT_CHARS:,} 且该文件类型暂不自动拆分"
                    ),
                },
            )
            continue
        if over_warn:
            await emit(
                "execution",
                {
                    "step": "文件较大",
                    "status": "warning",
                    "log": (
                        f"{path} · {size:,} 字符"
                        f"（建议 ≤ {config.FILE_SIZE_WARN_CHARS:,}）"
                    ),
                },
            )
        if not over_split:
            continue
        files = await _split_large_file(path, content, plan, message, llm, emit, toolbox)
        if files:
            contents.update(files)


# ---------------------------------------------------------------------------
# Unified tool-loop build (first build + iteration)
# ---------------------------------------------------------------------------

ALEX_TOOL_SYSTEM = """你是 Alex，团队的工程师。你通过工具读写项目文件，并负责构建和运行验证。
工具使用规则：
1. 修改已有文件前先 read_file；优先 edit_file（精确匹配）。write_file 只用于新建文件，或显式 overwrite=true 的整文件重写。
2. 只操作项目内的源码路径；不要碰 .published、.preview、backend/data、node_modules、.runtime.log。
3. 新项目工作区只有确定性脚手架：前端必须创建 frontend/src/App.tsx（export default function App()）和 frontend/src/styles.css；全栈/后端必须创建 backend/main.py。
4. 如果项目形态升级（例如新增后端），请创建缺失侧的最小必需文件。
5. 前端只 import react / react-dom 和本轮规划中的本地文件；禁止第三方库；不要 import CSS（styles.css 由 main.tsx 引入）。
6. 全栈项目前端所有请求使用相对路径 "api/..."，不要以 / 开头；禁止 localStorage/sessionStorage。
7. 后端只允许 fastapi、pydantic、aiosqlite 和标准库；必须 from db import connection, init_db；lifespan 中 await init_db()；app = FastAPI(root_path=os.getenv("APP_ROOT_PATH",""), lifespan=lifespan)；CORS 全开；至少实现 GET /api/health。
8. 单个文件尽量控制在 8,000 字符以内；结构完整闭合，不要写到一半停止。
9. 改完代码后调用 build_preview；后端项目还要 start_runtime 并 check_health。构建/启动失败时先 read_file 看真实错误，再用 edit_file 精准修复，不要整文件瞎改。
10. 保持现有 UI、文案、交互与数据；不要重写与本次需求无关的文件。
11. 完成时用中文简短总结：修改了哪些文件、是否构建/启动成功。不要声称成功但没有跑 build。
"""


def _schema_changed(plan: dict, existing: dict[str, str]) -> bool:
    if plan["mode"] not in ("backend", "fullstack"):
        return False
    return existing.get("backend/schema.sql") != scaffold.schema_sql(plan["entities"])


def _tool_budget(
    plan: dict,
    *,
    first_build: bool,
    schema_changed: bool,
) -> tuple[int, float, int]:
    planned = max(1, len(plan.get("files") or []))
    if first_build:
        steps = min(
            config.AGENT_MAX_STEPS_FIRST_BUILD,
            max(40, 12 + 6 * planned),
        )
        seconds = config.AGENT_MAX_SECONDS_FIRST_BUILD
    else:
        steps = min(
            config.AGENT_MAX_STEPS_ITERATION,
            max(24, 12 + 4 * planned),
        )
        if schema_changed:
            steps = min(config.AGENT_MAX_STEPS_ITERATION, steps + 6)
        seconds = config.AGENT_MAX_SECONDS_ITERATION
    max_calls = min(config.AGENT_MAX_TOOL_CALLS, 6 * steps)
    return steps, seconds, max_calls


def _workspace_context(workspace: Workspace, plan: dict) -> str:
    files = workspace.files
    tree = "\n".join(
        f"- {path} ({len(content.encode('utf-8')):,} 字节)"
        for path, content in sorted(files.items())
    )
    blocks = [f"当前文件树（{len(files)} 个）：\n{tree or '（空）'}"]

    targets = [item["path"] for item in plan.get("files") or []]
    preferred: list[str] = []
    for path in [
        "frontend/src/App.tsx",
        "frontend/src/styles.css",
        "backend/main.py",
        *targets,
    ]:
        if path in files and path not in preferred:
            preferred.append(path)
    total_size = sum(len(content) for content in files.values())
    if total_size <= config.AGENT_CONTEXT_INLINE_CHARS:
        include = sorted(files)
    else:
        include = preferred
    chunks: list[str] = []
    used = 0
    for path in include:
        content = files[path]
        cap = config.AGENT_CONTEXT_FILE_CHARS
        if cap and len(content) > cap:
            content = content[:cap] + "\n/* ... 内容已截断，请 read_file 查看完整文件 ... */"
        if (
            chunks
            and used + len(content) > config.AGENT_CONTEXT_INLINE_CHARS
        ):
            break
        chunks.append(f"--- {path} ---\n{content}")
        used += len(content)
    if chunks:
        blocks.append(
            f"已有文件内容（共 {len(include)} 个候选，已注入 {len(chunks)} 个；"
            "需要更多请 read_file）：\n" + "\n\n".join(chunks)
        )
    return "\n\n".join(blocks)


def _alex_tool_user(
    plan: dict,
    message: str,
    workspace: Workspace,
    *,
    first_build: bool,
    bob_text: str = "",
) -> str:
    blocks = [
        f"用户需求：\n{message}",
        f"项目概述：{plan['summary']}",
        f"项目形态：{plan['mode']}（title: {plan['title']}）",
        "Planner 建议文件："
        + ("、".join(item["path"] for item in plan["files"]) or "（未指定）"),
        _contract(plan),
    ]
    if first_build:
        blocks.append(
            "这是一个新项目：工作区只有确定性脚手架。"
            "请先用 write_file 创建最小必需文件，再实现完整需求。"
        )
    else:
        blocks.append(
            "这是对已有项目的迭代：先 read_file 看相关文件，"
            "优先 edit_file 精准修改；不要全量重写无关文件。"
        )
    if bob_text:
        blocks.append(f"Bob 的建筑方案：\n{bob_text}")
    blocks.append(_workspace_context(workspace, plan))
    return "\n\n".join(blocks)


async def _seed_scaffold(
    ctx: ToolContext,
    workspace: Workspace,
    plan: dict,
    emit: RoleEmitter,
) -> int:
    scaffold_files = _scaffold_files(plan, workspace.base)
    writes: dict[str, str] = {}
    for path, content in scaffold_files.items():
        if path == "backend/schema.sql":
            if workspace.base.get(path) != content:
                writes[path] = content
        elif path not in workspace.base:
            writes[path] = content
    if not writes:
        return 0

    step = await emit(
        "execution",
        {
            "step": "生成项目脚手架",
            "status": "running",
            "log": f"{len(writes)} 个确定性基础文件",
        },
    )
    ctx.execution_id = step if isinstance(step, int) else None
    for path, content in writes.items():
        change = workspace.write(
            path,
            content,
            overwrite=path in workspace.base,
        )
        if change is None:
            continue
        await db.add_artifact(ctx.pid, path, content, ctx.version)
        await record_change(ctx, change)
        await emit(
            "artifact",
            {
                "filename": path,
                "content": content,
                "version": ctx.version,
                "run_id": ctx.run_id,
            },
        )
    await emit(
        "execution",
        {
            "id": step,
            "step": "生成项目脚手架",
            "status": "success",
            "log": f"{len(writes)} 个基础文件",
            "change_count": len(writes),
        },
    )
    return len(writes)


async def _repair_with_tools(
    *,
    llm,
    toolbox: Toolbox,
    loop_result: LoopResult,
    instruction: str,
    plan: dict,
    message: str,
    emit: RoleEmitter,
    max_steps: int = 12,
    timeout_seconds: float = 300.0,
) -> LoopResult:
    meta = {
        "prompt": message,
        "mode": plan["mode"],
        "title": plan["title"],
        "existing": toolbox.ctx.workspace.files if toolbox.ctx.workspace else {},
        "iteration": True,
    }
    return await run_tool_loop(
        llm=llm,
        toolbox=toolbox,
        initial_messages=list(loop_result.messages)
        + [{"role": "user", "content": instruction}],
        meta=meta,
        emit=emit,
        max_steps=max_steps,
        timeout_seconds=timeout_seconds,
        max_tool_calls=min(config.AGENT_MAX_TOOL_CALLS, 8 * max_steps),
        max_tool_calls_per_step=config.AGENT_MAX_TOOL_CALLS_PER_STEP,
        no_progress_limit=config.AGENT_MAX_NO_PROGRESS_STEPS,
    )


async def _review_with_tools(
    *,
    llm,
    toolbox: Toolbox,
    loop_result: LoopResult,
    plan: dict,
    message: str,
    emit: RoleEmitter,
) -> tuple[LoopResult, list[str]]:
    workspace = toolbox.ctx.workspace
    assert workspace is not None
    issues = _review(workspace.files, plan["mode"])
    if not issues:
        await emit(
            "execution",
            {
                "step": "结构与联调检查",
                "status": "success",
                "log": f"{len(workspace.files)} 个文件通过检查",
            },
        )
        return loop_result, issues
    if not config.AUTO_REPAIR:
        await emit(
            "execution",
            {
                "step": "结构与联调检查",
                "status": "warning",
                "log": "；".join(issues)[:180],
            },
        )
        return loop_result, issues

    check = await emit(
        "execution",
        {
            "step": "结构与联调检查",
            "status": "running",
            "log": "；".join(issues)[:180],
        },
    )
    for round_index in range(config.AGENT_REPAIR_MAX_ROUNDS):
        if not issues:
            break
        instruction = (
            f"Reviewer 发现以下问题（第 {round_index + 1} 轮自动回修）：\n- "
            + "\n- ".join(issues)
            + "\n请用工具精准修复，不要重写无关文件；修复后如可构建请调用 build_preview。"
        )
        loop_result = await _repair_with_tools(
            llm=llm,
            toolbox=toolbox,
            loop_result=loop_result,
            instruction=instruction,
            plan=plan,
            message=message,
            emit=emit,
        )
        issues = _review(workspace.files, plan["mode"])
    await emit(
        "execution",
        {
            "id": check,
            "step": "结构与联调检查",
            "status": "success" if not issues else "warning",
            "log": (
                "自动回修后仍有问题：" + "；".join(issues)[:160]
                if issues
                else "检查通过（已自动回修）"
            ),
        },
    )
    return loop_result, issues


async def _apply_and_build(
    pid: str,
    workspace: Workspace,
    plan: dict,
    emit: RoleEmitter,
    ctx: ToolContext,
    *,
    stop_backend: bool,
) -> tuple[bool, str]:
    if stop_backend:
        await runtime.runtime.stop(pid)
    try:
        stats = await asyncio.to_thread(
            workspace.apply_to,
            config.APPS_DIR / pid,
            reconcile_source=True,
        )
    except Exception as exc:  # noqa: BLE001 - path/runtime errors become repair input
        return False, f"写入项目文件失败：{type(exc).__name__}: {exc}"
    await emit(
        "execution",
        {
            "step": "写入项目文件",
            "status": "success",
            "log": f"写入 {stats['written']} 个，删除 {stats['removed']} 个",
        },
    )

    if plan["mode"] in ("frontend", "fullstack"):
        build = await emit(
            "execution",
            {
                "step": "构建前端预览",
                "status": "running",
                "log": "esbuild 打包 React + TypeScript…",
            },
        )
        try:
            built = await frontend_builder.build(pid, plan["title"])
        except Exception as exc:  # noqa: BLE001 - build errors are repair input
            text = str(exc) if isinstance(exc, frontend_builder.BuildError) else (
                f"{type(exc).__name__}: {exc}"
            )
            await emit(
                "execution",
                {
                    "id": build,
                    "step": "构建前端预览",
                    "status": "error",
                    "log": text.replace("\n", " ")[:180],
                },
            )
            return False, text
        if built is False:
            text = "前端入口 frontend/src/main.tsx 不存在，无法构建预览"
            await emit(
                "execution",
                {
                    "id": build,
                    "step": "构建前端预览",
                    "status": "error",
                    "log": text,
                },
            )
            return False, text
        await emit(
            "execution",
            {
                "id": build,
                "step": "构建前端预览",
                "status": "success",
                "log": "预览产物已生成",
            },
        )

    if plan["mode"] in ("backend", "fullstack"):
        start = await emit(
            "execution",
            {
                "step": "启动后端运行时",
                "status": "running",
                "log": "独立 uvicorn 进程 · SQLite 跟随项目",
            },
        )
        try:
            port = await runtime.runtime.ensure(pid)
            await check_runtime_health(ctx, port)
        except Exception as exc:  # noqa: BLE001 - runtime errors are repair input
            text = f"{type(exc).__name__}: {exc}"
            await emit(
                "execution",
                {
                    "id": start,
                    "step": "启动后端运行时",
                    "status": "error",
                    "log": text[:180],
                },
            )
            return False, text
        await emit(
            "execution",
            {
                "id": start,
                "step": "启动后端运行时",
                "status": "success",
                "log": f"运行时已就绪：/apps/{pid}/api/*",
            },
        )
    return True, ""


async def _build_project_tools(
    pid: str,
    message: str,
    plan: dict,
    emit: RoleEmitter,
    *,
    existing: dict[str, str],
    version: int,
    llm,
    progress: dict,
    bob_text: str = "",
) -> str:
    """Unified first-build/iteration path: scaffold -> tool loop -> verify -> commit."""
    initial_latest = dict(existing)
    existing = _prune(existing, plan["mode"])
    first_build = not existing
    schema_changed = _schema_changed(plan, existing)

    workspace = Workspace(existing)
    ctx = ToolContext(
        pid=pid,
        run_id=emit.run_id,
        agent="alex",
        emit=emit,
        version=version,
        plan=plan,
        workspace=workspace,
    )
    toolbox = Toolbox(ctx, agent_roster.AGENTS["alex"].tools)

    if bob_text:
        await emit(
            "execution",
            {
                "step": "对齐 Bob 的方案",
                "status": "success",
                "log": bob_text.replace("\n", " ")[:140],
            },
        )

    await _seed_scaffold(ctx, workspace, plan, emit)
    # Build/start tools materialise the staged tree during the loop. From here
    # on any failure must restore the previous tree, not only delete artifacts.
    progress["published"] = True

    steps, seconds, max_calls = _tool_budget(
        plan,
        first_build=first_build,
        schema_changed=schema_changed,
    )
    user = _alex_tool_user(
        plan,
        message,
        workspace,
        first_build=first_build,
        bob_text=bob_text,
    )
    meta = {
        "prompt": message,
        "mode": plan["mode"],
        "title": plan["title"],
        "existing": workspace.files,
        "iteration": not first_build,
    }

    loop_result = await run_tool_loop(
        llm=llm,
        toolbox=toolbox,
        system=ALEX_TOOL_SYSTEM,
        user=user,
        meta=meta,
        emit=emit,
        max_steps=steps,
        timeout_seconds=seconds,
        max_tool_calls=max_calls,
        max_tool_calls_per_step=config.AGENT_MAX_TOOL_CALLS_PER_STEP,
        no_progress_limit=config.AGENT_MAX_NO_PROGRESS_STEPS,
    )
    if loop_result.stopped_reason != "done":
        await emit(
            "execution",
            {
                "step": "工具循环结束",
                "status": "warning",
                "log": (
                    f"停止原因：{loop_result.stopped_reason} · "
                    f"{loop_result.steps} 步 / {loop_result.tool_calls} 次工具调用"
                ),
            },
        )

    loop_result, issues = await _review_with_tools(
        llm=llm,
        toolbox=toolbox,
        loop_result=loop_result,
        plan=plan,
        message=message,
        emit=emit,
    )

    # A real no-op is a workspace identical to the pre-round tree. Comparing to
    # ``workspace.base`` would miss an explicit mode prune (base is pruned too).
    if workspace.files == initial_latest:
        await emit(
            "execution",
            {
                "step": "检查变更",
                "status": "warning",
                "log": "本轮没有检测到文件变更，未写入新版本",
            },
        )
        # A build tool may have materialised an intermediate edit that was later
        # reverted; make disk match the final workspace without bumping a version.
        try:
            await asyncio.to_thread(
                workspace.apply_to,
                config.APPS_DIR / pid,
                reconcile_source=True,
            )
        except Exception:  # noqa: BLE001 - best effort on a no-op round
            pass
        return loop_result.text or "本轮没有检测到需要修改的文件。"

    repair_notes: list[str] = []
    for attempt in range(config.AGENT_REPAIR_MAX_ROUNDS + 1):
        changed, deleted = workspace.commit_plan()
        backend_changed = any(path.startswith("backend/") for path in changed) or any(
            path.startswith("backend/") for path in deleted
        )
        ok, error = await _apply_and_build(
            pid,
            workspace,
            plan,
            emit,
            ctx,
            stop_backend=backend_changed,
        )
        if ok:
            break
        if attempt >= config.AGENT_REPAIR_MAX_ROUNDS:
            raise GenerationError(f"构建/启动失败：{error[:300]}")
        repair_notes.append(f"构建/启动回修第 {attempt + 1} 轮：{error[:80]}")
        instruction = (
            "上一轮构建/启动失败，真实错误如下：\n"
            f"{error[:3000]}\n\n"
            "请先用 read_file 查看相关文件，再用 edit_file 精准修复；"
            "前端修复后调用 build_preview，后端修复后调用 start_runtime 并 check_health。"
            "不要整文件重写无关内容。"
        )
        loop_result = await _repair_with_tools(
            llm=llm,
            toolbox=toolbox,
            loop_result=loop_result,
            instruction=instruction,
            plan=plan,
            message=message,
            emit=emit,
            max_steps=min(16, steps),
        )

    # Reconcile files that disappeared (mode changes, deletes that bypassed the
    # tool loop) with tombstones so latest_artifacts matches the workspace.
    for path in sorted(set(initial_latest) - set(workspace.files)):
        await db.add_artifact_deleted(pid, path, version)

    await db.mark_built(pid, version)

    changed, deleted = workspace.commit_plan()
    changed_list = sorted(changed)
    files_text = "、".join(changed_list[:8])
    if len(changed_list) > 8:
        files_text += "…"
    if deleted:
        files_text += ("；删除 " if files_text else "删除 ") + "、".join(
            sorted(deleted)[:4]
        )
    notes = list(repair_notes)
    if loop_result.stopped_reason != "done":
        notes.append(f"工具循环因 {loop_result.stopped_reason} 结束")
    if issues:
        notes.append("仍有检查项未通过：" + "；".join(issues[:3]))

    preview_url = f"/apps/{pid}/?v={version}"
    await emit(
        "execution",
        {
            "step": "生成构建产物",
            "status": "success",
            "log": f"v{version} 可访问：{preview_url}",
        },
    )
    await emit(
        "preview",
        {"url": preview_url, "version": version, "mode": plan["mode"]},
    )

    assistant = (
        f"已完成 v{version}：{plan['summary']}\n"
        f"形态：{MODE_LABEL[plan['mode']]}（{plan['mode']}）\n"
        f"本轮修改：{files_text or '无文件变更'}\n"
        + ("\n".join(f"- {note}" for note in notes) + "\n" if notes else "")
        + (
            f"\nAlex 总结：{loop_result.text.strip()[:600]}\n"
            if loop_result.text.strip()
            else ""
        )
        + (
            "\n数据保存在 backend/data/app.db，刷新或重启后仍在。\n"
            if plan["mode"] in ("backend", "fullstack")
            else "\n"
        )
        + "右侧可以直接预览；如果想调整，继续告诉我就行。"
    )
    return assistant


async def _build_project(
    pid: str,
    message: str,
    plan: dict,
    emit: RoleEmitter,
    *,
    existing: dict[str, str],
    version: int,
    llm,
    progress: dict,
    bob_text: str = "",
) -> str:
    """Dispatch to the unified tool loop, or the legacy generator when disabled."""
    if not config.AGENT_TOOL_LOOP:
        return await _build_project_legacy(
            pid,
            message,
            plan,
            emit,
            existing=existing,
            version=version,
            llm=llm,
            progress=progress,
            bob_text=bob_text,
        )
    return await _build_project_tools(
        pid,
        message,
        plan,
        emit,
        existing=existing,
        version=version,
        llm=llm,
        progress=progress,
        bob_text=bob_text,
    )


async def _build_project_legacy(
    pid: str,
    message: str,
    plan: dict,
    emit: RoleEmitter,
    *,
    existing: dict[str, str],
    version: int,
    llm,
    progress: dict,
    bob_text: str = "",
) -> str:
    toolbox = emit.toolbox()
    existing = _prune(existing, plan["mode"])

    if bob_text:
        await emit(
            "execution",
            {
                "step": "对齐 Bob 的方案",
                "status": "success",
                "log": bob_text.replace("\n", " ")[:140],
            },
        )

    # 1) Scaffold ------------------------------------------------------------
    scaffolds = _scaffold_files(plan, existing)
    scaffold_ex = await emit(
        "execution",
        {
            "step": "生成项目脚手架",
            "status": "running",
            "log": "Vite / FastAPI / SQLite 基础文件",
        },
    )
    for path, content in scaffolds.items():
        if existing.get(path) != content:
            await toolbox.call("write_file", path=path, content=content)
    await emit(
        "execution",
        {
            "id": scaffold_ex,
            "step": "生成项目脚手架",
            "status": "success",
            "log": f"{len(scaffolds)} 个基础文件 · {plan['mode']}",
        },
    )

    # 2) Application files ---------------------------------------------------
    contents: dict[str, str] = {}
    for item in plan["files"]:
        path = item["path"]
        step_ex = await emit(
            "execution",
            {"step": f"生成 {path}", "status": "running", "log": item["purpose"]},
        )
        await emit("file_start", {"filename": path, "purpose": item["purpose"]})
        known = {**existing, **contents}
        try:
            raw = await _llm_text(
                llm,
                role="coder",
                system=_system_for(path),
                user=_coder_user(path, item["purpose"], plan, message, known),
                meta={
                    "prompt": message,
                    "filename": path,
                    "existing": known,
                    "mode": plan["mode"],
                    "title": plan["title"],
                },
                emit=emit,
                emit_tokens=True,
                validator=lambda text, p=path: _valid_content(
                    p, _extract_requested_file(text, p)
                ),
            )
        except Exception as exc:
            await emit(
                "execution",
                {
                    "id": step_ex,
                    "step": f"生成 {path}",
                    "status": "error",
                    "log": f"{type(exc).__name__}: {str(exc)[:160]}",
                },
            )
            raise
        content = _extract_requested_file(raw, path)
        contents[path] = content
        await toolbox.call("write_file", path=path, content=content)
        await emit(
            "execution",
            {
                "id": step_ex,
                "step": f"生成 {path}",
                "status": "success",
                "log": f"{len(content):,} 字符",
            },
        )

    await _guard_large_files(contents, plan, message, llm, emit, toolbox)

    published = _prune({**existing, **scaffolds, **contents}, plan["mode"])

    # 3) Reviewer: deterministic checks + auto repair ------------------------
    review_ex = await emit(
        "execution",
        {
            "step": "结构与联调检查",
            "status": "running",
            "log": "检查文件、样式、API 路径与 Python 语法…",
        },
    )
    issues = _review(published, plan["mode"])
    repair_notes: list[str] = []

    if config.AUTO_REPAIR:
        if plan["mode"] in ("frontend", "fullstack") and _needs_style_repair(issues):
            repair_ex = await emit(
                "execution",
                {
                    "step": "修复 styles.css",
                    "status": "running",
                    "log": ("Reviewer 自动回修：" + "；".join(issues))[:180],
                },
            )
            for round_index in range(2):
                if not _needs_style_repair(issues):
                    break
                await emit(
                    "file_start",
                    {
                        "filename": "frontend/src/styles.css",
                        "purpose": f"Reviewer 自动回修（第 {round_index + 1} 轮）",
                    },
                )
                try:
                    raw = await _llm_text(
                        llm,
                        role="coder",
                        system=STYLES_SYSTEM,
                        user=_repair_styles_user(published, issues),
                        meta={
                            "prompt": message,
                            "filename": "frontend/src/styles.css",
                            "existing": published,
                            "mode": plan["mode"],
                            "title": plan["title"],
                        },
                        emit=emit,
                        emit_tokens=True,
                        validator=lambda text: _valid_content(
                            "frontend/src/styles.css",
                            _extract_requested_file(text, "frontend/src/styles.css"),
                        ),
                    )
                except GenerationError as exc:
                    repair_notes.append(f"样式回修失败：{str(exc)[:80]}")
                    break
                repaired = _extract_requested_file(raw, "frontend/src/styles.css")
                if not repaired:
                    break
                published["frontend/src/styles.css"] = repaired
                contents["frontend/src/styles.css"] = repaired
                await toolbox.call(
                    "write_file", path="frontend/src/styles.css", content=repaired
                )
                issues = _review(published, plan["mode"])
            repair_notes.append("样式缺口与移动端规则已自动回修")
            await emit(
                "execution",
                {
                    "id": repair_ex,
                    "step": "修复 styles.css",
                    "status": "success" if not _needs_style_repair(issues) else "warning",
                    "log": (
                        "回修后仍有问题：" + "；".join(issues)[:160]
                        if issues
                        else "样式检查通过"
                    ),
                },
            )

        if plan["mode"] in ("frontend", "fullstack") and _needs_app_repair(issues):
            target_path = _offending_frontend_file(published, issues)
            repair_ex = await emit(
                "execution",
                {
                    "step": f"修复 {target_path}",
                    "status": "running",
                    "log": "；".join(issues)[:180],
                },
            )
            await emit(
                "file_start",
                {"filename": target_path, "purpose": "Reviewer 联调回修"},
            )
            try:
                raw = await _llm_text(
                    llm,
                    role="coder",
                    system=_system_for(target_path),
                    user=_repair_app_user(published, issues, plan, target_path),
                    meta={
                        "prompt": message,
                        "filename": target_path,
                        "existing": published,
                        "mode": plan["mode"],
                        "title": plan["title"],
                    },
                    emit=emit,
                    emit_tokens=True,
                    validator=lambda text, p=target_path: _valid_content(
                        p, _extract_requested_file(text, p)
                    ),
                )
            except GenerationError as exc:
                raw = ""
                repair_notes.append(f"联调回修失败：{str(exc)[:80]}")
            repaired = _extract_requested_file(raw, target_path)
            if repaired:
                published[target_path] = repaired
                contents[target_path] = repaired
                await toolbox.call("write_file", path=target_path, content=repaired)
                issues = _review(published, plan["mode"])
                repair_notes.append("前后端 API 调用已自动回修")
            await emit(
                "execution",
                {
                    "id": repair_ex,
                    "step": f"修复 {target_path}",
                    "status": "success" if not _needs_app_repair(issues) else "warning",
                    "log": "联调检查通过" if not _needs_app_repair(issues) else "；".join(issues)[:160],
                },
            )

        backend_issues = [
            issue
            for issue in issues
            if issue.startswith("main.py") or issue.startswith("backend/main.py")
        ]
        if plan["mode"] in ("backend", "fullstack") and backend_issues:
            repair_ex = await emit(
                "execution",
                {
                    "step": "修复 backend/main.py",
                    "status": "running",
                    "log": "；".join(backend_issues)[:180],
                },
            )
            await emit(
                "file_start",
                {"filename": "backend/main.py", "purpose": "Reviewer 后端回修"},
            )
            try:
                raw = await _llm_text(
                    llm,
                    role="coder",
                    system=BACKEND_SYSTEM,
                    user=_repair_backend_user(published, backend_issues, plan),
                    meta={
                        "prompt": message,
                        "filename": "backend/main.py",
                        "existing": published,
                        "mode": plan["mode"],
                        "title": plan["title"],
                    },
                    emit=emit,
                    emit_tokens=True,
                    validator=lambda text: _valid_content(
                        "backend/main.py", _extract_requested_file(text, "backend/main.py")
                    ),
                )
            except GenerationError as exc:
                raw = ""
                repair_notes.append(f"后端回修失败：{str(exc)[:80]}")
            repaired = _extract_requested_file(raw, "backend/main.py")
            if repaired:
                published["backend/main.py"] = repaired
                contents["backend/main.py"] = repaired
                await toolbox.call(
                    "write_file", path="backend/main.py", content=repaired
                )
                issues = _review(published, plan["mode"])
                backend_issues = [
                    issue
                    for issue in issues
                    if issue.startswith("main.py") or issue.startswith("backend/main.py")
                ]
                repair_notes.append("后端骨架已自动回修")
            await emit(
                "execution",
                {
                    "id": repair_ex,
                    "step": "修复 backend/main.py",
                    "status": "success" if not backend_issues else "warning",
                    "log": "后端检查通过" if not backend_issues else "回修后仍有问题",
                },
            )

    await emit(
        "execution",
        {
            "id": review_ex,
            "step": "结构与联调检查",
            "status": "warning" if issues else "success",
            "log": ("；".join(issues) if issues else f"{len(published)} 个文件通过检查")
            + ("（已自动回修）" if repair_notes else ""),
        },
    )

    # 4) Deployer: write, build preview, start backend ----------------------
    deploy_ex = await emit(
        "execution",
        {
            "step": "生成构建产物",
            "status": "running",
            "log": f"写入 /apps/{pid}/ 并准备运行时",
        },
    )
    progress["published"] = True
    await toolbox.call("publish_files", files=published)
    if plan["mode"] == "backend":
        await toolbox.call("build_preview", plan=plan)

    if plan["mode"] in ("frontend", "fullstack"):
        build_ex = await emit(
            "execution",
            {
                "step": "构建前端预览",
                "status": "running",
                "log": "esbuild 打包 React + TypeScript…",
            },
        )
        try:
            await toolbox.call("build_preview", plan=plan)
        except frontend_builder.BuildError as exc:
            error_text = str(exc)
            repaired = False
            if config.AUTO_REPAIR:
                target_path = _build_error_path(error_text, published)
                if target_path:
                    await emit(
                        "file_start",
                        {"filename": target_path, "purpose": "修复构建错误"},
                    )
                    repair_ex = await emit(
                        "execution",
                        {
                            "step": f"修复构建错误：{target_path}",
                            "status": "running",
                            "log": error_text.replace("\n", " ")[:180],
                        },
                    )
                    try:
                        raw = await _llm_text(
                            llm,
                            role="coder",
                            system=_system_for(target_path),
                            user=_repair_build_user(
                                message, plan, target_path, error_text, published
                            ),
                            meta={
                                "prompt": message,
                                "filename": target_path,
                                "existing": published,
                                "mode": plan["mode"],
                                "title": plan["title"],
                            },
                            emit=emit,
                            emit_tokens=True,
                            validator=lambda text, p=target_path: _valid_content(
                                p, _extract_requested_file(text, p)
                            ),
                        )
                    except GenerationError as repair_exc:
                        raw = ""
                        error_text = f"{error_text}\n自动修复失败：{repair_exc}"
                    fixed = _extract_requested_file(raw, target_path) if raw else ""
                    if fixed:
                        published[target_path] = fixed
                        contents[target_path] = fixed
                        await toolbox.call(
                            "write_file", path=target_path, content=fixed
                        )
                        progress["published"] = True
                        await toolbox.call("publish_files", files=published)
                        try:
                            await toolbox.call("build_preview", plan=plan)
                            repaired = True
                        except frontend_builder.BuildError as retry_exc:
                            error_text = str(retry_exc)
                            repaired = False
                        remaining = _review(published, plan["mode"])
                        if remaining:
                            repair_notes.append(
                                f"构建错误修复后仍有 {len(remaining)} 项检查未通过"
                            )
                    await emit(
                        "execution",
                        {
                            "id": repair_ex,
                            "step": f"修复构建错误：{target_path}",
                            "status": "success" if repaired else "warning",
                            "log": "已修复并重新构建"
                            if repaired
                            else "修复后仍无法构建，本轮将回滚",
                        },
                    )
            if not repaired:
                await emit(
                    "execution",
                    {
                        "id": build_ex,
                        "step": "构建前端预览",
                        "status": "error",
                        "log": error_text.replace("\n", " ")[:180],
                    },
                )
                await emit(
                    "execution",
                    {
                        "id": deploy_ex,
                        "step": "生成构建产物",
                        "status": "error",
                        "log": "前端构建失败，本轮改动已回滚",
                    },
                )
                raise GenerationError(f"前端预览构建失败：{error_text[:300]}")
            await emit(
                "execution",
                {
                    "id": build_ex,
                    "step": "构建前端预览",
                    "status": "success",
                    "log": "预览产物已生成",
                },
            )
        else:
            await emit(
                "execution",
                {
                    "id": build_ex,
                    "step": "构建前端预览",
                    "status": "success",
                    "log": "预览产物已生成",
                },
            )

    if plan["mode"] in ("backend", "fullstack"):
        start_ex = await emit(
            "execution",
            {
                "step": "启动后端运行时",
                "status": "running",
                "log": "独立 uvicorn 进程 · SQLite 跟随项目",
            },
        )
        started = False
        last_error = ""
        try:
            port = await toolbox.call("start_runtime")
            await toolbox.call("check_health", port=port)
            started = True
        except (runtime.AppRuntimeError, RuntimeError) as exc:
            last_error = str(exc)
            if config.AUTO_REPAIR and "backend/main.py" in published:
                await emit(
                    "file_start",
                    {"filename": "backend/main.py", "purpose": "修复后端启动错误"},
                )
                try:
                    raw = await _llm_text(
                        llm,
                        role="coder",
                        system=BACKEND_SYSTEM,
                        user=(
                            f"后端启动失败，日志如下：\n{last_error[:3000]}\n\n"
                            "请修复 backend/main.py，保留现有 API 合约，只输出 main.py 完整内容。"
                        ),
                        meta={
                            "prompt": message,
                            "filename": "backend/main.py",
                            "existing": published,
                            "mode": plan["mode"],
                            "title": plan["title"],
                        },
                        emit=emit,
                        emit_tokens=True,
                        validator=lambda text: _valid_content(
                            "backend/main.py", _extract_requested_file(text, "backend/main.py")
                        ),
                    )
                except GenerationError as repair_exc:
                    raw = ""
                    last_error = f"{last_error}\n自动修复失败：{repair_exc}"
                fixed = _extract_requested_file(raw, "backend/main.py") if raw else ""
                if fixed:
                    published["backend/main.py"] = fixed
                    contents["backend/main.py"] = fixed
                    await toolbox.call(
                        "write_file", path="backend/main.py", content=fixed
                    )
                    progress["published"] = True
                    await toolbox.call("publish_files", files=published)
                    try:
                        port = await toolbox.call("start_runtime")
                        await toolbox.call("check_health", port=port)
                        started = True
                    except (runtime.AppRuntimeError, RuntimeError) as retry_exc:
                        last_error = str(retry_exc)
        if not started:
            await emit(
                "execution",
                {
                    "id": start_ex,
                    "step": "启动后端运行时",
                    "status": "error",
                    "log": last_error[:180],
                },
            )
            await emit(
                "execution",
                {
                    "id": deploy_ex,
                    "step": "生成构建产物",
                    "status": "error",
                    "log": "后端启动失败，本轮改动已回滚",
                },
            )
            raise GenerationError(f"后端运行时启动失败：{last_error[:300]}")
        await emit(
            "execution",
            {
                "id": start_ex,
                "step": "启动后端运行时",
                "status": "success",
                "log": f"运行时已就绪：/apps/{pid}/api/*",
            },
        )

    # Keep the artifact table in sync with what is actually on disk (mode
    # downgrades can drop files from the project tree).
    await db.delete_artifacts_except(pid, set(published))
    # Persisted success marker: the overview only offers publish after this
    # point (preview built and, for fullstack/backend, runtime healthy).
    await db.mark_built(pid, version)

    preview_url = f"/apps/{pid}/?v={version}"
    await emit(
        "execution",
        {
            "id": deploy_ex,
            "step": "生成构建产物",
            "status": "success",
            "log": f"v{version} 可访问：{preview_url}",
        },
    )
    await emit("preview", {"url": preview_url, "version": version, "mode": plan["mode"]})

    assistant = (
        f"已完成 v{version}：{plan['summary']}\n"
        f"形态：{MODE_LABEL[plan['mode']]}（{plan['mode']}）\n"
        f"文件：{', '.join(contents)}\n"
        + ("\n".join(f"{note}。" for note in repair_notes) + "\n" if repair_notes else "")
        + (
            "\n数据保存在 backend/data/app.db，刷新或重启后仍在。\n"
            if plan["mode"] in ("backend", "fullstack")
            else "\n"
        )
        + "右侧可以直接预览；如果想调整，继续告诉我就行。"
    )
    return assistant


# ---------------------------------------------------------------------------
# Consult mode: every mentioned agent answers independently (in parallel)
# ---------------------------------------------------------------------------

def _consult_context(
    agent: str,
    project_name: str,
    existing: dict[str, str],
    mode: str | None,
    version: int,
    recent: list[dict],
) -> str:
    lines = [
        f"项目：{project_name}",
        f"形态：{mode or '空项目'}",
        f"版本：v{version}",
        f"文件（{len(existing)}）：{', '.join(sorted(existing)[:40]) or '（空）'}",
    ]
    if recent:
        lines.append("最近对话：")
        for item in recent[-4:]:
            content = str(item.get("content") or "").replace("\n", " ")[:160]
            who = item.get("agent") or item.get("role") or "user"
            lines.append(f"- {who}: {content}")
    if agent == "bob":
        for path in ("backend/schema.sql", "backend/main.py", "frontend/src/App.tsx"):
            if path in existing:
                lines.append(f"\n--- {path} 摘录 ---\n{existing[path][:2000]}")
    elif agent == "alex":
        for path in ("frontend/src/App.tsx", "frontend/src/styles.css", "backend/main.py"):
            if path in existing:
                lines.append(f"\n--- {path} 摘录 ---\n{existing[path][:1500]}")
    return "\n".join(lines)


async def _run_consult_agent(
    pid: str,
    message: str,
    agent: str,
    run_id: str,
    base_emit: Emit,
    *,
    project_name: str,
    existing: dict[str, str],
    mode: str | None,
    version: int,
    recent: list[dict],
    index: int = 0,
) -> None:
    emit = RoleEmitter(pid, run_id, agent, base_emit, version, index)
    spec = agent_roster.AGENTS[agent]
    try:
        ex = await emit(
            "execution",
            {
                "step": "理解问题",
                "status": "running",
                "log": f"问题：{message.replace(chr(10), ' ')[:80]}",
            },
        )
        context = _consult_context(agent, project_name, existing, mode, version, recent)
        user = f"用户问题：\n{message}\n\n项目上下文：\n{context}"
        text = await _llm_text(
            get_llm(),
            role="consult",
            system=agent_roster.CONSULT_SYSTEMS[agent],
            user=user,
            meta={
                "agent": agent,
                "prompt": message,
                "project_name": project_name,
                "mode": mode or "frontend",
                "files": sorted(existing),
                "version": version,
            },
            emit=emit,
            emit_tokens=False,
            retry_hint=ANSWER_RETRY_HINT,
        )
        text = text.strip()
        if not text:
            fallback = "当前上下文不足，暂时无法回答这个问题。"
            text = f"{fallback}\n\n补充：请在消息里 @Mike、@Bob 或 @Alex 指定角色。"
        await emit(
            "execution",
            {
                "id": ex,
                "step": "理解问题",
                "status": "success",
                "log": f"{len(existing)} 个文件 · 最近 {len(recent)} 条对话",
            },
        )
        ex2 = await emit(
            "execution",
            {
                "step": "整理回答",
                "status": "running",
                "log": "按角色视角组织答案…",
            },
        )
        await emit(
            "execution",
            {
                "id": ex2,
                "step": "整理回答",
                "status": "success",
                "log": f"{len(text)} 字符",
            },
        )
        await emit("message", {"role": "assistant", "content": text})
        await base_emit(
            "agent_end",
            {
                "run_id": run_id,
                "agent": agent,
                "run_index": index,
                "status": "success",
            },
        )
    except Exception as exc:  # noqa: BLE001 - one consult failure must not stop others
        await emit(
            "execution",
            {
                "step": "回答失败",
                "status": "error",
                "log": f"{type(exc).__name__}: {str(exc)[:180]}",
            },
        )
        await base_emit(
            "message",
            {
                "role": "assistant",
                "agent": agent,
                "run_id": run_id,
                "content": f"回答失败：{type(exc).__name__}: {str(exc)[:200]}",
            },
        )
        await base_emit(
            "agent_end",
            {
                "run_id": run_id,
                "agent": agent,
                "run_index": index,
                "status": "error",
            },
        )


async def _run_consult_segments(
    pid: str,
    segments: list[agent_roster.Segment],
    emit: Emit,
    *,
    project_name: str,
    existing: dict[str, str],
    mode: str | None,
    version: int,
    recent: list[dict],
    index_state: dict[str, int],
) -> None:
    """Run all consult tasks in parallel, one group per agent.

    Multiple segments addressed to the same agent are merged into one prompt,
    so the agent answers exactly the sub-questions that mention it.
    """
    merged: dict[str, list[str]] = {}
    order: list[str] = []
    for segment in segments:
        for agent in segment.agents:
            if agent not in merged:
                merged[agent] = []
                order.append(agent)
            if segment.text and segment.text not in merged[agent]:
                merged[agent].append(segment.text)

    tasks = []
    for agent in order:
        run_id = _new_run_id()
        run_index = index_state["next"]
        index_state["next"] += 1
        spec = agent_roster.AGENTS[agent]
        await emit(
            "agent_start",
            {
                "run_id": run_id,
                "agent": agent,
                "name": spec.name,
                "role": spec.role,
                "index": run_index,
            },
        )
        tasks.append(
            _run_consult_agent(
                pid,
                "\n\n".join(merged[agent]),
                agent,
                run_id,
                emit,
                project_name=project_name,
                existing=existing,
                mode=mode,
                version=version,
                recent=recent,
                index=run_index,
            )
        )
    if len(tasks) == 1:
        await tasks[0]
    else:
        await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# Build mode: dependency-ordered runs with trailing @ hand-off
# ---------------------------------------------------------------------------

async def _run_build_turn(
    pid: str,
    message: str,
    emit: Emit,
    *,
    project_name: str,
    existing: dict[str, str],
    mode: str | None,
    version: int,
    targets: list[str] | None = None,
    index_state: dict[str, int] | None = None,
) -> None:
    targets = agent_roster.dependency_order(
        targets or agent_roster.initial_targets(message, "build")
    )
    index_state = index_state or {"next": 0}
    queue: deque[str] = deque(targets)
    runs: Counter[str] = Counter()
    plan: dict | None = None
    mike_text = ""
    bob_text = ""
    last_emitter: RoleEmitter | None = None

    while queue and sum(runs.values()) < MAX_TOTAL_RUNS:
        agent = queue.popleft()
        if runs[agent] >= MAX_RUNS_PER_AGENT:
            if last_emitter is not None:
                await last_emitter(
                    "execution",
                    {
                        "step": "自动交接",
                        "status": "warning",
                        "log": f"@{agent_roster.AGENT_NAMES[agent]} 已达单轮上限，跳过",
                    },
                )
            continue

        runs[agent] += 1
        run_id = _new_run_id()
        spec = agent_roster.AGENTS[agent]
        run_index = index_state["next"]
        index_state["next"] += 1
        await emit(
            "agent_start",
            {
                "run_id": run_id,
                "agent": agent,
                "name": spec.name,
                "role": spec.role,
                "index": run_index,
            },
        )
        emitter = RoleEmitter(pid, run_id, agent, emit, version, run_index)
        try:
            if agent == "mike":
                text = await _run_mike(
                    pid,
                    message,
                    emitter,
                    project_name=project_name,
                    existing=existing,
                    existing_mode=mode,
                    current_version=max(0, version - 1),
                )
                mike_text = text
            elif agent == "bob":
                plan, text = await _run_bob(
                    pid,
                    message,
                    emitter,
                    project_name=project_name,
                    existing=existing,
                    existing_mode=mode,
                    mike_text=mike_text,
                )
                bob_text = text
            else:
                text = await _run_alex(
                    pid,
                    message,
                    emitter,
                    project_name=project_name,
                    existing=existing,
                    existing_mode=mode,
                    version=version,
                    plan=plan,
                    bob_text=bob_text,
                )
        except Exception as exc:  # noqa: BLE001 - surface the failing role only
            log_detail = f"{type(exc).__name__}: {str(exc)[:240]}"
            user_detail = (
                str(exc)[:300]
                if isinstance(exc, GenerationError)
                else log_detail
            )
            note = (
                "项目已保留上一个可用版本。"
                if existing
                else "本轮没有发布任何文件。"
            )
            await emitter(
                "execution",
                {
                    "step": "执行失败",
                    "status": "error",
                    "log": log_detail,
                },
            )
            await emit("error", {"message": f"本轮生成失败：{user_detail}。{note}"})
            text = f"执行失败：{user_detail}\n\n{note}可以调整需求后重试。"
            await emit(
                "message",
                {
                    "role": "assistant",
                    "agent": agent,
                    "run_id": run_id,
                    "run_index": run_index,
                    "content": text,
                },
            )
            await emit(
                "agent_end",
                {
                    "run_id": run_id,
                    "agent": agent,
                    "run_index": run_index,
                    "status": "error",
                },
            )
            last_emitter = emitter
            break

        await emit(
            "message",
            {
                "role": "assistant",
                "agent": agent,
                "run_id": run_id,
                "run_index": run_index,
                "content": text,
            },
        )
        await emit(
            "agent_end",
            {
                "run_id": run_id,
                "agent": agent,
                "run_index": run_index,
                "status": "success",
            },
        )
        last_emitter = emitter
        next_targets = agent_roster.parse_mentions(text, tail_only=True)
        queue = deque(
            agent_roster.merge_targets(
                list(queue), next_targets, current=agent, intent="build"
            )
        )

    if queue and last_emitter is not None:
        await last_emitter(
            "execution",
            {
                "step": "自动交接",
                "status": "warning",
                "log": "已达自动交接上限，未执行 "
                + "、".join(f"@{agent_roster.AGENT_NAMES[key]}" for key in queue),
            },
        )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def run_turn(pid: str, message: str, emit: Emit) -> None:
    project = await db.get_project(pid)
    project_name = (project or {}).get("name") or "未命名项目"
    existing = await db.latest_artifacts(pid)
    mode = _existing_mode(existing)
    next_version = await db.next_version(pid)

    segments = agent_roster.split_segments(message) or [
        agent_roster.Segment(("mike",), message)
    ]
    has_project = bool(existing)
    intents = [
        (segment, agent_roster.classify_intent(segment.text, has_project=has_project))
        for segment in segments
    ]

    index_state: dict[str, int] = {"next": 0}
    recent = [
        item
        for item in await db.recent_conversations(pid, 8)
        if not (item.get("role") == "user" and item.get("content") == message)
    ]

    if all(intent == "consult" for _, intent in intents):
        await _run_consult_segments(
            pid,
            segments,
            emit,
            project_name=project_name,
            existing=existing,
            mode=mode,
            version=max(0, next_version - 1),
            recent=recent,
            index_state=index_state,
        )
        return

    # Mixed build + consult: keep the user's order. Builds change files, so
    # refresh the project snapshot and re-classify before the next segment.
    for segment, _ in intents:
        intent = agent_roster.classify_intent(segment.text, has_project=bool(existing))
        if intent == "consult":
            await _run_consult_segments(
                pid,
                [segment],
                emit,
                project_name=project_name,
                existing=existing,
                mode=mode,
                version=max(0, next_version - 1),
                recent=recent,
                index_state=index_state,
            )
            continue

        await _run_build_turn(
            pid,
            segment.text,
            emit,
            project_name=project_name,
            existing=existing,
            mode=mode,
            version=next_version,
            targets=list(segment.agents),
            index_state=index_state,
        )
        existing = await db.latest_artifacts(pid)
        mode = _existing_mode(existing)
        next_version = await db.next_version(pid)
        recent = [
            item
            for item in await db.recent_conversations(pid, 8)
            if not (item.get("role") == "user" and item.get("content") == message)
        ]
