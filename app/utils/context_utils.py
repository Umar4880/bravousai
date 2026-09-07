"""
Shared context-management utilities for all agents and sub-agents.

Every function in this module is a pure data transformation — no LLM calls,
no I/O, no side effects. This keeps context preparation deterministic and
testable.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Sequence

from langchain_core.messages import BaseMessage

from app.core.config import setting

logger = logging.getLogger(__name__)


# ── File Context ────────────────────────────────────────────────────

def build_files_context(
    uploaded_files: list[Any],
    *,
    include_content: bool = True,
    max_chars_per_file: int | None = None,
) -> str:
    """Build a prompt-safe string summarising uploaded files.

    Args:
        uploaded_files: List of UserFileContext objects or dicts.
        include_content: If True, include (truncated) extracted_text.
                         If False, only include filename + summary.
        max_chars_per_file: Per-file character cap for extracted_text.
                           Defaults to ``setting.CONTEXT_MAX_FILE_TEXT_CHARS``.
    """
    if not uploaded_files:
        return "None"

    if max_chars_per_file is None:
        max_chars_per_file = setting.CONTEXT_MAX_FILE_TEXT_CHARS

    parts: list[str] = []
    for f in uploaded_files:
        filename = _val(f, "filename", "Unknown")
        summary = _val(f, "summary", "")

        if include_content:
            raw_text = _val(f, "extracted_text", "")
            if len(raw_text) > max_chars_per_file:
                text = raw_text[:max_chars_per_file] + "\n... [truncated]"
                logger.debug(
                    "Truncated file context | file=%s | original=%d | capped=%d",
                    filename, len(raw_text), max_chars_per_file,
                )
            else:
                text = raw_text
            parts.append(
                f"File: {filename}\nSummary: {summary}\nContent:\n{text}"
            )
        else:
            parts.append(f"File: {filename}\nSummary: {summary}")

    return "\n\n".join(parts)


# ── Message History ─────────────────────────────────────────────────

def trim_message_history(
    messages: list[BaseMessage],
    max_messages: int | None = None,
) -> list[BaseMessage]:
    """Return the most recent *max_messages* messages (sliding window).

    Always keeps the very first message (the system/human seed) and then
    takes the last ``max_messages - 1`` messages from the tail so the
    model sees the opening context plus the most recent conversation.
    """
    if max_messages is None:
        max_messages = setting.CONTEXT_MAX_HISTORY_MESSAGES

    if len(messages) <= max_messages:
        return messages

    # Keep first message (often the initial human query) + latest tail
    trimmed = [messages[0]] + messages[-(max_messages - 1):]
    logger.debug(
        "Trimmed message history | original=%d | kept=%d",
        len(messages), len(trimmed),
    )
    return trimmed


# ── Merged-Source Truncation (for Synthesizer) ──────────────────────

def truncate_merged_sources(
    sources: list[dict],
    *,
    max_chars_per_source: int | None = None,
    max_total_chars: int | None = None,
) -> list[dict]:
    """Return a copy of *sources* with ``extracted_text`` capped.

    1. Each source's ``extracted_text`` is capped to *max_chars_per_source*.
    2. Sources are sorted by quality (``content_quality_score`` desc, then
       ``relevance_score`` desc) and included until *max_total_chars* is
       reached; remaining sources are dropped.
    """
    if max_chars_per_source is None:
        max_chars_per_source = setting.CONTEXT_MAX_CHARS_PER_SOURCE_SYNTHESIS
    if max_total_chars is None:
        max_total_chars = setting.CONTEXT_MAX_TOTAL_SYNTHESIS_CHARS

    if not sources:
        return []

    # Sort by quality desc so the best sources get budget priority
    scored = sorted(
        sources,
        key=lambda s: (
            s.get("content_quality_score") or 0,
            s.get("relevance_score") or 0,
        ),
        reverse=True,
    )

    result: list[dict] = []
    total_chars = 0

    for src in scored:
        entry = dict(src)  # shallow copy — don't mutate originals

        text = entry.get("extracted_text") or ""
        if len(text) > max_chars_per_source:
            text = text[:max_chars_per_source] + "\n... [truncated]"
            entry["extracted_text"] = text

        text_len = len(text)
        if total_chars + text_len > max_total_chars:
            # Budget exhausted — skip remaining sources
            logger.debug(
                "Synthesis source budget exhausted | included=%d | dropped=%d",
                len(result), len(scored) - len(result),
            )
            break

        total_chars += text_len
        result.append(entry)

    return result


# ── Compact JSON ────────────────────────────────────────────────────

def compact_json(data: Any) -> str:
    """Serialize *data* to JSON with minimal whitespace.

    Saves ~30% tokens compared to ``json.dumps(data, indent=2)`` for
    typical nested structures.
    """
    return json.dumps(data, default=str, separators=(",", ":"))


# ── Private Helpers ─────────────────────────────────────────────────

def _val(obj: Any, key: str, default: Any = "") -> Any:
    """Read a value from a dict or Pydantic model uniformly."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
