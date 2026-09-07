from typing import Any, Literal, Optional
import asyncio
import logging
from pydantic import BaseModel
from langchain_core.callbacks.manager import adispatch_custom_event

logger = logging.getLogger(__name__)


class DeepResearchEvent(BaseModel):
    """Event emitted across SSE to power the live research timeline."""
    type: Literal[
        "research_scoped",
        "search_dispatched",
        "search_completed",
        "source_extracted",
        "evidence_added",
        "gap_analysis_completed",
        "section_drafting_started",
        "section_drafted",
        "research_completed",
        "error"
    ]
    phase: str
    message: str
    data: Optional[dict[str, Any]] = None


async def emit_research_event(event: DeepResearchEvent) -> None:
    """Dispatches a custom research event across the callback framework for SSE streaming."""
    try:
        await asyncio.wait_for(
            adispatch_custom_event("deep_research_event", event.model_dump()),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        logger.warning("Research event dispatch timed out | type=%s", event.type)
    except Exception as exc:
        logger.debug("Research event dispatch skipped or failed | type=%s | err=%s", event.type, exc)

