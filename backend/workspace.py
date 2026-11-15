"""In-memory source workspace used by the agent's file tools.

The workspace is the single place where an agent reads and mutates project
files. Nothing touches disk until ``apply_to`` is called, so a failed tool
round can be discarded without repairing a half-written project tree.

Safety rules live here rather than in individual tools:

* paths are normalised and must stay inside the generated project;
* runtime/published/data directories are never writable;
* only source-like extensions are accepted;
* edits are exact-match and must be unique unless ``replace_all`` is set.
"""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import diffing
import scaffold

MAX_READ_BYTES = 64_000
MAX_READ_LINES = 800
MAX_WRITE_BYTES = 200_000
MAX_PATH_LENGTH = 200
MAX_GREP_PATTERN = 200
MAX_GREP_RESULTS = 50
MAX_GREP_LINE = 300

# Directories that belong to the runtime, a published snapshot, package
# tooling or VCS. They are never part of the editable source tree.
PROTECTED_PREFIXES = (
    ".published",
    ".published.tmp-",
    ".published.old-",
    ".preview",
    ".build",
    ".git",
    ".venv",
    "node_modules",
    "frontend/node_modules",
    "frontend/dist",
    "backend/.venv",
    "backend/data",
    "backend/__pycache__",
    "frontend/__pycache__",
    "__pycache__",
)
PROTECTED_EXACT = {".runtime.log", "backend/.runtime.log"}

# .gitignore has no extension; every other file must use a generated-source
# extension. This blocks .env, shell scripts and other accidental artefacts.
ALLOWED_NAMELESS = {".gitignore"}
_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_DRIVE_RE = re.compile(r"^[A-Za-z]:")


class WorkspaceError(Exception):
    """Base class for errors that should be returned to the model as a tool result."""

    code = "workspace_error"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_result(self) -> dict:
        return {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
                **({"details": self.details} if self.details else {}),
            },
        }


class PathDenied(WorkspaceError):
    code = "path_denied"


class NotFound(WorkspaceError):
    code = "not_found"


class OverwriteRequired(WorkspaceError):
    code = "overwrite_required"


class NoMatch(WorkspaceError):
    code = "no_match"


class AmbiguousMatch(WorkspaceError):
    code = "ambiguous_match"


class TooLarge(WorkspaceError):
    code = "too_large"


class InvalidPattern(WorkspaceError):
    code = "invalid_pattern"


def normalize_path(path: str) -> str:
    """Return a safe, normalised project-relative path or raise PathDenied."""
    if not isinstance(path, str):
        raise PathDenied("路径必须是字符串")
    raw = path.strip().replace("\\", "/")
    if not raw or len(raw) > MAX_PATH_LENGTH:
        raise PathDenied("路径为空或过长")
    if raw.startswith("/") or _DRIVE_RE.match(raw) or "\x00" in raw:
        raise PathDenied("只允许项目内的相对路径")
    segments = raw.split("/")
    if ".." in segments:
        raise PathDenied("路径不能包含 ..")
    normalized = posixpath.normpath(raw)
    if normalized in (".", "..") or normalized.startswith("../"):
        raise PathDenied("只允许项目内的相对路径")
    segments = normalized.split("/")
    for segment in segments:
        if segment in ("", ".", "..") or not _SEGMENT_RE.match(segment):
            raise PathDenied(f"非法路径片段：{segment!r}")
    if normalized != ".gitignore":
        # Hidden files (other than .gitignore) are not part of the source tree.
        for segment in segments:
            if segment.startswith("."):
                raise PathDenied(f"不允许隐藏文件：{normalized}")
    if normalized.lower() in {name.lower() for name in PROTECTED_EXACT}:
        raise PathDenied(f"受保护的文件：{normalized}")
    for prefix in PROTECTED_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            raise PathDenied(f"受保护的目录：{prefix}")
    if normalized not in ALLOWED_NAMELESS:
        ext = "." + normalized.rsplit(".", 1)[-1].lower() if "." in normalized else ""
        if ext not in scaffold.ALLOWED_EXT:
            raise PathDenied(f"不允许的文件类型：{ext or '（无扩展名）'}")
    return normalized


def _glob_regex(pattern: str) -> re.Pattern[str]:
    """Translate a small, predictable glob (``**`` and ``*``) to a regex."""
    out: list[str] = ["^"]
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if pattern[i : i + 2] == "**":
                i += 2
                if pattern[i : i + 1] == "/":
                    i += 1
                    out.append("(?:.*/)?")
                else:
                    out.append(".*")
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    out.append("$")
    return re.compile("".join(out))


def _matches_glob(path: str, pattern: str | None) -> bool:
    if not pattern:
        return True
    pattern = pattern.strip().replace("\\", "/")
    if not pattern:
        return True
    if "*" not in pattern and "?" not in pattern:
        cleaned = pattern.rstrip("/")
        return path == cleaned or path.startswith(cleaned + "/")
    return bool(_glob_regex(pattern).match(path))


@dataclass(frozen=True)
class FileInfo:
    path: str
    bytes: int
    lines: int


@dataclass(frozen=True)
class ReadResult:
    path: str
    content: str
    start_line: int
    end_line: int
    total_lines: int
    truncated: bool


@dataclass(frozen=True)
class GrepMatch:
    path: str
    line: int
    text: str


@dataclass(frozen=True)
class GrepResult:
    matches: list[GrepMatch]
    total: int
    truncated: bool


@dataclass(frozen=True)
class FileChange:
    """One mutation inside a workspace round."""

    path: str
    change_type: str  # created | modified | deleted
    old: str | None
    new: str | None
    diff: diffing.DiffResult

    @property
    def additions(self) -> int:
        return self.diff.additions

    @property
    def deletions(self) -> int:
        return self.diff.deletions


@dataclass
class Workspace:
    """A staged copy of the project source tree."""

    base: dict[str, str] = field(default_factory=dict)
    files: dict[str, str] = field(init=False)
    deleted: set[str] = field(default_factory=set)
    history: list[FileChange] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Normalise keys once; callers load from artifacts, which should already
        # be clean, but a stale row must never bypass the path policy.
        clean: dict[str, str] = {}
        for path, content in self.base.items():
            try:
                clean[normalize_path(path)] = content
            except WorkspaceError:
                continue
        self.base = clean
        self.files = dict(clean)

    # -- reads -------------------------------------------------------------

    def read(self, path: str, offset: int = 1, limit: int = 400) -> ReadResult:
        path = normalize_path(path)
        if path not in self.files:
            raise NotFound(f"文件不存在：{path}", path=path)
        content = self.files[path]
        lines = content.splitlines()
        total = len(lines)
        if total == 0:
            return ReadResult(path, "", 0, 0, 0, False)
        offset = max(1, min(int(offset), total))
        limit = max(1, min(int(limit), MAX_READ_LINES))
        start = offset - 1
        end = min(total, start + limit)
        selected: list[str] = []
        size = 0
        truncated = False
        for line in lines[start:end]:
            extra = len(line.encode("utf-8")) + 1
            if selected and size + extra > MAX_READ_BYTES:
                truncated = True
                break
            selected.append(line)
            size += extra
        if end < total:
            truncated = True
        return ReadResult(
            path=path,
            content="\n".join(selected),
            start_line=start + 1,
            end_line=start + len(selected),
            total_lines=total,
            truncated=truncated,
        )

    def list_files(self, pattern: str | None = None) -> list[FileInfo]:
        infos: list[FileInfo] = []
        for path in sorted(self.files):
            if not _matches_glob(path, pattern):
                continue
            content = self.files[path]
            infos.append(
                FileInfo(
                    path=path,
                    bytes=len(content.encode("utf-8")),
                    lines=len(content.splitlines()),
                )
            )
        return infos

    def grep(
        self,
        pattern: str,
        glob: str | None = None,
        max_results: int = 30,
    ) -> GrepResult:
        if not isinstance(pattern, str) or not pattern.strip():
            raise InvalidPattern("搜索表达式不能为空")
        if len(pattern) > MAX_GREP_PATTERN:
            raise InvalidPattern("搜索表达式过长")
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise InvalidPattern(f"无效正则：{exc}") from exc
        max_results = max(1, min(int(max_results), MAX_GREP_RESULTS))
        found: list[GrepMatch] = []
        total = 0
        for path in sorted(self.files):
            if not _matches_glob(path, glob):
                continue
            for number, line in enumerate(self.files[path].splitlines(), start=1):
                if not regex.search(line):
                    continue
                total += 1
                if len(found) < max_results:
                    found.append(
                        GrepMatch(
                            path=path,
                            line=number,
                            text=line[:MAX_GREP_LINE],
                        )
                    )
        return GrepResult(
            matches=found,
            total=total,
            truncated=total > max_results,
        )

    # -- writes ------------------------------------------------------------

    def write(self, path: str, content: str, overwrite: bool = False) -> FileChange | None:
        path = normalize_path(path)
        if not isinstance(content, str):
            raise TooLarge("文件内容必须是字符串", path=path)
        size = len(content.encode("utf-8"))
        if size > MAX_WRITE_BYTES:
            raise TooLarge(
                f"文件超过 {MAX_WRITE_BYTES:,} 字节上限",
                path=path,
                bytes=size,
            )
        exists = path in self.files
        if exists and not overwrite:
            raise OverwriteRequired(
                "文件已存在；修改请用 edit_file，整文件重写请显式 overwrite=true",
                path=path,
            )
        old = self.files.get(path)
        if exists and old == content:
            return None
        kind = "modified" if exists else "created"
        self.files[path] = content
        self.deleted.discard(path)
        change = self._change(path, kind, old, content)
        self.history.append(change)
        return change

    def edit(
        self,
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> FileChange | None:
        path = normalize_path(path)
        if path not in self.files:
            raise NotFound(f"文件不存在：{path}", path=path)
        if not isinstance(old_string, str) or not old_string:
            raise NoMatch("old_string 不能为空", path=path)
        if not isinstance(new_string, str):
            raise NoMatch("new_string 必须是字符串", path=path)
        content = self.files[path]
        count = content.count(old_string)
        if count == 0:
            raise NoMatch(
                "old_string 在文件中不存在；文件可能已变化，请重新 read_file",
                path=path,
                match_count=0,
            )
        if count > 1 and not replace_all:
            raise AmbiguousMatch(
                "old_string 命中多处；请提供更长的唯一片段，或设置 replace_all=true",
                path=path,
                match_count=count,
                lines=self._match_lines(content, old_string),
            )
        updated = content.replace(
            old_string, new_string, -1 if replace_all else 1
        )
        if updated == content:
            return None
        self.files[path] = updated
        change = self._change(path, "modified", content, updated)
        self.history.append(change)
        return change

    def delete(self, path: str) -> FileChange:
        path = normalize_path(path)
        if path not in self.files:
            raise NotFound(f"文件不存在：{path}", path=path)
        old = self.files.pop(path)
        self.deleted.add(path)
        change = self._change(path, "deleted", old, None)
        self.history.append(change)
        return change

    # -- diff / materialisation -------------------------------------------

    def _change(
        self, path: str, kind: str, old: str | None, new: str | None
    ) -> FileChange:
        return FileChange(
            path=path,
            change_type=kind,
            old=old,
            new=new,
            diff=diffing.unified_diff(path=path, old=old, new=new),
        )

    @staticmethod
    def _match_lines(content: str, needle: str) -> list[int]:
        lines: list[int] = []
        cursor = 0
        for _ in range(5):
            index = content.find(needle, cursor)
            if index < 0:
                break
            lines.append(content.count("\n", 0, index) + 1)
            cursor = index + 1
        return lines

    @property
    def dirty(self) -> bool:
        return self.files != self.base

    def diff_base(self) -> list[diffing.TreeChange]:
        return diffing.diff_trees(self.base, self.files)

    def commit_plan(self) -> tuple[dict[str, str], list[str]]:
        """Return (changed files, deleted paths) relative to the round's base."""
        changed = {
            path: content
            for path, content in self.files.items()
            if self.base.get(path) != content
        }
        deleted = sorted(set(self.base) - set(self.files))
        return changed, deleted

    def apply_to(
        self,
        root: Path,
        *,
        reconcile_source: bool = False,
    ) -> dict[str, int]:
        """Write changed files and remove deleted ones under ``root``.

        Only changed files are written; unchanged files keep their existing
        bytes/mtime. ``reconcile_source`` additionally removes source files that
        exist on disk but not in the workspace (mode changes, stale files), while
        never touching protected runtime/data directories.
        """
        root = Path(root).resolve()
        changed, deleted = self.commit_plan()
        written = 0
        removed = 0
        for path, content in changed.items():
            dest = self._safe_dest(root, path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            written += 1
        for path in deleted:
            dest = self._safe_dest(root, path)
            if dest.is_file() or dest.is_symlink():
                dest.unlink()
                removed += 1
        if reconcile_source:
            known = set(self.files)
            for prefix in ("frontend", "backend"):
                base = root / prefix
                if not base.is_dir():
                    continue
                for item in base.rglob("*"):
                    if not item.is_file():
                        continue
                    rel = item.relative_to(root).as_posix()
                    try:
                        normalize_path(rel)
                    except WorkspaceError:
                        continue
                    if rel in known:
                        continue
                    item.unlink()
                    removed += 1
        return {"written": written, "removed": removed}

    @staticmethod
    def _safe_dest(root: Path, path: str) -> Path:
        dest = (root / path).resolve()
        if dest != root and root not in dest.parents:
            raise PathDenied(f"路径逃逸项目目录：{path}")
        return dest


def workspace_from(files: dict[str, str]) -> Workspace:
    return Workspace(dict(files))
