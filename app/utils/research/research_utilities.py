from app.domain.schemas.agents_schemas.research_plan_schema import ResearchPlan
from app.ai.tools.web_search_tool import web_search_tool
from app.ai.nodes.graph.state import AgentState, SearchResult, ResearchState
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.runnables import RunnableConfig
from app.core.prompt_loader import PromptManager
from app.utils.research.evidence_normalization import (
    build_normalized_result_fields,
    deduplicate_result_dicts,
)
from app.core.config import setting
import json
import logging
import time

import asyncio

logger = logging.getLogger(__name__)


class ResearchUtilities:
    """Utility functions for research planning, search execution, and LLM synthesis."""
    
    def __init__(self, llm: BaseChatModel, prompt_manager: PromptManager):
        self.llm = llm
        self.prompt_mng = prompt_manager
    
    async def generate_research_plan(self, user_query: str, mode: str = "extended", user_instructions: str = "None", uploaded_files: str = "None") -> ResearchPlan:
        """
        Generate a structured research plan from user query.
        Handles both structured output and manual JSON parsing with retry logic.
        """
        started_at = time.perf_counter()
        
        if mode == "instant":
            user_query = f"{user_query}\n\n[SYSTEM DIRECTIVE: This is an INSTANT mode query. You MUST generate at most 3 targeted search queries, and you MUST set depth to 'shallow'. Keep the plan very focused.]"
            
        logger.info(
            "Research planning started | query_chars=%s | timeout_seconds=%s",
            len(user_query or ""),
            setting.RESEARCH_PLAN_TIMEOUT_SECONDS,
        )
        
        prompt = self.prompt_mng.load_agent_system_prompt(
            agent_name="research_planer",
            include_history=False
        )
        
        try:
            structured_llm = self.llm.with_structured_output(ResearchPlan)
        except Exception:
            structured_llm = self.llm
        
        chain = prompt | structured_llm
        
        try:
            result = await asyncio.wait_for(
                chain.ainvoke({
                    "user_input": user_query,
                    "user_instructions": user_instructions,
                    "uploaded_files": uploaded_files,
                }),
                timeout=setting.RESEARCH_PLAN_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.exception(
                "Research planning timed out | query_chars=%s | timeout_seconds=%s",
                len(user_query or ""),
                setting.RESEARCH_PLAN_TIMEOUT_SECONDS,
            )
            return self._fallback_research_plan(user_query, reason="planner_timeout")
        except Exception:
            logger.exception("Research planning failed")
            return self._fallback_research_plan(user_query, reason="planner_error")

        logger.info(
            "Research planning LLM response received | elapsed_ms=%s | result_type=%s",
            round((time.perf_counter() - started_at) * 1000, 2),
            type(result).__name__,
        )
        
        # If result is already a ResearchPlan object, return it
        if isinstance(result, ResearchPlan):
            return result
        
        # Parse if string
        if isinstance(result, str):
            try:
                # Clean up common JSON issues
                cleaned = result.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                
                plan_dict = json.loads(cleaned)
                return ResearchPlan.model_validate(plan_dict)
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"Failed to parse research plan JSON: {e} | Result: {result[:500]}")
                return self._fallback_research_plan(user_query, reason="planner_parse_error")
        
        logger.warning(f"Unexpected result type: {type(result)}")
        return self._fallback_research_plan(user_query, reason="planner_unexpected_result")

    def _fallback_research_plan(self, user_query: str, *, reason: str) -> ResearchPlan:
        cleaned_query = " ".join((user_query or "").split())
        fallback_query = cleaned_query[:300] or "current research topic"
        logger.warning(
            "Using fallback research plan | reason=%s | query_chars=%s",
            reason,
            len(cleaned_query),
        )
        return ResearchPlan(
            topic=fallback_query[:100],
            research_areas=["General research"],
            primary_queries=[fallback_query],
            depth="shallow",
        )
        
    async def execute_search_queries(
        self, 
        search_queries: list[str], 
        depth: str, 
        exclude_domains: list[str] | None = None,
        config: RunnableConfig | None = None
    ) -> list[SearchResult]:
        """
        Execute multiple search queries in parallel and aggregate results.
        """
        unique_queries: list[str] = []
        seen_queries: set[str] = set()
        for query in search_queries:
            normalized_query = " ".join(query.split()).casefold()
            if not normalized_query or normalized_query in seen_queries:
                continue
            seen_queries.add(normalized_query)
            unique_queries.append(query)

        if len(unique_queries) != len(search_queries):
            logger.info(
                "Deduplicated research search queries | original=%s | unique=%s",
                len(search_queries),
                len(unique_queries),
            )
        search_queries = unique_queries

        logger.debug(f"Executing {len(search_queries)} search queries in parallel...")
        
        # Create parallel tasks for all queries
        for query in search_queries:
            await adispatch_custom_event(
                "search_query_started",
                {
                    "node": "researcher",
                    "query": query,
                    "message": "Search query started.",
                },
            )

        tasks = [
            web_search_tool.ainvoke(
                {"user_query": q, "search_depth": depth, "exclude_domains": exclude_domains},
                config=config
            )
            for q in search_queries
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        raw_results = []
        raw_counts_by_query: dict[str, int] = {}
        
        for query, response in zip(search_queries, responses):
            if isinstance(response, Exception):
                logger.warning(f"Error searching '{query}': {response}")
                raw_counts_by_query[query] = 0
                await adispatch_custom_event(
                    "search_query_completed",
                    {
                        "node": "researcher",
                        "query": query,
                        "result_count": 0,
                        "message": "Search query completed with an error.",
                    },
                )
                continue
            
            try:
                # Parse response if string
                if isinstance(response, str):
                    if not response.strip():
                        response = "{}"
                    response = json.loads(response)
                
                # Extract results from Tavily response
                if isinstance(response, dict):
                    items = response.get("results", [])
                    raw_counts_by_query[query] = len(items)
                    
                    for item in items:
                        result_fields = build_normalized_result_fields(
                            query=query,
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            source=item.get("source"),
                            published_at=item.get("published_date") or item.get("published_at"),
                            snippet=item.get("content", item.get("snippet", "")),
                            relevance_score=item.get("score"),
                        )
                        search_result = SearchResult(**result_fields)
                        raw_results.append(search_result)
                        logger.debug(f"Found: {search_result.title}")

                    await adispatch_custom_event(
                        "search_query_completed",
                        {
                            "node": "researcher",
                            "query": query,
                            "result_count": len(items),
                            "message": "Search query completed.",
                        },
                    )
            
            except Exception as e:
                logger.warning(f"Error parsing results for '{query}': {e}")
                raw_counts_by_query[query] = 0
                await adispatch_custom_event(
                    "search_query_completed",
                    {
                        "node": "researcher",
                        "query": query,
                        "result_count": 0,
                        "message": "Search query completed with a parsing error.",
                    },
                )
        
        deduplicated_results = [
            SearchResult(**result)
            for result in deduplicate_result_dicts(
                [result.model_dump() for result in raw_results]
            )
        ]

        for result in deduplicated_results:
            if result.url:
                await adispatch_custom_event(
                    "search_result_found",
                    {
                        "node": "researcher",
                        "query": result.query,
                        "matched_queries": result.matched_queries,
                        "result_id": result.result_id,
                        "title": result.title,
                        "url": result.url,
                        "domain": result.domain,
                        "source_type": result.source_type,
                    },
                )

        logger.info(
            "Retrieved %s total results, %s after deterministic deduplication",
            len(raw_results),
            len(deduplicated_results),
        )
        return deduplicated_results
