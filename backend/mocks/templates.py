"""Mock demo templates used ONLY when no LLM key is configured.

They intentionally produce a neutral placeholder instead of pretending to be
the requested app: without an LLM the system cannot honour arbitrary natural
language, and a canned "todo list" used to leak into real projects whenever a
generation failed. Real projects now keep their last good version on failure
and never fall back to these templates.

The shape matches the real path: a Vite + React + TypeScript frontend
(``frontend/src/App.tsx`` + ``frontend/src/styles.css``) and, for full-stack /
backend requests, a FastAPI service using the per-project SQLite file.
"""
from __future__ import annotations

import json
import re

# ---------------------------------------------------------------------------
# Mode selection (shared with the planner fallback)
# ---------------------------------------------------------------------------

FRONTEND_ONLY = ("落地页", "官网", "展示页", "宣传页", "纯前端", "不要后端", "去掉后端", "只做前端", "只要前端")
BACKEND_ONLY = ("只做后端", "只要后端", "纯后端", "只写后端", "只写api", "只提供api", "api服务", "后端服务", "没有前端", "不要前端")
FULLSTACK_KEYS = (
    "持久化",
    "数据库",
    "sqlite",
    "保存",
    "存储",
    "增删改查",
    "crud",
    "后端",
    "api",
    "登录",
    "注册",
    "用户系统",
    "订单",
    "记账",
    "留言",
    "评论",
    "投票",
    "表单提交",
    "数据管理",
)

DEFAULT_TITLE = {
    "frontend": "Atoms 应用",
    "fullstack": "Atoms 全栈应用",
    "backend": "Atoms API 服务",
}


def pick_mode(prompt: str, existing_mode: str | None = None) -> str:
    p = prompt.lower()
    if any(key in p for key in FRONTEND_ONLY):
        return "frontend"
    if any(key in p for key in BACKEND_ONLY):
        return "backend"
    upgrade = any(key in p for key in FULLSTACK_KEYS)
    if existing_mode == "fullstack":
        return "fullstack"
    if upgrade:
        return "fullstack"
    return existing_mode or "frontend"


# ---------------------------------------------------------------------------
# Mock planner: neutral demo metadata
# ---------------------------------------------------------------------------

def _items_entity() -> dict:
    return {
        "table": "items",
        "fields": [
            {"name": "id", "type": "INTEGER", "primary_key": True, "autoincrement": True},
            {"name": "title", "type": "TEXT", "not_null": True},
        ],
    }


def entities_for(mode: str, prompt: str) -> list[dict]:
    if mode == "frontend":
        return []
    return [_items_entity()]


def api_for(mode: str, entities: list[dict]) -> list[dict]:
    if mode == "frontend":
        return []
    table = entities[0]["table"] if entities else "items"
    return [
        {"method": "GET", "path": f"/api/{table}", "description": f"获取 {table} 列表"},
        {"method": "GET", "path": "/api/health", "description": "健康检查"},
    ]


def mock_plan(
    prompt: str,
    existing: dict[str, str] | None = None,
    existing_mode: str | None = None,
) -> str:
    mode = pick_mode(prompt, existing_mode)
    entities = entities_for(mode, prompt)
    api = api_for(mode, entities)
    files: list[dict] = []
    if mode in ("frontend", "fullstack"):
        files += [
            {"path": "frontend/src/App.tsx", "purpose": "Mock 演示占位页"},
            {"path": "frontend/src/styles.css", "purpose": "Mock 演示样式"},
        ]
    if mode in ("backend", "fullstack"):
        files.append({"path": "backend/main.py", "purpose": "Mock 演示后端"})
    plan = {
        "summary": "未配置 LLM_API_KEY，已生成 Mock 演示占位项目（不会根据需求生成真实应用）。",
        "title": extract_title(prompt, mode),
        "mode": mode,
        "reason": "Mock 模式：仅根据需求中的持久化 / 后端关键词选择形态",
        "entities": entities,
        "api": api,
        "files": files,
    }
    return json.dumps(plan, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Mock app sources: clearly labelled placeholder, never a fake product
# ---------------------------------------------------------------------------

DEMO_APP = """import { useEffect, useState } from "react";

const TITLE = __TITLE_JSON__;
const PROMPT = __PROMPT_JSON__;
const HAS_BACKEND = __HAS_BACKEND__;

type Health = "idle" | "checking" | "ok" | "offline";

export default function App() {
  const [health, setHealth] = useState<Health>(HAS_BACKEND ? "checking" : "idle");

  useEffect(() => {
    if (!HAS_BACKEND) return;
    let alive = true;
    fetch("api/health")
      .then((res) => {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(() => {
        if (alive) setHealth("ok");
      })
      .catch(() => {
        if (alive) setHealth("offline");
      });
    return () => {
      alive = false;
    };
  }, []);

  const healthText =
    health === "ok"
      ? "已连接"
      : health === "offline"
        ? "暂未响应"
        : health === "checking"
          ? "检查中…"
          : "无后端";

  return (
    <main className="demo">
      <section className="demo__card">
        <p className="demo__eyebrow">ATOMS · MOCK PREVIEW</p>
        <h1 className="demo__title">{TITLE || "Mock 演示项目"}</h1>
        <p className="demo__lead">
          当前未配置 <code className="demo__code">LLM_API_KEY</code>，这里只展示一个
          Mock 占位页。配置 Key 后，系统会按你的需求生成真实的 React / FastAPI 代码。
        </p>
        <div className="demo__prompt">
          <span className="demo__label">本次需求</span>
          <p className="demo__text">{PROMPT || "（空需求）"}</p>
        </div>
        <p className="demo__status">后端状态：{healthText}</p>
      </section>
    </main>
  );
}
"""

DEMO_CSS = """* { box-sizing: border-box; }

body {
  margin: 0;
  min-height: 100vh;
  font-family: "IBM Plex Sans", "PingFang SC", "Noto Sans CJK SC", system-ui, sans-serif;
  color: rgba(12, 12, 12, 0.95);
  background:
    radial-gradient(900px 600px at 8% -10%, rgba(66, 103, 255, 0.12), transparent 60%),
    radial-gradient(700px 520px at 110% 15%, rgba(56, 225, 198, 0.10), transparent 55%),
    #f6f6f6;
}

.demo {
  display: grid;
  place-items: center;
  min-height: 100vh;
  padding: 32px 16px;
}

.demo__card {
  width: min(640px, 100%);
  padding: 36px;
  border: 1px solid rgba(12, 12, 12, 0.06);
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 24px 70px rgba(18, 24, 32, 0.08);
}

.demo__eyebrow {
  margin: 0 0 10px;
  font-family: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.22em;
  color: #4267ff;
}

.demo__title {
  margin: 0 0 12px;
  font-size: clamp(26px, 5vw, 38px);
  line-height: 1.15;
  letter-spacing: -0.03em;
}

.demo__lead {
  margin: 0 0 22px;
  font-size: 14px;
  line-height: 1.75;
  color: rgba(12, 12, 12, 0.55);
}

.demo__code {
  padding: 1px 5px;
  border-radius: 5px;
  background: rgba(66, 103, 255, 0.08);
  color: #425ce1;
  font-family: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}

.demo__prompt {
  padding: 16px 18px;
  border: 1px solid rgba(12, 12, 12, 0.06);
  border-radius: 14px;
  background: #f6f6f6;
}

.demo__label {
  display: block;
  margin-bottom: 6px;
  font-size: 11px;
  letter-spacing: 0.08em;
  color: rgba(12, 12, 12, 0.3);
}

.demo__text {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: rgba(12, 12, 12, 0.8);
  white-space: pre-wrap;
  word-break: break-word;
}

.demo__status {
  margin: 18px 0 0;
  font-size: 12px;
  color: rgba(12, 12, 12, 0.55);
}

@media (max-width: 768px) {
  .demo {
    padding: 20px 12px;
  }

  .demo__card {
    padding: 24px 20px;
    border-radius: 18px;
  }
}
"""

DEMO_BACKEND = '''import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import connection, init_db

TITLE = __TITLE_PY__


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=TITLE,
    root_path=os.getenv("APP_ROOT_PATH", ""),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "mode": "mock"}


@app.get("/api/items")
async def list_items() -> list[dict]:
    async with connection() as conn:
        cur = await conn.execute(
            "SELECT id, title, created_at FROM items ORDER BY id DESC"
        )
        rows = await cur.fetchall()
    return [dict(row) for row in rows]
'''


def extract_title(prompt: str, mode: str) -> str:
    text = re.sub(
        r"^\s*(帮我|请|我想|想要|做一个|做|生成|开发|设计|搭建|一个|一款|一套)+",
        "",
        prompt.strip(),
    )
    text = re.sub(r"[。！!？?，,；;：:].*$", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    if 2 <= len(text) <= 24:
        return text
    return DEFAULT_TITLE[mode]


def mock_file(
    prompt: str,
    filename: str,
    existing: dict[str, str] | None = None,
    mode: str | None = None,
    title: str | None = None,
) -> str:
    resolved = mode or pick_mode(prompt)
    name = title or extract_title(prompt, resolved)

    if filename == "frontend/src/App.tsx":
        return (
            DEMO_APP.replace("__TITLE_JSON__", json.dumps(name, ensure_ascii=False))
            .replace("__PROMPT_JSON__", json.dumps(prompt.strip()[:400], ensure_ascii=False))
            .replace("__HAS_BACKEND__", "true" if resolved in ("fullstack", "backend") else "false")
        )
    if filename == "frontend/src/styles.css":
        return DEMO_CSS
    if filename == "backend/main.py":
        return DEMO_BACKEND.replace("__TITLE_PY__", json.dumps(name, ensure_ascii=False))

    # Defensive fallbacks for unexpected requested paths.
    return {
        "frontend/src/App.tsx": DEMO_APP.replace(
            "__TITLE_JSON__", json.dumps(name, ensure_ascii=False)
        )
        .replace("__PROMPT_JSON__", json.dumps(prompt.strip()[:400], ensure_ascii=False))
        .replace("__HAS_BACKEND__", "false"),
        "frontend/src/styles.css": DEMO_CSS,
        "backend/main.py": DEMO_BACKEND.replace(
            "__TITLE_PY__", json.dumps(name, ensure_ascii=False)
        ),
    }.get(filename, "")
