"""Bundle generated React/TSX sources into a preview the iframe can load.

The generated repository is a normal Vite project (``npm run dev`` / ``npm run
build`` for humans). For instant preview inside the demo we bundle the same
sources with esbuild from a shared, pre-installed toolchain — no per-project
``npm install`` and no build step on the 2C2G box beyond this one process.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from pathlib import Path

import config
import scaffold


class BuildError(RuntimeError):
    """Frontend sources could not be bundled."""


def _toolchain() -> Path | None:
    """esbuild ships a native binary; run it directly (no Node at runtime)."""
    candidates: list[Path] = []
    if os.getenv("ESBUILD_BIN"):
        candidates.append(Path(os.environ["ESBUILD_BIN"]))
    modules = config.PREVIEW_NODE_MODULES
    candidates += [
        modules / "esbuild" / "bin" / "esbuild",
        modules / ".bin" / "esbuild",
    ]
    for candidate in candidates:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate
    return None


def toolchain_hint() -> str:
    return (
        "预览构建工具未安装。请在项目根目录执行 "
        "`npm --prefix backend/runtime/frontend install` 后重试（Docker 镜像已内置）。"
    )


def _toolchain_bin(name: str) -> Path | None:
    modules = config.PREVIEW_NODE_MODULES
    candidates = [
        modules / ".bin" / name,
        modules / name / "bin" / name,
    ]
    if name == "tsc":
        candidates.append(modules / "typescript" / "bin" / "tsc")
    for candidate in candidates:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate
    return None


async def _run_typecheck(work: Path) -> None:
    """Block on real TypeScript errors before esbuild strips the types."""
    tsc = _toolchain_bin("tsc")
    if not tsc:
        return
    proc = await asyncio.create_subprocess_exec(
        str(tsc),
        "--noEmit",
        "-p",
        "tsconfig.json",
        cwd=str(work),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=config.FRONTEND_TYPECHECK_TIMEOUT
        )
    except asyncio.TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise BuildError(
            "TypeScript 类型检查超时（超过 "
            f"{int(config.FRONTEND_TYPECHECK_TIMEOUT)}s）"
        ) from exc
    if proc.returncode != 0:
        output = (stdout + stderr).decode("utf-8", "ignore").strip()
        raise BuildError(
            "TypeScript 类型检查失败：\n" + (output[-4000:] or "未知错误")
        )


def _copy_sources(source: Path, target: Path) -> None:
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("node_modules", "dist", ".preview", ".runtime.log"),
    )
    shared = config.PREVIEW_NODE_MODULES
    if not shared.exists():
        raise BuildError(toolchain_hint())
    link = target / "node_modules"
    try:
        link.symlink_to(shared, target_is_directory=True)
    except OSError as exc:  # pragma: no cover - platform specific
        raise BuildError(f"无法链接共享 node_modules：{exc}") from exc


async def build(pid: str, title: str) -> bool:
    """Build ``frontend/`` into ``apps/{pid}/.preview/``.

    Returns False when the project has no frontend at all.
    """
    source = config.APPS_DIR / pid / "frontend"
    entry = source / "src" / "main.tsx"
    if not entry.exists():
        return False

    esbuild = _toolchain()
    if not esbuild:
        raise BuildError(toolchain_hint())

    work = config.BUILD_DIR / f"{pid}-{uuid.uuid4().hex[:8]}"
    work.parent.mkdir(parents=True, exist_ok=True)
    try:
        await asyncio.to_thread(_copy_sources, source, work)
        if config.FRONTEND_TYPECHECK:
            await _run_typecheck(work)
        cmd = [
            str(esbuild),
            "src/main.tsx",
            "--bundle",
            "--outdir=dist",
            "--entry-names=app",
            "--format=iife",
            "--jsx=automatic",
            "--loader:.tsx=tsx",
            "--loader:.ts=ts",
            "--loader:.css=css",
            "--loader:.svg=dataurl",
            # Fonts are served by the demo shell at /fonts/; keep the absolute
            # URL instead of trying to resolve it from the project source.
            "--external:/fonts/*",
            "--target=es2020",
            "--minify",
            '--define:process.env.NODE_ENV="production"',
            "--log-level=warning",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(work),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=config.FRONTEND_BUILD_TIMEOUT
            )
        except asyncio.TimeoutError as exc:
            proc.kill()
            await proc.wait()
            raise BuildError("前端构建超时（超过 %ss）" % int(config.FRONTEND_BUILD_TIMEOUT)) from exc
        if proc.returncode != 0:
            message = stderr.decode("utf-8", "ignore").strip()
            raise BuildError(message[-4000:] or "esbuild 构建失败")

        dist = work / "dist"
        if not (dist / "app.js").exists():
            raise BuildError("构建产物缺少 app.js")
        await asyncio.to_thread(_publish_build, pid, title, dist)
        return True
    finally:
        await asyncio.to_thread(shutil.rmtree, work, True)


def _publish_build(pid: str, title: str, dist: Path) -> None:
    target = config.APPS_DIR / pid / ".preview"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    for item in dist.iterdir():
        if item.is_file():
            shutil.copy2(item, target / item.name)
    has_css = (target / "app.css").exists()
    (target / "index.html").write_text(
        scaffold.preview_shell(pid, title, has_css), encoding="utf-8"
    )


def publish_api_page(pid: str, title: str, api: list[dict]) -> None:
    """Backend-only projects get a small built-in API console as preview."""
    target = config.APPS_DIR / pid / ".preview"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text(
        scaffold.api_preview_page(pid, title, api), encoding="utf-8"
    )
