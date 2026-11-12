"""FastAPI entrypoint: REST + SSE + generated-project hosting."""
from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import shutil
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

import agent
import config
import db
import naming
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


def _project_mode(paths: set[str]) -> str:
    has_frontend = any(path.startswith("frontend/") for path in paths)
    has_backend = any(path.startswith("backend/") for path in paths)
    if has_frontend and has_backend:
        return "fullstack"
    if has_backend:
        return "backend"
    return "frontend"


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "llm_mode": config.LLM_MODE,
        "model": config.LLM_MODEL,
        "version": "0.2.0",
        "running_apps": runtime.runtime.running(),
    }


@app.get("/api/projects")
async def list_projects() -> dict:
    projects = await db.list_projects()
    for project in projects:
        if project.get("has_frontend") and project.get("has_backend"):
            project["mode"] = "fullstack"
        elif project.get("has_backend"):
            project["mode"] = "backend"
        else:
            project["mode"] = "frontend"
        project["generating"] = _is_generating(project["id"])
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
async def create_project(body: CreateProjectBody) -> dict:
    prompt = (body.prompt or "").strip()
    name = (body.name or "").strip()
    explicit_name = bool(name)
    if not name:
        name = naming.draft_title(prompt)
    project = await db.create_project((name[:80] or "未命名项目"))

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
async def get_project(pid: str) -> dict:
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
    return state


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
async def export_project(pid: str):
    project = await db.get_project(pid)
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
async def delete_project(pid: str) -> dict:
    if not await db.get_project(pid):
        raise HTTPException(status_code=404, detail="项目不存在")
    await runtime.runtime.stop(pid)
    await db.delete_project(pid)
    target = config.APPS_DIR / pid
    if target.exists():
        await asyncio.to_thread(shutil.rmtree, target, True)
    return {"ok": True}


@app.post("/api/projects/{pid}/generate")
async def generate(pid: str, body: GenerateBody):
    if not await db.get_project(pid):
        raise HTTPException(status_code=404, detail="项目不存在")
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="需求不能为空")

    async def event_stream():
        if _is_generating(pid):
            yield _sse("error", {"message": "该项目正在生成中，请稍候。"})
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
async def generation_events(pid: str):
    if not await db.get_project(pid):
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
async def cancel_generation(pid: str) -> dict:
    """Explicitly stop a build. The SSE stream alone only detaches."""
    if not await db.get_project(pid):
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


async def _serve_project_file(pid: str, path: str) -> FileResponse:
    target = _static_target(pid, path)
    if target is None:
        raise HTTPException(status_code=404, detail="预览文件不存在")
    if path.strip("/") in ("", "index.html"):
        await _ensure_backend_for_page(pid)
    headers = {
        **CORS_HEADERS,
        "Cache-Control": "no-store",
    }
    return FileResponse(target, headers=headers)


async def _proxy_backend(pid: str, path: str, request: Request):
    if not await db.get_project(pid):
        raise HTTPException(status_code=404, detail="项目不存在")
    if not runtime.runtime.has_backend(pid):
        return JSONResponse(
            {"detail": "该项目没有后端服务"},
            status_code=404,
            headers=CORS_HEADERS,
        )
    try:
        port = await runtime.runtime.ensure(pid)
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


@app.get("/apps/{pid}")
async def preview_root(pid: str):
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
    return await _serve_project_file(pid, path)
