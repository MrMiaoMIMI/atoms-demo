"""Canned agent replies used when no LLM key is configured.

They follow the same output contract as the real prompts: Mike ends with
``@Bob`` or ``@Alex``; consult replies never hand off.
"""
from __future__ import annotations

from typing import Any


def _file_list(meta: dict[str, Any]) -> list[str]:
    files = meta.get("files") or []
    if isinstance(files, dict):
        files = list(files)
    return [str(item) for item in files][:12]


def _complexity(message: str, mode: str | None, files: list[str]) -> bool:
    text = (message or "").lower()
    backend_need = any(
        token in text
        for token in (
            "登录",
            "支付",
            "订单",
            "数据库",
            "数据保存",
            "持久化",
            "存储",
            "sqlite",
            "多表",
            "权限",
            "购物车",
            "后台",
            "库存",
            "api",
            "后端",
            "全栈",
            "webhook",
            "用户",
            "fullstack",
        )
    )
    frontend_only = any(
        token in text
        for token in (
            "颜色",
            "配色",
            "样式",
            "字体",
            "文案",
            "按钮",
            "布局",
            "间距",
            "圆角",
            "图片",
            "动效",
            "首页",
            "落地页",
        )
    )
    if backend_need:
        return True
    if mode in ("fullstack", "backend") and not frontend_only:
        return True
    if len(files) > 12:
        return True
    return len(message or "") > 240


def mike_reply(meta: dict[str, Any]) -> str:
    message = str(meta.get("prompt") or "").strip()
    project_name = str(meta.get("project_name") or "当前项目")
    mode = meta.get("mode")
    files = _file_list(meta)
    complex_task = _complexity(message, mode, files)
    target = "Bob" if complex_task else "Alex"
    summary = message.replace("\n", " ").strip()
    if len(summary) > 90:
        summary = summary[:90] + "…"
    if not summary:
        summary = "理解并推进当前需求。"
    steps = (
        "1. 明确目标与约束，确认现有项目状态。\n"
        "2. 设计数据模型、接口和文件改动范围。\n"
        "3. 由 Alex 完成实现、自检和预览。"
        if complex_task
        else "1. 明确目标与约束。\n2. 直接在当前代码上完成实现与自检。"
    )
    return (
        f"需求理解：{summary}\n\n"
        f"任务拆解：\n{steps}\n\n"
        f"复杂度：{'较高' if complex_task else '较低'}（{mode or '空项目'} · {len(files)} 个已有文件）\n"
        f"下一步：@{target}"
    )


def consult_reply(meta: dict[str, Any]) -> str:
    agent = str(meta.get("agent") or "mike")
    project_name = str(meta.get("project_name") or "当前项目")
    mode = str(meta.get("mode") or "frontend")
    files = _file_list(meta)
    version = int(meta.get("version") or 0)
    prompt = str(meta.get("prompt") or "")
    realtime = any(token in prompt for token in ("天气", "新闻", "股价", "实时", "今天"))
    realtime_note = (
        "\n\n说明：我没有接入实时外部数据，无法给出真实天气/新闻等实时信息；"
        "如果需要，可以接一个天气或搜索工具后再查询。"
        if realtime
        else ""
    )
    joined = "、".join(files) if files else "（还没有文件）"
    received = f"收到的问题：{prompt[:120]}\n\n" if prompt else ""

    if agent == "bob":
        mode_text = {
            "frontend": "纯前端（Vite + React + TypeScript）",
            "fullstack": "前后端一体（React + FastAPI + SQLite）",
            "backend": "纯后端 API（FastAPI + SQLite）",
        }.get(mode, mode)
        backend_files = [f for f in files if f.startswith("backend/")]
        frontend_files = [f for f in files if f.startswith("frontend/")]
        return (
            f"{received}"
            f"从架构上看，「{project_name}」当前是 {mode_text}，最新版本 v{version}。\n\n"
            f"- 前端文件：{len(frontend_files)} 个"
            + (f"（如 {', '.join(frontend_files[:4])}）" if frontend_files else "")
            + "\n"
            f"- 后端文件：{len(backend_files)} 个"
            + (f"（如 {', '.join(backend_files[:4])}）" if backend_files else "")
            + "\n"
            f"- 全部文件：{joined}\n\n"
            "边界上，前端只依赖 React，后端使用 FastAPI + aiosqlite；"
            "数据保存在项目自己的 backend/data/app.db，与 demo 数据库隔离。"
            + realtime_note
        )

    if agent == "alex":
        frontend = any(f.startswith("frontend/") for f in files)
        backend = any(f.startswith("backend/") for f in files)
        parts = []
        if frontend:
            parts.append("前端由 Vite + React 18 + TypeScript 构建，样式在 frontend/src/styles.css")
        if backend:
            parts.append("后端是独立的 FastAPI 进程，数据库在 backend/data/app.db")
        if not parts:
            parts.append("当前项目还没有生成可运行代码")
        return (
            f"{received}"
            f"从实现上看，「{project_name}」最新版本 v{version}，共 {len(files)} 个文件。\n\n"
            + "；".join(parts)
            + "。\n\n"
            f"文件清单：{joined}\n\n"
            "预览由共享 esbuild 工具链打包，后端按项目启动独立 uvicorn 子进程。"
            + realtime_note
        )

    return (
        f"{received}"
        f"「{project_name}」目前是一个 {mode} 形态的项目，最新版本 v{version}，"
        f"共有 {len(files)} 个文件。\n\n"
        "从团队领导的角度，我会先确认目标和边界，再安排架构与实现；"
        "当前项目可以直接在右侧预览，继续对话即可增量修改。\n\n"
        f"文件清单：{joined}"
        + realtime_note
    )
