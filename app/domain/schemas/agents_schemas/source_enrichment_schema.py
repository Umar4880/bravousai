from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class EvidenceNeed(BaseModel):
    need_id: str
    description: str
    priority: Literal["high", "medium", "low"]


class CandidateSource(BaseModel):
    result_id: str
    title: str
    url: str
    domain: str
    source_type: str
    source_quality_score: float
    freshness_score: float
    relevance_score: Optional[float] = None
    matched_queries: list[str] = Field(default_factory=list)
    snippet: str
    extraction_policy: Literal["prefer_extract", "try_extract", "snippet_only"]


class SourceEnrichmentDecision(BaseModel):
    result_id: str
    action: Literal["use_snippet", "extract", "skip"]
    priority: Literal["high", "medium", "low"]
    reason: str
    evidence_need_ids: list[str] = Field(default_factory=list)
    extraction_query: Optional[str] = None
    recommended_depth: Literal["basic", "advanced"] = "basic"


class SourceEnrichmentPlan(BaseModel):
    decisions: list[SourceEnrichmentDecision] = Field(default_factory=list)
    planner_summary: Optional[str] = None


class RejectedEnrichmentDecision(BaseModel):
    result_id: str
    reason: str


class ApprovedEnrichmentPlan(BaseModel):
    extract_decisions: list[SourceEnrichmentDecision] = Field(default_factory=list)
    snippet_decisions: list[SourceEnrichmentDecision] = Field(default_factory=list)
    skipped_decisions: list[SourceEnrichmentDecision] = Field(default_factory=list)
    rejected_decisions: list[RejectedEnrichmentDecision] = Field(default_factory=list)

    @property
    def approved_result_ids(self) -> list[str]:
        return [decision.result_id for decision in self.extract_decisions]
