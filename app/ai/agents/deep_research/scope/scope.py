import logging
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field
from langchain_core.language_models.chat_models import BaseChatModel
from app.ai.agents.deep_research.state import (
    DeepResearchState,
    ResearchOutline,
    OutlineSection,
)
from app.ai.agents.deep_research.events import DeepResearchEvent, emit_research_event

logger = logging.getLogger(__name__)

class ScopeOutput(BaseModel):
    topic: str
    executive_objective: str
    target_audience: str = "Technical & Business Decision Makers"
    sections: list[OutlineSection] = Field(default_factory=list)
    initial_search_queries: list[str] = Field(default_factory=list)

class ScopeEngine:
    """Decomposes complex inquiries into structured outlines and seed search queries."""
    def __init__(self, llm: BaseChatModel):
        self.llm = llm.with_structured_output(ScopeOutput)

    async def scope_research(
        self,
        user_query: str,
        user_instructions: Optional[str] = None,
    ) -> tuple[ResearchOutline, list[str]]:
        messages = self._build_prompt_messages(user_instructions, user_query)
        logger.info("ScopeEngine: Decomposing research query: %s", user_query[:80])
        output: ScopeOutput = await self.llm.ainvoke(messages)

        outline = ResearchOutline(
            topic=output.topic,
            executive_objective=output.executive_objective,
            target_audience=output.target_audience,
            sections=output.sections,
        )
        return outline, output.initial_search_queries

    async def scoper_node(self, state: DeepResearchState) -> dict[str, Any]:
        """LangGraph node execution function for the Scoping phase."""
        outline, queries = await self.scope_research(
            user_query=state.user_query,
            user_instructions=state.user_instructions,
        )

        await emit_research_event(
            DeepResearchEvent(
                type="research_scoped",
                phase="scoping",
                message=f"Research scoped: '{outline.topic}' ({len(outline.sections)} sections, {len(queries)} seed queries)",
                data={
                    "topic": outline.topic,
                    "sections_count": len(outline.sections),
                    "queries": queries,
                },
            )
        )

        return {
            "phase": "searching",
            "outline": outline,
            "active_search_queries": queries,
            "current_iteration": 1,
        }

    def _build_prompt_messages(self, user_instructions: Optional[str], user_query: str):
        path = Path(__file__).parent / "prompt.md"
        with open(path, "r", encoding="utf-8") as f:
            prompt_content = f.read()
        if not user_instructions:
            return [
                ("system", prompt_content),
                ("user", user_query),
            ]
        return [
            ("system", prompt_content),
            ("user", f"User Instructions: {user_instructions}\nUser Request: {user_query}"),
        ]