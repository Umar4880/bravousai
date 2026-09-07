import logging
from pathlib import Path
from typing import Any, Optional
from langchain_core.language_models.chat_models import BaseChatModel

from app.ai.agents.deep_research.events import DeepResearchEvent, emit_research_event
from app.ai.agents.deep_research.state import (
    DeepResearchState,
    EvidenceItem,
    GapReport,
    ResearchOutline,
)

logger = logging.getLogger(__name__)


def route_after_critique(state: DeepResearchState) -> str:
    """LangGraph conditional edge router determining whether to loop for more research or advance to synthesis."""
    if state.phase == "searching":
        return "search"
    return "synthesizer"


class CritiqueEngine:
    """Audits the accumulated evidence against the research outline, evaluates gaps, and coordinates iteration."""

    def __init__(self, llm: BaseChatModel, sufficiency_threshold: float = 0.85):
        self.llm = llm.with_structured_output(GapReport)
        self.sufficiency_threshold = sufficiency_threshold

    async def evaluate_research(
        self,
        outline: ResearchOutline,
        evidence: list[EvidenceItem],
    ) -> GapReport:
        """Perform gap analysis and contradiction detection on current evidence against the outline."""
        if not evidence:
            logger.warning("CritiqueEngine: No evidence provided to evaluate.")
            # Formulate initial follow-ups from the first section if evidence is completely empty
            fallback_queries = [
                q for sec in outline.sections for q in sec.key_questions_to_answer[:1]
            ][:3]
            return GapReport(
                coverage_score=0.0,
                is_sufficient=False,
                missing_information=["No evidence has been gathered yet."],
                contradictions=[],
                follow_up_queries=fallback_queries,
            )

        messages = self._build_prompt_messages(outline, evidence)
        logger.info(
            "CritiqueEngine: Auditing %d evidence items across %d outline sections",
            len(evidence),
            len(outline.sections),
        )

        report: GapReport = await self.llm.ainvoke(messages)

        # Enforce threshold consistency
        if report.coverage_score >= self.sufficiency_threshold and not report.missing_information:
            report.is_sufficient = True

        # Dispatch telemetry event
        await emit_research_event(
            DeepResearchEvent(
                type="gap_analysis_completed",
                phase="critiquing",
                message=(
                    f"Gap analysis completed | Coverage: {report.coverage_score * 100:.1f}% | "
                    f"Sufficient: {report.is_sufficient} | Gaps: {len(report.missing_information)} | "
                    f"Contradictions: {len(report.contradictions)}"
                ),
                data={
                    "coverage_score": report.coverage_score,
                    "is_sufficient": report.is_sufficient,
                    "covered_topics_count": len(report.covered_topics),
                    "missing_information": report.missing_information,
                    "contradictions_count": len(report.contradictions),
                    "follow_up_queries": report.follow_up_queries,
                },
            )
        )

        return report

    async def critique_node(self, state: DeepResearchState) -> dict[str, Any]:
        """LangGraph node execution function for the Critique / Gap Analysis phase."""
        if not state.outline:
            logger.warning("CritiqueEngine node: No outline found in state.")
            return {"phase": "synthesizing"}

        report = await self.evaluate_research(
            outline=state.outline,
            evidence=state.evidence_ledger,
        )

        # Decision logic for iterative exploration vs synthesis
        current_iter = state.current_iteration
        max_iter = state.max_iterations

        needs_more_research = (
            not report.is_sufficient
            and current_iter < max_iter
            and bool(report.follow_up_queries)
        )

        if needs_more_research:
            next_iter = current_iter + 1
            logger.info(
                "CritiqueEngine: Gaps remain (score=%.2f). Starting research iteration %d/%d with %d follow-up queries",
                report.coverage_score,
                next_iter,
                max_iter,
                len(report.follow_up_queries),
            )
            return {
                "phase": "searching",
                "current_iteration": next_iter,
                "active_search_queries": report.follow_up_queries,
                "gap_reports": state.gap_reports + [report],
            }
        else:
            reason = "sufficient coverage" if report.is_sufficient else "reached max iterations budget"
            logger.info("CritiqueEngine: Advancing to synthesis (%s).", reason)
            return {
                "phase": "synthesizing",
                "active_search_queries": [],
                "gap_reports": state.gap_reports + [report],
            }

    def _build_prompt_messages(self, outline: ResearchOutline, evidence: list[EvidenceItem]):
        path = Path(__file__).parent / "prompt.md"
        with open(path, "r", encoding="utf-8") as f:
            prompt_system = f.read()

        # Format outline
        outline_lines = [
            f"Topic: {outline.topic}",
            f"Executive Objective: {outline.executive_objective}",
            "Outline Sections:",
        ]
        for s in outline.sections:
            outline_lines.append(
                f"- Section [{s.section_id}] {s.title}\n"
                f"  Questions to answer: {', '.join(s.key_questions_to_answer)}\n"
                f"  Required metrics: {', '.join(s.required_metrics)}\n"
                f"  Linked evidence IDs: {', '.join(s.evidence_ids) or 'None'}"
            )

        # Format evidence items
        evidence_lines = []
        for i, ev in enumerate(evidence, 1):
            metric_str = f" [Metric: {ev.metric_value}]" if ev.metric_value else ""
            evidence_lines.append(
                f"[{ev.id}] Claim: {ev.claim}{metric_str}\n"
                f"  Quote: \"{ev.exact_quote}\"\n"
                f"  Source: {ev.source_title or 'Untitled'} ({ev.source_url})\n"
                f"  Tags: {', '.join(ev.tags)}"
            )

        user_content = (
            f"<research_outline>\n"
            f"{chr(10).join(outline_lines)}\n"
            f"</research_outline>\n\n"
            f"<accumulated_evidence>\n"
            f"{chr(10).join(evidence_lines)}\n"
            f"</accumulated_evidence>\n\n"
            f"Perform a comprehensive audit. Evaluate coverage, isolate missing data/metrics, identify contradictions, and formulate targeted follow-up queries."
        )

        return [
            ("system", prompt_system),
            ("user", user_content),
        ]
