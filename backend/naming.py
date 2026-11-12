"""Project naming for newly created projects.

The first prompt is summarized into a short, intent-revealing project name.
The project row is created immediately with a deterministic draft name so the
workspace opens without waiting; the LLM call runs in the background and the
resolved name is pushed to the UI on the next generation stream.
"""
from __future__ import annotations

import asyncio
import logging

import agents
import config
import llm

logger = logging.getLogger(__name__)


def draft_title(prompt: str | None) -> str:
    """Synchronous name used for the initial insert and as the LLM fallback."""
    return agents.fallback_title(prompt)


async def suggest_title(prompt: str) -> str:
    """Ask the LLM for a concise title; fall back to the heuristic on failure."""
    fallback = draft_title(prompt)
    cleaned = (prompt or "").strip()
    if not cleaned:
        return fallback
    try:
        raw = await asyncio.wait_for(
            llm.complete(
                role="title",
                system=agents.TITLE_SYSTEM,
                user=cleaned[:4000],
                meta={"prompt": cleaned},
                max_chars=96,
            ),
            timeout=config.TITLE_TIMEOUT,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - naming must never break creation
        logger.warning("project title generation failed, using fallback: %s", exc)
        return fallback
    return agents.sanitize_title(raw, fallback)
