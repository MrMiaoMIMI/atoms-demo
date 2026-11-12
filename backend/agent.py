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
from tools import Toolbox, ToolContext

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
    {"table": "todos", "fields": [
      {"name": "id", "type": "INTEGER", "primary_key": true, "autoincrement": true},
      {"name": "title", "type": "TEXT", "not_null": true},
      {"name": "done", "type": "INTEGER", "not_null": true, "default": 0}
    ]}
  ],
  "api": [{"method": "GET", "path": "/api/todos", "description": "获取列表"}],
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
5. 前端所有后端请求使用相对路径 "api/..."（不要以 / 开头），例如 fetch("api/todos")。
6. 后端只能使用 fastapi、pydantic、aiosqlite、uvicorn 与 Python 标准库。
7. 用户是在续改已有项目时，列出所有需要新增或修改的文件；不要重复列出不需要改的文件。
8. 如果已有项目是 fullstack，除非用户明确要求去掉后端，否则继续保持 fullstack。
"""

FRONTEND_SYSTEM = """你是 "Coder" Agent，负责写出一个 React + TypeScript 文件的完整内容。
只输出文件内容本身：不要 markdown 代码围栏，不要任何解释、标题或前后缀。

要求：
- React 18 函数组件 + hooks，TypeScript，单文件可独立被 Vite/esbuild 编译。
- 只 import react / react-dom 以及本轮文件清单中的本地文件；禁止任何第三方库。
- 不要 import CSS（样式统一写在 frontend/src/styles.css，由 main.tsx 引入）。
- 所有 className 使用字面量字符串（条件样式用 "a" + (cond ? " b" : "")），不要在运行时拼出未定义的类名。
- 全栈项目必须调用后端 API：所有请求使用相对路径 "api/..."，例如 fetch("api/todos")，禁止以 / 开头。
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

RETRY_HINT = (
    "\n\n重要：上一次输出被截断或不完整。请重新输出完整文件，"
    "确保所有标签与括号闭合，不要省略任何部分，也不要加解释。"
)

FENCE = re.compile(r"^```[a-zA-Z0-9]*\s*\n?")
REMOVE_BACKEND = ("不要后端", "去掉后端", "纯前端", "只做前端", "只要前端")
REMOVE_FRONTEND = ("只做后端", "只要后端", "纯后端", "只写后端", "不要前端", "没有前端", "只提供api")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _clean_file_content(text: str) -> str:
    content = text.strip()
    content = FENCE.sub("", content)
    content = re.sub(r"\n?```\s*$", "", content)
    return content.strip()


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


def _plan_from_text(
    text: str,
    message: str,
    existing: dict[str, str],
    existing_mode: str | None,
    project_name: str,
) -> dict:
    data: dict = {}
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            loaded = json.loads(match.group(0))
            if isinstance(loaded, dict):
                data = loaded
        except (ValueError, TypeError):
            data = {}

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


def _mock_plan_data(
    message: str,
    existing: dict[str, str],
    existing_mode: str | None,
    project_name: str,
) -> dict:
    mode = _resolve_mode(templates.pick_mode(message, existing_mode), message, existing_mode)
    entities = templates.entities_for(mode, message)
    api = templates.api_for(mode, entities)
    title = _existing_title(existing) or templates.extract_title(message, mode)
    return {
        "summary": "LLM 输出异常，已整轮回退到一致的 Mock 模板，保证项目完整可运行。",
        "title": title or (project_name or "Atoms App"),
        "mode": mode,
        "entities": entities,
        "api": api,
        "files": _normalize_files(None, mode),
    }


def _mock_contents(plan: dict) -> dict[str, str]:
    contents: dict[str, str] = {}
    for item in plan["files"]:
        path = item["path"]
        content = templates.mock_file(
            "",
            path,
            None,
            mode=plan["mode"],
            title=plan["title"],
        )
        if content:
            contents[path] = content
    return contents


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
    state: dict,
    validator: Callable[[str], bool] | None = None,
) -> str:
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

    if state.get("degraded"):
        return await run(MockLLM(), user)

    last_error: Exception | None = None
    for attempt in range(2):
        prompt_user = user if attempt == 0 else user + RETRY_HINT
        try:
            text = await run(llm, prompt_user)
        except Exception as exc:
            last_error = exc
            if isinstance(llm, MockLLM):
                raise
            break
        candidate = _clean_file_content(text) if validator else text
        if validator is None or validator(candidate):
            return text
        last_error = RuntimeError("LLM output incomplete")
        if emit_tokens:
            await emit("token_reset", {"filename": meta.get("filename")})
        if attempt == 0:
            await emit(
                "execution",
                {
                    "agent": "Coder" if role == "coder" else "Orchestrator",
                    "step": f"重试 {meta.get('filename') or role}",
                    "status": "warning",
                    "log": "输出缺少闭合结构，自动重试一次",
                },
            )

    state["degraded"] = True
    assert last_error is not None
    await emit(
        "execution",
        {
            "agent": "Orchestrator",
            "step": "降级 Mock Agent",
            "status": "warning",
            "log": f"{type(last_error).__name__}: {str(last_error)[:180]}",
        },
    )
    if emit_tokens:
        await emit("token_reset", {"filename": meta.get("filename")})
    return await run(MockLLM(), user)


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
        elif event in {"artifact", "file_start", "token", "token_reset"}:
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
    state: dict = {}
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
        state=state,
    )
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
) -> tuple[dict, bool]:
    planner_user = (
        f"用户需求：\n{message}\n\n"
        + (f"{extra_context}\n\n" if extra_context else "")
        + f"当前项目文件：{', '.join(existing) if existing else '（空项目）'}\n"
        + f"当前形态：{existing_mode or '（空项目）'}\n\n"
        + "输出 JSON。"
    )
    state: dict = {}
    plan_text = await _llm_text(
        get_llm(),
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
        state=state,
    )
    plan = _plan_from_text(plan_text, message, existing, existing_mode, project_name)
    is_mock = bool(state.get("degraded"))
    if is_mock:
        plan = _mock_plan_data(message, existing, existing_mode, project_name)
    return plan, is_mock


async def _run_bob(
    pid: str,
    message: str,
    emit: RoleEmitter,
    *,
    project_name: str,
    existing: dict[str, str],
    existing_mode: str | None,
    mike_text: str,
) -> tuple[dict, str, bool]:
    ex = await emit(
        "execution",
        {
            "step": "分析项目形态",
            "status": "running",
            "log": "阅读现有结构，判断前端 / 全栈 / 后端…",
        },
    )
    plan, is_mock = await _call_planner(
        message,
        emit,
        project_name=project_name,
        existing=existing,
        existing_mode=existing_mode,
        extra_context=(f"Mike 的计划：\n{mike_text}" if mike_text else ""),
    )
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
        plan = _mock_plan_data(message, existing, existing_mode, project_name)
        is_mock = True
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
    return plan, text, is_mock


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
    plan_is_mock: bool,
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
        plan, plan_is_mock = await _call_planner(
            message,
            emit,
            project_name=project_name,
            existing=existing,
            existing_mode=existing_mode,
        )
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
                "log": f"{plan['mode']} · {len(plan['files'])} 个文件"
                + ("（Mock 方案）" if plan_is_mock else ""),
            },
        )

    state: dict = {}
    return await _build_project(
        pid,
        message,
        plan,
        emit,
        existing=existing,
        existing_mode=existing_mode,
        project_name=project_name,
        version=version,
        llm=get_llm(),
        state=state,
        plan_is_mock=plan_is_mock,
        bob_text=bob_text,
    )


async def _install_mock_fallback(
    pid: str,
    version: int,
    existing: dict[str, str],
    message: str,
    existing_mode: str | None,
    project_name: str,
    emit: RoleEmitter,
    toolbox: Toolbox,
) -> dict:
    plan = _mock_plan_data(message, existing, existing_mode, project_name)
    scaffolds = _scaffold_files(plan, existing)
    contents = _mock_contents(plan)
    published = _prune({**existing, **scaffolds, **contents}, plan["mode"])
    for path, content in {**scaffolds, **contents}.items():
        if existing.get(path) != content:
            await toolbox.call("write_file", path=path, content=content)
    await toolbox.call("publish_files", files=published)
    return {"plan": plan, "published": published, "contents": contents}


def _build_error_path(error: str, published: dict[str, str]) -> str | None:
    match = re.search(r"((?:src/)[^\s:]+\.(?:tsx|ts|jsx|js|css))", error)
    if not match:
        return None
    path = "frontend/" + match.group(1)
    return path if path in published else None


async def _build_project(
    pid: str,
    message: str,
    plan: dict,
    emit: RoleEmitter,
    *,
    existing: dict[str, str],
    existing_mode: str | None,
    project_name: str,
    version: int,
    llm,
    state: dict,
    plan_is_mock: bool,
    bob_text: str = "",
) -> str:
    toolbox = emit.toolbox()
    existing = _prune(existing, plan["mode"])
    force_mock = plan_is_mock or bool(state.get("degraded"))

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
        if force_mock:
            continue
        step_ex = await emit(
            "execution",
            {"step": f"生成 {path}", "status": "running", "log": item["purpose"]},
        )
        await emit("file_start", {"filename": path, "purpose": item["purpose"]})
        known = {**existing, **contents}
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
            state=state,
            validator=lambda text, p=path: _valid_content(p, _clean_file_content(text)),
        )
        content = _clean_file_content(raw)
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
        if state.get("degraded"):
            break

    if state.get("degraded") and not force_mock:
        fallback = await _install_mock_fallback(
            pid,
            version,
            existing,
            message,
            existing_mode,
            project_name,
            emit,
            toolbox,
        )
        plan = fallback["plan"]
        published = fallback["published"]
        contents = fallback["contents"]
        force_mock = True
        await emit(
            "execution",
            {
                "step": "整轮回退 Mock 模板",
                "status": "warning",
                "log": "LLM 输出异常，已替换为一致的可运行模板",
            },
        )
    else:
        published = _prune({**existing, **scaffolds, **contents}, plan["mode"])

    if force_mock and not contents:
        contents = _mock_contents(plan)
        updated = _scaffold_files(plan, existing)
        published = _prune({**existing, **updated, **contents}, plan["mode"])
        for path, content in contents.items():
            await toolbox.call("write_file", path=path, content=content)

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

    if config.AUTO_REPAIR and not force_mock:
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
                    state=state,
                    validator=lambda text: _valid_content(
                        "frontend/src/styles.css", _clean_file_content(text)
                    ),
                )
                repaired = _clean_file_content(raw)
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
                state=state,
                validator=lambda text, p=target_path: _valid_content(
                    p, _clean_file_content(text)
                ),
            )
            repaired = _clean_file_content(raw)
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
                state=state,
                validator=lambda text: _valid_content(
                    "backend/main.py", _clean_file_content(text)
                ),
            )
            repaired = _clean_file_content(raw)
            if repaired and not state.get("degraded"):
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

    # A repair call may itself have degraded to the Mock Agent. Never ship a
    # hybrid (real files + mock file): replace the whole round consistently.
    if state.get("degraded") and not force_mock:
        fallback = await _install_mock_fallback(
            pid,
            version,
            existing,
            message,
            existing_mode,
            project_name,
            emit,
            toolbox,
        )
        plan = fallback["plan"]
        published = fallback["published"]
        contents = fallback["contents"]
        force_mock = True
        issues = _review(published, plan["mode"])
        repair_notes.clear()
        await emit(
            "execution",
            {
                "step": "整轮回退 Mock 模板",
                "status": "warning",
                "log": "回修阶段 LLM 输出异常，已替换为一致的可运行模板",
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
            "step": "发布项目",
            "status": "running",
            "log": f"写入 /apps/{pid}/ 并准备运行时",
        },
    )
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
            if config.AUTO_REPAIR and not force_mock:
                target_path = _build_error_path(error_text, published)
                if target_path:
                    await emit(
                        "file_start",
                        {"filename": target_path, "purpose": "修复构建错误"},
                    )
                    raw = await _llm_text(
                        llm,
                        role="coder",
                        system=_system_for(target_path),
                        user=(
                            f"前端构建失败，错误如下：\n{error_text[:3000]}\n\n"
                            f"请修复 {target_path}，保留现有功能与视觉，只输出该文件完整内容。"
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
                        state=state,
                        validator=lambda text, p=target_path: _valid_content(
                            p, _clean_file_content(text)
                        ),
                    )
                    fixed = _clean_file_content(raw)
                    if fixed and not state.get("degraded"):
                        published[target_path] = fixed
                        contents[target_path] = fixed
                        await toolbox.call(
                            "write_file", path=target_path, content=fixed
                        )
                        await toolbox.call("publish_files", files=published)
                        try:
                            await toolbox.call("build_preview", plan=plan)
                            repaired = True
                        except frontend_builder.BuildError:
                            repaired = False
            if not repaired:
                if not force_mock:
                    fallback = await _install_mock_fallback(
                        pid,
                        version,
                        existing,
                        message,
                        existing_mode,
                        project_name,
                        emit,
                        toolbox,
                    )
                    plan = fallback["plan"]
                    published = fallback["published"]
                    contents = fallback["contents"]
                    force_mock = True
                    await emit(
                        "execution",
                        {
                            "step": "整轮回退 Mock 模板",
                            "status": "warning",
                            "log": f"前端构建失败，已回退：{error_text[:140]}",
                        },
                    )
                    await toolbox.call("build_preview", plan=plan)
                else:
                    await emit("error", {"message": f"前端预览构建失败：{error_text[:300]}"})
            await emit(
                "execution",
                {
                    "id": build_ex,
                    "step": "构建前端预览",
                    "status": "success" if (repaired or force_mock or not error_text) else "warning",
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
            if config.AUTO_REPAIR and not force_mock and "backend/main.py" in published:
                await emit(
                    "file_start",
                    {"filename": "backend/main.py", "purpose": "修复后端启动错误"},
                )
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
                    state=state,
                    validator=lambda text: _valid_content(
                        "backend/main.py", _clean_file_content(text)
                    ),
                )
                fixed = _clean_file_content(raw)
                if fixed and not state.get("degraded"):
                    published["backend/main.py"] = fixed
                    contents["backend/main.py"] = fixed
                    await toolbox.call(
                        "write_file", path="backend/main.py", content=fixed
                    )
                    await toolbox.call("publish_files", files=published)
                    try:
                        port = await toolbox.call("start_runtime")
                        await toolbox.call("check_health", port=port)
                        started = True
                    except (runtime.AppRuntimeError, RuntimeError) as retry_exc:
                        last_error = str(retry_exc)
        if not started:
            if not force_mock:
                fallback = await _install_mock_fallback(
                    pid,
                    version,
                    existing,
                    message,
                    existing_mode,
                    project_name,
                    emit,
                    toolbox,
                )
                plan = fallback["plan"]
                published = fallback["published"]
                contents = fallback["contents"]
                force_mock = True
                await emit(
                    "execution",
                    {
                        "step": "整轮回退 Mock 模板",
                        "status": "warning",
                        "log": f"后端启动失败，已回退：{last_error[:140]}",
                    },
                )
                try:
                    await toolbox.call("build_preview", plan=plan)
                    if plan["mode"] in ("backend", "fullstack"):
                        port = await toolbox.call("start_runtime")
                        await toolbox.call("check_health", port=port)
                    started = True
                except (
                    runtime.AppRuntimeError,
                    frontend_builder.BuildError,
                    RuntimeError,
                ) as exc:
                    last_error = str(exc)
            if not started:
                await emit("error", {"message": f"后端运行时启动失败：{last_error[:300]}"})
        await emit(
            "execution",
            {
                "id": start_ex,
                "step": "启动后端运行时",
                "status": "success" if started else "warning",
                "log": (
                    "运行时已就绪：/apps/%s/api/*" % pid
                    if started
                    else last_error[:180]
                ),
            },
        )

    # Keep the artifact table in sync with what is actually on disk (mode
    # downgrades and mock fallbacks can drop files from the project tree).
    await db.delete_artifacts_except(pid, set(published))

    preview_url = f"/apps/{pid}/?v={version}"
    await emit(
        "execution",
        {
            "id": deploy_ex,
            "step": "发布项目",
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
        state: dict = {}
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
            state=state,
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
    plan_is_mock = False
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
                plan, text, plan_is_mock = await _run_bob(
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
                    plan_is_mock=plan_is_mock,
                    bob_text=bob_text,
                )
        except Exception as exc:  # noqa: BLE001 - surface the failing role only
            await emitter(
                "execution",
                {
                    "step": "执行失败",
                    "status": "error",
                    "log": f"{type(exc).__name__}: {str(exc)[:180]}",
                },
            )
            text = f"执行失败：{type(exc).__name__}: {str(exc)[:240]}"
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
