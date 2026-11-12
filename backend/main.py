"""FastAPI entrypoint: REST + SSE + hosted previews."""
import asyncio
import json
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import agent
import config
import db

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

_locks: dict[str, asyncio.Lock] = {}


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.init_db()
    yield


app = FastAPI(title="Atoms Demo", lifespan=lifespan)


class CreateProjectBody(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    prompt: str | None = Field(default=None, max_length=4000)


class GenerateBody(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "llm_mode": config.LLM_MODE,
        "model": config.LLM_MODEL,
        "version": "0.1.0",
    }


@app.get("/api/projects")
async def list_projects() -> dict:
    return {"projects": await db.list_projects()}


@app.post("/api/projects")
async def create_project(body: CreateProjectBody) -> dict:
    name = (body.name or "").strip() or (body.prompt or "").strip()[:24] or "未命名项目"
    return await db.create_project(name[:80])


@app.get("/api/projects/{pid}")
async def get_project(pid: str) -> dict:
    state = await db.get_state(pid)
    if not state:
        raise HTTPException(status_code=404, detail="项目不存在")
    return state


@app.delete("/api/projects/{pid}")
async def delete_project(pid: str) -> dict:
    if not await db.get_project(pid):
        raise HTTPException(status_code=404, detail="项目不存在")
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

    lock = _locks.setdefault(pid, asyncio.Lock())

    async def event_stream():
        if lock.locked():
            yield _sse("error", {"message": "该项目正在生成中，请稍候。"})
            yield _sse("done", {"project_id": pid})
            return

        async with lock:
            await db.add_conversation(pid, "user", message)
            queue: asyncio.Queue = asyncio.Queue()

            async def emit(event: str, payload: dict):
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
                            ),
                        }
                await queue.put((event, payload))
                return payload.get("id")

            async def worker():
                try:
                    await agent.run_generation(pid, message, emit)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001 - surface everything to the UI
                    await emit("error", {"message": f"{type(exc).__name__}: {exc}"})
                finally:
                    await queue.put(("done", {"project_id": pid}))
                    await queue.put(None)

            task = asyncio.create_task(worker())
            try:
                while True:
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=15)
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"
                        continue
                    if item is None:
                        break
                    event, payload = item
                    yield _sse(event, payload)
            finally:
                if not task.done():
                    task.cancel()

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)


app.mount("/apps", StaticFiles(directory=str(config.APPS_DIR), html=True), name="apps")
