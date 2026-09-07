"""Tavily Extract provider adapter.

The callable integration remains in app.ai.tools because Tavily is an external
tool provider. This module gives the research package a stable import surface.
"""

from app.ai.tools.tavily_extract_tool import (
    ProviderExtractedContent,
    ProviderExtractionResult,
    SourceEnrichmentProvider,
    TavilyExtractProvider,
    normalize_tavily_extract_response,
)

__all__ = [
    "ProviderExtractedContent",
    "ProviderExtractionResult",
    "SourceEnrichmentProvider",
    "TavilyExtractProvider",
    "normalize_tavily_extract_response",
]

