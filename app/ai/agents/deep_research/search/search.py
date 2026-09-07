import asyncio
import logging
import os
from typing import Any, Literal, Optional
from urllib.parse import urlparse

from tavily import AsyncTavilyClient

from app.core.config import setting
from app.ai.agents.deep_research.events import DeepResearchEvent, emit_research_event
from app.ai.agents.deep_research.state import DeepResearchState, SearchResultItem

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """Normalize URL by stripping trailing slashes, fragments, and whitespace."""
    if not url:
        return ""
    url = url.strip()
    parsed = urlparse(url)
    # Remove fragment and trailing slash from path
    path = parsed.path.rstrip("/")
    normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return normalized


class SearchEngine:
    """Dispatches targeted web search queries, aggregates sources, and deduplicates URLs."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        search_depth: Literal["basic", "advanced"] = "basic",
        max_results_per_query: int = 5,
        max_concurrency: int = 3,
        include_raw_content: bool = False,
    ):
        self.api_key = api_key or setting.TAVILY_API_KEY or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            logger.warning(
                "SearchEngine: TAVILY_API_KEY not found in settings or environment. "
                "Web searches will fail unless an API key is provided."
            )
        self.search_depth = search_depth
        self.max_results_per_query = max_results_per_query
        self.max_concurrency = max_concurrency
        self.include_raw_content = include_raw_content
        self._client: Optional[AsyncTavilyClient] = (
            AsyncTavilyClient(api_key=self.api_key) if self.api_key else None
        )

    def _get_client(self) -> AsyncTavilyClient:
        if not self._client:
            self.api_key = self.api_key or setting.TAVILY_API_KEY or os.getenv("TAVILY_API_KEY")
            if not self.api_key:
                raise ValueError("TAVILY_API_KEY is required to perform web searches.")
            self._client = AsyncTavilyClient(api_key=self.api_key)
        return self._client

    async def search_single_query(
        self,
        query: str,
        visited_urls: set[str],
        semaphore: asyncio.Semaphore,
    ) -> list[SearchResultItem]:
        """Execute an individual search query with concurrency limits, deduplication, and event telemetry."""
        await emit_research_event(
            DeepResearchEvent(
                type="search_dispatched",
                phase="searching",
                message=f"Dispatching web search: '{query}'",
                data={"query": query},
            )
        )

        client = self._get_client()
        async with semaphore:
            try:
                response = await client.search(
                    query=query,
                    search_depth=self.search_depth,
                    max_results=self.max_results_per_query,
                    include_raw_content="text" if self.include_raw_content else None,
                )
            except Exception as e:
                logger.error("Search failed for query '%s': %s", query, e)
                await emit_research_event(
                    DeepResearchEvent(
                        type="error",
                        phase="searching",
                        message=f"Search failed for '{query}': {str(e)}",
                        data={"query": query, "error": str(e)},
                    )
                )
                return []

        results: list[SearchResultItem] = []
        raw_items = response.get("results", []) if isinstance(response, dict) else []

        for item in raw_items:
            raw_url = item.get("url", "")
            norm_url = normalize_url(raw_url)
            if not norm_url or norm_url in visited_urls:
                continue

            visited_urls.add(norm_url)
            results.append(
                SearchResultItem(
                    url=norm_url,
                    title=item.get("title", ""),
                    snippet=item.get("content", ""),
                    raw_content=item.get("raw_content"),
                    published_date=item.get("published_date"),
                    query=query,
                    score=item.get("score"),
                )
            )

        await emit_research_event(
            DeepResearchEvent(
                type="search_completed",
                phase="searching",
                message=f"Search completed: '{query}' ({len(results)} new unique sources)",
                data={
                    "query": query,
                    "result_count": len(results),
                    "urls": [r.url for r in results],
                },
            )
        )
        return results

    async def execute_searches(
        self,
        queries: list[str],
        visited_urls: Optional[list[str]] = None,
    ) -> tuple[list[SearchResultItem], list[str]]:
        """Run multiple queries concurrently, returning unique search results and updated visited URLs."""
        if not queries:
            logger.info("SearchEngine: No queries to execute.")
            return [], visited_urls or []

        visited_set = set(normalize_url(u) for u in (visited_urls or []) if u)
        semaphore = asyncio.Semaphore(self.max_concurrency)

        tasks = [
            self.search_single_query(query=q, visited_urls=visited_set, semaphore=semaphore)
            for q in queries
        ]
        results_nested = await asyncio.gather(*tasks, return_exceptions=False)

        all_new_results = [item for sublist in results_nested for item in sublist]
        logger.info(
            "SearchEngine: Completed %d queries | Discovered %d new unique sources",
            len(queries),
            len(all_new_results),
        )
        return all_new_results, list(visited_set)

    async def search_node(self, state: DeepResearchState) -> dict[str, Any]:
        """LangGraph node execution function for the Searching / Exploration phase."""
        queries = state.active_search_queries
        logger.info("SearchEngine node: executing %d queries", len(queries))

        new_results, updated_visited_urls = await self.execute_searches(
            queries=queries,
            visited_urls=state.visited_urls,
        )

        # Merge new results with any previous results
        combined_results = state.raw_search_results + new_results

        return {
            "phase": "distilling",
            "visited_urls": updated_visited_urls,
            "raw_search_results": combined_results,
            "active_search_queries": [],  # Completed for this cycle
        }
