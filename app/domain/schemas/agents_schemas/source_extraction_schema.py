from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ExtractedSource(BaseModel):
    result_id: str
    title: str
    url: str

    content_type: Literal["html", "pdf", "text", "unknown"] = "unknown"
    extraction_status: Literal["success", "partial", "failed", "skipped"] = "skipped"

    cleaned_text: str = ""
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    char_count: int = 0
    truncated: bool = False
    snippet_fallback_used: bool = False

    content_hash: Optional[str] = None
    error_message: Optional[str] = None
    provider: Literal[
        "tavily_extract_basic",
        "tavily_extract_advanced",
        "custom_http",
        "snippet_fallback",
    ] = "custom_http"
    extraction_depth: Literal["basic", "advanced", "custom", "snippet"] = "custom"
    extraction_query: Optional[str] = None
    evidence_need_ids: list[str] = Field(default_factory=list)
    planner_reason: Optional[str] = None


class SourceExtractionBudget(BaseModel):
    max_selected_sources_total: int = 8
    max_new_sources_after_follow_up: int = 3
    max_sources_per_domain: int = 2
    max_concurrent_fetches: int = 4

    request_timeout_seconds: float = 8.0
    max_redirects: int = 3

    max_html_bytes: int = 1_500_000
    max_pdf_bytes: int = 5_000_000

    max_chars_per_source: int = 12_000
    max_total_cleaned_chars: int = 80_000
    max_candidates_for_llm_planner: int = 16
    max_tavily_basic_urls_total: int = 8
    max_advanced_retries_total: int = 2
    max_custom_fallback_urls_total: int = 3
    tavily_chunks_per_source: int = 3
    tavily_extract_timeout_seconds: float = 15.0
    allow_snippet_only_extraction_override: bool = False


class SourceExtractionTrace(BaseModel):
    selected_result_ids: list[str] = Field(default_factory=list)
    candidate_count: int = 0
    planner_decision_count: int = 0
    approved_result_ids: list[str] = Field(default_factory=list)
    rejected_result_ids: list[str] = Field(default_factory=list)
    tavily_basic_attempted: int = 0
    tavily_basic_succeeded: int = 0
    tavily_advanced_attempted: int = 0
    tavily_advanced_succeeded: int = 0
    custom_fallback_attempted: int = 0
    custom_fallback_succeeded: int = 0
    snippet_fallbacks: int = 0
    successfully_extracted: int = 0
    partially_extracted: int = 0
    failed: int = 0
    skipped: int = 0
    total_cleaned_chars: int = 0
    estimated_tavily_extract_credits: float = 0.0
