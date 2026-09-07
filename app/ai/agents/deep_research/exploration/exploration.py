import logging
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse
from pydantic import BaseModel, Field
from langchain_core.language_models.chat_models import BaseChatModel

from app.ai.agents.deep_research.events import DeepResearchEvent, emit_research_event
from app.ai.agents.deep_research.state import (
    DeepResearchState,
    EvidenceItem,
    ResearchOutline,
    SearchResultItem,
)

logger = logging.getLogger(__name__)


class ExtractedEvidence(BaseModel):
    """An individual piece of extracted factual evidence from a web source."""
    claim: str = Field(description="Objective, factual claim supported by the source.")
    exact_quote: str = Field(description="Direct verbatim quote from the source text verifying the claim.")
    metric_value: Optional[str] = Field(default=None, description="Specific number, percentage, dollar figure, date, or benchmark, if mentioned.")
    source_url: str = Field(description="URL of the source document.")
    source_title: Optional[str] = Field(default=None, description="Title of the source document.")
    section_ids: list[str] = Field(default_factory=list, description="IDs of outline sections this evidence informs (e.g. ['sec_1']).")
    tags: list[str] = Field(default_factory=list, description="Key concept tags or categories.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in accuracy or reliability.")


class ExplorationOutput(BaseModel):
    """Container for all evidence items distilled from search results."""
    evidence_items: list[ExtractedEvidence] = Field(default_factory=list)


class ExplorationEngine:
    """Distills raw search results into atomic, verified evidence records aligned with the research outline."""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm.with_structured_output(ExplorationOutput)

    async def distill_sources(
        self,
        outline: ResearchOutline,
        sources: list[SearchResultItem],
    ) -> list[EvidenceItem]:
        """Analyze gathered sources and extract verified EvidenceItems answering outline questions."""
        if not sources:
            logger.info("ExplorationEngine: No sources provided to distill.")
            return []

        messages = self._build_prompt_messages(outline, sources)
        logger.info(
            "ExplorationEngine: Distilling evidence from %d sources across %d outline sections",
            len(sources),
            len(outline.sections),
        )

        output: ExplorationOutput = await self.llm.ainvoke(messages)

        evidence_list: list[EvidenceItem] = []
        for item in output.evidence_items:
            domain = urlparse(item.source_url).netloc or "web"
            tags = list(set(item.tags + item.section_ids))

            # Match source published_date if available
            pub_date = None
            for src in sources:
                if src.url == item.source_url:
                    pub_date = src.published_date
                    break

            evidence = EvidenceItem(
                claim=item.claim,
                exact_quote=item.exact_quote,
                metric_value=item.metric_value,
                source_url=item.source_url,
                source_domain=domain,
                source_title=item.source_title,
                confidence=item.confidence,
                published_date=pub_date,
                tags=tags,
            )
            evidence_list.append(evidence)

        # Dispatch telemetry event
        await emit_research_event(
            DeepResearchEvent(
                type="evidence_added",
                phase="distilling",
                message=f"Distilled {len(evidence_list)} atomic evidence items from {len(sources)} sources",
                data={
                    "evidence_count": len(evidence_list),
                    "sources_analyzed": len(sources),
                    "metrics_found": sum(1 for e in evidence_list if e.metric_value),
                },
            )
        )

        return evidence_list

    async def exploration_node(self, state: DeepResearchState) -> dict[str, Any]:
        """LangGraph node execution function for the Distillation / Exploration phase."""
        if not state.outline:
            logger.warning("ExplorationEngine node: No outline found in state.")
            return {"phase": "critiquing"}

        # Only process sources not already in evidence_ledger to avoid duplicates
        existing_urls = {e.source_url for e in state.evidence_ledger}
        new_sources = [s for s in state.raw_search_results if s.url not in existing_urls]
        sources_to_process = new_sources if new_sources else state.raw_search_results

        new_evidence = await self.distill_sources(
            outline=state.outline,
            sources=sources_to_process,
        )

        updated_ledger = state.evidence_ledger + new_evidence

        # Link evidence IDs into corresponding outline sections and update status
        evidence_by_section: dict[str, list[str]] = {}
        for ev in updated_ledger:
            for tag in ev.tags:
                evidence_by_section.setdefault(tag, []).append(ev.id)

        updated_sections = []
        for sec in state.outline.sections:
            sec_ev_ids = list(set(sec.evidence_ids + evidence_by_section.get(sec.section_id, [])))
            status = "ready_to_write" if len(sec_ev_ids) >= 2 else ("researching" if sec_ev_ids else "pending")
            updated_sections.append(
                sec.model_copy(update={"evidence_ids": sec_ev_ids, "status": status})
            )

        updated_outline = state.outline.model_copy(update={"sections": updated_sections})

        return {
            "phase": "critiquing",
            "outline": updated_outline,
            "evidence_ledger": updated_ledger,
        }

    def _build_prompt_messages(self, outline: ResearchOutline, sources: list[SearchResultItem]):
        path = Path(__file__).parent / "prompt.md"
        with open(path, "r", encoding="utf-8") as f:
            prompt_system = f.read()

        outline_summary = [
            f"Topic: {outline.topic}",
            f"Objective: {outline.executive_objective}",
            "Target Sections:",
        ]
        for s in outline.sections:
            outline_summary.append(
                f"- Section [{s.section_id}] '{s.title}': {s.description}\n"
                f"  Questions: {', '.join(s.key_questions_to_answer)}\n"
                f"  Required Metrics: {', '.join(s.required_metrics)}"
            )

        sources_summary = []
        for i, src in enumerate(sources, 1):
            body = (src.raw_content or src.snippet)[:1500]
            sources_summary.append(
                f"Source #{i}:\n"
                f"Title: {src.title}\n"
                f"URL: {src.url}\n"
                f"Content Excerpt:\n{body}\n"
            )

        user_content = (
            f"<research_outline>\n"
            f"{chr(10).join(outline_summary)}\n"
            f"</research_outline>\n\n"
            f"<collected_sources>\n"
            f"{chr(10).join(sources_summary)}\n"
            f"</collected_sources>\n\n"
            f"Extract all verified, atomic evidence items strictly grounded in the sources."
        )

        return [
            ("system", prompt_system),
            ("user", user_content),
        ]
