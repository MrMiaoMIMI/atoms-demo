"""FastAPI entrypoint: REST + SSE + generated-project hosting."""
from __future__ import annotations

import asyncio
import base64
import binascii
import hmac
import io
import json
import logging
import re
import shutil
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

import agent
import auth
import categories
import config
import db
import mailer
import naming
import publisher
import runtime

logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "X-Content-Type-Options": "nosniff",
}

# Project id -> background naming task, kept alive until it resolves.
_title_tasks: dict[str, asyncio.Task] = {}
# Project id -> in-flight generation task. It deliberately outlives the SSE
# connection so closing the workspace tab does not abort a running build.
_generation_tasks: dict[str, asyncio.Task] = {}
# Project ids currently being snapshotted for publish. Publish is deliberately
# exclusive with generation so a half-built tree can never go online.
_publishing: set[str] = set()


class _GenerationHub:
    """Fan-out for one project's generation events.

    Any number of clients can subscribe. Late subscribers get a snapshot of the
    persisted state plus the in-flight file buffer, then continue with live
    events (tokens included), so a re-opened workspace behaves like the
    original one.
    """

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.seq = 0
        self.done = False
        self.stream_file: str | None = None
        self.stream_buffer = ""
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: str, payload: dict) -> None:
        """Broadcast while holding ``lock`` so snapshots stay consistent."""
        self.seq += 1
        self._track(event, payload)
        for queue in list(self._subscribers):
            queue.put_nowait((self.seq, event, payload))

    def _track(self, event: str, payload: dict) -> None:
        if event == "file_start":
            self.stream_file = payload.get("filename")
            self.stream_buffer = ""
        elif event == "token":
            name = payload.get("filename")
            if self.stream_file is None or name == self.stream_file:
                self.stream_buffer += payload.get("delta") or ""
        elif event == "token_reset":
            self.stream_buffer = ""
        elif event == "artifact":
            self.stream_file = None
            self.stream_buffer = ""


# Project id -> hub for the generation currently running in this process.
_hubs: dict[str, _GenerationHub] = {}


def _is_generating(pid: str) -> bool:
    task = _generation_tasks.get(pid)
    return task is not None and not task.done()


def _is_publishing(pid: str) -> bool:
    return pid in _publishing


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    # No generation task survives a process restart; make stale rows honest.
    await db.interrupt_running_executions()
    app.state.http = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=600.0, write=60.0, pool=30.0),
        follow_redirects=False,
    )
    try:
        yield
    finally:
        pending = [*_title_tasks.values(), *_generation_tasks.values()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        _generation_tasks.clear()
        _hubs.clear()
        await runtime.runtime.stop_all()
        await app.state.http.aclose()


app = FastAPI(title="Atoms Demo", lifespan=lifespan)


class CreateProjectBody(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    prompt: str | None = Field(default=None, max_length=4000)


class GenerateBody(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    team_mode: bool = True  # kept for UI parity; routing is always team-routed


class PublishBody(BaseModel):
    """Optional discover metadata supplied with a publish.

    Omitted fields keep the project's current values. Sending an empty
    description clears it, which is why the handler distinguishes ``None``
    (body absent) from an explicit empty string.
    """

    description: str | None = Field(default=None, max_length=280)
    category: str | None = Field(default=None, max_length=20)


class CoverBody(BaseModel):
    version: int = Field(ge=0)
    image: str = Field(min_length=32, max_length=2_000_000)


class CategorySuggestBody(BaseModel):
    description: str | None = Field(default=None, max_length=280)


class EmailBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class PasswordBody(EmailBody):
    password: str = Field(min_length=1, max_length=128)


class RegisterBody(PasswordBody):
    redirect: str = Field(default="/dashboard", max_length=500)


class LoginBody(PasswordBody):
    pass


class ResendBody(EmailBody):
    redirect: str = Field(default="/dashboard", max_length=500)


class VerifyBody(BaseModel):
    token: str = Field(min_length=8, max_length=256)


class ResetBody(VerifyBody):
    password: str = Field(min_length=1, max_length=128)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def _validated_email(value: str) -> str:
    email = auth.normalize_email(value)
    if not auth.is_valid_email(email):
        raise HTTPException(status_code=400, detail="请输入有效的邮箱地址")
    return email


def _validated_password(value: str) -> str:
    error = auth.validate_password(value)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return value


def _display_name(email: str) -> str:
    local = email.split("@", 1)[0].strip()
    return (local[:40] or "Atoms 用户")


async def _session_response(user: dict, request: Request, payload: dict) -> JSONResponse:
    token = await auth.create_session(user, request)
    response = JSONResponse(payload)
    auth.set_session_cookie(response, token)
    await db.delete_expired_sessions()
    return response


@app.get("/api/auth/providers")
async def auth_providers() -> dict:
    """Public capabilities so the login page can render honest buttons."""
    return {
        "google": auth.google_configured(),
        "quick": config.AUTH_DEMO_QUICK_LOGIN,
        "quick_password": (
            config.AUTH_DEMO_PASSWORD if config.AUTH_DEMO_QUICK_LOGIN else None
        ),
        "mail": mailer.mode(),
        "dev_links": auth.dev_links_enabled(),
    }


@app.post("/api/auth/check-email")
async def auth_check_email(body: EmailBody, request: Request) -> dict:
    await auth.enforce_limit(f"check:{auth.client_ip(request)}", 30, 60)
    email = _validated_email(body.email)
    user = await db.get_user_by_email(email)
    return {
        "registered": bool(user),
        "provider": user.get("provider") if user else None,
        "verified": bool(user and user.get("email_verified")),
    }


@app.post("/api/auth/register")
async def auth_register(body: RegisterBody, request: Request):
    await auth.enforce_limit(f"register:{auth.client_ip(request)}", 10, 60)
    email = _validated_email(body.email)
    password = _validated_password(body.password)
    existing = await db.get_user_by_email(email)

    if existing and existing.get("email_verified"):
        raise HTTPException(status_code=409, detail="该邮箱已注册，请直接登录")

    if existing:
        # Unverified account: let the user correct the password and resend.
        await db.update_user_password(existing["id"], auth.hash_password(password))
        user = existing
    else:
        user = await db.create_user(
            email,
            name=_display_name(email),
            password_hash=auth.hash_password(password),
            provider="email",
            email_verified=False,
        )

    token = await auth.issue_email_token(user, "verify")
    url = auth.verification_url(
        request, token, email, auth.safe_redirect(body.redirect)
    )
    delivered = await mailer.send_verification_email(email, url)
    return {
        "email": email,
        "verification_sent": delivered,
        "already_registered": bool(existing),
        "dev_verify_url": url if auth.dev_links_enabled() else None,
        "warning": (
            None
            if delivered or auth.dev_links_enabled()
            else "验证邮件发送失败，请稍后重新发送"
        ),
    }


@app.post("/api/auth/verify-email")
async def auth_verify_email(body: VerifyBody, request: Request):
    row = await db.consume_email_token(auth.token_digest(body.token), "verify")
    if not row:
        raise HTTPException(
            status_code=400,
            detail="验证链接已过期或无效，请返回注册页面重新发送。",
        )
    user = await db.get_user(row["user_id"])
    if not user:
        raise HTTPException(status_code=400, detail="账号不存在")
    await db.mark_email_verified(user["id"])
    user["email_verified"] = 1
    return await _session_response(
        user,
        request,
        {
            "ok": True,
            "email": user["email"],
            "user": auth.public_user(user),
            "redirect": "/dashboard",
        },
    )


@app.post("/api/auth/resend-verification")
async def auth_resend_verification(
    body: ResendBody, request: Request
) -> dict:
    email = _validated_email(body.email)
    await auth.enforce_limit(f"resend:{email}", 1, 60)
    user = await db.get_user_by_email(email)
    if not user or user.get("email_verified"):
        # Do not reveal whether an address exists.
        return {"sent": True, "dev_verify_url": None}
    token = await auth.issue_email_token(user, "verify")
    url = auth.verification_url(
        request, token, email, auth.safe_redirect(body.redirect)
    )
    delivered = await mailer.send_verification_email(email, url)
    return {
        "sent": delivered,
        "dev_verify_url": url if auth.dev_links_enabled() else None,
    }


@app.post("/api/auth/login")
async def auth_login(body: LoginBody, request: Request):
    email = _validated_email(body.email)
    password = body.password
    ip = auth.client_ip(request)
    await auth.enforce_limit(f"login:{ip}", 20, 300)
    await auth.enforce_limit(f"login:{ip}:{email}", 8, 300)

    user = await db.get_user_by_email(email)
    if user and not user.get("password_hash"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "password_not_set",
                "message": "该账号尚未设置密码。请通过「忘记密码」设置密码，或使用 Google 登录。",
            },
        )
    if not user or not auth.verify_password(password, user.get("password_hash")):
        raise HTTPException(status_code=401, detail="邮箱或密码不正确")
    if not user.get("email_verified"):
        raise HTTPException(status_code=403, detail="请先验证邮箱后再登录")

    await auth.limiter.reset(f"login:{ip}:{email}")
    return await _session_response(
        user, request, {"user": auth.public_user(user)}
    )


@app.post("/api/auth/quick")
async def auth_quick_login(body: EmailBody, request: Request):
    if not config.AUTH_DEMO_QUICK_LOGIN:
        raise HTTPException(status_code=404, detail="快捷登录未开启")
    await auth.enforce_limit(f"quick:{auth.client_ip(request)}", 30, 60)
    email = _validated_email(body.email)

    user = await db.get_user_by_email(email)
    created = False
    default_password: str | None = None
    if user is None:
        default_password = config.AUTH_DEMO_PASSWORD
        user = await db.create_user(
            email,
            name=_display_name(email),
            password_hash=auth.hash_password(default_password),
            provider="quick",
            email_verified=True,
        )
        created = True
    elif not user.get("email_verified"):
        await db.mark_email_verified(user["id"])
        user["email_verified"] = 1

    return await _session_response(
        user,
        request,
        {
            "user": auth.public_user(user),
            "created": created,
            "default_password": default_password,
        },
    )


@app.post("/api/auth/logout")
async def auth_logout(request: Request):
    token = request.cookies.get(config.AUTH_COOKIE_NAME)
    if token:
        await db.delete_session(auth.token_digest(token))
    response = JSONResponse({"ok": True})
    auth.clear_session_cookie(response)
    return response


@app.get("/api/auth/me")
async def auth_me(user: dict = Depends(auth.current_user)) -> dict:
    return {"user": user}


@app.post("/api/auth/password/forgot")
async def auth_forgot_password(body: EmailBody, request: Request) -> dict:
    email = _validated_email(body.email)
    await auth.enforce_limit(f"forgot:{auth.client_ip(request)}", 10, 300)
    await auth.enforce_limit(f"forgot:{email}", 1, 60)

    user = await db.get_user_by_email(email)
    dev_url: str | None = None
    delivered: bool | None = None
    if user:
        token = await auth.issue_email_token(user, "reset")
        url = auth.reset_url(request, token, email)
        send_ok = await mailer.send_reset_email(email, url)
        if auth.dev_links_enabled():
            dev_url = url
            # Only expose delivery status when the dev link already reveals
            # that the address exists.
            delivered = send_ok
    # Always generic: do not reveal whether an address is registered.
    return {"sent": True, "dev_reset_url": dev_url, "delivered": delivered}


@app.post("/api/auth/password/reset")
async def auth_reset_password(body: ResetBody):
    password = _validated_password(body.password)
    row = await db.consume_email_token(auth.token_digest(body.token), "reset")
    if not row:
        raise HTTPException(
            status_code=400, detail="重置链接已过期或无效，请重新发起。"
        )
    user = await db.get_user(row["user_id"])
    if not user:
        raise HTTPException(status_code=400, detail="账号不存在")
    await db.update_user_password(user["id"], auth.hash_password(password))
    await db.mark_email_verified(user["id"])
    # A password change invalidates every existing session.
    await db.delete_user_sessions(user["id"])
    response = JSONResponse({"ok": True})
    auth.clear_session_cookie(response)
    return response


@app.get("/api/auth/google/start")
async def google_start(request: Request, redirect: str = "/dashboard"):
    if not auth.google_configured():
        raise HTTPException(
            status_code=503,
            detail="Google 登录尚未配置，请先设置 GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET",
        )
    state = auth.new_token(24)
    response = RedirectResponse(
        auth.google_auth_url(request, state), status_code=302
    )
    cookie_args = {
        "max_age": 600,
        "httponly": True,
        "samesite": "lax",
        "secure": config.AUTH_COOKIE_SECURE,
        "path": "/api/auth/google",
    }
    response.set_cookie("atoms_oauth_state", state, **cookie_args)
    response.set_cookie(
        "atoms_oauth_redirect", auth.safe_redirect(redirect), **cookie_args
    )
    return response


@app.get("/api/auth/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    base = auth.public_base_url(request)
    redirect_path = auth.safe_redirect(
        request.cookies.get("atoms_oauth_redirect")
    )
    expected = request.cookies.get("atoms_oauth_state")

    def failure(reason: str):
        response = RedirectResponse(
            f"{base}/login?error={quote(reason)}", status_code=303
        )
        response.delete_cookie("atoms_oauth_state", path="/api/auth/google")
        response.delete_cookie("atoms_oauth_redirect", path="/api/auth/google")
        return response

    if error or not code or not state or not expected:
        return failure("google_failed")
    if not hmac.compare_digest(state, expected):
        return failure("google_failed")

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": config.GOOGLE_CLIENT_ID,
                    "client_secret": config.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": auth.google_redirect_uri(request),
                    "grant_type": "authorization_code",
                },
            )
            if token_response.status_code != 200:
                logger.warning(
                    "Google token exchange failed: %s %s",
                    token_response.status_code,
                    token_response.text[:300],
                )
                return failure("google_failed")
            access_token = token_response.json().get("access_token")
            if not access_token:
                return failure("google_failed")
            info_response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if info_response.status_code != 200:
                return failure("google_failed")
            info = info_response.json()
    except httpx.HTTPError as exc:
        logger.warning("Google OAuth request failed: %s", exc)
        return failure("google_failed")

    email = auth.normalize_email(info.get("email"))
    if not auth.is_valid_email(email) or not info.get("email_verified"):
        return failure("google_failed")

    user = await db.get_user_by_email(email)
    if user is None:
        user = await db.create_user(
            email,
            name=info.get("name") or _display_name(email),
            password_hash=None,
            provider="google",
            email_verified=True,
        )
    else:
        if not user.get("email_verified"):
            await db.mark_email_verified(user["id"])
            user["email_verified"] = 1
        if not user.get("name") and info.get("name"):
            await db.update_user_login(user["id"], info["name"])
            user["name"] = info["name"]

    token = await auth.create_session(user, request)
    response = RedirectResponse(f"{base}{redirect_path}", status_code=303)
    auth.set_session_cookie(response, token)
    response.delete_cookie("atoms_oauth_state", path="/api/auth/google")
    response.delete_cookie("atoms_oauth_redirect", path="/api/auth/google")
    return response


def _project_mode(paths: set[str]) -> str:
    has_frontend = any(path.startswith("frontend/") for path in paths)
    has_backend = any(path.startswith("backend/") for path in paths)
    if has_frontend and has_backend:
        return "fullstack"
    if has_backend:
        return "backend"
    return "frontend"


def _project_mode_on_disk(pid: str) -> str:
    """Cheap mode lookup for publish snapshots (no artifact content load)."""
    root = config.APPS_DIR / pid
    has_frontend = (root / "frontend" / "src" / "main.tsx").is_file()
    has_backend = (root / "backend" / "main.py").is_file()
    if has_frontend and has_backend:
        return "fullstack"
    if has_backend:
        return "backend"
    return "frontend"


def _decorate_state(state: dict) -> dict:
    """Expose the derived lifecycle fields at both state and project level."""
    project = state.get("project")
    if project:
        db.decorate_project(project)
        state["status"] = project["status"]
        state["has_changes"] = project["has_changes"]
        state["published_url"] = project["published_url"]
        state["paused"] = project["paused"]
    return state


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "llm_mode": config.LLM_MODE,
        "model": config.LLM_MODEL,
        "version": "0.3.0",
        "running_apps": runtime.runtime.running(),
        "auth": {
            "mail": mailer.mode(),
            "google": auth.google_configured(),
            "quick": config.AUTH_DEMO_QUICK_LOGIN,
        },
    }


@app.get("/api/projects")
async def list_projects(user: dict = Depends(auth.current_user)) -> dict:
    projects = await db.list_projects(user["id"])
    for project in projects:
        if project.get("has_frontend") and project.get("has_backend"):
            project["mode"] = "fullstack"
        elif project.get("has_backend"):
            project["mode"] = "backend"
        else:
            project["mode"] = "frontend"
        project["generating"] = _is_generating(project["id"])
        db.decorate_project(project)
        project["cover_url"] = _project_cover_url(project)
    return {"projects": projects}


async def _name_project(pid: str, prompt: str) -> None:
    """Resolve an LLM title in the background and persist it."""
    try:
        name = await naming.suggest_title(prompt)
        project = await db.get_project(pid)
        if project and name and name != project["name"]:
            await db.update_project_name(pid, name[:80])
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - naming must never break creation
        logger.warning("project naming failed for %s: %s", pid, exc)


@app.post("/api/projects")
async def create_project(
    body: CreateProjectBody, user: dict = Depends(auth.current_user)
) -> dict:
    prompt = (body.prompt or "").strip()
    name = (body.name or "").strip()
    explicit_name = bool(name)
    if not name:
        name = naming.draft_title(prompt)
    project = await db.create_project((name[:80] or "未命名项目"), user["id"])

    # Long first prompts lose intent when cut to N characters; let the LLM
    # summarize one. The workspace opens with the draft name in the meantime.
    if prompt and not explicit_name:
        task = asyncio.create_task(_name_project(project["id"], prompt))
        _title_tasks[project["id"]] = task
        task.add_done_callback(
            lambda _task, pid=project["id"]: _title_tasks.pop(pid, None)
        )
    return project


def _preview_ready(pid: str) -> bool:
    """Preview is only served after the builder wrote its static shell."""
    return (config.APPS_DIR / pid / ".preview" / "index.html").exists()


@app.get("/api/projects/{pid}")
async def get_project(pid: str, user: dict = Depends(auth.current_user)) -> dict:
    if not await db.get_project_for_user(pid, user["id"]):
        raise HTTPException(status_code=404, detail="项目不存在")
    state = await db.get_state(pid)
    if not state:
        raise HTTPException(status_code=404, detail="项目不存在")
    paths = {artifact["filename"] for artifact in state["artifacts"]}
    artifacts = state["artifacts"]
    version = max((artifact["version"] for artifact in artifacts), default=0)
    state["mode"] = _project_mode(paths)
    ready = _preview_ready(pid)
    state["preview_url"] = (
        f"/apps/{pid}/?v={version or 1}" if artifacts and ready else None
    )
    state["generating"] = _is_generating(pid)
    return _decorate_state(state)


@app.post("/api/projects/{pid}/publish")
async def publish_project(
    pid: str,
    body: PublishBody | None = None,
    user: dict = Depends(auth.current_user),
) -> dict:
    """Snapshot the last successful build and make it publicly reachable."""
    project = await db.get_project_for_user(pid, user["id"])
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if _is_generating(pid) or _is_publishing(pid):
        raise HTTPException(status_code=409, detail="项目正在构建或发布中，请稍候")
    built = project.get("built_version")
    if built is None:
        raise HTTPException(status_code=409, detail="项目还没有成功构建，无法发布")
    if not _preview_ready(pid):
        raise HTTPException(status_code=409, detail="构建产物不存在，请先重新构建")

    # Validate discover metadata before touching the snapshot. The author can
    # publish without a body (older clients); an explicit body updates both
    # fields, and an empty description clears it.
    final_description: str | None = None
    final_category: str | None = None
    if body is not None:
        final_description = (
            body.description
            if body.description is not None
            else (project.get("description") or "")
        ).strip()[:280]
        current_category = categories.normalize_category(project.get("category"))
        requested = (body.category or "").strip()
        if requested and requested not in categories.CATEGORIES:
            raise HTTPException(status_code=400, detail="分类不正确")
        final_category = requested or current_category

    # Mark synchronously before the first await inside the snapshot section;
    # the re-check below closes the window opened by the ownership query.
    _publishing.add(pid)
    try:
        if _is_generating(pid):
            raise HTTPException(status_code=409, detail="项目正在构建，请稍候")
        mode = _project_mode_on_disk(pid)
        # The published process must not keep the old tree open while it is
        # swapped; it restarts lazily on the next visitor request.
        await runtime.runtime.stop(pid, published=True)
        manifest = await asyncio.to_thread(
            publisher.snapshot, pid, int(built), mode, project["name"]
        )
        await db.mark_published(pid, int(built))
        if body is not None:
            await db.update_project_meta(
                pid,
                final_description or "",
                final_category or categories.DEFAULT_CATEGORY,
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - surface the snapshot failure
        logger.exception("publish failed for %s", pid)
        raise HTTPException(status_code=500, detail=f"发布失败：{exc}") from exc
    finally:
        _publishing.discard(pid)

    updated = await db.get_project(pid)
    if updated:
        db.decorate_project(updated)
    return {
        "ok": True,
        "project": updated,
        "manifest": manifest,
        "published_url": f"/s/{pid}/",
    }


@app.post("/api/projects/{pid}/pause")
async def pause_project(pid: str, user: dict = Depends(auth.current_user)) -> dict:
    """Block every visitor without rebuilding or touching the snapshot."""
    project = await db.get_project_for_user(pid, user["id"])
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.get("published_version") is None:
        raise HTTPException(status_code=409, detail="项目还没有发布")
    if _is_publishing(pid):
        raise HTTPException(status_code=409, detail="项目正在发布中，请稍候")
    await db.set_project_paused(pid, True)
    # Free the process slot; resume starts it lazily on the first request.
    await runtime.runtime.stop(pid, published=True)
    updated = await db.get_project(pid)
    if updated:
        db.decorate_project(updated)
    return {"ok": True, "project": updated}


@app.post("/api/projects/{pid}/resume")
async def resume_project(pid: str, user: dict = Depends(auth.current_user)) -> dict:
    project = await db.get_project_for_user(pid, user["id"])
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.get("published_version") is None:
        raise HTTPException(status_code=409, detail="项目还没有发布")
    if _is_publishing(pid):
        raise HTTPException(status_code=409, detail="项目正在发布中，请稍候")
    await db.set_project_paused(pid, False)
    updated = await db.get_project(pid)
    if updated:
        db.decorate_project(updated)
    return {"ok": True, "project": updated}


# ---------------------------------------------------------------------------
# Discover: other users' published apps
# ---------------------------------------------------------------------------


def _cover_file(pid: str) -> tuple[Path, str] | None:
    root = config.APPS_DIR / pid
    for name, media_type in (("cover.jpg", "image/jpeg"), ("cover.png", "image/png")):
        path = root / name
        if path.is_file():
            return path, media_type
    return None


def _build_cover_file(pid: str) -> tuple[Path, str] | None:
    root = config.APPS_DIR / pid
    for name, media_type in (
        ("build-cover.jpg", "image/jpeg"),
        ("build-cover.png", "image/png"),
    ):
        path = root / name
        if path.is_file():
            return path, media_type
    return None


def _project_cover_url(project: dict) -> str | None:
    """Owner-facing project card cover.

    A published snapshot cover wins over a working-build cover, matching the
    rule that the online thumbnail is the canonical one. A build cover exists
    for projects that are built but not published yet.
    """
    pid = project["id"]
    published = project.get("published_version")
    cover_version = project.get("cover_version")
    if (
        published is not None
        and cover_version == published
        and _cover_file(pid) is not None
    ):
        return f"/api/projects/{pid}/cover?v={cover_version}"

    built = project.get("built_version")
    build_cover = project.get("build_cover_version")
    if (
        built is not None
        and build_cover == built
        and _build_cover_file(pid) is not None
    ):
        return f"/api/projects/{pid}/cover?v=b{build_cover}"
    return None


def _decorate_discover(row: dict) -> dict:
    app = dict(row)
    has_frontend = bool(app.pop("has_frontend", 0))
    has_backend = bool(app.pop("has_backend", 0))
    if has_frontend and has_backend:
        app["mode"] = "fullstack"
    elif has_backend:
        app["mode"] = "backend"
    else:
        app["mode"] = "frontend"
    app["description"] = app.get("description") or ""
    app["category"] = categories.normalize_category(app.get("category"))
    app["view_count"] = int(app.get("view_count") or 0)
    app["saved"] = bool(app.get("saved"))
    app["published_url"] = f"/s/{app['id']}/"
    cover_version = app.get("cover_version")
    cover = _cover_file(app["id"])
    if (
        cover is not None
        and cover_version is not None
        and cover_version == app.get("published_version")
    ):
        app["cover_url"] = f"/api/discover/{app['id']}/cover?v={cover_version}"
    else:
        app["cover_url"] = None
    # These are storage details, not part of the public discover contract.
    app.pop("cover_version", None)
    app.pop("cover_at", None)
    return app


async def _store_cover(pid: str, data: bytes, ext: str, prefix: str) -> None:
    root = config.APPS_DIR / pid
    await asyncio.to_thread(root.mkdir, parents=True, exist_ok=True)
    target = root / f"{prefix}.{ext}"
    tmp = root / f".{prefix}-{uuid.uuid4().hex}.tmp"
    await asyncio.to_thread(tmp.write_bytes, data)
    await asyncio.to_thread(tmp.replace, target)
    for name in (f"{prefix}.jpg", f"{prefix}.png"):
        other = root / name
        if other != target and other.exists():
            await asyncio.to_thread(other.unlink)


_COVER_DATA_URL = re.compile(r"^data:image/(png|jpeg);base64,([A-Za-z0-9+/=]+)$")


def _decode_cover_image(image: str) -> tuple[bytes, str]:
    match = _COVER_DATA_URL.match((image or "").strip())
    if not match:
        raise HTTPException(status_code=400, detail="封面格式不正确")
    kind = match.group(1)
    try:
        data = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="封面格式不正确") from exc
    if len(data) > 1_200_000:
        raise HTTPException(status_code=413, detail="封面图片不能超过 1.2MB")
    if kind == "jpeg" and not data.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=400, detail="封面格式不正确")
    if kind == "png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=400, detail="封面格式不正确")
    return data, ("jpg" if kind == "jpeg" else "png")


@app.post("/api/projects/{pid}/category/suggest")
async def suggest_project_category(
    pid: str,
    body: CategorySuggestBody | None = None,
    user: dict = Depends(auth.current_user),
) -> dict:
    """Offer one category. This never persists anything; the author confirms."""
    project = await db.get_project_for_user(pid, user["id"])
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    prompt = await db.first_user_message(pid)
    files = await db.latest_artifact_names(pid)
    description = (
        (body.description if body is not None else None)
        or project.get("description")
        or ""
    ).strip()
    category = await categories.suggest_category(
        name=project["name"],
        prompt=prompt,
        description=description,
        files=files,
    )
    return {"category": category}


@app.post("/api/projects/{pid}/cover")
async def upload_project_cover(
    pid: str,
    body: CoverBody,
    user: dict = Depends(auth.current_user),
) -> dict:
    """Store the browser-captured cover for the current published version."""
    project = await db.get_project_for_user(pid, user["id"])
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    published = project.get("published_version")
    if published is None or body.version != published:
        raise HTTPException(status_code=409, detail="封面版本与线上版本不一致")

    data, ext = _decode_cover_image(body.image)
    await _store_cover(pid, data, ext, "cover")
    await db.set_project_cover(pid, body.version)
    return {"ok": True}


@app.post("/api/projects/{pid}/build-cover")
async def upload_project_build_cover(
    pid: str,
    body: CoverBody,
    user: dict = Depends(auth.current_user),
) -> dict:
    """Store the browser-captured cover for the latest successful build."""
    project = await db.get_project_for_user(pid, user["id"])
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    built = project.get("built_version")
    if built is None or body.version != built:
        raise HTTPException(status_code=409, detail="缩略图版本与最近构建版本不一致")

    data, ext = _decode_cover_image(body.image)
    await _store_cover(pid, data, ext, "build-cover")
    await db.set_project_build_cover(pid, body.version)
    return {"ok": True}


@app.get("/api/projects/{pid}/cover")
async def project_card_cover(pid: str, user: dict = Depends(auth.current_user)):
    """Serve the owner's card cover: published cover first, then build cover."""
    project = await db.get_project_for_user(pid, user["id"])
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    published = project.get("published_version")
    if published is not None and project.get("cover_version") == published:
        cover = _cover_file(pid)
        if cover is not None:
            path, media_type = cover
            return FileResponse(
                path,
                media_type=media_type,
                headers={
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )
    built = project.get("built_version")
    if built is not None and project.get("build_cover_version") == built:
        cover = _build_cover_file(pid)
        if cover is not None:
            path, media_type = cover
            return FileResponse(
                path,
                media_type=media_type,
                headers={
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )
    raise HTTPException(status_code=404, detail="缩略图不存在")


@app.get("/api/discover")
async def discover_list(
    sort: str = "latest",
    category: str | None = None,
    q: str | None = None,
    saved: bool = False,
    offset: int = 0,
    limit: int = 24,
    user: dict = Depends(auth.current_user),
) -> dict:
    if sort not in {"latest", "popular"}:
        raise HTTPException(status_code=400, detail="排序方式不正确")
    if category and category != "全部" and category not in categories.CATEGORIES:
        raise HTTPException(status_code=400, detail="分类不正确")
    page_size = max(1, min(limit, 60))
    rows = await db.list_discover(
        user["id"],
        sort=sort,
        category=None if category == "全部" else category,
        query=(q or "")[:80],
        saved=saved,
        limit=page_size,
        offset=max(0, offset),
    )
    has_more = len(rows) > page_size
    return {
        "apps": [_decorate_discover(row) for row in rows[:page_size]],
        "has_more": has_more,
    }


@app.get("/api/discover/{pid}")
async def discover_detail(pid: str, user: dict = Depends(auth.current_user)) -> dict:
    row = await db.get_discover(pid, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="应用不存在或已下线")
    app = _decorate_discover(row)
    related = await db.list_related(pid, user["id"], app["category"], 4)
    app["related"] = [_decorate_discover(item) for item in related]
    return {"app": app}


@app.post("/api/discover/{pid}/view")
async def discover_view(pid: str, user: dict = Depends(auth.current_user)) -> dict:
    if not await db.get_discover(pid, user["id"]):
        raise HTTPException(status_code=404, detail="应用不存在或已下线")
    return {"ok": True, "view_count": await db.increment_view(pid)}


@app.post("/api/discover/{pid}/save")
async def discover_save(pid: str, user: dict = Depends(auth.current_user)) -> dict:
    if not await db.get_discover(pid, user["id"]):
        raise HTTPException(status_code=404, detail="应用不存在或已下线")
    await db.save_project(user["id"], pid)
    return {"ok": True, "saved": True}


@app.delete("/api/discover/{pid}/save")
async def discover_unsave(
    pid: str, user: dict = Depends(auth.current_user)
) -> dict:
    # Unconditionally removing the row lets a user tidy up after an app is
    # paused or taken down.
    await db.unsave_project(user["id"], pid)
    return {"ok": True, "saved": False}


@app.get("/api/discover/{pid}/cover")
async def discover_cover(pid: str, user: dict = Depends(auth.current_user)):
    row = await db.get_discover(pid, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="应用不存在或已下线")
    cover = _cover_file(pid)
    if (
        cover is None
        or row.get("cover_version") is None
        or row.get("cover_version") != row.get("published_version")
    ):
        raise HTTPException(status_code=404, detail="封面不存在")
    path, media_type = cover
    return FileResponse(
        path,
        media_type=media_type,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _zip_artifacts(files: dict[str, str]) -> bytes:
    """Pack the latest source files into an in-memory repository archive."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename in sorted(files):
            name = filename.replace("\\", "/").lstrip("/")
            if not name or ".." in Path(name).parts:
                continue
            archive.writestr(name, files[filename])
    return buffer.getvalue()


@app.get("/api/projects/{pid}/export")
async def export_project(pid: str, user: dict = Depends(auth.current_user)):
    project = await db.get_project_for_user(pid, user["id"])
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    files = await db.latest_artifacts(pid)
    if not files:
        raise HTTPException(status_code=409, detail="项目还没有可导出的文件")

    payload = await asyncio.to_thread(_zip_artifacts, files)
    safe_name = re.sub(r'[\\/:*?"<>|\r\n]+', "-", project["name"]).strip(" .")
    download = f"{safe_name[:60] or 'atoms-project'}.zip"
    headers = {
        "Content-Disposition": (
            f'attachment; filename="atoms-{pid}.zip"; '
            f"filename*=UTF-8''{quote(download, safe='')}"
        ),
        "Cache-Control": "no-store",
    }
    return Response(payload, media_type="application/zip", headers=headers)


@app.delete("/api/projects/{pid}")
async def delete_project(pid: str, user: dict = Depends(auth.current_user)) -> dict:
    if not await db.get_project_for_user(pid, user["id"]):
        raise HTTPException(status_code=404, detail="项目不存在")
    await runtime.runtime.stop(pid)
    await runtime.runtime.stop(pid, published=True)
    await db.delete_project(pid)
    target = config.APPS_DIR / pid
    if target.exists():
        await asyncio.to_thread(shutil.rmtree, target, True)
    return {"ok": True}


@app.post("/api/projects/{pid}/generate")
async def generate(
    pid: str, body: GenerateBody, user: dict = Depends(auth.current_user)
):
    if not await db.get_project_for_user(pid, user["id"]):
        raise HTTPException(status_code=404, detail="项目不存在")
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="需求不能为空")

    async def event_stream():
        if _is_generating(pid) or _is_publishing(pid):
            yield _sse("error", {"message": "该项目正在生成或发布中，请稍候。"})
            yield _sse("done", {"project_id": pid})
            return

        hub = _GenerationHub()
        _hubs[pid] = hub
        queue = hub.subscribe()

        async def emit(event: str, payload: dict):
            # Holding the hub lock keeps the DB rows and the broadcast order in
            # sync, so a late subscriber never sees a half-applied step.
            async with hub.lock:
                if event == "execution":
                    if payload.get("id"):
                        await db.update_execution(
                            int(payload["id"]), payload["status"], payload.get("log")
                        )
                    else:
                        payload = {
                            **payload,
                            "id": await db.add_execution(
                                pid,
                                payload["agent"],
                                payload["step"],
                                payload["status"],
                                payload.get("log") or "",
                                payload.get("run_id"),
                            ),
                        }
                elif event == "message":
                    role = payload.get("role")
                    content = payload.get("content")
                    if role == "assistant" and isinstance(content, str) and content:
                        row_id = await db.add_conversation(
                            pid,
                            "assistant",
                            content,
                            agent=payload.get("agent"),
                            run_id=payload.get("run_id"),
                            run_index=payload.get("run_index"),
                        )
                        payload = {**payload, "id": row_id}
                hub.publish(event, payload)
            return payload.get("id")

        async def worker():
            try:
                await db.interrupt_running_executions(pid=pid)
                await db.add_conversation(pid, "user", message)
                await agent.run_turn(pid, message, emit)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - surface everything to the UI
                await emit("error", {"message": f"{type(exc).__name__}: {exc}"})
            finally:
                # Closed subscribers do not block the worker: publish() never
                # awaits, it just appends to live queues.
                async with hub.lock:
                    hub.done = True
                    hub.publish("done", {"project_id": pid})
                _hubs.pop(pid, None)
                _generation_tasks.pop(pid, None)

        # Register before the first await so concurrent requests cannot start
        # two builds for the same project.
        task = asyncio.create_task(worker())
        _generation_tasks[pid] = task

        # Send the current name at once (it may already hold the resolved
        # background title), then push a second event if naming finishes
        # while this run is still streaming.
        # Read the task reference before the row: if naming finishes in
        # between, the row already carries the final name.
        naming_task = _title_tasks.get(pid)
        current = await db.get_project(pid)
        if current:
            async with hub.lock:
                hub.publish("project", current)

        async def notify_rename() -> None:
            if naming_task is None:
                return
            try:
                await asyncio.shield(naming_task)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - naming already logged it
                return
            project = await db.get_project(pid)
            if project:
                async with hub.lock:
                    hub.publish("project", project)

        watcher = asyncio.create_task(notify_rename())
        try:
            while True:
                try:
                    _, event, payload = await asyncio.wait_for(
                        queue.get(), timeout=15
                    )
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield _sse(event, payload)
                if event == "done":
                    break
        finally:
            # Do NOT cancel `task`: the build must survive a page navigation.
            hub.unsubscribe(queue)
            if not watcher.done():
                watcher.cancel()

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)


async def _resume_event_stream(pid: str, hub: _GenerationHub):
    """Attach to an in-flight build: snapshot first, then live events."""
    queue = hub.subscribe()
    try:
        async with hub.lock:
            snap_seq = hub.seq
            stream = {
                "filename": hub.stream_file,
                "content": hub.stream_buffer,
            }
            state = await db.get_state(pid)
        if state:
            paths = {artifact["filename"] for artifact in state["artifacts"]}
            version = max(
                (artifact["version"] for artifact in state["artifacts"]), default=0
            )
            state["mode"] = _project_mode(paths)
            state["preview_url"] = (
                f"/apps/{pid}/?v={version or 1}"
                if state["artifacts"] and _preview_ready(pid)
                else None
            )
            state["generating"] = True
            _decorate_state(state)
            yield _sse(
                "snapshot",
                {"state": state, "stream": stream, "seq": snap_seq},
            )
        if hub.done:
            return
        while True:
            try:
                seq, event, payload = await asyncio.wait_for(queue.get(), timeout=15)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if seq <= snap_seq:
                continue
            yield _sse(event, payload)
            if event == "done":
                break
    finally:
        hub.unsubscribe(queue)


@app.get("/api/projects/{pid}/events")
async def generation_events(
    pid: str, user: dict = Depends(auth.current_user)
):
    if not await db.get_project_for_user(pid, user["id"]):
        raise HTTPException(status_code=404, detail="项目不存在")
    hub = _hubs.get(pid)
    if hub is None:
        # The build finished between the page load and the subscribe call.
        async def finished():
            yield _sse("done", {"project_id": pid})

        return StreamingResponse(
            finished(), media_type="text/event-stream", headers=SSE_HEADERS
        )
    return StreamingResponse(
        _resume_event_stream(pid, hub),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.post("/api/projects/{pid}/cancel")
async def cancel_generation(
    pid: str, user: dict = Depends(auth.current_user)
) -> dict:
    """Explicitly stop a build. The SSE stream alone only detaches."""
    if not await db.get_project_for_user(pid, user["id"]):
        raise HTTPException(status_code=404, detail="项目不存在")
    task = _generation_tasks.get(pid)
    if task is None or task.done():
        return {"ok": True, "cancelled": False}
    task.cancel()
    try:
        await asyncio.wait_for(
            asyncio.gather(task, return_exceptions=True), timeout=3
        )
    except asyncio.TimeoutError:
        pass
    await db.interrupt_running_executions(log="生成已取消", pid=pid)
    return {"ok": True, "cancelled": True}


# ---------------------------------------------------------------------------
# Generated project hosting
# ---------------------------------------------------------------------------

def _is_backend_path(path: str) -> bool:
    return (
        path == "api"
        or path.startswith("api/")
        or path in {"docs", "redoc", "openapi.json"}
        or path.startswith(("docs/", "redoc/"))
    )


async def _wake_backend(pid: str) -> None:
    try:
        await runtime.runtime.ensure(pid)
    except Exception:  # noqa: BLE001 - preview must render even if API is down
        pass


async def _ensure_backend_for_page(pid: str) -> None:
    if not runtime.runtime.has_backend(pid):
        return
    await _wake_backend(pid)


def _static_target(pid: str, path: str) -> Path | None:
    project = config.APPS_DIR / pid
    preview = project / ".preview"
    if (preview / "index.html").exists():
        base = preview
        relative = path.strip("/")
    else:
        # Legacy flat project (pre full-stack generation).
        if "/" in path.strip("/") or path.strip("/").startswith("."):
            return None
        base = project
        relative = path.strip("/") or "index.html"

    if not relative:
        relative = "index.html"
    if ".." in Path(relative).parts:
        return None
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    if candidate.is_dir():
        candidate = candidate / "index.html"
    if not candidate.exists():
        if "." not in Path(relative).name:
            candidate = base / "index.html"
        else:
            return None
    return candidate if candidate.exists() and candidate.is_file() else None


def _published_target(pid: str, path: str) -> Path | None:
    """Resolve a public static path inside the published snapshot only."""
    base = publisher.site_dir(pid)
    if not (base / "index.html").is_file():
        return None
    relative = path.strip("/") or "index.html"
    if ".." in Path(relative).parts:
        return None
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    if candidate.is_dir():
        candidate = candidate / "index.html"
    if not candidate.exists():
        if "." not in Path(relative).name:
            candidate = base / "index.html"
        else:
            return None
    return candidate if candidate.is_file() else None


_CAPTURE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Runs inside the sandboxed preview iframe. It captures the app's own DOM and
# posts a JPEG back to the workspace, which uploads it as the discover cover.
# The tool itself is a same-origin classic script in the demo's public assets.
_CAPTURE_SCRIPT = """
<script>
(function () {
  var ID = __ID__;
  var TOOL = __TOOL__;
  var started = false;
  function post(type, extra) {
    try {
      parent.postMessage(Object.assign({ type: type, id: ID }, extra || {}), '*');
    } catch (e) {}
  }
  function loadTool() {
    return new Promise(function (resolve, reject) {
      if (window.htmlToImage) return resolve();
      var script = document.createElement('script');
      script.src = TOOL;
      script.onload = function () { resolve(); };
      script.onerror = function () { reject(new Error('无法加载截图工具')); };
      document.head.appendChild(script);
    });
  }
  function capture() {
    if (started) return;
    started = true;
    // The worker may be offscreen, where Chrome can throttle rAF to a crawl.
    // html-to-image uses rAF after decoding the SVG image, so give it a
    // timer-backed implementation just for this capture.
    window.requestAnimationFrame = function (callback) {
      return setTimeout(function () { callback(Date.now()); }, 16);
    };
    loadTool()
      .then(function () {
        return new Promise(function (resolve) { setTimeout(resolve, 350); });
      })
      .then(function () {
        var fonts = document.fonts && document.fonts.ready
          ? document.fonts.ready
          : Promise.resolve();
        return Promise.race([
          fonts,
          new Promise(function (resolve) { setTimeout(resolve, 1200); })
        ]);
      })
      .then(function () {
        return window.htmlToImage.toJpeg(document.body, {
          quality: 0.86,
          backgroundColor: '#ffffff',
          width: 1280,
          height: 720,
          canvasWidth: 1280,
          canvasHeight: 720,
          pixelRatio: 1,
          cacheBust: true,
          skipFonts: true,
          imagePlaceholder: 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=='
        });
      })
      .then(function (data) {
        if (!data || data.length < 5000) throw new Error('截图内容为空');
        post('atoms-cover', { dataUrl: data });
      })
      .catch(function (err) {
        post('atoms-cover-error', { message: String((err && err.message) || err) });
      });
  }
  window.addEventListener('message', function (event) {
    if (event.data && event.data.type === 'atoms-capture' && event.data.id === ID) {
      capture();
    }
  });
  function ready() { post('atoms-cover-ready'); }
  if (document.readyState === 'complete') ready();
  else window.addEventListener('load', ready, { once: true });
})();
</script>
"""


def _capture_document(html_text: str, capture_id: str) -> str:
    safe_id = capture_id if _CAPTURE_ID_RE.match(capture_id or "") else uuid.uuid4().hex
    script = _CAPTURE_SCRIPT.replace(
        "__ID__", json.dumps(safe_id)
    ).replace("__TOOL__", json.dumps("/preview-assets/html-to-image.js"))
    index = html_text.lower().rfind("</body>")
    if index >= 0:
        return html_text[:index] + script + html_text[index:]
    return html_text + script


async def _serve_project_file(
    pid: str, path: str, capture_id: str | None = None
) -> FileResponse | HTMLResponse:
    target = _static_target(pid, path)
    if target is None:
        raise HTTPException(status_code=404, detail="预览文件不存在")
    if path.strip("/") in ("", "index.html"):
        await _ensure_backend_for_page(pid)
    headers = {
        **CORS_HEADERS,
        "Cache-Control": "no-store",
    }
    if capture_id is not None and target.name == "index.html":
        html_text = await asyncio.to_thread(target.read_text, encoding="utf-8")
        return HTMLResponse(_capture_document(html_text, capture_id), headers=headers)
    return FileResponse(target, headers=headers)


async def _proxy_backend(
    pid: str, path: str, request: Request, published: bool = False
):
    project = await db.get_project(pid)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if published and (
        project.get("published_version") is None or project.get("paused")
    ):
        raise HTTPException(status_code=404, detail="站点不存在")
    if not runtime.runtime.has_backend(pid, published):
        return JSONResponse(
            {"detail": "该项目没有后端服务"},
            status_code=404,
            headers=CORS_HEADERS,
        )
    try:
        port = await runtime.runtime.ensure(pid, published=published)
    except runtime.AppRuntimeError as exc:
        return JSONResponse(
            {"detail": str(exc)[:800]},
            status_code=502,
            headers=CORS_HEADERS,
        )

    client: httpx.AsyncClient = request.app.state.http
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower()
        not in {
            "host",
            "content-length",
            "transfer-encoding",
            "connection",
            "accept-encoding",
        }
    }
    body = await request.body()
    url = f"http://127.0.0.1:{port}/{path.lstrip('/')}"
    try:
        upstream = client.build_request(
            request.method,
            url,
            headers=headers,
            content=body,
            params=request.query_params,
        )
        response = await client.send(upstream, stream=True)
    except httpx.HTTPError as exc:
        return JSONResponse(
            {"detail": f"后端不可达：{type(exc).__name__}: {exc}"},
            status_code=502,
            headers=CORS_HEADERS,
        )

    response_headers: dict[str, str] = {}
    for key, value in response.headers.items():
        if key.lower() in {
            "content-length",
            "content-encoding",
            "transfer-encoding",
            "connection",
            "keep-alive",
        }:
            continue
        response_headers[key] = value
    # Never emit a second CORS header: duplicate ACAO values are invalid and
    # make fetch() fail inside the sandboxed (opaque-origin) preview iframe.
    present = {key.lower() for key in response_headers}
    if "access-control-allow-origin" not in present:
        response_headers["Access-Control-Allow-Origin"] = "*"
    if request.method == "OPTIONS" and "access-control-allow-methods" not in present:
        response_headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        )
    if request.method == "OPTIONS" and "access-control-allow-headers" not in present:
        response_headers["Access-Control-Allow-Headers"] = (
            request.headers.get("access-control-request-headers") or "*"
        )
    if "x-content-type-options" not in present:
        response_headers["X-Content-Type-Options"] = "nosniff"
    return StreamingResponse(
        response.aiter_raw(),
        status_code=response.status_code,
        headers=response_headers,
        media_type=response.headers.get("content-type"),
        background=BackgroundTask(response.aclose),
    )


def _is_preview_document(pid: str, path: str) -> bool:
    """True for the HTML entry (including SPA fallbacks), not subresources.

    The iframe runs in an opaque sandboxed origin, so its own fetch() calls do
    not carry the demo session cookie. Protecting only the document keeps the
    generated app working while still requiring a signed-in owner to open it.
    """
    clean = path.strip("/")
    if clean in ("", "index.html"):
        return True
    target = _static_target(pid, path)
    return bool(target and target.name == "index.html")


@app.get("/apps/{pid}")
async def preview_root(pid: str, user: dict = Depends(auth.current_user)):
    if not await db.get_project_for_user(pid, user["id"]):
        raise HTTPException(status_code=404, detail="项目不存在")
    return RedirectResponse(url=f"/apps/{pid}/", status_code=307)


@app.api_route(
    "/apps/{pid}/{path:path}",
    methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def preview(pid: str, path: str, request: Request):
    if _is_backend_path(path):
        return await _proxy_backend(pid, path, request)
    if request.method not in {"GET", "HEAD"}:
        raise HTTPException(status_code=405, detail="静态预览只支持 GET")
    if _is_preview_document(pid, path):
        user = await auth.current_user(request)
        if not await db.get_project_for_user(pid, user["id"]):
            raise HTTPException(status_code=404, detail="项目不存在")
    capture_id = (
        request.query_params.get("capture_id", "")
        if request.query_params.get("atoms_capture") == "1"
        else None
    )
    return await _serve_project_file(pid, path, capture_id)


# ---------------------------------------------------------------------------
# Published site (public, unlike the owner-only /apps/ workspace preview)
# ---------------------------------------------------------------------------


@app.get("/s/{pid}")
async def published_root(pid: str):
    project = await db.get_project(pid)
    if (
        not project
        or project.get("published_version") is None
        or project.get("paused")
    ):
        raise HTTPException(status_code=404, detail="站点不存在")
    return RedirectResponse(url=f"/s/{pid}/", status_code=307)


@app.api_route(
    "/s/{pid}/{path:path}",
    methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def published_site(pid: str, path: str, request: Request):
    project = await db.get_project(pid)
    if (
        not project
        or project.get("published_version") is None
        or project.get("paused")
    ):
        raise HTTPException(status_code=404, detail="站点不存在")
    if _is_backend_path(path):
        return await _proxy_backend(pid, path, request, published=True)
    if request.method not in {"GET", "HEAD"}:
        raise HTTPException(status_code=405, detail="静态站点只支持 GET")
    target = _published_target(pid, path)
    if target is None:
        raise HTTPException(status_code=404, detail="页面不存在")
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }
    return FileResponse(target, headers=headers)
