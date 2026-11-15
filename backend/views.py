"""Per-tool detail views for the workspace execution timeline.

The timeline only stores a short ``log`` per step, so anything richer (the
file a tool read, grep hits, build output, runtime logs) is turned into a
small, bounded JSON payload here. ``Toolbox.invoke`` persists that payload
next to the execution step and the UI fetches it on demand.

The module is deliberately pure: it never touches the database or the
filesystem. That keeps the presenters easy to unit test and lets the tool loop
decide how a failure should be shown.
"""
from __future__ import annotations

import json
from typing import Any

# Tools without an entry here have no dedicated view. ``read_project_state``
# deliberately stays out for now: its result mixes project metadata with the
# full file tree, and the timeline already shows enough of that in the log.
VIEW_TYPE_BY_TOOL: dict[str, str | None] = {
    "read_project_state": None,
    "list_files": "files",
    "read_file": "file",
    "grep": "search",
    "write_file": "diff",
    "edit_file": "diff",
    "delete_file": "diff",
    "build_preview": "terminal",
    "start_runtime": "terminal",
    "check_health": "http",
    "read_runtime_log": "terminal",
    "validate_plan": "json",
}

DIFF_TOOLS = frozenset({"write_file", "edit_file", "delete_file"})

MAX_TEXT = 32_000
MAX_CONTENT = 48_000
MAX_LOG = 32_000
MAX_BODY = 16_000
MAX_JSON = 32_000
MAX_PAYLOAD = 64_000
MAX_FILES = 500
MAX_MATCHES = 200
MAX_MATCH_LINE = 500

# Arguments that are safe and useful to show on a failed step. File contents
# from write_file/edit_file are never kept: the diff already covers them.
_ARG_KEYS: dict[str, tuple[str, ...]] = {
    "list_files": ("pattern",),
    "read_file": ("path", "offset", "limit"),
    "grep": ("pattern", "glob", "max_results"),
    "write_file": ("path", "overwrite"),
    "edit_file": ("path", "replace_all"),
    "delete_file": ("path",),
    "validate_plan": ("plan",),
    "check_health": ("port",),
    "read_runtime_log": ("lines",),
}


def _text(value: Any, limit: int = MAX_TEXT) -> tuple[str, bool]:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text, False
    return text[:limit] + "\n…（已截断）", True


def _safe_args(name: str, arguments: Any) -> dict:
    if not isinstance(arguments, dict):
        return {}
    keys = _ARG_KEYS.get(name, tuple(arguments.keys()))
    result: dict[str, Any] = {}
    for key in keys:
        if key not in arguments:
            continue
        value = arguments[key]
        if key == "plan":
            try:
                value = json.loads(json.dumps(value, ensure_ascii=False, default=str))
            except (TypeError, ValueError):
                value, _ = _text(value, MAX_JSON)
        result[key] = value
    return result


def _fit(payload: dict, truncated: bool) -> tuple[dict, bool]:
    """Keep a payload below the size the UI will fetch over the wire."""
    try:
        encoded = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return {"summary": str(payload)[:MAX_TEXT]}, True
    if len(encoded) <= MAX_PAYLOAD:
        return payload, truncated

    def shrink(value: Any, depth: int = 0) -> Any:
        if isinstance(value, str):
            limit = MAX_TEXT // (depth + 1)
            return value if len(value) <= limit else value[:limit] + "\n…（已截断）"
        if isinstance(value, list):
            return [shrink(item, depth + 1) for item in value[:MAX_MATCHES]]
        if isinstance(value, dict):
            return {
                key: shrink(item, depth + 1)
                for key, item in list(value.items())[:100]
            }
        return value

    return shrink(payload), True


def _finalize(
    view_type: str, payload: dict, truncated: bool = False
) -> tuple[str, dict, bool]:
    payload, truncated = _fit(payload, truncated)
    return view_type, payload, truncated


def _error_message(result: dict) -> str:
    error = result.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or "工具执行失败")
    return "工具执行失败"


def _error_view(name: str, arguments: Any, result: dict) -> tuple[str, dict, bool]:
    error = result.get("error")
    error = error if isinstance(error, dict) else {}
    message, _ = _text(error.get("message") or "工具执行失败", 4000)
    payload = {
        "tool": name,
        "arguments": _safe_args(name, arguments),
        "error": {
            "code": error.get("code") or "error",
            "message": message,
        },
    }
    return _finalize("json", payload)


def _list_files_view(arguments: Any, data: dict) -> tuple[str, dict, bool]:
    raw = data.get("files")
    entries: list[dict] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict) or not item.get("path"):
                continue
            entries.append(
                {
                    "path": str(item["path"]),
                    "bytes": int(item.get("bytes") or 0),
                    "lines": int(item.get("lines") or 0),
                }
            )
    pattern = arguments.get("pattern") if isinstance(arguments, dict) else None
    payload = {
        "pattern": pattern if isinstance(pattern, str) else None,
        "files": entries[:MAX_FILES],
        "total": int(data.get("total") or len(entries)),
        "truncated": len(entries) > MAX_FILES,
    }
    return _finalize("files", payload, len(entries) > MAX_FILES)


def _read_file_view(data: dict) -> tuple[str, dict, bool]:
    content, truncated = _text(data.get("content") or "", MAX_CONTENT)
    payload = {
        "path": data.get("path"),
        "start_line": int(data.get("start_line") or 1),
        "end_line": data.get("end_line"),
        "total_lines": data.get("total_lines"),
        "content": content,
        "truncated": bool(data.get("truncated")) or truncated,
    }
    return _finalize(
        "file", payload, bool(data.get("truncated")) or truncated
    )


def _grep_view(arguments: Any, data: dict) -> tuple[str, dict, bool]:
    raw = data.get("matches")
    matches: list[dict] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict) or not item.get("path"):
                continue
            text, _ = _text(item.get("text") or "", MAX_MATCH_LINE)
            matches.append(
                {
                    "path": str(item["path"]),
                    "line": int(item.get("line") or 0),
                    "text": text,
                }
            )
    truncated = bool(data.get("truncated")) or len(matches) > MAX_MATCHES
    payload = {
        "pattern": arguments.get("pattern") if isinstance(arguments, dict) else None,
        "glob": arguments.get("glob") if isinstance(arguments, dict) else None,
        "matches": matches[:MAX_MATCHES],
        "total": int(data.get("total") or len(matches)),
        "truncated": truncated,
    }
    return _finalize("search", payload, truncated)


def _terminal_view(
    name: str,
    result: dict,
    data: dict,
) -> tuple[str, dict, bool]:
    ok = bool(result.get("ok"))
    error_message = _error_message(result) if not ok else ""
    output = data.get("output") or data.get("log") or error_message or ""
    output, truncated = _text(output, MAX_LOG)
    payload: dict[str, Any] = {
        "ok": ok,
        "command": data.get("command") or "",
        "mode": data.get("mode"),
        "port": data.get("port"),
        "duration_ms": data.get("duration_ms"),
        "exit_code": data.get("exit_code"),
        "output": output,
        "truncated": truncated,
    }
    if name == "read_runtime_log":
        lines = data.get("lines")
        payload["lines"] = lines if isinstance(lines, list) else []
        if not output and isinstance(lines, list):
            payload["output"] = "\n".join(str(line) for line in lines)
        payload["truncated"] = bool(data.get("truncated")) or truncated
        return _finalize("terminal", payload, payload["truncated"])
    return _finalize("terminal", payload, truncated)


def _http_view(result: dict, data: dict) -> tuple[str, dict, bool]:
    ok = bool(result.get("ok"))
    body = data.get("body") or ("" if ok else _error_message(result))
    body, truncated = _text(body, MAX_BODY)
    payload = {
        "ok": ok,
        "method": data.get("method") or "GET",
        "url": data.get("url") or "/api/health",
        "status": data.get("status"),
        "duration_ms": data.get("duration_ms"),
        "body": body,
        "truncated": truncated,
    }
    return _finalize("http", payload, truncated)


def _validate_plan_view(arguments: Any, data: dict) -> tuple[str, dict, bool]:
    plan = arguments.get("plan") if isinstance(arguments, dict) else None
    truncated = False
    if plan is not None:
        try:
            encoded = json.dumps(plan, ensure_ascii=False, default=str)
            if len(encoded) > MAX_JSON:
                plan = encoded[:MAX_JSON] + "\n…（已截断）"
                truncated = True
        except (TypeError, ValueError):
            plan, truncated = _text(plan, MAX_JSON)
    payload = {"valid": bool(data.get("valid")), "plan": plan}
    return _finalize("json", payload, truncated)


def build_view(
    name: str,
    arguments: Any,
    result: Any,
) -> tuple[str, dict, bool] | None:
    """Return ``(view_type, payload, truncated)`` for one tool call, or None.

    ``result`` is what ``Toolbox.invoke`` is about to hand back to the model:
    either ``{"ok": True, "data": ...}`` or ``{"ok": False, "error": ...}``.
    """
    if not isinstance(result, dict):
        result = {"ok": True, "data": result}
    ok = bool(result.get("ok"))
    data = result.get("data")
    data = data if isinstance(data, dict) else {}

    if name in DIFF_TOOLS:
        # A real mutation already has a persisted file_changes row; the UI
        # shows that diff instead of a separate payload.
        if ok and data.get("change_id"):
            return "diff", {}, False
        if ok:
            return None
        return _error_view(name, arguments, result)

    planned = VIEW_TYPE_BY_TOOL.get(name)
    if planned is None:
        return None

    if not ok:
        if name in {"build_preview", "start_runtime"}:
            return _terminal_view(name, result, data)
        if name == "check_health":
            return _http_view(result, data)
        return _error_view(name, arguments, result)

    if name == "list_files":
        return _list_files_view(arguments, data)
    if name == "read_file":
        return _read_file_view(data)
    if name == "grep":
        return _grep_view(arguments, data)
    if name in {"build_preview", "start_runtime", "read_runtime_log"}:
        return _terminal_view(name, result, data)
    if name == "check_health":
        return _http_view(result, data)
    if name == "validate_plan":
        return _validate_plan_view(arguments, data)
    return None
