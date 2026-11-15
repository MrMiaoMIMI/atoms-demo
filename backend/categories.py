"""Discover categories and the optional LLM-assisted suggestion.

Categories mirror the public Atoms discover tags. They are *metadata*: the
author picks one when publishing, and the "auto detect" button only offers a
suggestion that the author can override. Nothing here inspects generated code
to infer a category.

The keyword table is deliberately small and deterministic. It is the fallback
when no LLM key is configured, when the model times out, or when it returns
something outside the allowed list.
"""
from __future__ import annotations

import asyncio
import logging

import config
import llm

logger = logging.getLogger(__name__)

CATEGORIES = [
    "网站",
    "电商",
    "游戏",
    "效率",
    "原型",
    "数据分析",
    "博客",
    "名片",
    "深度研究",
    "其他",
]
DEFAULT_CATEGORY = "其他"

# Order matters for ties: earlier categories win. Keep this list aligned with
# CATEGORIES (minus "其他", which is the no-match fallback).
_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("网站", ("官网", "落地页", "主页", "门户", "网站", "website", "landing", "portfolio")),
    ("电商", ("商城", "商店", "购物", "电商", "商品", "订单", "购物车", "支付", "ecommerce", "e-commerce", "shop", "store", "cart", "checkout")),
    ("游戏", ("游戏", "闯关", "贪吃蛇", "俄罗斯方块", "射击", "game", "arcade", "puzzle")),
    ("效率", ("效率", "工具", "待办", "todo", "任务", "笔记", "日历", "番茄钟", "productivity", "tracker")),
    ("原型", ("原型", "演示", "demo", "prototype", "mockup")),
    ("数据分析", ("数据分析", "图表", "分析", "报表", "统计", "可视化", "analytics", "chart", "report", "dashboard")),
    ("博客", ("博客", "文章", "资讯", "新闻", "blog", "post", "article", "magazine")),
    ("名片", ("名片", "个人介绍", "简历", "business card", "resume", "vcard")),
    ("深度研究", ("深度研究", "研究", "调研", "研究报告", "research", "survey")),
]

_SYSTEM_PROMPT = """你是应用分类助手。只能从下面的分类中选一个返回：
网站、电商、游戏、效率、原型、数据分析、博客、名片、深度研究、其他。
只输出分类名本身，不要解释、不要标点、不要代码块。"""


def normalize_category(value: str | None) -> str:
    """Return an allowed category, falling back to "其他"."""
    candidate = (value or "").strip()
    return candidate if candidate in CATEGORIES else DEFAULT_CATEGORY


def heuristic_category(*parts: str) -> str:
    """Pick the category with the most keyword hits across the given text."""
    text = "\n".join(part for part in parts if part).lower()
    if not text:
        return DEFAULT_CATEGORY
    best = DEFAULT_CATEGORY
    best_score = 0
    for category, keywords in _KEYWORDS:
        score = sum(1 for keyword in keywords if keyword.lower() in text)
        if score > best_score:
            best = category
            best_score = score
    return best


def _parse_llm_category(raw: str) -> str | None:
    """Extract the first allowed category mentioned in a short LLM reply."""
    cleaned = (raw or "").strip().strip("`'\"。.,，:：\n\t ")
    if not cleaned:
        return None
    # Direct match first; then the earliest occurrence in a chatty answer.
    if cleaned in CATEGORIES:
        return cleaned
    best: tuple[int, str] | None = None
    for category in CATEGORIES:
        index = cleaned.find(category)
        if index >= 0 and (best is None or index < best[0]):
            best = (index, category)
    return best[1] if best else None


async def suggest_category(
    *,
    name: str,
    prompt: str = "",
    description: str = "",
    files: list[str] | None = None,
) -> str:
    """Suggest one category, using the LLM when configured, then keywords."""
    files = files or []
    fallback = heuristic_category(name, prompt, description, " ".join(files[:40]))

    # Mock mode is a deterministic demo; do not spend a fake LLM call on it.
    if config.LLM_MODE != "deepseek":
        return fallback

    user = (
        f"项目名称：{name[:120]}\n"
        f"首条需求：{prompt[:1500]}\n"
        f"作者简介：{description[:300]}\n"
        f"主要文件：{', '.join(files[:30])}"
    )
    try:
        raw = await asyncio.wait_for(
            llm.complete(
                role="category",
                system=_SYSTEM_PROMPT,
                user=user,
                meta={"prompt": f"{name}\n{prompt}"},
                max_chars=64,
            ),
            timeout=min(10.0, config.LLM_TIMEOUT),
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - suggestion must never break publish
        logger.warning("category suggestion failed, using heuristic: %s", exc)
        return fallback
    return _parse_llm_category(raw) or fallback
