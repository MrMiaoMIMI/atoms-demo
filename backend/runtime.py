"""Per-project backend runtime.

Each generated backend is started as its own single-worker uvicorn process on
127.0.0.1. Only a bounded number run at once (LRU eviction), which keeps a
2C2G box comfortable while preserving per-project SQLite files on disk.
"""
from __future__ import annotations

import asyncio
import os
import signal
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import config


@dataclass
class Instance:
    pid: str
    port: int
    proc: asyncio.subprocess.Process
    log_path: Path
    last_used: float


class AppRuntimeError(RuntimeError):
    """Generated backend could not be started."""


def _read_tail(path: Path, limit: int = 4000) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    return data[-limit:].decode("utf-8", "ignore").strip()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _port_open(port: int) -> bool:
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.close()
        await writer.wait_closed()
        del reader
        return True
    except OSError:
        return False


class AppRuntime:
    def __init__(self) -> None:
        self._instances: dict[str, Instance] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    # ------------------------------------------------------------------ paths
    @staticmethod
    def backend_dir(pid: str) -> Path:
        return config.APPS_DIR / pid / "backend"

    @classmethod
    def has_backend(cls, pid: str) -> bool:
        return (cls.backend_dir(pid) / "main.py").exists()

    # ------------------------------------------------------------------ lifecycle
    async def ensure(self, pid: str) -> int:
        """Start (or reuse) the project backend and return its localhost port."""
        lock = self._locks.setdefault(pid, asyncio.Lock())
        async with lock:
            instance = self._instances.get(pid)
            if instance and instance.proc.returncode is None:
                if await _port_open(instance.port):
                    instance.last_used = time.monotonic()
                    return instance.port
                await self._stop_locked(pid)

            if not self.has_backend(pid):
                raise AppRuntimeError("该项目没有后端服务")

            await self._evict_if_needed()
            return await self._spawn(pid)

    async def _evict_if_needed(self) -> None:
        async with self._guard:
            while len(self._instances) >= config.MAX_RUNNING_APPS:
                victim = min(self._instances.values(), key=lambda item: item.last_used)
                await self._stop_locked(victim.pid)

    async def _spawn(self, pid: str) -> int:
        backend = self.backend_dir(pid)
        log_path = config.APPS_DIR / pid / ".runtime.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        port = _free_port()
        # Minimal environment: never expose the demo's LLM key or other
        # platform secrets to generated code.
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": str(backend),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
            "APP_ROOT_PATH": f"/apps/{pid}",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        kwargs: dict = {}
        if sys.platform.startswith("linux") and config.GENERATED_APP_MEMORY_MB:
            limit = config.GENERATED_APP_MEMORY_MB * 1024 * 1024

            def _limit_memory() -> None:  # pragma: no cover - Linux only
                import resource

                resource.setrlimit(resource.RLIMIT_AS, (limit, limit))

            kwargs["preexec_fn"] = _limit_memory

        log_file = open(log_path, "ab", buffering=0)
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--workers",
                "1",
                "--proxy-headers",
                "--log-level",
                "warning",
                cwd=str(backend),
                env=env,
                stdout=log_file,
                stderr=log_file,
                start_new_session=True,
                **kwargs,
            )
        finally:
            log_file.close()

        deadline = time.monotonic() + config.RUNTIME_START_TIMEOUT
        while time.monotonic() < deadline:
            if proc.returncode is not None:
                tail = _read_tail(log_path)
                raise AppRuntimeError(
                    f"后端启动失败（exit {proc.returncode}）：{tail[-1200:] or '无日志'}"
                )
            if await _port_open(port):
                self._instances[pid] = Instance(
                    pid=pid,
                    port=port,
                    proc=proc,
                    log_path=log_path,
                    last_used=time.monotonic(),
                )
                return port
            await asyncio.sleep(0.15)

        self._kill(proc)
        tail = _read_tail(log_path)
        raise AppRuntimeError(
            f"后端启动超时（{int(config.RUNTIME_START_TIMEOUT)}s）：{tail[-1200:] or '无日志'}"
        )

    async def logs(self, pid: str) -> str:
        return _read_tail(config.APPS_DIR / pid / ".runtime.log")

    async def stop(self, pid: str) -> None:
        async with self._locks.setdefault(pid, asyncio.Lock()):
            await self._stop_locked(pid)

    async def _stop_locked(self, pid: str) -> None:
        instance = self._instances.pop(pid, None)
        if not instance:
            return
        self._kill(instance.proc)
        try:
            await asyncio.wait_for(instance.proc.wait(), timeout=6)
        except asyncio.TimeoutError:  # pragma: no cover - stubborn child
            try:
                instance.proc.kill()
            except ProcessLookupError:
                pass

    @staticmethod
    def _kill(proc: asyncio.subprocess.Process) -> None:
        if proc.returncode is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGTERM)
            else:  # pragma: no cover
                proc.terminate()
        except ProcessLookupError:
            pass

    async def stop_all(self) -> None:
        for pid in list(self._instances):
            await self.stop(pid)

    def running(self) -> dict[str, int]:
        return {
            pid: item.port
            for pid, item in self._instances.items()
            if item.proc.returncode is None
        }


runtime = AppRuntime()
