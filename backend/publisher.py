"""Published-site snapshots.

A published project is a copy of the last successful working build:

    apps/{pid}/.published/
        site/        built frontend (or API console), base rewritten to /s/{pid}/
        backend/     backend source snapshot; data -> ../../backend/data
        manifest.json

The working tree keeps being rewritten by chat builds, while this snapshot is
only replaced by an explicit publish. That is what keeps an online site stable.
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import config

PUBLISHED_DIR = ".published"
SITE_DIR = "site"
BACKEND_DIR = "backend"
SOURCE_FILE = "source.json"

# Source paths that belong to the editable tree. The published baseline is used
# for the "unpublished changes" diff, so it must contain exactly the files the
# author edits, never runtime artefacts.
_SOURCE_ROOTS = ("frontend", "backend")
_SOURCE_ROOT_FILES = ("README.md", ".gitignore")
_IGNORE_PARTS = {
    "data",
    "node_modules",
    "dist",
    "__pycache__",
    ".venv",
    ".preview",
    ".published",
}


class PublishError(RuntimeError):
    """The working build could not be snapshotted."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def project_root(pid: str) -> Path:
    return config.APPS_DIR / pid


def published_root(pid: str) -> Path:
    return project_root(pid) / PUBLISHED_DIR


def site_dir(pid: str) -> Path:
    return published_root(pid) / SITE_DIR


def backend_dir(pid: str) -> Path:
    return published_root(pid) / BACKEND_DIR


def manifest_path(pid: str) -> Path:
    return published_root(pid) / "manifest.json"


def is_ready(pid: str) -> bool:
    """True when a published static entry actually exists on disk."""
    return (site_dir(pid) / "index.html").is_file()


def read_manifest(pid: str) -> dict | None:
    try:
        return json.loads(manifest_path(pid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_source(pid: str) -> dict | None:
    """Read the published source baseline, or None when it is not available.

    Older snapshots (or a partially failed publish) may not have source.json;
    callers should show "baseline unavailable" instead of fabricating a diff.
    """
    path = published_root(pid) / SOURCE_FILE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), dict):
        return None
    return payload


def _read_source_tree(root: Path) -> dict[str, str]:
    """Fallback: collect source files from disk when the caller did not pass them."""
    files: dict[str, str] = {}
    for name in _SOURCE_ROOT_FILES:
        path = root / name
        if path.is_file():
            files[name] = path.read_text(encoding="utf-8", errors="replace")
    for prefix in _SOURCE_ROOTS:
        base = root / prefix
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if any(part in _IGNORE_PARTS for part in relative.parts):
                continue
            if path.suffix == ".pyc":
                continue
            try:
                files[relative.as_posix()] = path.read_text(
                    encoding="utf-8", errors="replace"
                )
            except OSError:
                continue
    return files


def _rewrite_base(index: Path, pid: str) -> None:
    """Point the published shell at /s/{pid}/ instead of the workspace route."""
    text = index.read_text(encoding="utf-8")
    text = text.replace(f'href="/apps/{pid}/"', f'href="/s/{pid}/"')
    text = text.replace(f"href='/apps/{pid}/'", f"href='/s/{pid}/'")
    index.write_text(text, encoding="utf-8")


def snapshot(
    pid: str,
    version: int,
    mode: str,
    title: str,
    source: dict[str, str] | None = None,
) -> dict:
    """Copy the current successful build into a new published snapshot.

    Synchronous on purpose; callers run it with ``asyncio.to_thread``. The
    caller must stop the published runtime first so no process keeps files
    open from the old tree.
    """
    root = project_root(pid)
    preview = root / ".preview"
    if not (preview / "index.html").is_file():
        raise PublishError("构建产物不存在，请先在对话中完成一次构建")

    tmp = root / f".published.tmp-{uuid.uuid4().hex[:8]}"
    old = root / f".published.old-{uuid.uuid4().hex[:8]}"
    final = published_root(pid)
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    try:
        shutil.copytree(preview, tmp / SITE_DIR)
        _rewrite_base(tmp / SITE_DIR / "index.html", pid)

        source_backend = root / "backend"
        if (source_backend / "main.py").is_file():
            shutil.copytree(
                source_backend,
                tmp / BACKEND_DIR,
                ignore=shutil.ignore_patterns("data", "__pycache__", "*.pyc"),
            )
            # The published backend keeps using the project's one SQLite file
            # so visitor writes and the workspace preview see the same data.
            live_data = source_backend / "data"
            live_data.mkdir(parents=True, exist_ok=True)
            os.symlink(
                "../../backend/data",
                tmp / BACKEND_DIR / "data",
                target_is_directory=True,
            )

        manifest = {
            "version": version,
            "mode": mode,
            "title": title,
            "published_at": _now(),
        }
        (tmp / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # Baseline for the "unpublished changes" diff. Callers pass the artifact
        # tree; the disk fallback exists for direct publisher use.
        baseline = {
            "version": version,
            "mode": mode,
            "title": title,
            "published_at": manifest["published_at"],
            "files": source if source is not None else _read_source_tree(root),
        }
        (tmp / SOURCE_FILE).write_text(
            json.dumps(baseline, ensure_ascii=False), encoding="utf-8"
        )

        if final.exists():
            os.replace(final, old)
        try:
            os.replace(tmp, final)
        except Exception:
            if old.exists():
                os.replace(old, final)
            raise
        if old.exists():
            shutil.rmtree(old, ignore_errors=True)
        return manifest
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        if old.exists() and not final.exists():
            os.replace(old, final)
        raise
