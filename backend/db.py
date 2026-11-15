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
    created_at  TEXT NOT NULL,
    built_version     INTEGER,
    built_at          TEXT,
    published_version INTEGER,
    published_at      TEXT,
    paused            INTEGER NOT NULL DEFAULT 0,
    description       TEXT,
    category          TEXT NOT NULL DEFAULT '其他',
    view_count        INTEGER NOT NULL DEFAULT 0,
    cover_version     INTEGER,
    cover_at          TEXT,
    build_cover_version INTEGER,
    build_cover_at      TEXT
);

CREATE TABLE IF NOT EXISTS project_saves (
    user_id    TEXT NOT NULL,
    project_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, project_id)
);
CREATE INDEX IF NOT EXISTS idx_project_saves_project ON project_saves(project_id);

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
    deleted     INTEGER NOT NULL DEFAULT 0,
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
    tool        TEXT,
    target      TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_executions_project ON executions(project_id, id);

CREATE TABLE IF NOT EXISTS file_changes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   TEXT NOT NULL,
    version      INTEGER NOT NULL,
    run_id       TEXT,
    agent        TEXT,
    execution_id INTEGER,
    filename     TEXT NOT NULL,
    change_type  TEXT NOT NULL,
    diff         TEXT NOT NULL DEFAULT '',
    additions    INTEGER NOT NULL DEFAULT 0,
    deletions    INTEGER NOT NULL DEFAULT 0,
    rolled_back  INTEGER NOT NULL DEFAULT 0,
    truncated    INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_file_changes_project ON file_changes(project_id, id);
CREATE INDEX IF NOT EXISTS idx_file_changes_exec ON file_changes(project_id, execution_id);
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
        "executions": {"run_id": "TEXT", "tool": "TEXT", "target": "TEXT"},
        "artifacts": {"deleted": "INTEGER NOT NULL DEFAULT 0"},
        "projects": {
            "user_id": "TEXT",
            "built_version": "INTEGER",
            "built_at": "TEXT",
            "published_version": "INTEGER",
            "published_at": "TEXT",
            "paused": "INTEGER NOT NULL DEFAULT 0",
            "description": "TEXT",
            "category": "TEXT NOT NULL DEFAULT '其他'",
            "view_count": "INTEGER NOT NULL DEFAULT 0",
            "cover_version": "INTEGER",
            "cover_at": "TEXT",
            "build_cover_version": "INTEGER",
            "build_cover_at": "TEXT",
        },
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
        # Discover only ever reads online projects, newest first.
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_projects_discover "
            "ON projects(paused, published_at DESC)"
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


def decorate_project(project: dict) -> dict:
    """Attach derived lifecycle fields used by every project response.

    ``built_version`` is only written after a full successful build, so a
    failed or rolled-back round can never make a project look publishable.
    """
    built = project.get("built_version")
    published = project.get("published_version")
    if built is None:
        status = "draft"
    elif published is None:
        status = "unpublished"
    elif project.get("paused"):
        status = "paused"
    else:
        status = "online"
    project["status"] = status
    project["paused"] = bool(project.get("paused"))
    project["has_changes"] = bool(
        published is not None and built is not None and built > published
    )
    project["published_url"] = (
        f"/s/{project['id']}/" if published is not None else None
    )
    return project


async def mark_built(pid: str, version: int) -> None:
    """Record the last version whose preview and runtime both came up."""
    async with _connect() as conn:
        await conn.execute(
            "UPDATE projects SET built_version = ?, built_at = ? WHERE id = ?",
            (version, now(), pid),
        )
        await conn.commit()


async def mark_published(pid: str, version: int) -> None:
    """Point the public snapshot at a successfully built version.

    ``paused`` is intentionally preserved: updating a paused site keeps it
    paused until the owner explicitly resumes it.
    """
    async with _connect() as conn:
        await conn.execute(
            "UPDATE projects SET published_version = ?, published_at = ? WHERE id = ?",
            (version, now(), pid),
        )
        await conn.commit()


async def set_project_paused(pid: str, paused: bool) -> None:
    async with _connect() as conn:
        await conn.execute(
            "UPDATE projects SET paused = ? WHERE id = ?",
            (1 if paused else 0, pid),
        )
        await conn.commit()


async def list_projects(user_id: str | None = None) -> list[dict]:
    """List projects, scoped to one owner for every user-facing route."""
    where = "WHERE p.user_id = ?" if user_id is not None else ""
    params: tuple[object, ...] = (user_id,) if user_id is not None else ()
    async with _connect() as conn:
        async with conn.execute(
            f"""
            SELECT p.id, p.name, p.user_id, p.created_at,
                   p.built_version, p.built_at,
                   p.published_version, p.published_at, p.paused,
                   p.description, p.category, p.view_count,
                   p.cover_version, p.cover_at, p.build_cover_version, p.build_cover_at,
                   (SELECT COUNT(*) FROM conversations c WHERE c.project_id = p.id) AS message_count,
                   (
                       SELECT COUNT(*) FROM artifacts a
                       JOIN (
                           SELECT filename, MAX(version) AS v FROM artifacts
                           WHERE project_id = p.id GROUP BY filename
                       ) m ON a.filename = m.filename AND a.version = m.v
                       WHERE a.project_id = p.id AND a.deleted = 0
                   ) AS artifact_count,
                   (SELECT MAX(a.version) FROM artifacts a WHERE a.project_id = p.id) AS latest_version,
                   EXISTS(
                       SELECT 1 FROM artifacts a
                       JOIN (
                           SELECT filename, MAX(version) AS v FROM artifacts
                           WHERE project_id = p.id GROUP BY filename
                       ) m ON a.filename = m.filename AND a.version = m.v
                       WHERE a.project_id = p.id AND a.deleted = 0
                         AND a.filename LIKE 'frontend/%'
                   ) AS has_frontend,
                   EXISTS(
                       SELECT 1 FROM artifacts a
                       JOIN (
                           SELECT filename, MAX(version) AS v FROM artifacts
                           WHERE project_id = p.id GROUP BY filename
                       ) m ON a.filename = m.filename AND a.version = m.v
                       WHERE a.project_id = p.id AND a.deleted = 0
                         AND a.filename LIKE 'backend/%'
                   ) AS has_backend
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


# ---------------------------------------------------------------------------
# Discover (read-only across users, but only for published, non-paused apps)
# ---------------------------------------------------------------------------

# ``?`` order: the viewer id for the ``saved`` flag comes first, before the
# WHERE placeholders. Callers must keep that order.
_DISCOVER_SELECT = """
    SELECT p.id, p.name, p.created_at,
           COALESCE(p.description, '') AS description,
           COALESCE(NULLIF(p.category, ''), '其他') AS category,
           COALESCE(p.view_count, 0) AS view_count,
           p.published_version, p.published_at,
           p.cover_version, p.cover_at,
           COALESCE(
               NULLIF(TRIM(u.name), ''),
               '用户 ' || substr(COALESCE(u.id, p.user_id, 'anon'), 1, 4)
           ) AS author_name,
           CASE
               WHEN TRIM(COALESCE(u.name, '')) = ''
                   THEN upper(substr(COALESCE(u.id, p.user_id, 'a'), 1, 1))
               ELSE upper(substr(TRIM(u.name), 1, 1))
           END AS author_initial,
           EXISTS(
               SELECT 1 FROM project_saves s2
               WHERE s2.project_id = p.id AND s2.user_id = ?
           ) AS saved,
           EXISTS(
               SELECT 1 FROM artifacts a
               WHERE a.project_id = p.id AND a.filename LIKE 'frontend/%'
           ) AS has_frontend,
           EXISTS(
               SELECT 1 FROM artifacts a
               WHERE a.project_id = p.id AND a.filename LIKE 'backend/%'
           ) AS has_backend
    FROM projects p
    LEFT JOIN users u ON u.id = p.user_id
"""


async def list_discover(
    viewer_id: str,
    *,
    sort: str = "latest",
    category: str | None = None,
    query: str | None = None,
    saved: bool = False,
    limit: int = 24,
    offset: int = 0,
) -> list[dict]:
    """List other users' online apps. The viewer's own projects are excluded."""
    where = [
        "p.published_version IS NOT NULL",
        "p.paused = 0",
        "p.user_id != ?",
    ]
    params: list[object] = [viewer_id, viewer_id]
    if category and category != "全部":
        where.append("COALESCE(NULLIF(p.category, ''), '其他') = ?")
        params.append(category)
    keyword = (query or "").strip()
    if keyword:
        where.append(
            "(instr(lower(p.name), lower(?)) > 0 "
            "OR instr(lower(COALESCE(p.description, '')), lower(?)) > 0)"
        )
        params.extend([keyword, keyword])
    if saved:
        where.append(
            "EXISTS (SELECT 1 FROM project_saves s3 "
            "WHERE s3.project_id = p.id AND s3.user_id = ?)"
        )
        params.append(viewer_id)

    order = (
        "p.view_count DESC, p.published_at DESC, p.created_at DESC"
        if sort == "popular"
        else "p.published_at DESC, p.created_at DESC"
    )
    page_size = max(1, min(limit, 60))
    # Fetch one extra row so the caller can report has_more accurately.
    params.extend([page_size + 1, max(0, offset)])
    sql = f"{_DISCOVER_SELECT} WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ? OFFSET ?"
    async with _connect() as conn:
        async with conn.execute(sql, params) as cur:
            return [dict(row) for row in await cur.fetchall()]


async def get_discover(pid: str, viewer_id: str) -> dict | None:
    sql = (
        f"{_DISCOVER_SELECT} "
        "WHERE p.id = ? AND p.published_version IS NOT NULL "
        "AND p.paused = 0 AND p.user_id != ?"
    )
    async with _connect() as conn:
        async with conn.execute(sql, (viewer_id, pid, viewer_id)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def list_related(
    pid: str, viewer_id: str, category: str, limit: int = 4
) -> list[dict]:
    """Other users' online apps, same category first, then popular/newest."""
    sql = (
        f"{_DISCOVER_SELECT} "
        "WHERE p.id != ? AND p.published_version IS NOT NULL "
        "AND p.paused = 0 AND p.user_id != ? "
        "ORDER BY (COALESCE(NULLIF(p.category, ''), '其他') = ?) DESC, "
        "p.view_count DESC, p.published_at DESC LIMIT ?"
    )
    async with _connect() as conn:
        async with conn.execute(
            sql, (viewer_id, pid, viewer_id, category, max(1, min(limit, 12)))
        ) as cur:
            return [dict(row) for row in await cur.fetchall()]


async def increment_view(pid: str) -> int:
    async with _connect() as conn:
        await conn.execute(
            "UPDATE projects SET view_count = COALESCE(view_count, 0) + 1 "
            "WHERE id = ? AND published_version IS NOT NULL AND paused = 0",
            (pid,),
        )
        await conn.commit()
        async with conn.execute(
            "SELECT COALESCE(view_count, 0) FROM projects WHERE id = ?", (pid,)
        ) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row else 0


async def save_project(user_id: str, pid: str) -> None:
    async with _connect() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO project_saves (user_id, project_id, created_at) "
            "VALUES (?, ?, ?)",
            (user_id, pid, now()),
        )
        await conn.commit()


async def unsave_project(user_id: str, pid: str) -> None:
    async with _connect() as conn:
        await conn.execute(
            "DELETE FROM project_saves WHERE user_id = ? AND project_id = ?",
            (user_id, pid),
        )
        await conn.commit()


async def update_project_meta(pid: str, description: str, category: str) -> None:
    async with _connect() as conn:
        await conn.execute(
            "UPDATE projects SET description = ?, category = ? WHERE id = ?",
            (description, category, pid),
        )
        await conn.commit()


async def set_project_cover(pid: str, version: int) -> None:
    async with _connect() as conn:
        await conn.execute(
            "UPDATE projects SET cover_version = ?, cover_at = ? WHERE id = ?",
            (version, now(), pid),
        )
        await conn.commit()


async def set_project_build_cover(pid: str, version: int) -> None:
    async with _connect() as conn:
        await conn.execute(
            "UPDATE projects SET build_cover_version = ?, build_cover_at = ? "
            "WHERE id = ?",
            (version, now(), pid),
        )
        await conn.commit()


async def first_user_message(pid: str) -> str:
    async with _connect() as conn:
        async with conn.execute(
            "SELECT content FROM conversations "
            "WHERE project_id = ? AND role = 'user' ORDER BY id LIMIT 1",
            (pid,),
        ) as cur:
            row = await cur.fetchone()
            return str(row[0]) if row else ""


async def latest_artifact_names(pid: str) -> list[str]:
    async with _connect() as conn:
        async with conn.execute(
            """
            SELECT a.filename FROM artifacts a
            JOIN (
                SELECT filename, MAX(version) AS v
                FROM artifacts WHERE project_id = ?
                GROUP BY filename
            ) m ON a.filename = m.filename AND a.version = m.v
            WHERE a.project_id = ? AND a.deleted = 0
            ORDER BY a.filename LIMIT 80
            """,
            (pid, pid),
        ) as cur:
            return [str(row[0]) for row in await cur.fetchall()]


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
            WHERE a.project_id = ? AND a.deleted = 0
            ORDER BY a.filename
            """,
            (pid, pid),
        ) as cur:
            artifacts = [dict(r) for r in await cur.fetchall()]
        async with conn.execute(
            """
            SELECT e.id, e.agent, e.step, e.status, e.log, e.run_id,
                   e.tool, e.target, e.created_at,
                   (
                       SELECT COUNT(*) FROM file_changes c
                       WHERE c.execution_id = e.id
                   ) AS change_count
            FROM executions e
            WHERE e.project_id = ?
            ORDER BY e.id
            """,
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
            WHERE a.project_id = ? AND a.deleted = 0
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


async def add_artifact(
    pid: str,
    filename: str,
    content: str,
    version: int,
    deleted: bool = False,
) -> None:
    """Replace-then-insert: a repair pass may rewrite a file within one round.

    Deletions are stored as tombstones (``deleted=1``) so the latest-version
    queries can hide the file while older versions remain available for diffs
    and rollback.
    """
    async with _connect() as conn:
        await conn.execute(
            "DELETE FROM artifacts WHERE project_id = ? AND filename = ? AND version = ?",
            (pid, filename, version),
        )
        await conn.execute(
            """
            INSERT INTO artifacts
                (project_id, filename, content, version, deleted, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (pid, filename, content, version, 1 if deleted else 0, now()),
        )
        await conn.commit()


async def add_artifact_deleted(pid: str, filename: str, version: int) -> None:
    await add_artifact(pid, filename, "", version, deleted=True)


async def add_execution(
    pid: str,
    agent: str,
    step: str,
    status: str,
    log: str,
    run_id: str | None = None,
    tool: str | None = None,
    target: str | None = None,
) -> int:
    async with _connect() as conn:
        cur = await conn.execute(
            """
            INSERT INTO executions
                (project_id, agent, step, status, log, run_id, tool, target, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (pid, agent, step, status, log, run_id, tool, target, now()),
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


# ---------------------------------------------------------------------------
# File changes (per-tool diff history + rollback bookkeeping)
# ---------------------------------------------------------------------------


async def add_file_change(
    pid: str,
    *,
    version: int,
    filename: str,
    change_type: str,
    diff: str,
    additions: int = 0,
    deletions: int = 0,
    run_id: str | None = None,
    agent: str | None = None,
    execution_id: int | None = None,
    rolled_back: bool = False,
    truncated: bool = False,
) -> int:
    async with _connect() as conn:
        cur = await conn.execute(
            """
            INSERT INTO file_changes
                (project_id, version, run_id, agent, execution_id, filename,
                 change_type, diff, additions, deletions, rolled_back, truncated,
                 created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pid,
                version,
                run_id,
                agent,
                execution_id,
                filename,
                change_type,
                diff,
                additions,
                deletions,
                1 if rolled_back else 0,
                1 if truncated else 0,
                now(),
            ),
        )
        await conn.commit()
        return int(cur.lastrowid)


async def get_file_change(pid: str, change_id: int) -> dict | None:
    async with _connect() as conn:
        async with conn.execute(
            "SELECT * FROM file_changes WHERE project_id = ? AND id = ?",
            (pid, change_id),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def list_file_changes(
    pid: str,
    *,
    execution_id: int | None = None,
    run_id: str | None = None,
    version: int | None = None,
    include_rolled_back: bool = True,
) -> list[dict]:
    sql = "SELECT * FROM file_changes WHERE project_id = ?"
    params: list[object] = [pid]
    if execution_id is not None:
        sql += " AND execution_id = ?"
        params.append(execution_id)
    if run_id is not None:
        sql += " AND run_id = ?"
        params.append(run_id)
    if version is not None:
        sql += " AND version = ?"
        params.append(version)
    if not include_rolled_back:
        sql += " AND rolled_back = 0"
    sql += " ORDER BY id"
    async with _connect() as conn:
        async with conn.execute(sql, params) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def mark_file_changes_rolled_back(pid: str, version: int) -> None:
    """Keep failed-round diffs visible in the timeline, but mark them as rolled back."""
    async with _connect() as conn:
        await conn.execute(
            "UPDATE file_changes SET rolled_back = 1 "
            "WHERE project_id = ? AND version = ?",
            (pid, version),
        )
        await conn.commit()


async def delete_file_changes_version(pid: str, version: int) -> None:
    async with _connect() as conn:
        await conn.execute(
            "DELETE FROM file_changes WHERE project_id = ? AND version = ?",
            (pid, version),
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
        for table in (
            "conversations",
            "artifacts",
            "executions",
            "file_changes",
            "project_saves",
            "projects",
        ):
            column = "id" if table == "projects" else "project_id"
            await conn.execute(f"DELETE FROM {table} WHERE {column} = ?", (pid,))
        await conn.commit()
