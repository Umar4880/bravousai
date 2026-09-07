import asyncio
import logging
from pathlib import Path
from typing import Any, Optional
from langchain_core.language_models.chat_models import BaseChatModel

from app.ai.agents.deep_research.events import DeepResearchEvent, emit_research_event
from app.ai.agents.deep_research.state import (
    Contradiction,
    DeepResearchState,
    EvidenceItem,
    GapReport,
    OutlineSection,
    ResearchOutline,
)

logger = logging.getLogger(__name__)


class SynthesisEngine:
    """Synthesizes verified evidence into an authoritative, cited, publication-grade research report."""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    async def draft_section(
        self,
        section: OutlineSection,
        evidence: list[EvidenceItem],
        topic: str,
        system_prompt: str,
    ) -> str:
        """Draft an individual technical section grounded strictly in the provided evidence."""
        await emit_research_event(
            DeepResearchEvent(
                type="section_drafting_started",
                phase="synthesizing",
                message=f"Drafting section: '{section.title}'",
                data={"section_id": section.section_id, "title": section.title},
            )
        )

        evidence_lines = []
        for ev in evidence:
            metric_info = f" [Metric: {ev.metric_value}]" if ev.metric_value else ""
            evidence_lines.append(
                f"- Claim: {ev.claim}{metric_info}\n"
                f"  Exact Quote: \"{ev.exact_quote}\"\n"
                f"  Source: [{ev.source_title or ev.source_domain}]({ev.source_url})\n"
            )

        user_content = (
            f"Overall Research Topic: {topic}\n\n"
            f"Section ID: {section.section_id}\n"
            f"Section Title: {section.title}\n"
            f"Description: {section.description}\n"
            f"Key Questions to Answer:\n"
            f"{chr(10).join(f'- {q}' for q in section.key_questions_to_answer)}\n\n"
            f"Required Metrics to Highlight:\n"
            f"{chr(10).join(f'- {m}' for m in section.required_metrics)}\n\n"
            f"<section_evidence>\n"
            f"{chr(10).join(evidence_lines) if evidence_lines else 'No direct quotes available. Generalize responsibly from topic context.'}\n"
            f"</section_evidence>\n\n"
            f"Write a thorough, highly analytical chapter for this section. "
            f"Integrate metrics, include tables where suitable, and link inline markdown citations."
        )

        messages = [
            ("system", system_prompt),
            ("user", user_content),
        ]

        response = await self.llm.ainvoke(messages)
        content = response.content.strip()

        word_count = len(content.split())
        await emit_research_event(
            DeepResearchEvent(
                type="section_drafted",
                phase="synthesizing",
                message=f"Completed section: '{section.title}' ({word_count} words)",
                data={
                    "section_id": section.section_id,
                    "title": section.title,
                    "word_count": word_count,
                },
            )
        )
        return content

    async def draft_executive_summary(
        self,
        outline: ResearchOutline,
        drafted_sections: list[str],
        contradictions: list[Contradiction],
        system_prompt: str,
    ) -> str:
        """Draft the overarching executive summary and strategic takeaways."""
        sections_overview = "\n\n".join(
            f"### Section: {sec.title}\n{draft[:800]}..."
            for sec, draft in zip(outline.sections, drafted_sections)
        )

        contradictions_str = "\n".join(
            f"- {c.topic}: Source A ({c.source_a_url}) claims '{c.claim_a}' vs Source B ({c.source_b_url}) claims '{c.claim_b}'"
            for c in contradictions
        )

        user_content = (
            f"Topic: {outline.topic}\n"
            f"Executive Objective: {outline.executive_objective}\n"
            f"Target Audience: {outline.target_audience}\n\n"
            f"Drafted Sections Overview:\n{sections_overview}\n\n"
            f"Known Contradictions / Discrepancies:\n{contradictions_str or 'None detected'}\n\n"
            f"Draft a compelling, high-level Executive Summary (300-500 words) with:\n"
            f"1. Core Thesis & Strategic Implications\n"
            f"2. High-Impact Findings & Key Metrics\n"
            f"3. Concise Risk / Contradiction Notes\n"
        )

        messages = [
            ("system", system_prompt),
            ("user", user_content),
        ]
        response = await self.llm.ainvoke(messages)
        return response.content.strip()

    def _build_bibliography(self, evidence: list[EvidenceItem]) -> str:
        """Generate a formatted markdown table of all unique sources consulted."""
        seen_urls: set[str] = set()
        bib_lines = [
            "## Sources & Bibliography\n",
            "| Source | Domain | Citations / Relevance |",
            "| :--- | :--- | :--- |",
        ]
        for ev in evidence:
            if ev.source_url not in seen_urls:
                seen_urls.add(ev.source_url)
                title = ev.source_title or ev.source_domain or "Web Source"
                bib_lines.append(f"| [{title}]({ev.source_url}) | `{ev.source_domain}` | Verified Evidence |")

        return "\n".join(bib_lines)

    async def synthesize_report(
        self,
        outline: ResearchOutline,
        evidence_ledger: list[EvidenceItem],
        gap_reports: list[GapReport],
    ) -> tuple[str, list[OutlineSection]]:
        """Coordinate section-by-section drafting and assemble the unified publication report."""
        system_prompt = self._load_prompt()

        # Group evidence by section tags / IDs
        evidence_map: dict[str, list[EvidenceItem]] = {}
        for ev in evidence_ledger:
            for tag in ev.tags:
                evidence_map.setdefault(tag, []).append(ev)

        # Draft each section concurrently or sequentially
        drafted_sections_content: list[str] = []
        updated_sections: list[OutlineSection] = []

        for sec in outline.sections:
            sec_evidence = evidence_map.get(sec.section_id, [])
            if not sec_evidence:
                # Fall back to general evidence if none explicitly tagged
                sec_evidence = evidence_ledger[:10]

            content = await self.draft_section(
                section=sec,
                evidence=sec_evidence,
                topic=outline.topic,
                system_prompt=system_prompt,
            )
            drafted_sections_content.append(content)
            updated_sections.append(
                sec.model_copy(update={"draft_content": content, "status": "drafted"})
            )

        # Extract all detected contradictions
        all_contradictions = [
            c for gr in gap_reports for c in gr.contradictions
        ]

        # Draft executive summary
        exec_summary = await self.draft_executive_summary(
            outline=outline,
            drafted_sections=drafted_sections_content,
            contradictions=all_contradictions,
            system_prompt=system_prompt,
        )

        # Assemble full document
        bibliography = self._build_bibliography(evidence_ledger)
        report_parts = [
            f"# {outline.topic}\n",
            f"> **Target Audience**: {outline.target_audience}  \n"
            f"> **Executive Objective**: {outline.executive_objective}\n",
            "## Executive Summary\n",
            exec_summary,
            "\n---\n",
            "\n\n---\n\n".join(drafted_sections_content),
            "\n---\n",
            bibliography,
        ]

        final_report = "\n\n".join(report_parts)

        # Emit completion telemetry
        total_words = len(final_report.split())
        await emit_research_event(
            DeepResearchEvent(
                type="research_completed",
                phase="complete",
                message=f"Deep research completed: '{outline.topic}' ({total_words} words across {len(outline.sections)} sections)",
                data={
                    "topic": outline.topic,
                    "sections_count": len(outline.sections),
                    "total_words": total_words,
                    "sources_cited": len(evidence_ledger),
                },
            )
        )

        return final_report, updated_sections

    async def synthesizer_node(self, state: DeepResearchState) -> dict[str, Any]:
        """LangGraph node execution function for the Final Synthesis phase."""
        if not state.outline:
            logger.error("Synthesizer node: Missing outline in state.")
            return {"phase": "complete", "is_complete": True}

        final_report, updated_sections = await self.synthesize_report(
            outline=state.outline,
            evidence_ledger=state.evidence_ledger,
            gap_reports=state.gap_reports,
        )

        updated_outline = state.outline.model_copy(update={"sections": updated_sections})

        return {
            "phase": "complete",
            "outline": updated_outline,
            "final_report": final_report,
            "is_complete": True,
        }

    def _load_prompt(self) -> str:
        path = Path(__file__).parent / "prompt.md"
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
