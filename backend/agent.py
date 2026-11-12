"""Multi-role orchestration on top of a single LLM.

Planner -> Coder (per file) -> Reviewer -> Deployer. Each role is a prompt
route; every transition is emitted as an SSE event and persisted as an
execution row so the timeline survives a refresh.
"""
import asyncio
import json
import re
import shutil
from collections.abc import Awaitable, Callable
from typing import Any

import config
import db
from llm import MockLLM, get_llm

Emit = Callable[[str, dict], Awaitable[Any]]

PLANNER_SYSTEM = """你是 "Planner" Agent，负责把用户的自然语言需求拆解为一个可直接在浏览器打开的静态 Web 项目。
只输出 JSON，不要 markdown 代码围栏，不要任何解释。

JSON 结构：
{"summary": "一句话说明要做什么", "files": [{"path": "index.html", "purpose": "该文件的职责"}]}

规则：
1. 1-4 个扁平文件（不要子目录），必须包含 index.html。
2. 样式放 styles.css，交互逻辑放 app.js；纯展示页可以省略 app.js。
3. 只允许纯静态前端（HTML/CSS/JS，可通过 CDN 引用库），不得要求 npm 构建。
4. 禁止 localStorage / sessionStorage（预览运行在不透明源的沙箱 iframe 中）。
5. 用户是在续改已有项目时，只列出需要新增或修改的文件。
"""

CODER_SYSTEM = """你是 "Coder" Agent，负责写出单个文件的完整内容。
只输出文件内容本身：不要 markdown 代码围栏，不要任何解释、标题或前后缀。

要求：
- 生成可直接在浏览器打开运行的静态站点，所有本地资源使用相对路径（styles.css / app.js）。
- 不要使用 localStorage / sessionStorage；状态保存在内存即可。
- 不要引用本地绝对路径，不依赖构建工具；第三方库使用 CDN。
- 视觉现代、精致、响应式，文案使用真实内容，不要 Lorem ipsum 占位。
- index.html 中出现的每个 class 都必须在 styles.css 中有对应样式（JS 钩子请用 data-* 属性，不要留下无样式 class）。
- styles.css 必须包含至少一个 @media (max-width: 768px) 媒体查询，保证窄屏可用。
- 布局容器（hero、统计区、卡片网格等）必须有明确的 display / grid / flex 规则，禁止依赖浏览器默认块级堆叠。
- 单个文件尽量控制在 8,000 字符以内：内容多时精简文案、复用样式类，优先保证结构完整闭合，绝不能写到一半停止。
- 如果提供了当前文件内容，在保留原有可用功能的基础上修改。
"""

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
FENCE = re.compile(r"^```[a-zA-Z0-9]*\s*\n?")


def _clean_file_content(text: str) -> str:
    content = text.strip()
    content = FENCE.sub("", content)
    content = re.sub(r"\n?```\s*$", "", content)
    return content.strip()


def _parse_plan(text: str, fallback_prompt: str) -> tuple[str, list[dict]]:
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            data = json.loads(match.group(0))
            summary = str(data.get("summary") or "").strip()
            raw_files = data.get("files") or []
            files: list[dict] = []
            seen: set[str] = set()
            for item in raw_files:
                name = str(item.get("path", "")).strip().replace("\\", "/").split("/")[-1]
                if not name or not SAFE_NAME.match(name) or ".." in name or name in seen:
                    continue
                purpose = str(item.get("purpose") or "").strip() or "项目文件"
                files.append({"path": name, "purpose": purpose})
                seen.add(name)
            files = _ensure_index(files)
            if files:
                return summary or "生成一个静态 Web 应用。", files
        except (ValueError, TypeError, AttributeError):
            pass
    return (
        f"生成一个静态 Web 应用：{fallback_prompt[:60]}",
        [
            {"path": "index.html", "purpose": "页面结构"},
            {"path": "styles.css", "purpose": "视觉样式"},
            {"path": "app.js", "purpose": "交互逻辑"},
        ],
    )


def _ensure_index(files: list[dict]) -> list[dict]:
    if not any(f["path"] == "index.html" for f in files):
        files.insert(0, {"path": "index.html", "purpose": "页面结构"})
    order = {"index.html": 0, "styles.css": 1, "app.js": 2}
    return sorted(files, key=lambda f: order.get(f["path"], 9))


RETRY_HINT = (
    "\n\n重要：上一次输出被截断或不完整。请重新输出完整文件，"
    "确保所有标签与括号闭合，不要省略任何部分，也不要加解释。"
)


def _valid_content(filename: str, content: str) -> bool:
    """Cheap structural validation; catches empty or truncated files."""
    text = content.strip()
    if len(text) < 24:
        return False
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("html", "htm"):
        lower = text.lower()
        return "<html" in lower and "</body>" in lower and "</html>" in lower
    if ext in ("css", "js"):
        return text.count("{") == text.count("}")
    return True


async def _collect(stream) -> str:
    return "".join([chunk async for chunk in stream])


async def _mock_bundle(
    planned: list[dict], message: str, existing: dict[str, str]
) -> dict[str, str]:
    """Coherent fallback: regenerate every known file, not just this round's."""
    mock = MockLLM()
    paths = [item["path"] for item in planned]
    paths.extend(name for name in existing if name not in paths)
    bundle: dict[str, str] = {}
    for path in paths:
        text = await _collect(
            mock.stream(
                role="coder",
                system=CODER_SYSTEM,
                user="",
                meta={"prompt": message, "filename": path, "existing": existing},
            )
        )
        bundle[path] = _clean_file_content(text)
    return bundle


async def _llm_text(
    llm,
    *,
    role: str,
    system: str,
    user: str,
    meta: dict,
    emit: Emit,
    emit_tokens: bool,
    state: dict,
    validator: Callable[[str], bool] | None = None,
) -> str:
    async def run(current, prompt_user: str) -> str:
        parts: list[str] = []
        async for chunk in current.stream(role=role, system=system, user=prompt_user, meta=meta):
            parts.append(chunk)
            if emit_tokens:
                await emit("token", {"filename": meta.get("filename"), "delta": chunk})
        text = "".join(parts)
        if not text.strip():
            raise RuntimeError("LLM returned empty content")
        return text

    if state.get("degraded"):
        return await run(MockLLM(), user)

    last_error: Exception | None = None
    for attempt in range(2):
        prompt_user = user if attempt == 0 else user + RETRY_HINT
        try:
            text = await run(llm, prompt_user)
        except Exception as exc:
            last_error = exc
            if isinstance(llm, MockLLM):
                raise
            break
        candidate = _clean_file_content(text) if validator else text
        if validator is None or validator(candidate):
            return text
        last_error = RuntimeError("LLM output incomplete")
        if emit_tokens:
            await emit("token_reset", {"filename": meta.get("filename")})
        if attempt == 0:
            await emit(
                "execution",
                {
                    "agent": "Coder" if role == "coder" else "Orchestrator",
                    "step": f"重试 {meta.get('filename') or role}",
                    "status": "warning",
                    "log": "输出缺少闭合结构，自动重试一次",
                },
            )

    state["degraded"] = True
    assert last_error is not None
    await emit(
        "execution",
        {
            "agent": "Orchestrator",
            "step": "降级 Mock Agent",
            "status": "warning",
            "log": f"{type(last_error).__name__}: {str(last_error)[:180]}",
        },
    )
    if emit_tokens:
        await emit("token_reset", {"filename": meta.get("filename")})
    return await run(MockLLM(), user)


def _needs_style_repair(issues: list[str]) -> bool:
    return any(
        issue.startswith("样式缺口") or issue.startswith("styles.css 缺少") for issue in issues
    )


def _repair_user(files: dict[str, str], issues: list[str]) -> str:
    return "\n\n".join(
        [
            "Reviewer 发现以下样式问题，请修复 styles.css：\n- " + "\n- ".join(issues),
            "index.html（供参考）：\n" + files.get("index.html", "")[:16000],
            "当前 styles.css：\n" + files.get("styles.css", "")[:16000],
            "要求：保留现有设计语言与全部已有样式；补齐缺失 class 的样式；"
            "文件末尾添加 @media (max-width: 768px) 移动端规则；只输出 styles.css 完整内容。",
        ]
    )


def _review(files: dict[str, str]) -> list[str]:
    issues: list[str] = []
    html = files.get("index.html", "")
    if not html:
        return ["index.html 缺失"]
    if "<html" not in html.lower() or "</html>" not in html.lower():
        issues.append("index.html 结构不完整")
    for ref in re.findall(r'(?:src|href)="([^"]+)"', html):
        if ref.startswith(("http://", "https://", "//", "#", "data:", "mailto:", "javascript:")):
            continue
        clean = ref.split("?")[0].split("#")[0].lstrip("./")
        if clean and clean not in files:
            issues.append(f"引用了不存在的文件 {clean}")
    css = files.get("styles.css", "")
    if not css and not any("styles" in f for f in files):
        issues.append("缺少样式文件")
    if css:
        used: set[str] = set()
        for attr in re.findall(r'class="([^"]+)"', html):
            used.update(token for token in attr.split() if not token.startswith("js-"))
        defined = set(re.findall(r"\.([A-Za-z_][\w-]*)", css))
        missing = sorted(used - defined)
        if missing:
            issues.append("样式缺口：" + "、".join("." + name for name in missing[:6]))
        if "@media" not in css:
            issues.append("styles.css 缺少移动端媒体查询")
    if any(len(v) < 20 for v in files.values()):
        issues.append("存在空文件")
    return issues


async def _publish(pid: str, files: dict[str, str]) -> None:
    target = config.APPS_DIR / pid

    def write() -> None:
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (target / name).write_text(content, encoding="utf-8")

    await asyncio.to_thread(write)


def _coder_user(
    path: str,
    purpose: str,
    summary: str,
    message: str,
    planned: list[dict],
    existing: dict[str, str],
) -> str:
    blocks = [
        f"用户需求：\n{message}",
        f"项目概述：{summary}",
        f"需要生成的文件：{path}（{purpose}）",
        f"本轮文件清单：{', '.join(f['path'] for f in planned)}",
    ]
    if path in existing:
        blocks.append(f"当前 {path} 的内容（在此基础上修改）：\n<current>\n{existing[path][:7000]}\n</current>")
    siblings = [(n, c) for n, c in existing.items() if n != path][:2]
    if siblings:
        joined = "\n\n".join(f"--- {n} ---\n{c[:2200]}" for n, c in siblings)
        blocks.append(f"其他已有文件（供保持命名/风格一致参考）：\n{joined}")
    return "\n\n".join(blocks)


async def run_generation(pid: str, message: str, emit: Emit) -> None:
    existing = await db.latest_artifacts(pid)
    version = await db.next_version(pid)
    llm = get_llm()
    llm_state: dict = {}

    ctx = await emit(
        "execution",
        {
            "agent": "Orchestrator",
            "step": "载入上下文",
            "status": "running",
            "log": f"{len(existing)} 个已有文件 · 模型 {config.LLM_MODEL if config.LLM_MODE == 'deepseek' else 'mock'}",
        },
    )
    await emit(
        "execution",
        {
            "id": ctx,
            "agent": "Orchestrator",
            "step": "载入上下文",
            "status": "success",
            "log": f"目标版本 v{version}",
        },
    )

    # 1) Planner
    plan_ex = await emit(
        "execution",
        {"agent": "Planner", "step": "需求分析与文件规划", "status": "running", "log": "拆解需求…"},
    )
    planner_user = (
        f"用户需求：\n{message}\n\n"
        f"当前项目文件：{', '.join(existing) if existing else '（空项目）'}\n\n"
        "输出 JSON。"
    )
    plan_text = await _llm_text(
        llm,
        role="planner",
        system=PLANNER_SYSTEM,
        user=planner_user,
        meta={"prompt": message, "existing": existing},
        emit=emit,
        emit_tokens=False,
        state=llm_state,
    )
    summary, planned = _parse_plan(plan_text, message)
    await emit(
        "execution",
        {
            "id": plan_ex,
            "agent": "Planner",
            "step": "需求分析与文件规划",
            "status": "success",
            "log": f"{summary} → {', '.join(f['path'] for f in planned)}",
        },
    )
    await asyncio.sleep(0.25)

    # 2) Coder, one file at a time
    contents: dict[str, str] = {}
    for item in planned:
        path = item["path"]
        step_ex = await emit(
            "execution",
            {"agent": "Coder", "step": f"生成 {path}", "status": "running", "log": item["purpose"]},
        )
        await emit("file_start", {"filename": path, "purpose": item["purpose"]})
        raw = await _llm_text(
            llm,
            role="coder",
            system=CODER_SYSTEM,
            user=_coder_user(path, item["purpose"], summary, message, planned, existing),
            meta={"prompt": message, "filename": path, "existing": existing},
            emit=emit,
            emit_tokens=True,
            state=llm_state,
            validator=lambda text, p=path: _valid_content(p, _clean_file_content(text)),
        )
        content = _clean_file_content(raw)
        contents[path] = content
        await db.add_artifact(pid, path, content, version)
        await emit("artifact", {"filename": path, "content": content, "version": version})
        await emit(
            "execution",
            {
                "id": step_ex,
                "agent": "Coder",
                "step": f"生成 {path}",
                "status": "success",
                "log": f"{len(content):,} 字符",
            },
        )

    # Any degraded call means the round is inconsistent (real + mock files).
    # Regenerate a coherent mock bundle rather than shipping a broken hybrid.
    if llm_state.get("degraded"):
        contents = await _mock_bundle(planned, message, existing)
        for name, content in contents.items():
            await db.add_artifact(pid, name, content, version)
            await emit(
                "artifact",
                {"filename": name, "content": content, "version": version},
            )
        await emit(
            "execution",
            {
                "agent": "Orchestrator",
                "step": "整轮回退 Mock 模板",
                "status": "warning",
                "log": "LLM 输出异常，已替换为一致的预置模板，保证站点完整可运行",
            },
        )

    # 3) Reviewer (deterministic checks, no extra LLM call)
    # Follow-ups may regenerate only a subset of files; review and publish the
    # merged project, otherwise unchanged files would be dropped on deploy.
    published = {**existing, **contents}
    review_ex = await emit(
        "execution",
        {"agent": "Reviewer", "step": "静态检查", "status": "running", "log": "检查结构与资源引用…"},
    )
    issues = _review(published)
    repair_note = ""

    if config.AUTO_REPAIR and "styles.css" in published and _needs_style_repair(issues):
        repair_ex = await emit(
            "execution",
            {
                "agent": "Coder",
                "step": "修复 styles.css",
                "status": "running",
                "log": ("Reviewer 自动回修：" + "；".join(issues))[:180],
            },
        )
        rounds = 0
        for round_index in range(2):
            if not _needs_style_repair(issues):
                break
            rounds = round_index + 1
            await emit(
                "file_start",
                {
                    "filename": "styles.css",
                    "purpose": f"Reviewer 自动回修（第 {rounds} 轮）",
                },
            )
            raw = await _llm_text(
                llm,
                role="coder",
                system=CODER_SYSTEM,
                user=_repair_user(published, issues),
                meta={"prompt": message, "filename": "styles.css", "existing": published},
                emit=emit,
                emit_tokens=True,
                state=llm_state,
                validator=lambda text: _valid_content("styles.css", _clean_file_content(text)),
            )
            repaired = _clean_file_content(raw)
            if not repaired:
                break
            published["styles.css"] = repaired
            contents["styles.css"] = repaired
            await db.add_artifact(pid, "styles.css", repaired, version)
            await emit(
                "artifact",
                {"filename": "styles.css", "content": repaired, "version": version},
            )
            issues = _review(published)

        if not issues:
            repair_note = f"Reviewer 自动补齐了样式缺口与移动端规则（{rounds} 轮）。"
        await emit(
            "execution",
            {
                "id": repair_ex,
                "agent": "Coder",
                "step": "修复 styles.css",
                "status": "success" if not issues else "warning",
                "log": (
                    "回修后仍有问题：" + "；".join(issues)[:160]
                    if issues
                    else f"样式缺口与移动端规则已补齐（{rounds} 轮）"
                ),
            },
        )

    await emit(
        "execution",
        {
            "id": review_ex,
            "agent": "Reviewer",
            "step": "静态检查",
            "status": "warning" if issues else "success",
            "log": (
                "；".join(issues) if issues else f"{len(published)} 个文件通过检查"
            ) + ("（已自动回修）" if repair_note else ""),
        },
    )

    # 4) Deployer
    deploy_ex = await emit(
        "execution",
        {"agent": "Deployer", "step": "发布静态站点", "status": "running", "log": f"写入 /apps/{pid}/"},
    )
    await _publish(pid, published)
    preview_url = f"/apps/{pid}/index.html?v={version}"
    await emit(
        "execution",
        {
            "id": deploy_ex,
            "agent": "Deployer",
            "step": "发布静态站点",
            "status": "success",
            "log": f"v{version} 可访问：{preview_url}",
        },
    )
    await emit("preview", {"url": preview_url, "version": version})

    assistant = (
        f"已完成 v{version}：{summary}\n"
        f"文件：{', '.join(contents)}\n"
        + (f"{repair_note}\n" if repair_note else "")
        + "\n右侧可以直接预览；如果想调整，继续告诉我就行。"
    )
    await db.add_conversation(pid, "assistant", assistant)
    await emit("message", {"role": "assistant", "content": assistant})
