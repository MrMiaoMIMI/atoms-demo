"""SQLite access layer (WAL, short-lived connections)."""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import aiosqlite

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversations_project ON conversations(project_id, id);

CREATE TABLE IF NOT EXISTS artifacts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL,
    filename    TEXT NOT NULL,
    content     TEXT NOT NULL,
    version     INTEGER NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_project ON artifacts(project_id, filename, version);

CREATE TABLE IF NOT EXISTS executions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL,
    agent       TEXT NOT NULL,
    step        TEXT NOT NULL,
    status      TEXT NOT NULL,
    log         TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_executions_project ON executions(project_id, id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@asynccontextmanager
async def _connect():
    conn = await aiosqlite.connect(str(DB_PATH))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        await conn.close()


async def init_db() -> None:
    async with _connect() as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.executescript(SCHEMA)
        await conn.commit()


async def create_project(name: str) -> dict:
    pid = uuid.uuid4().hex[:12]
    async with _connect() as conn:
        await conn.execute(
            "INSERT INTO projects (id, name, created_at) VALUES (?, ?, ?)",
            (pid, name, now()),
        )
        await conn.commit()
    return {"id": pid, "name": name}


async def list_projects() -> list[dict]:
    async with _connect() as conn:
        async with conn.execute(
            """
            SELECT p.id, p.name, p.created_at,
                   (SELECT COUNT(*) FROM conversations c WHERE c.project_id = p.id) AS message_count,
                   (SELECT COUNT(DISTINCT filename) FROM artifacts a WHERE a.project_id = p.id) AS artifact_count,
                   (SELECT MAX(a.version) FROM artifacts a WHERE a.project_id = p.id) AS latest_version,
                   EXISTS(SELECT 1 FROM artifacts a WHERE a.project_id = p.id AND a.filename LIKE 'frontend/%') AS has_frontend,
                   EXISTS(SELECT 1 FROM artifacts a WHERE a.project_id = p.id AND a.filename LIKE 'backend/%') AS has_backend
            FROM projects p
            ORDER BY p.created_at DESC
            """
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_project(pid: str) -> dict | None:
    async with _connect() as conn:
        async with conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_state(pid: str) -> dict | None:
    project = await get_project(pid)
    if not project:
        return None
    async with _connect() as conn:
        async with conn.execute(
            "SELECT id, role, content, created_at FROM conversations WHERE project_id = ? ORDER BY id",
            (pid,),
        ) as cur:
            conversations = [dict(r) for r in await cur.fetchall()]
        async with conn.execute(
            """
            SELECT a.filename, a.content, a.version, a.created_at
            FROM artifacts a
            JOIN (
                SELECT filename, MAX(version) AS v
                FROM artifacts WHERE project_id = ?
                GROUP BY filename
            ) m ON a.filename = m.filename AND a.version = m.v
            WHERE a.project_id = ?
            ORDER BY a.filename
            """,
            (pid, pid),
        ) as cur:
            artifacts = [dict(r) for r in await cur.fetchall()]
        async with conn.execute(
            "SELECT id, agent, step, status, log, created_at FROM executions WHERE project_id = ? ORDER BY id",
            (pid,),
        ) as cur:
            executions = [dict(r) for r in await cur.fetchall()]
    return {
        "project": project,
        "conversations": conversations,
        "artifacts": artifacts,
        "executions": executions,
    }


async def latest_artifacts(pid: str) -> dict[str, str]:
    async with _connect() as conn:
        async with conn.execute(
            """
            SELECT a.filename, a.content FROM artifacts a
            JOIN (SELECT filename, MAX(version) AS v FROM artifacts WHERE project_id = ? GROUP BY filename) m
              ON a.filename = m.filename AND a.version = m.v
            WHERE a.project_id = ?
            """,
            (pid, pid),
        ) as cur:
            return {r["filename"]: r["content"] for r in await cur.fetchall()}


async def next_version(pid: str) -> int:
    async with _connect() as conn:
        async with conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM artifacts WHERE project_id = ?", (pid,)
        ) as cur:
            row = await cur.fetchone()
            return int(row[0])


async def add_conversation(pid: str, role: str, content: str) -> int:
    async with _connect() as conn:
        cur = await conn.execute(
            "INSERT INTO conversations (project_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (pid, role, content, now()),
        )
        await conn.commit()
        return int(cur.lastrowid)


async def add_artifact(pid: str, filename: str, content: str, version: int) -> None:
    """Replace-then-insert: a repair pass may rewrite a file within one round."""
    async with _connect() as conn:
        await conn.execute(
            "DELETE FROM artifacts WHERE project_id = ? AND filename = ? AND version = ?",
            (pid, filename, version),
        )
        await conn.execute(
            "INSERT INTO artifacts (project_id, filename, content, version, created_at) VALUES (?, ?, ?, ?, ?)",
            (pid, filename, content, version, now()),
        )
        await conn.commit()


async def add_execution(pid: str, agent: str, step: str, status: str, log: str) -> int:
    async with _connect() as conn:
        cur = await conn.execute(
            "INSERT INTO executions (project_id, agent, step, status, log, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (pid, agent, step, status, log, now()),
        )
        await conn.commit()
        return int(cur.lastrowid)


async def update_execution(exec_id: int, status: str, log: str | None) -> None:
    async with _connect() as conn:
        await conn.execute(
            "UPDATE executions SET status = ?, log = COALESCE(?, log) WHERE id = ?",
            (status, log, exec_id),
        )
        await conn.commit()


async def delete_artifacts_except(pid: str, keep: set[str]) -> None:
    """Drop latest-file rows for paths that no longer exist on disk."""
    async with _connect() as conn:
        if keep:
            placeholders = ",".join("?" for _ in keep)
            await conn.execute(
                f"DELETE FROM artifacts WHERE project_id = ? AND filename NOT IN ({placeholders})",
                (pid, *sorted(keep)),
            )
        else:
            await conn.execute("DELETE FROM artifacts WHERE project_id = ?", (pid,))
        await conn.commit()


async def delete_project(pid: str) -> None:
    async with _connect() as conn:
        for table in ("conversations", "artifacts", "executions", "projects"):
            await conn.execute(f"DELETE FROM {table} WHERE {'id' if table == 'projects' else 'project_id'} = ?", (pid,))
        await conn.commit()
