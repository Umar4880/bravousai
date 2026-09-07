import logging
from typing import Any, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.core.config import setting
from app.core.llm_provider import LLMFactory
from app.ai.agents.deep_research.graph import create_deep_research_graph
from app.ai.agents.deep_research.events import DeepResearchEvent, emit_research_event

logger = logging.getLogger(__name__)


class DeepResearchArgs(BaseModel):
    """Input parameters for the Deep Research tool."""
    query: str = Field(
        ...,
        description="The strategic topic, research inquiry, or complex subject to investigate in depth."
    )
    instructions: Optional[str] = Field(
        default=None,
        description="Specific focus areas, required metrics, constraints, target audience, or formatting preferences."
    )
    max_iterations: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Exploration and gap-analysis iteration budget (default: 2, range: 1-5)."
    )


class DeepResearchTool(BaseTool):
    """Guarded BaseTool subclass executing the autonomous Deep Research agent workflow."""

    name: str = "deep_research"
    description: str = (
        "Execute a comprehensive, publication-grade deep research investigation on a topic. "
        "Scopes a multi-section outline, executes multi-source web searches, extracts verified evidence and metrics, "
        "audits contradictions and gaps, and compiles a fully cited final report. "
        "Use for complex, multi-faceted, or forward-looking inquiries requiring empirical backing."
    )
    args_schema: type[BaseModel] = DeepResearchArgs
    handle_tool_error: bool = True  

    # Dependency injection attributes
    llm: Optional[BaseChatModel] = None
    tavily_api_key: Optional[str] = None
    search_depth: str = "basic"
    max_concurrency: int = 3

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """Synchronous execution is intentionally blocked to protect concurrency."""
        raise NotImplementedError(
            "DeepResearchTool only supports asynchronous execution via arun()."
        )

    async def _arun(
        self,
        query: str,
        instructions: Optional[str] = None,
        max_iterations: int = 2,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> str:
        """Guarded asynchronous execution of the deep research graph."""
        clean_query = (query or "").strip()
        if not clean_query:
            return "Error: A valid, non-empty research query is required to perform deep research."

        # Guard iteration budget
        safe_iterations = max(1, min(int(max_iterations), 5))

        logger.info(
            "DeepResearchTool: starting guarded execution | query='%s' | max_iterations=%d",
            clean_query[:80],
            safe_iterations,
        )

        try:
            # 1. Resolve API key & credentials guard
            api_key = (
                self.tavily_api_key
                or setting.TAVILY_API_KEY
            )
            if not api_key:
                logger.error("DeepResearchTool: TAVILY_API_KEY is not configured.")
                return (
                    "Execution halted: Web search credentials (TAVILY_API_KEY) are not configured. "
                    "Please configure search credentials to run deep research."
                )

            # 2. Resolve LLM guard
            model = self.llm or LLMFactory.get_llm(agent_name="deep_research")

            # 3. Compile graph
            graph = create_deep_research_graph(
                llm=model,
                tavily_api_key=api_key,
                search_depth=self.search_depth,
                max_concurrency=self.max_concurrency,
            )

            # 4. Invoke graph execution
            initial_state = {
                "user_query": clean_query,
                "user_instructions": instructions.strip() if instructions else None,
                "max_iterations": safe_iterations,
            }

            config = None
            if run_manager and hasattr(run_manager, "get_child"):
                config = {"callbacks": run_manager.get_child()}

            result = await graph.ainvoke(initial_state, config=config)

            final_report = result.get("final_report")
            if not final_report:
                logger.warning("DeepResearchTool: Graph finished without producing a final report.")
                return "Deep research completed its exploration cycles, but could not compile a final report."

            logger.info("DeepResearchTool: Successfully generated final report (%d words)", len(final_report.split()))
            return final_report

        except Exception as exc:
            logger.exception("DeepResearchTool: Unhandled failure during research execution: %s", exc)
            await emit_research_event(
                DeepResearchEvent(
                    type="error",
                    phase="error",
                    message=f"Deep research execution error: {str(exc)}",
                    data={"query": clean_query, "error": str(exc)},
                )
            )
            return (
                f"Deep Research encountered an unexpected issue while investigating '{clean_query}': {str(exc)}. "
                "You may attempt to narrow the inquiry or answer with existing knowledge."
            )


# Default singleton tool instance
deep_research_tool = DeepResearchTool()
