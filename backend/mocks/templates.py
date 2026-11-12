"""Pre-built templates used by MockLLM.

The mock path must produce exactly the same project shape as the real path:
a Vite + React + TypeScript frontend (``frontend/src/App.tsx`` +
``frontend/src/styles.css``) and, for full-stack requests, a FastAPI backend
using the per-project SQLite file.
"""
from __future__ import annotations

import json
import re

TITLE_JSON = "__TITLE_JSON__"

# ---------------------------------------------------------------------------
# Mock planners
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


def _todo_entity() -> dict:
    return {
        "table": "todos",
        "fields": [
            {"name": "id", "type": "INTEGER", "primary_key": True, "autoincrement": True},
            {"name": "title", "type": "TEXT", "not_null": True},
            {"name": "done", "type": "INTEGER", "not_null": True, "default": 0},
        ],
    }


def _notes_entity() -> dict:
    return {
        "table": "notes",
        "fields": [
            {"name": "id", "type": "INTEGER", "primary_key": True, "autoincrement": True},
            {"name": "content", "type": "TEXT", "not_null": True},
        ],
    }


def entities_for(mode: str, prompt: str) -> list[dict]:
    if mode == "frontend":
        return []
    p = prompt.lower()
    if any(key in p for key in ("笔记", "留言", "note", "备忘")):
        return [_notes_entity()]
    if mode == "backend":
        return [_notes_entity()]
    return [_todo_entity()]


def api_for(mode: str, entities: list[dict]) -> list[dict]:
    if mode == "frontend":
        return []
    table = entities[0]["table"] if entities else "items"
    return [
        {"method": "GET", "path": f"/api/{table}", "description": f"获取 {table} 列表"},
        {"method": "POST", "path": f"/api/{table}", "description": f"新增一条 {table} 记录"},
        {"method": "PUT", "path": f"/api/{table}/{{id}}", "description": f"更新 {table} 记录"},
        {"method": "DELETE", "path": f"/api/{table}/{{id}}", "description": f"删除 {table} 记录"},
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
            {"path": "frontend/src/App.tsx", "purpose": "根组件与页面交互"},
            {"path": "frontend/src/styles.css", "purpose": "视觉样式与响应式布局"},
        ]
    if mode in ("backend", "fullstack"):
        files.append({"path": "backend/main.py", "purpose": "FastAPI 路由与 SQLite 读写"})
    label = {"frontend": "纯前端应用", "fullstack": "前后端一体应用", "backend": "纯后端 API"}[mode]
    plan = {
        "summary": f"基于「{prompt.strip()[:40]}」生成一个{label}（Mock 模板）。",
        "title": extract_title(prompt, mode),
        "mode": mode,
        "reason": "根据需求中的持久化 / 后端关键词判断",
        "entities": entities,
        "api": api,
        "files": files,
    }
    return json.dumps(plan, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Mock app sources
# ---------------------------------------------------------------------------

FULLSTACK_TODO_APP = """import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

interface Todo {
  id: number;
  title: string;
  done: number;
  created_at: string;
}

const BRAND = __TITLE_JSON__;

type Filter = "all" | "active" | "done";

export default function App() {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [draft, setDraft] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function request(path: string, init?: RequestInit) {
    const res = await fetch(path, init);
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(body || "请求失败 (" + res.status + ")");
    }
    return res;
  }

  async function load() {
    try {
      const res = await request("api/todos");
      setTodos(await res.json());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function add(event: FormEvent) {
    event.preventDefault();
    const title = draft.trim();
    if (!title || busy) return;
    setBusy(true);
    try {
      const res = await request("api/todos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      const created = (await res.json()) as Todo;
      setTodos((prev) => [created, ...prev]);
      setDraft("");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "添加失败");
    } finally {
      setBusy(false);
    }
  }

  async function toggle(todo: Todo) {
    try {
      const res = await request("api/todos/" + todo.id, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ done: todo.done ? 0 : 1 }),
      });
      const updated = (await res.json()) as Todo;
      setTodos((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新失败");
    }
  }

  async function remove(todo: Todo) {
    try {
      await request("api/todos/" + todo.id, { method: "DELETE" });
      setTodos((prev) => prev.filter((item) => item.id !== todo.id));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    }
  }

  const visible = useMemo(() => {
    if (filter === "active") return todos.filter((todo) => !todo.done);
    if (filter === "done") return todos.filter((todo) => todo.done);
    return todos;
  }, [filter, todos]);

  const done = todos.filter((todo) => todo.done).length;
  const percent = todos.length ? Math.round((done / todos.length) * 100) : 0;

  return (
    <main className="app">
      <header className="app__header">
        <div>
          <p className="eyebrow">SQLITE PERSISTED</p>
          <h1>{BRAND}</h1>
          <p className="subtitle">任务保存在项目自带的 SQLite 中，刷新或重启都不会丢失。</p>
        </div>
        <div className="progress">
          <div className="progress__bar">
            <span style={{ width: percent + "%" }} />
          </div>
          <strong>{percent}%</strong>
        </div>
      </header>

      <form className="composer" onSubmit={add}>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="添加一个新任务…"
          maxLength={120}
          autoComplete="off"
        />
        <button type="submit" disabled={busy}>
          {busy ? "添加中…" : "添加"}
        </button>
      </form>

      <div className="toolbar">
        <div className="filters">
          {(["all", "active", "done"] as Filter[]).map((item) => (
            <button
              key={item}
              type="button"
              className={"filter" + (filter === item ? " is-active" : "")}
              onClick={() => setFilter(item)}
            >
              {item === "all" ? "全部" : item === "active" ? "进行中" : "已完成"}
            </button>
          ))}
        </div>
        <span className="count">
          {done} / {todos.length} 已完成
        </span>
      </div>

      {error ? <p className="error">{error}</p> : null}
      {loading ? (
        <p className="empty">正在从 SQLite 加载…</p>
      ) : visible.length === 0 ? (
        <p className="empty">这里还没有任务，先添加一个吧。</p>
      ) : (
        <ul className="list">
          {visible.map((todo) => (
            <li key={todo.id} className={"todo" + (todo.done ? " is-done" : "")}>
              <button
                type="button"
                className="todo__check"
                aria-label="切换完成"
                onClick={() => void toggle(todo)}
              />
              <span className="todo__text">{todo.title}</span>
              <button
                type="button"
                className="todo__delete"
                aria-label="删除"
                onClick={() => void remove(todo)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      <footer className="app__footer">
        <span>FastAPI + SQLite · backend/data/app.db</span>
        <button type="button" className="clear" onClick={() => void load()}>
          重新加载
        </button>
      </footer>
    </main>
  );
}
"""

FULLSTACK_TODO_CSS = """* { box-sizing: border-box; }

body {
  margin: 0;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 32px 16px;
  color: #e9edf9;
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  background:
    radial-gradient(900px 600px at 8% -10%, rgba(108, 140, 255, .3), transparent 60%),
    radial-gradient(700px 520px at 110% 15%, rgba(56, 225, 198, .18), transparent 55%),
    #0a0f1f;
}

.app {
  width: min(680px, 100%);
  padding: 34px;
  border: 1px solid rgba(255, 255, 255, .09);
  border-radius: 26px;
  background: linear-gradient(180deg, rgba(255, 255, 255, .07), rgba(255, 255, 255, .02));
  box-shadow: 0 32px 90px rgba(0, 0, 0, .5);
  backdrop-filter: blur(16px);
}

.app__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.eyebrow { margin: 0 0 10px; font-size: 11px; letter-spacing: .26em; color: #7f8bab; font-weight: 600; }
h1 { margin: 0; font-size: clamp(24px, 4vw, 32px); letter-spacing: -.02em; }
.subtitle { margin: 8px 0 0; color: #8f98b3; font-size: 14px; }

.progress { flex: none; width: 104px; display: grid; gap: 8px; justify-items: end; }
.progress__bar { width: 100%; height: 8px; border-radius: 999px; background: rgba(255, 255, 255, .08); overflow: hidden; }
.progress__bar span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #6c8cff, #38e1c6); transition: width .35s ease; }
.progress strong { font-size: 13px; color: #aab4cf; }

.composer { display: flex; gap: 10px; margin: 28px 0 22px; }
.composer input {
  flex: 1;
  min-width: 0;
  padding: 14px 16px;
  font-size: 15px;
  color: inherit;
  background: rgba(8, 13, 28, .72);
  border: 1px solid rgba(255, 255, 255, .1);
  border-radius: 14px;
  outline: none;
  transition: border-color .2s, box-shadow .2s;
}
.composer input::placeholder { color: #66708c; }
.composer input:focus { border-color: #6c8cff; box-shadow: 0 0 0 4px rgba(108, 140, 255, .16); }
.composer button {
  padding: 0 22px;
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  border: 0;
  border-radius: 14px;
  cursor: pointer;
  background: linear-gradient(135deg, #6c8cff, #8f6cff);
  box-shadow: 0 10px 26px rgba(108, 140, 255, .35);
  transition: transform .15s, box-shadow .2s;
}
.composer button:hover { transform: translateY(-1px); box-shadow: 0 14px 30px rgba(108, 140, 255, .45); }
.composer button:disabled { opacity: .6; cursor: wait; }

.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.filters { display: flex; gap: 6px; padding: 4px; border-radius: 12px; background: rgba(255, 255, 255, .04); }
.filter {
  padding: 7px 14px;
  font-size: 13px;
  color: #8f98b3;
  background: transparent;
  border: 0;
  border-radius: 9px;
  cursor: pointer;
  transition: background .2s, color .2s;
}
.filter:hover { color: #d7ddf0; }
.filter.is-active { color: #0a0f1f; background: #e9edf9; font-weight: 600; }
.count { font-size: 12px; color: #737d99; }

.error {
  margin: 16px 0 0;
  padding: 10px 14px;
  font-size: 12px;
  color: #ffc2cb;
  border: 1px solid rgba(255, 107, 129, .3);
  border-radius: 10px;
  background: rgba(255, 107, 129, .1);
}

.list { list-style: none; margin: 18px 0 0; padding: 0; display: grid; gap: 9px; }
.todo {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 14px 16px;
  border: 1px solid rgba(255, 255, 255, .07);
  border-radius: 14px;
  background: rgba(255, 255, 255, .025);
  animation: rise .28s ease both;
}
@keyframes rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

.todo__check {
  flex: none;
  width: 22px;
  height: 22px;
  border-radius: 7px;
  border: 1.5px solid rgba(255, 255, 255, .22);
  background: transparent;
  cursor: pointer;
  position: relative;
  transition: background .2s, border-color .2s;
}
.todo__check::after {
  content: "";
  position: absolute;
  left: 7px;
  top: 3px;
  width: 6px;
  height: 11px;
  border: solid #08111f;
  border-width: 0 2px 2px 0;
  transform: rotate(42deg) scale(0);
  transition: transform .18s ease;
}
.todo.is-done .todo__check { background: #38e1c6; border-color: #38e1c6; }
.todo.is-done .todo__check::after { transform: rotate(42deg) scale(1); }

.todo__text { flex: 1; font-size: 15px; line-height: 1.45; word-break: break-word; }
.todo.is-done .todo__text { color: #66708c; text-decoration: line-through; }

.todo__delete {
  flex: none;
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  color: #6b7490;
  font-size: 17px;
  background: transparent;
  border: 0;
  border-radius: 8px;
  cursor: pointer;
  opacity: 0;
  transition: opacity .15s, color .15s, background .15s;
}
.todo:hover .todo__delete { opacity: 1; }
.todo__delete:hover { color: #ff6b81; background: rgba(255, 107, 129, .1); }

.empty { margin: 30px 0; text-align: center; color: #66708c; font-size: 14px; }

.app__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 22px;
  padding-top: 18px;
  border-top: 1px solid rgba(255, 255, 255, .07);
  font-size: 12px;
  color: #66708c;
}
.clear { color: #8f98b3; background: transparent; border: 0; font-size: 12px; cursor: pointer; }
.clear:hover { color: #ff9bab; }

@media (max-width: 560px) {
  .app { padding: 24px 20px; border-radius: 20px; }
  .app__header { flex-direction: column; align-items: stretch; }
  .progress { width: 100%; justify-items: stretch; }
  .composer { flex-direction: column; }
  .composer button { padding: 12px; }
}
"""

FULLSTACK_TODO_BACKEND = '''import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import connection, init_db

TITLE = __TITLE_PY__


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(title=TITLE, root_path=os.getenv("APP_ROOT_PATH", ""), lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TodoIn(BaseModel):
    title: str


class TodoPatch(BaseModel):
    title: str | None = None
    done: int | None = None


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "service": "todos", "database": "sqlite"}


@app.get("/api/todos")
async def list_todos() -> list[dict]:
    async with connection() as conn:
        cur = await conn.execute(
            "SELECT id, title, done, created_at FROM todos ORDER BY id DESC"
        )
        return [dict(row) for row in await cur.fetchall()]


@app.post("/api/todos", status_code=201)
async def create_todo(payload: TodoIn) -> dict:
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title 不能为空")
    async with connection() as conn:
        cur = await conn.execute(
            "INSERT INTO todos (title, done, created_at) VALUES (?, 0, ?)",
            (title, now()),
        )
        await conn.commit()
        row = await (
            await conn.execute(
                "SELECT id, title, done, created_at FROM todos WHERE id = ?",
                (cur.lastrowid,),
            )
        ).fetchone()
        return dict(row)


@app.put("/api/todos/{todo_id}")
async def update_todo(todo_id: int, payload: TodoPatch) -> dict:
    async with connection() as conn:
        row = await (
            await conn.execute("SELECT id, title, done FROM todos WHERE id = ?", (todo_id,))
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="任务不存在")
        title = payload.title.strip() if payload.title is not None else row["title"]
        done = int(payload.done) if payload.done is not None else row["done"]
        await conn.execute(
            "UPDATE todos SET title = ?, done = ? WHERE id = ?", (title, done, todo_id)
        )
        await conn.commit()
        updated = await (
            await conn.execute(
                "SELECT id, title, done, created_at FROM todos WHERE id = ?", (todo_id,)
            )
        ).fetchone()
        return dict(updated)


@app.delete("/api/todos/{todo_id}")
async def delete_todo(todo_id: int) -> dict:
    async with connection() as conn:
        cur = await conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        await conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="任务不存在")
    return {"ok": True}
'''

NOTES_BACKEND = '''import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import connection, init_db

TITLE = __TITLE_PY__


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(title=TITLE, root_path=os.getenv("APP_ROOT_PATH", ""), lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class NoteIn(BaseModel):
    content: str


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "service": "notes", "database": "sqlite"}


@app.get("/api/notes")
async def list_notes() -> list[dict]:
    async with connection() as conn:
        cur = await conn.execute(
            "SELECT id, content, created_at FROM notes ORDER BY id DESC"
        )
        return [dict(row) for row in await cur.fetchall()]


@app.post("/api/notes", status_code=201)
async def create_note(payload: NoteIn) -> dict:
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="content 不能为空")
    async with connection() as conn:
        cur = await conn.execute(
            "INSERT INTO notes (content, created_at) VALUES (?, ?)", (content, now())
        )
        await conn.commit()
        row = await (
            await conn.execute(
                "SELECT id, content, created_at FROM notes WHERE id = ?", (cur.lastrowid,)
            )
        ).fetchone()
        return dict(row)


@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: int) -> dict:
    async with connection() as conn:
        cur = await conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        await conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True}
'''

LANDING_APP = """import { useEffect, useState } from "react";

const BRAND = __TITLE_JSON__;

const FEATURES = [
  { icon: "✦", title: "自然语言生成", body: "描述你的需求，自动拆解页面结构与交互，不必从空白文件开始。" },
  { icon: "◈", title: "实时预览", body: "生成的同时即可预览，随时对话修改，所见即所得。" },
  { icon: "◇", title: "一键上线", body: "生成完成即拥有独立访问地址，分享给任何人即可查看。" },
];

const STATS = [
  { value: 128, label: "个项目已上线" },
  { value: 96, label: "% 用户满意度" },
  { value: 43, label: "秒平均生成时间" },
];

export default function App() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(true), 60);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div className="page">
      <div className="glow glow--a" />
      <div className="glow glow--b" />

      <header className="nav">
        <a className="brand" href="#top">
          <span className="brand__mark">◆</span>
          <span>{BRAND}</span>
        </a>
        <nav className="nav__links">
          <a href="#features">特性</a>
          <a href="#showcase">案例</a>
          <a href="#cta">开始</a>
        </nav>
        <a className="nav__cta" href="#cta">免费试用</a>
      </header>

      <main id="top">
        <section className={"hero" + (visible ? " is-visible" : "")}>
          <p className="pill">全新 2.0 版本 · 由 AI 驱动</p>
          <h1>
            把想法，<span className="grad">变成产品</span>。
          </h1>
          <p className="hero__desc">
            从一句话描述到可上线的网页应用，自动完成规划、编码与发布。无需样板代码，无需等待。
          </p>
          <div className="hero__actions">
            <a className="btn btn--primary" href="#cta">立即开始 <span>→</span></a>
            <a className="btn btn--ghost" href="#features">看看能做什么</a>
          </div>
          <div className="stats">
            {STATS.map((stat) => (
              <div className="stat" key={stat.label}>
                <strong>{stat.value}</strong>
                <span>{stat.label}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="features" id="features">
          <p className="section__eyebrow">FEATURES</p>
          <h2>从灵感到上线，只需要一步</h2>
          <div className="grid">
            {FEATURES.map((feature, index) => (
              <article
                className={"card" + (visible ? " is-visible" : "")}
                style={{ transitionDelay: index * 90 + "ms" }}
                key={feature.title}
              >
                <div className="card__icon">{feature.icon}</div>
                <h3>{feature.title}</h3>
                <p>{feature.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="showcase" id="showcase">
          <div className="showcase__copy">
            <p className="section__eyebrow">SHOWCASE</p>
            <h2>一个下午，上线三个产品</h2>
            <p>落地页、数据看板、内部工具——用同一套工作流快速验证你的想法。</p>
            <a className="btn btn--primary" href="#cta">创建你的第一个项目 <span>→</span></a>
          </div>
          <div className="showcase__mock">
            <div className="mock__bar"><i /><i /><i /></div>
            <div className="mock__body">
              <div className="mock__side" />
              <div className="mock__main">
                <div className="mock__line mock__line--lg" />
                <div className="mock__line" />
                <div className="mock__cards"><span /><span /><span /></div>
              </div>
            </div>
          </div>
        </section>

        <section className="cta" id="cta">
          <h2>准备好构建你的下一个产品了吗？</h2>
          <p>打开页面即可使用，无需注册。</p>
          <a className="btn btn--primary" href="#top">开始构建 <span>→</span></a>
        </section>
      </main>

      <footer className="footer">
        <span>© 2026 {BRAND}</span>
        <span>Built with Atoms Demo</span>
      </footer>
    </div>
  );
}
"""

LANDING_CSS = """* { box-sizing: border-box; }
html { scroll-behavior: smooth; }

body {
  margin: 0;
  color: #eef1fb;
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  background: #070b16;
  overflow-x: hidden;
}

a { color: inherit; text-decoration: none; }
.page { position: relative; min-height: 100vh; }

.glow { position: fixed; border-radius: 50%; filter: blur(120px); pointer-events: none; z-index: 0; }
.glow--a { width: 520px; height: 520px; top: -180px; left: -120px; background: rgba(108, 140, 255, .32); }
.glow--b { width: 460px; height: 460px; top: 30%; right: -180px; background: rgba(56, 225, 198, .16); }

.nav {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px clamp(20px, 5vw, 72px);
  background: rgba(7, 11, 22, .72);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(255, 255, 255, .06);
}
.brand { display: flex; align-items: center; gap: 10px; font-weight: 700; letter-spacing: -.01em; }
.brand__mark { color: #6c8cff; }
.nav__links { display: flex; gap: 28px; font-size: 14px; color: #9aa4bf; }
.nav__links a:hover { color: #fff; }
.nav__cta {
  padding: 9px 18px;
  font-size: 14px;
  font-weight: 600;
  border: 1px solid rgba(255, 255, 255, .16);
  border-radius: 999px;
  transition: background .2s, border-color .2s;
}
.nav__cta:hover { background: rgba(255, 255, 255, .08); border-color: rgba(255, 255, 255, .3); }

main { position: relative; z-index: 1; padding: 0 clamp(20px, 5vw, 72px); }

.hero { max-width: 920px; margin: 0 auto; padding: clamp(70px, 12vw, 130px) 0 90px; text-align: center; opacity: 0; transform: translateY(14px); transition: opacity .6s ease, transform .6s ease; }
.hero.is-visible { opacity: 1; transform: none; }
.pill {
  display: inline-block;
  margin: 0 0 26px;
  padding: 7px 14px;
  font-size: 12px;
  color: #aab4cf;
  border: 1px solid rgba(255, 255, 255, .12);
  border-radius: 999px;
  background: rgba(255, 255, 255, .04);
}
h1 {
  margin: 0;
  font-size: clamp(42px, 8vw, 82px);
  line-height: 1.05;
  letter-spacing: -.04em;
}
.grad {
  background: linear-gradient(100deg, #7d9bff, #38e1c6 55%, #c38bff);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.hero__desc {
  max-width: 580px;
  margin: 26px auto 0;
  font-size: clamp(15px, 2vw, 18px);
  line-height: 1.75;
  color: #98a2bd;
}
.hero__actions { display: flex; justify-content: center; flex-wrap: wrap; gap: 12px; margin-top: 38px; }
.btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 14px 26px;
  font-size: 15px;
  font-weight: 600;
  border-radius: 14px;
  transition: transform .18s, box-shadow .2s, background .2s;
}
.btn:hover { transform: translateY(-2px); }
.btn--primary {
  color: #06101f;
  background: linear-gradient(135deg, #8fa8ff, #38e1c6);
  box-shadow: 0 16px 40px rgba(108, 140, 255, .35);
}
.btn--primary:hover { box-shadow: 0 20px 50px rgba(108, 140, 255, .5); }
.btn--ghost { color: #dfe4f5; background: rgba(255, 255, 255, .06); border: 1px solid rgba(255, 255, 255, .12); }
.btn--ghost:hover { background: rgba(255, 255, 255, .1); }

.stats { display: flex; justify-content: center; flex-wrap: wrap; gap: clamp(28px, 6vw, 72px); margin-top: 64px; }
.stat { display: grid; gap: 6px; }
.stat strong { font-size: clamp(26px, 4vw, 36px); letter-spacing: -.02em; }
.stat span { font-size: 13px; color: #7c87a4; }

section { max-width: 1080px; margin: 0 auto; padding: 80px 0; }
.section__eyebrow { margin: 0 0 12px; font-size: 11px; letter-spacing: .28em; color: #6c8cff; font-weight: 700; }
h2 { margin: 0 0 14px; font-size: clamp(26px, 4vw, 40px); letter-spacing: -.03em; }
section > p { color: #98a2bd; line-height: 1.7; }

.features { text-align: center; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 18px; margin-top: 46px; text-align: left; }
.card {
  padding: 28px;
  border: 1px solid rgba(255, 255, 255, .08);
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255, 255, 255, .05), rgba(255, 255, 255, .015));
  opacity: 0;
  transform: translateY(16px);
  transition: opacity .55s ease, transform .55s ease, border-color .25s;
}
.card.is-visible { opacity: 1; transform: none; }
.card:hover { border-color: rgba(108, 140, 255, .4); }
.card__icon {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  margin-bottom: 18px;
  font-size: 18px;
  color: #8fa8ff;
  background: rgba(108, 140, 255, .12);
  border-radius: 12px;
}
.card h3 { margin: 0 0 10px; font-size: 17px; }
.card p { margin: 0; font-size: 14px; line-height: 1.7; color: #8b96b2; }

.showcase { display: grid; grid-template-columns: 1fr 1.1fr; align-items: center; gap: 48px; }
.showcase__copy p { max-width: 420px; }
.showcase__copy .btn { margin-top: 26px; }
.showcase__mock {
  border: 1px solid rgba(255, 255, 255, .1);
  border-radius: 20px;
  overflow: hidden;
  background: #0d1424;
  box-shadow: 0 40px 90px rgba(0, 0, 0, .5);
  transform: perspective(1000px) rotateY(-6deg) rotateX(2deg);
}
.mock__bar { display: flex; gap: 7px; padding: 13px 16px; border-bottom: 1px solid rgba(255, 255, 255, .07); }
.mock__bar i { width: 10px; height: 10px; border-radius: 50%; background: rgba(255, 255, 255, .16); }
.mock__bar i:first-child { background: #ff6b81; }
.mock__bar i:nth-child(2) { background: #ffd166; }
.mock__bar i:nth-child(3) { background: #38e1c6; }
.mock__body { display: flex; min-height: 260px; }
.mock__side { width: 90px; background: rgba(255, 255, 255, .025); border-right: 1px solid rgba(255, 255, 255, .06); }
.mock__main { flex: 1; padding: 24px; display: grid; align-content: start; gap: 14px; }
.mock__line { height: 10px; border-radius: 6px; background: rgba(255, 255, 255, .08); }
.mock__line--lg { width: 58%; height: 16px; background: linear-gradient(90deg, rgba(108, 140, 255, .55), rgba(56, 225, 198, .4)); }
.mock__cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 14px; }
.mock__cards span { height: 70px; border-radius: 12px; background: rgba(255, 255, 255, .05); border: 1px solid rgba(255, 255, 255, .06); }

.cta {
  text-align: center;
  padding: 90px 24px;
  margin-bottom: 40px;
  border: 1px solid rgba(255, 255, 255, .09);
  border-radius: 28px;
  background:
    radial-gradient(600px 240px at 50% 0, rgba(108, 140, 255, .22), transparent 70%),
    rgba(255, 255, 255, .02);
}
.cta .btn { margin-top: 26px; }

.footer {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 28px clamp(20px, 5vw, 72px);
  font-size: 12px;
  color: #66708c;
  border-top: 1px solid rgba(255, 255, 255, .06);
}

@media (max-width: 820px) {
  .nav__links { display: none; }
  .showcase { grid-template-columns: 1fr; }
  .showcase__mock { transform: none; }
  section { padding: 56px 0; }
}
"""


# ---------------------------------------------------------------------------
# Prompt helpers + rendering
# ---------------------------------------------------------------------------

PALETTES = {
    "暖色": ("#ff9f68", "#ffd166", "#ff7a8f"),
    "橙色": ("#ff9f68", "#ffd166", "#ff7a8f"),
    "红色": ("#ff7a8f", "#ffb199", "#ff5470"),
    "绿色": ("#34d399", "#a3e635", "#22c55e"),
    "紫色": ("#a78bfa", "#f0abfc", "#8b5cf6"),
}
DEFAULT_PALETTE = ("#6c8cff", "#38e1c6", "#8f6cff")
BASE_ACCENT = "#6c8cff"
BASE_ACCENT_SOFT = "#8fa8ff"
BASE_MINT = "#38e1c6"
BASE_VIOLET = "#8f6cff"
BASE_ACCENT_RGB = "108, 140, 255"
BASE_MINT_RGB = "56, 225, 198"


def _hex_rgb(color: str) -> str:
    value = color.lstrip("#")
    return f"{int(value[0:2], 16)}, {int(value[2:4], 16)}, {int(value[4:6], 16)}"


def _apply_palette(content: str, prompt: str) -> str:
    palette = next((value for key, value in PALETTES.items() if key in prompt), None)
    if not palette:
        return content
    accent, accent2, accent3 = palette
    replacements = {
        BASE_ACCENT: accent,
        BASE_ACCENT_SOFT: accent,
        BASE_MINT: accent2,
        BASE_VIOLET: accent3,
        BASE_ACCENT_RGB: _hex_rgb(accent),
        BASE_MINT_RGB: _hex_rgb(accent2),
    }
    for old, new in replacements.items():
        content = content.replace(old, new)
    return content


DEFAULT_TITLE = {
    "frontend": "Nova · 用 AI 构建产品",
    "fullstack": "我的待办清单",
    "backend": "Notes API",
}


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
    title_json = json.dumps(name, ensure_ascii=False)
    title_py = json.dumps(name, ensure_ascii=False)

    if resolved == "fullstack" and filename == "frontend/src/App.tsx":
        return _apply_palette(FULLSTACK_TODO_APP.replace(TITLE_JSON, title_json), prompt)
    if resolved == "fullstack" and filename == "frontend/src/styles.css":
        return _apply_palette(FULLSTACK_TODO_CSS, prompt)
    if resolved == "fullstack" and filename == "backend/main.py":
        return FULLSTACK_TODO_BACKEND.replace("__TITLE_PY__", title_py)
    if resolved == "frontend" and filename == "frontend/src/App.tsx":
        return _apply_palette(LANDING_APP.replace(TITLE_JSON, title_json), prompt)
    if resolved == "frontend" and filename == "frontend/src/styles.css":
        return _apply_palette(LANDING_CSS, prompt)
    if resolved == "backend" and filename == "backend/main.py":
        return NOTES_BACKEND.replace("__TITLE_PY__", title_py)

    # Defensive fallbacks for unexpected requested paths.
    return {
        "frontend/src/App.tsx": _apply_palette(
            LANDING_APP.replace(TITLE_JSON, title_json), prompt
        ),
        "frontend/src/styles.css": _apply_palette(LANDING_CSS, prompt),
        "backend/main.py": NOTES_BACKEND.replace("__TITLE_PY__", title_py),
    }.get(filename, "")
