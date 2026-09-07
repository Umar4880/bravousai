"""URL normalization helpers used by the research workflow."""

from app.utils.research.evidence_normalization import (
    duplicate_group_id_for_url,
    extract_domain,
    generate_result_id,
    normalize_url,
)

__all__ = [
    "duplicate_group_id_for_url",
    "extract_domain",
    "generate_result_id",
    "normalize_url",
]

