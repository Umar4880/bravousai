import logging
from typing import Literal, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.ai.agents.deep_research.critique.critique import CritiqueEngine, route_after_critique
from app.ai.agents.deep_research.exploration.exploration import ExplorationEngine
from app.ai.agents.deep_research.scope.scope import ScopeEngine
from app.ai.agents.deep_research.search.search import SearchEngine
from app.ai.agents.deep_research.state import DeepResearchState
from app.ai.agents.deep_research.synthesis.synthesis import SynthesisEngine

logger = logging.getLogger(__name__)


def create_deep_research_graph(
    llm: BaseChatModel,
    tavily_api_key: Optional[str] = None,
    search_depth: Literal["basic", "advanced"] = "basic",
    max_results_per_query: int = 5,
    max_concurrency: int = 3,
    sufficiency_threshold: float = 0.85,
) -> CompiledStateGraph:
    """Constructs and compiles the complete Deep Research LangGraph workflow.
    
    Phases:
      1. Scoping (Decomposes research inquiry into structured outline & seed queries)
      2. Searching (Executes concurrent search queries via Tavily with URL deduplication)
      3. Exploration / Distilling (Extracts atomic, verified EvidenceItems from sources)
      4. Critique / Gap Analysis (Evaluates coverage against outline, detects contradictions, loops if gaps remain)
      5. Synthesis (Drafts comprehensive section chapters, executive summary, and formatted report)
    """
    scoper = ScopeEngine(llm)
    searcher = SearchEngine(
        api_key=tavily_api_key,
        search_depth=search_depth,
        max_results_per_query=max_results_per_query,
        max_concurrency=max_concurrency,
    )
    explorer = ExplorationEngine(llm)
    critique = CritiqueEngine(llm, sufficiency_threshold=sufficiency_threshold)
    synthesizer = SynthesisEngine(llm)

    workflow = StateGraph(DeepResearchState)

    # Register nodes
    workflow.add_node("scoper", scoper.scoper_node)
    workflow.add_node("search", searcher.search_node)
    workflow.add_node("exploration", explorer.exploration_node)
    workflow.add_node("critique", critique.critique_node)
    workflow.add_node("synthesizer", synthesizer.synthesizer_node)

    # Set linear edges
    workflow.set_entry_point("scoper")
    workflow.add_edge("scoper", "search")
    workflow.add_edge("search", "exploration")
    workflow.add_edge("exploration", "critique")

    # Conditional feedback loop after critique
    workflow.add_conditional_edges(
        "critique",
        route_after_critique,
        {
            "search": "search",
            "synthesizer": "synthesizer",
        },
    )

    # Final transition
    workflow.add_edge("synthesizer", END)

    logger.info("Compiled Deep Research StateGraph successfully.")
    return workflow.compile()
