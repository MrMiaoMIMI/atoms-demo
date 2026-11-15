"""Unified diff helpers shared by tool changes and the published-vs-current view.

Both diff views in the product use the same primitives:

* a single tool call compares its before/after content (``unified_diff``);
* the code panel's "unpublished changes" view compares the last published
  source snapshot with the current artifact tree (``diff_trees``).

The implementation is deliberately stdlib-only: ``difflib`` is enough for the
small generated projects and keeps the container dependency-free.
"""
from __future__ import annotations

from dataclasses import dataclass

import difflib

# A single diff should never bloat an SSE event or a SQLite row. Generators
# overwrite whole files occasionally; truncating is better than dropping the
# change event entirely.
MAX_DIFF_CHARS = 200_000
DEFAULT_CONTEXT = 3


@dataclass(frozen=True)
class DiffResult:
    """One file's unified diff plus the counters the UI shows as ``+n -m``."""

    diff: str = ""
    additions: int = 0
    deletions: int = 0
    truncated: bool = False

    @property
    def has_changes(self) -> bool:
        return bool(self.diff)


@dataclass(frozen=True)
class TreeChange:
    """A file-level change between two trees."""

    path: str
    change_type: str  # created | modified | deleted
    diff: DiffResult


def change_type(old: str | None, new: str | None) -> str:
    if old is None:
        return "created"
    if new is None:
        return "deleted"
    return "modified"


def _lines(text: str | None) -> list[str]:
    if not text:
        return []
    return text.splitlines()


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    marker = "\n... diff truncated ...\n"
    head = text[: max(0, max_chars - len(marker))]
    return head + marker, True


def unified_diff(
    *,
    path: str,
    old: str | None,
    new: str | None,
    from_label: str = "before",
    to_label: str = "after",
    context: int = DEFAULT_CONTEXT,
    max_chars: int = MAX_DIFF_CHARS,
) -> DiffResult:
    """Diff two versions of one file.

    ``None`` means the file does not exist on that side, which produces the
    familiar ``/dev/null`` header for created/deleted files.
    """
    old_lines = _lines(old)
    new_lines = _lines(new)
    if old is None and new is None:
        return DiffResult()
    if old == new:
        return DiffResult()

    fromfile = "/dev/null" if old is None else f"{from_label}/{path}"
    tofile = "/dev/null" if new is None else f"{to_label}/{path}"
    raw_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=fromfile,
            tofile=tofile,
            n=max(0, context),
            lineterm="",
        )
    )
    if not raw_lines:
        return DiffResult()

    additions = 0
    deletions = 0
    # Skip +++/--- headers: they are not content changes.
    for line in raw_lines:
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1

    text, truncated = _truncate("\n".join(raw_lines) + "\n", max_chars)
    return DiffResult(
        diff=text,
        additions=additions,
        deletions=deletions,
        truncated=truncated,
    )


def diff_trees(
    published: dict[str, str],
    current: dict[str, str],
    *,
    context: int = DEFAULT_CONTEXT,
    max_chars: int = MAX_DIFF_CHARS,
) -> list[TreeChange]:
    """Compare two complete source trees, returning only changed files."""
    changes: list[TreeChange] = []
    for path in sorted(set(published) | set(current)):
        old = published.get(path)
        new = current.get(path)
        old_missing = path not in published
        new_missing = path not in current
        if old_missing and new_missing:
            continue
        if not old_missing and not new_missing and old == new:
            continue
        kind = change_type(None if old_missing else old, None if new_missing else new)
        changes.append(
            TreeChange(
                path=path,
                change_type=kind,
                diff=unified_diff(
                    path=path,
                    old=None if old_missing else old,
                    new=None if new_missing else new,
                    from_label="published",
                    to_label="current",
                    context=context,
                    max_chars=max_chars,
                ),
            )
        )
    return changes


def summarize(changes: list[TreeChange]) -> dict[str, int]:
    summary = {"created": 0, "modified": 0, "deleted": 0}
    for change in changes:
        summary[change.change_type] = summary.get(change.change_type, 0) + 1
    return summary
