import uuid
from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceItem(BaseModel):
    """An atomic, verified piece of evidence extracted from a source."""
    id: str = Field(default_factory=lambda: f"E{uuid.uuid4().hex[:6].upper()}")
    claim: str
    exact_quote: str
    metric_value: Optional[str] = None
    source_url: str
    source_domain: str
    source_title: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    published_date: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=utc_now)


class OutlineSection(BaseModel):
    """A single section or chapter in the planned report."""
    section_id: str
    title: str
    description: str
    key_questions_to_answer: list[str] = Field(default_factory=list)
    required_metrics: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["pending", "researching", "ready_to_write", "drafted"] = "pending"
    draft_content: Optional[str] = None


class ResearchOutline(BaseModel):
    """The master plan governing the entire investigation."""
    topic: str
    executive_objective: str
    target_audience: str = "Technical & Business Decision Makers"
    sections: list[OutlineSection] = Field(default_factory=list)


class Contradiction(BaseModel):
    """Represents conflicting claims discovered between sources."""
    topic: str
    claim_a: str
    source_a_url: str
    claim_b: str
    source_b_url: str
    resolution_status: Literal["unresolved", "resolved"] = "unresolved"


class GapReport(BaseModel):
    """Analysis of what information is missing or contradictory."""
    coverage_score: float = Field(ge=0.0, le=1.0, description="0.0 to 1.0 completeness")
    is_sufficient: bool = False
    covered_topics: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    follow_up_queries: list[str] = Field(default_factory=list)


class SearchResultItem(BaseModel):
    """An individual web search result discovered during exploration."""
    url: str
    title: str
    snippet: str
    raw_content: Optional[str] = None
    published_date: Optional[str] = None
    query: str
    score: Optional[float] = None


class DeepResearchState(BaseModel):
    """The master state carried through the research lifecycle."""
    # Control & Flow
    phase: Literal[
        "scoping", "searching", "distilling", "critiquing", "synthesizing", "complete"
    ] = "scoping"
    user_query: str
    user_instructions: Optional[str] = None
    max_iterations: int = 3
    current_iteration: int = 0

    # Phase 1: Scoping
    outline: Optional[ResearchOutline] = None

    # Phase 2: Exploration Memory
    active_search_queries: list[str] = Field(default_factory=list)
    visited_urls: list[str] = Field(default_factory=list)
    raw_search_results: list[SearchResultItem] = Field(default_factory=list)
    evidence_ledger: list[EvidenceItem] = Field(default_factory=list)
    gap_reports: list[GapReport] = Field(default_factory=list)

    # Phase 3: Synthesis
    final_report: Optional[str] = None
    is_complete: bool = False
