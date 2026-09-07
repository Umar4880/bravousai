from typing import Literal
from pydantic import BaseModel, Field, field_validator

class ResearchPlan(BaseModel):
    topic: str = Field(description="Short topic name")
    depth: Literal["shallow", "deep"] = "shallow"
    research_areas: list[str] = Field(default_factory=list, description="Key areas to research")
    primary_queries: list[str] = Field(
        description="4-6 self-contained queries covering the core information need. Always executed."
    )
    followup_queries: list[str] = Field(
        default_factory=list,
        description="2-3 targeted gap queries. Only run if the sufficiency gate fails after primary search."
    )
    must_find: list[str] = Field(default_factory=list, description="Specific information that must be found")
    avoid: list[str] = Field(default_factory=list, description="Information or angles to avoid if irrelevant")
    time_sensitive: bool = Field(
        default=False,
        description="True when the query requires recent information."
    )
    avoid_domains: list[str] = Field(
        default_factory=list,
        description="Domains to exclude from search results. E.g. youtube.com, quora.com. "
                    "These are passed to the search API as exclusions."
    )
    prefer_domains: list[str] = Field(
        default_factory=list,
        description="High-value domains to prioritize in results. E.g. reuters.com, "
                    "federalreserve.gov. Results from these get a relevance boost."
    )

    @field_validator("depth", mode="before")
    @classmethod
    def normalize_depth(cls, v: str) -> str:
        """Coerce legacy/LLM values to valid Literal. 'light'/'normal' -> 'shallow', 'detailed' -> 'deep'."""
        mapping = {
            "light": "shallow",
            "normal": "shallow",
            "detailed": "deep",
            "medium": "shallow",
            "heavy": "deep",
            "full": "deep",
        }
        return mapping.get(str(v).lower(), "shallow")
