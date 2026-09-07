from typing import Literal, Optional

from pydantic import BaseModel, Field


class ContentBlock(BaseModel):
    """A single section of the artifact, with render type matched to information shape."""
    render_type: Literal[
        "prose",         # narrative, reasoning, trade-offs — rendered as <p> paragraphs
        "card_grid",     # 3-5 parallel, independent, same-level facts
        "svg_diagram",   # relationships, flow, hierarchy, sequences — inline SVG
        "svg_chart",     # quantitative comparison across categories/time — inline SVG
        "table",         # multi-attribute structured data
        "kpi_strip",     # 2-5 headline numbers in a single row
    ]
    title: str
    prose_content: str = ""           # for render_type="prose": the actual paragraph text
    diagram_description: str = ""     # for svg_diagram/svg_chart: what to visualize and how
    data_refs: list[str] = Field(default_factory=list)   # F-1, D-1, T-1 IDs
    render_notes: str = ""            # concrete instructions: axis labels, colors, layout


class PresentationPlan(BaseModel):
    mode: Literal["chat", "markdown_notes", "formal_report", "artifact"]
    artifact_kind: Literal[
        "hybrid_article",          # mixed prose + inline SVG visuals — the default for research
        "research_dashboard",      # explicit dashboard with tabs/filters
        "comparison",
        "timeline",
        "interactive_explainer",
        "briefing",
        "none",
    ]
    interaction_level: Literal["static", "light_interactive"]
    title: str
    rationale: str
    content_blocks: list[ContentBlock] = Field(default_factory=list)
    supporting_visuals: list[str] = Field(
        default_factory=list,
        description=(
            "Only populated when mode='chat'. Names of diagrams/visuals the renderer should "
            "generate inline. E.g. ['rag_workflow_diagram', 'retrieval_vs_generation_comparison']."
        ),
    )


class CitationMetadata(BaseModel):
    result_id: str
    title: str
    url: str
    domain: str
    source_type: str = "unknown"


class ArtifactInputPackage(BaseModel):
    user_query: str
    final_report: Optional[str] = None
    synthesis: str = ""
    data_points: list[dict] = Field(default_factory=list)
    citation_metadata: list[CitationMetadata] = Field(default_factory=list)

    @classmethod
    def from_synthesis(
        cls,
        *,
        user_query: str,
        synthesis: str,
        data_points: list[dict],
        merged_sources: list[dict],
        final_report: Optional[str] = None,
    ) -> "ArtifactInputPackage":
        return cls(
            user_query=user_query,
            final_report=final_report,
            synthesis=synthesis,
            data_points=data_points,
            citation_metadata=[
                CitationMetadata(
                    result_id=src.get("result_id", ""),
                    title=src.get("title", ""),
                    url=src.get("url", ""),
                    domain=src.get("domain", ""),
                    source_type=src.get("source_type", "unknown"),
                )
                for src in merged_sources
            ],
        )


class SectionSpec(BaseModel):
    """A single section in the artifact spec — carries render_type so the bundle generator honours it."""
    render_type: Literal[
        "prose", "card_grid", "svg_diagram", "svg_chart", "table", "kpi_strip"
    ]
    title: str
    prose_content: str = ""       # verbatim text for prose sections
    diagram_description: str = "" # what to draw for diagram/chart sections
    data_refs: list[str] = Field(default_factory=list)
    render_notes: str = ""


class ArtifactSpec(BaseModel):
    artifact_kind: str
    title: str
    subtitle: Optional[str] = None
    layout: Literal["single_column", "hybrid_article", "dashboard", "comparison", "timeline"]
    sections: list[SectionSpec] = Field(default_factory=list)
    interactions: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)


class ArtifactBundle(BaseModel):
    html_body: str
    css: str
    javascript: Optional[str] = None


class ArtifactValidationReport(BaseModel):
    html_ok: bool
    css_ok: bool
    javascript_ok: bool
    citations_ok: bool
    sanitized: bool = False
    warnings: list[str] = Field(default_factory=list)


class BuildArtifactResult(BaseModel):
    artifact_id: str
    version_id: str
    render_url: str
    version: int
    validation_report: ArtifactValidationReport
