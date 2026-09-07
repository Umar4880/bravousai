from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.utils.research.evidence_normalization import classify_source_type, generate_result_id, normalize_url

SourceType = Literal[
    "official",
    "primary_research",
    "peer_reviewed",
    "official_documentation",
    "reputable_editorial",
    "financial",
    "vendor",
    "community",
    "social",
    "unknown",
    "penalized",
]


class SearchResult(BaseModel):
    result_id: str = ""
    query: str = ""
    matched_queries: list[str] = Field(default_factory=list)
    title: str = ""
    url: str = ""
    normalized_url: str = ""
    domain: str = ""
    source: Optional[str] = None
    published_at: Optional[datetime] = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    snippet: str = ""
    relevance_score: Optional[float] = None
    source_quality_score: float = 0.55
    source_type: SourceType = "unknown"
    freshness_score: float = 0.45
    duplicate_group_id: Optional[str] = None
    scholarly_identifier: Optional[str] = None
    first_seen_iteration: int = 0

    # Legacy compatibility for existing traces and downstream prompts.
    published_date: Optional[str] = None
    relevance: Optional[str] = None

    def model_post_init(self, __context: object) -> None:
        if not self.normalized_url and self.url:
            self.normalized_url = normalize_url(self.url)
        if not self.result_id and self.normalized_url:
            self.result_id = generate_result_id(self.normalized_url)
        if not self.matched_queries and self.query:
            self.matched_queries = [self.query]
        if self.published_at and self.published_date is None:
            self.published_date = self.published_at.date().isoformat()
        if self.source_type == "unknown" and self.domain:
            self.source_type = classify_source_type(self.domain)  # type: ignore[assignment]
