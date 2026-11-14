"""SQLite access layer (WAL, short-lived connections)."""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import aiosqlite

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    email           TEXT NOT NULL COLLATE NOCASE,
    name            TEXT,
    password_hash   TEXT,
    provider        TEXT NOT NULL DEFAULT 'email',
    email_verified  INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    last_login_at   TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    user_agent  TEXT,
    ip          TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS email_tokens (
    token_hash  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    kind        TEXT NOT NULL,
    email       TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    used_at     TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_email_tokens_user ON email_tokens(user_id, kind);

CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    user_id     TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    agent       TEXT,
    run_id      TEXT,
    run_index   INTEGER,
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
    run_id      TEXT,
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


async def _migrate(conn) -> None:
    """Add agent/run_id columns to databases created before the agent UI."""
    migrations = {
        "conversations": {"agent": "TEXT", "run_id": "TEXT", "run_index": "INTEGER"},
        "executions": {"run_id": "TEXT"},
        "projects": {"user_id": "TEXT"},
    }
    for table, columns in migrations.items():
        async with conn.execute(f"PRAGMA table_info({table})") as cur:
            existing = {row[1] for row in await cur.fetchall()}
        for name, declaration in columns.items():
            if name not in existing:
                await conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


async def init_db() -> None:
    async with _connect() as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.executescript(SCHEMA)
        await _migrate(conn)
        # This index must be created after _migrate adds projects.user_id to
        # databases created before accounts existed.
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id, created_at)"
        )
        await conn.commit()


# ---------------------------------------------------------------------------
# Users, sessions and one-time email tokens
# ---------------------------------------------------------------------------

async def create_user(
    email: str,
    name: str | None,
    password_hash: str | None,
    provider: str = "email",
    email_verified: bool = False,
) -> dict:
    uid = uuid.uuid4().hex
    stamp = now()
    async with _connect() as conn:
        await conn.execute(
            """
            INSERT INTO users
                (id, email, name, password_hash, provider, email_verified, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (uid, email, name, password_hash, provider, 1 if email_verified else 0, stamp),
        )
        await conn.commit()
    return {
        "id": uid,
        "email": email,
        "name": name,
        "provider": provider,
        "email_verified": 1 if email_verified else 0,
        "created_at": stamp,
    }


async def get_user(uid: str) -> dict | None:
    async with _connect() as conn:
        async with conn.execute(
            "SELECT * FROM users WHERE id = ?", (uid,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_user_by_email(email: str) -> dict | None:
    async with _connect() as conn:
        async with conn.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def update_user_password(uid: str, password_hash: str) -> None:
    async with _connect() as conn:
        await conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, uid)
        )
        await conn.commit()


async def update_user_login(uid: str, name: str | None = None) -> None:
    async with _connect() as conn:
        if name:
            await conn.execute(
                "UPDATE users SET last_login_at = ?, name = COALESCE(name, ?) WHERE id = ?",
                (now(), name, uid),
            )
        else:
            await conn.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?", (now(), uid)
            )
        await conn.commit()


async def mark_email_verified(uid: str) -> None:
    async with _connect() as conn:
        await conn.execute(
            "UPDATE users SET email_verified = 1 WHERE id = ?", (uid,)
        )
        await conn.commit()


async def create_session(
    token_hash: str,
    user_id: str,
    expires_at: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> None:
    async with _connect() as conn:
        await conn.execute(
            """
            INSERT INTO sessions
                (token_hash, user_id, created_at, expires_at, user_agent, ip)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (token_hash, user_id, now(), expires_at, user_agent, ip),
        )
        await conn.commit()


async def get_session_user(token_hash: str) -> dict | None:
    """Return the user for a live session, cleaning an expired row if found."""
    async with _connect() as conn:
        async with conn.execute(
            """
            SELECT u.* FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ?
            """,
            (token_hash, now()),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            await conn.execute(
                "DELETE FROM sessions WHERE token_hash = ?", (token_hash,)
            )
            await conn.commit()
            return None
        return dict(row)


async def delete_session(token_hash: str) -> None:
    async with _connect() as conn:
        await conn.execute(
            "DELETE FROM sessions WHERE token_hash = ?", (token_hash,)
        )
        await conn.commit()


async def delete_user_sessions(uid: str) -> None:
    async with _connect() as conn:
        await conn.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
        await conn.commit()


async def delete_expired_sessions() -> None:
    async with _connect() as conn:
        await conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now(),))
        await conn.commit()


async def create_email_token(
    token_hash: str,
    user_id: str,
    kind: str,
    email: str,
    expires_at: str,
) -> None:
    """Issue one token per kind; older unused tokens are invalidated."""
    async with _connect() as conn:
        await conn.execute(
            "DELETE FROM email_tokens WHERE user_id = ? AND kind = ? AND used_at IS NULL",
            (user_id, kind),
        )
        await conn.execute(
            """
            INSERT INTO email_tokens
                (token_hash, user_id, kind, email, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (token_hash, user_id, kind, email, expires_at, now()),
        )
        await conn.commit()


async def consume_email_token(token_hash: str, kind: str) -> dict | None:
    """Atomically mark a token used and return its row, or None if invalid."""
    async with _connect() as conn:
        cur = await conn.execute(
            """
            UPDATE email_tokens SET used_at = ?
            WHERE token_hash = ? AND kind = ? AND used_at IS NULL AND expires_at > ?
            """,
            (now(), token_hash, kind, now()),
        )
        if cur.rowcount != 1:
            await conn.commit()
            return None
        async with conn.execute(
            "SELECT * FROM email_tokens WHERE token_hash = ?", (token_hash,)
        ) as select:
            row = await select.fetchone()
        await conn.commit()
        return dict(row) if row else None


async def create_project(name: str, user_id: str | None = None) -> dict:
    pid = uuid.uuid4().hex[:12]
    async with _connect() as conn:
        await conn.execute(
            "INSERT INTO projects (id, name, user_id, created_at) VALUES (?, ?, ?, ?)",
            (pid, name, user_id, now()),
        )
        await conn.commit()
    return {"id": pid, "name": name, "user_id": user_id}


async def update_project_name(pid: str, name: str) -> None:
    async with _connect() as conn:
        await conn.execute("UPDATE projects SET name = ? WHERE id = ?", (name, pid))
        await conn.commit()


async def list_projects(user_id: str | None = None) -> list[dict]:
    """List projects, scoped to one owner for every user-facing route."""
    where = "WHERE p.user_id = ?" if user_id is not None else ""
    params: tuple[object, ...] = (user_id,) if user_id is not None else ()
    async with _connect() as conn:
        async with conn.execute(
            f"""
            SELECT p.id, p.name, p.user_id, p.created_at,
                   (SELECT COUNT(*) FROM conversations c WHERE c.project_id = p.id) AS message_count,
                   (SELECT COUNT(DISTINCT filename) FROM artifacts a WHERE a.project_id = p.id) AS artifact_count,
                   (SELECT MAX(a.version) FROM artifacts a WHERE a.project_id = p.id) AS latest_version,
                   EXISTS(SELECT 1 FROM artifacts a WHERE a.project_id = p.id AND a.filename LIKE 'frontend/%') AS has_frontend,
                   EXISTS(SELECT 1 FROM artifacts a WHERE a.project_id = p.id AND a.filename LIKE 'backend/%') AS has_backend
            FROM projects p
            {where}
            ORDER BY p.created_at DESC
            """,
            params,
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_project(pid: str) -> dict | None:
    """Internal lookup. User-facing routes must use ``get_project_for_user``."""
    async with _connect() as conn:
        async with conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_project_for_user(pid: str, user_id: str) -> dict | None:
    async with _connect() as conn:
        async with conn.execute(
            "SELECT * FROM projects WHERE id = ? AND user_id = ?", (pid, user_id)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_state(pid: str) -> dict | None:
    project = await get_project(pid)
    if not project:
        return None
    async with _connect() as conn:
        async with conn.execute(
            "SELECT id, role, content, agent, run_id, run_index, created_at FROM conversations WHERE project_id = ? ORDER BY id",
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
            "SELECT id, agent, step, status, log, run_id, created_at FROM executions WHERE project_id = ? ORDER BY id",
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


async def add_conversation(
    pid: str,
    role: str,
    content: str,
    agent: str | None = None,
    run_id: str | None = None,
    run_index: int | None = None,
) -> int:
    async with _connect() as conn:
        cur = await conn.execute(
            "INSERT INTO conversations (project_id, role, content, agent, run_id, run_index, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (pid, role, content, agent, run_id, run_index, now()),
        )
        await conn.commit()
        return int(cur.lastrowid)


async def recent_conversations(pid: str, limit: int = 8) -> list[dict]:
    async with _connect() as conn:
        async with conn.execute(
            "SELECT id, role, content, agent, run_id, run_index, created_at FROM conversations WHERE project_id = ? ORDER BY id DESC LIMIT ?",
            (pid, limit),
        ) as cur:
            return [dict(r) for r in reversed(await cur.fetchall())]


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


async def add_execution(
    pid: str,
    agent: str,
    step: str,
    status: str,
    log: str,
    run_id: str | None = None,
) -> int:
    async with _connect() as conn:
        cur = await conn.execute(
            "INSERT INTO executions (project_id, agent, step, status, log, run_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (pid, agent, step, status, log, run_id, now()),
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


async def interrupt_running_executions(
    log: str = "生成被中断，请重新发送需求", pid: str | None = None
) -> None:
    """Flush rows left in ``running`` by an interrupted or crashed build."""
    sql = (
        "UPDATE executions SET status = 'warning', "
        "log = CASE WHEN log = '' THEN ? ELSE log END WHERE status = 'running'"
    )
    params: list[object] = [log]
    if pid is not None:
        sql += " AND project_id = ?"
        params.append(pid)
    async with _connect() as conn:
        await conn.execute(sql, params)
        await conn.commit()


async def delete_artifacts_version(pid: str, version: int) -> None:
    """Discard one in-flight version so a failed round cannot leak files."""
    async with _connect() as conn:
        await conn.execute(
            "DELETE FROM artifacts WHERE project_id = ? AND version = ?",
            (pid, version),
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
