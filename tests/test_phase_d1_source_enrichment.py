import asyncio
import socket
import unittest
from unittest.mock import mock_open, patch

from app.agents.researcher import ResearchAgent
from app.models.agents_schemas.research_package_schema import EvidenceBackedFact, ResearchGap, StructuredSynthesisOutput
from app.models.agents_schemas.research_plan_schema import ResearchPlan
from app.models.agents_schemas.search_result_schema import SearchResult
from app.models.agents_schemas.source_enrichment_schema import CandidateSource, SourceEnrichmentDecision, SourceEnrichmentPlan
from app.models.agents_schemas.source_extraction_schema import ExtractedSource, SourceExtractionBudget
from app.utils.source_enrichment import (
    ProviderExtractedContent,
    ProviderExtractionResult,
    SourceEnrichmentCache,
    approve_enrichment_plan,
    build_candidate_sources,
    deterministic_enrichment_plan,
    enrich_sources,
    extraction_policy_for_source,
)
from app.utils.research.enrichment.planner import coerce_source_enrichment_plan


def fake_public_getaddrinfo(host, port, *args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def source(
    result_id,
    url,
    *,
    domain=None,
    source_type="official",
    query="q",
    snippet="snippet with method benchmark dataset",
    relevance_score=0.8,
    source_quality_score=0.8,
    scholarly_identifier=None,
):
    return SearchResult(
        result_id=result_id,
        query=query,
        matched_queries=[query],
        title=result_id,
        url=url,
        normalized_url=url,
        domain=domain or url.split("/")[2],
        source_type=source_type,
        snippet=snippet,
        relevance_score=relevance_score,
        source_quality_score=source_quality_score,
        freshness_score=0.7,
        scholarly_identifier=scholarly_identifier,
    )


def plan():
    return ResearchPlan(
        topic="RAG benchmarks",
        research_depth="normal",
        research_areas=["benchmark methodology", "vendor claims"],
        search_queries=["rag benchmark"],
        must_find=["dataset and metric definitions"],
    )


class FakeProvider:
    def __init__(self, failures=None):
        self.calls = []
        self.failures = set(failures or [])

    async def extract(self, urls, *, query, extract_depth, chunks_per_source):
        self.calls.append((list(urls), query, extract_depth, chunks_per_source))
        contents = []
        for url in urls:
            if url in self.failures:
                contents.append(ProviderExtractedContent(url=url, status="failed", error_message="failed"))
            else:
                contents.append(ProviderExtractedContent(url=url, status="success", raw_content=f"{extract_depth} content for {url} " * 80))
        return ProviderExtractionResult(contents=contents)


class CandidatePrefilterTests(unittest.TestCase):
    def test_prefilter_excludes_unsafe_duplicates_and_already_enriched_with_domain_diversity(self):
        results = [
            source("sr_a", "https://arxiv.org/html/1234.5678", domain="arxiv.org", source_type="primary_research", scholarly_identifier="arxiv:1234.5678"),
            source("sr_dup", "https://arxiv.org/pdf/1234.5678.pdf", domain="arxiv.org", source_type="primary_research", scholarly_identifier="arxiv:1234.5678"),
            source("sr_old", "https://bls.gov/old", domain="bls.gov", source_type="official"),
            source("sr_unsafe", "http://127.0.0.1/private", domain="127.0.0.1"),
            source("sr_vendor", "https://openai.com/bench", domain="openai.com", source_type="vendor", query="vendor benchmark methodology"),
            source("sr_social", "https://x.com/post", domain="x.com", source_type="social"),
        ]

        candidates = build_candidate_sources(
            results,
            plan(),
            [ResearchGap(gap_id="gap_1", description="benchmark methodology", priority="high", researchable=True)],
            already_enriched_result_ids={"sr_old"},
            budget=SourceExtractionBudget(max_candidates_for_llm_planner=16, max_sources_per_domain=1),
            resolver=fake_public_getaddrinfo,
        )
        ids = [item.result_id for item in candidates]

        self.assertIn("sr_a", ids)
        self.assertIn("sr_vendor", ids)
        self.assertNotIn("sr_dup", ids)
        self.assertNotIn("sr_old", ids)
        self.assertNotIn("sr_unsafe", ids)
        self.assertNotIn("sr_social", ids)
        self.assertEqual(ids, [item.result_id for item in candidates])

    def test_social_and_login_gated_sources_default_to_snippet_only(self):
        self.assertEqual(extraction_policy_for_source(source("sr_x", "https://x.com/a", domain="x.com", source_type="social")), "snippet_only")
        self.assertEqual(extraction_policy_for_source(source("sr_li", "https://linkedin.com/a", domain="linkedin.com", source_type="community")), "snippet_only")


class ApprovalTests(unittest.TestCase):
    def test_approval_rejects_invented_duplicates_budget_and_snippet_only_bypass(self):
        candidates = [
            source("sr_doc", "https://learn.microsoft.com/a", domain="learn.microsoft.com", source_type="official_documentation"),
            source("sr_x", "https://x.com/a", domain="x.com", source_type="social"),
        ]
        candidate_models = [
            CandidateSource(
                result_id=item.result_id,
                title=item.title,
                url=item.url,
                domain=item.domain,
                source_type=item.source_type,
                source_quality_score=item.source_quality_score,
                freshness_score=item.freshness_score,
                relevance_score=item.relevance_score,
                matched_queries=item.matched_queries,
                snippet=item.snippet,
                extraction_policy=extraction_policy_for_source(item),
            )
            for item in candidates
        ]
        llm_plan = SourceEnrichmentPlan(
            decisions=[
                SourceEnrichmentDecision(result_id="sr_doc", action="extract", priority="high", reason="primary doc"),
                SourceEnrichmentDecision(result_id="sr_doc", action="extract", priority="high", reason="duplicate"),
                SourceEnrichmentDecision(result_id="sr_fake", action="extract", priority="high", reason="invented"),
                SourceEnrichmentDecision(result_id="sr_x", action="extract", priority="high", reason="social"),
            ]
        )

        with patch("app.utils.url_safety.socket.getaddrinfo", fake_public_getaddrinfo):
            approved = approve_enrichment_plan(llm_plan, candidate_models, set(), SourceExtractionBudget(max_selected_sources_total=1))

        self.assertEqual([item.result_id for item in approved.extract_decisions], ["sr_doc"])
        self.assertIn("sr_fake", [item.result_id for item in approved.rejected_decisions])
        self.assertIn("sr_x", [item.result_id for item in approved.rejected_decisions])
        self.assertEqual([item.result_id for item in approved.snippet_decisions], ["sr_x"])


class ProviderChainTests(unittest.IsolatedAsyncioTestCase):
    async def test_tavily_basic_batches_and_cache_prevents_duplicate_provider_calls(self):
        results = [
            source("sr_1", "https://example.com/1"),
            source("sr_2", "https://example.com/2"),
        ]
        decisions = SourceEnrichmentPlan(
            decisions=[
                SourceEnrichmentDecision(result_id="sr_1", action="extract", priority="high", reason="need", extraction_query="metrics"),
                SourceEnrichmentDecision(result_id="sr_2", action="extract", priority="medium", reason="need", extraction_query="metrics"),
            ]
        )
        candidates = build_candidate_sources(results, plan(), [], already_enriched_result_ids=set(), budget=SourceExtractionBudget(), resolver=fake_public_getaddrinfo)
        provider = FakeProvider()
        cache = SourceEnrichmentCache()

        with patch("app.utils.url_safety.socket.getaddrinfo", fake_public_getaddrinfo):
            approved = approve_enrichment_plan(decisions, candidates, set(), SourceExtractionBudget())
            first, first_trace = await enrich_sources(results, approved, budget=SourceExtractionBudget(), provider=provider, cache=cache)
            second, second_trace = await enrich_sources(results, approved, budget=SourceExtractionBudget(), provider=provider, cache=cache)

        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0][0], ["https://example.com/1", "https://example.com/2"])
        self.assertEqual(provider.calls[0][2], "basic")
        self.assertEqual(provider.calls[0][3], 3)
        self.assertEqual(first["sr_1"].provider, "tavily_extract_basic")
        self.assertEqual(second["sr_2"].provider, "tavily_extract_basic")
        self.assertEqual(first_trace.tavily_basic_succeeded, 2)
        self.assertEqual(second_trace.tavily_basic_attempted, 0)

    async def test_advanced_retry_only_high_priority_and_custom_then_snippet_fallback(self):
        results = [
            source("sr_high", "https://example.com/high"),
            source("sr_low", "https://example.com/low"),
        ]
        decisions = SourceEnrichmentPlan(
            decisions=[
                SourceEnrichmentDecision(result_id="sr_high", action="extract", priority="high", reason="important", recommended_depth="advanced"),
                SourceEnrichmentDecision(result_id="sr_low", action="extract", priority="low", reason="less important", recommended_depth="advanced"),
            ]
        )
        candidates = build_candidate_sources(results, plan(), [], already_enriched_result_ids=set(), budget=SourceExtractionBudget(), resolver=fake_public_getaddrinfo)
        provider = FakeProvider(failures={"https://example.com/high", "https://example.com/low"})

        async def fake_custom(search_result, *, budget):
            if search_result.result_id == "sr_high":
                return ExtractedSource(
                    result_id=search_result.result_id,
                    title=search_result.title,
                    url=search_result.url,
                    content_type="html",
                    extraction_status="success",
                    cleaned_text="custom html success " * 50,
                    char_count=1000,
                    truncated=False,
                    snippet_fallback_used=False,
                )
            return ExtractedSource(
                result_id=search_result.result_id,
                title=search_result.title,
                url=search_result.url,
                extraction_status="failed",
                cleaned_text=search_result.snippet,
                char_count=len(search_result.snippet),
                snippet_fallback_used=True,
            )

        with patch("app.utils.url_safety.socket.getaddrinfo", fake_public_getaddrinfo):
            approved = approve_enrichment_plan(decisions, candidates, set(), SourceExtractionBudget(max_advanced_retries_total=1, max_custom_fallback_urls_total=1))
            extracted, trace = await enrich_sources(
                results,
                approved,
                budget=SourceExtractionBudget(max_advanced_retries_total=1, max_custom_fallback_urls_total=1),
                provider=provider,
                custom_extractor=fake_custom,
            )

        self.assertEqual([call[2] for call in provider.calls], ["basic", "advanced"])
        self.assertEqual(provider.calls[1][0], ["https://example.com/high"])
        self.assertEqual(trace.custom_fallback_attempted, 1)
        self.assertEqual(extracted["sr_high"].provider, "custom_http")
        self.assertEqual(extracted["sr_low"].provider, "snippet_fallback")

    async def test_login_gated_url_does_not_reach_provider_or_custom_fallback(self):
        results = [source("sr_x", "https://x.com/post", domain="x.com", source_type="social")]
        candidates = build_candidate_sources(results, plan(), [], already_enriched_result_ids=set(), budget=SourceExtractionBudget(allow_snippet_only_extraction_override=True), resolver=fake_public_getaddrinfo)
        decisions = SourceEnrichmentPlan(decisions=[SourceEnrichmentDecision(result_id="sr_x", action="extract", priority="high", reason="try")])
        provider = FakeProvider()

        with patch("app.utils.url_safety.socket.getaddrinfo", fake_public_getaddrinfo):
            approved = approve_enrichment_plan(decisions, candidates, set(), SourceExtractionBudget(allow_snippet_only_extraction_override=True))
            extracted, trace = await enrich_sources(results, approved, budget=SourceExtractionBudget(allow_snippet_only_extraction_override=True), provider=provider)

        self.assertEqual(provider.calls, [])
        self.assertEqual(trace.custom_fallback_attempted, 0)
        self.assertEqual(extracted["sr_x"].provider, "snippet_fallback")


class PlannerFallbackTests(unittest.TestCase):
    def test_planner_failure_can_fall_back_to_deterministic_selector(self):
        results = [source("sr_doc", "https://learn.microsoft.com/a", domain="learn.microsoft.com", source_type="official_documentation")]
        candidates = build_candidate_sources(results, plan(), [], already_enriched_result_ids=set(), budget=SourceExtractionBudget(), resolver=fake_public_getaddrinfo)
        fallback = deterministic_enrichment_plan(results, candidates, already_enriched_result_ids=set(), budget=SourceExtractionBudget())

        self.assertEqual(fallback.decisions[0].result_id, "sr_doc")
        self.assertEqual(fallback.decisions[0].action, "extract")

    def test_planner_list_response_is_wrapped_as_decisions(self):
        result = coerce_source_enrichment_plan(
            [
                {
                    "result_id": "sr_doc",
                    "action": "extract",
                    "priority": "high",
                    "reason": "Needs primary-source context.",
                }
            ]
        )

        self.assertEqual(result.decisions[0].result_id, "sr_doc")
        self.assertEqual(result.decisions[0].action, "extract")

    def test_planner_json_list_response_is_wrapped_as_decisions(self):
        result = coerce_source_enrichment_plan(
            '[{"result_id":"sr_doc","action":"use_snippet","priority":"medium","reason":"Snippet is enough."}]'
        )

        self.assertEqual(result.decisions[0].result_id, "sr_doc")
        self.assertEqual(result.decisions[0].action, "use_snippet")


class FakePlannerChain:
    def __init__(self):
        self.payloads = []

    async def plan(self, *args, **kwargs):
        self.payloads.append((args, kwargs))
        return SourceEnrichmentPlan(
            decisions=[
                SourceEnrichmentDecision(result_id="sr_initial", action="extract", priority="high", reason="initial", recommended_depth="advanced"),
                SourceEnrichmentDecision(result_id="sr_follow", action="extract", priority="high", reason="follow"),
            ]
        )

    async def ainvoke(self, payload):
        self.payloads.append(payload)
        return SourceEnrichmentPlan(
            decisions=[
                SourceEnrichmentDecision(result_id="sr_initial", action="extract", priority="high", reason="initial", recommended_depth="advanced"),
                SourceEnrichmentDecision(result_id="sr_follow", action="extract", priority="high", reason="follow"),
            ]
        )


class FakeResearchUtils:
    def __init__(self):
        self.search_calls = []

    async def generate_research_plan(self, user_query):
        return plan()

    async def execute_search_queries(self, queries, depth):
        self.search_calls.append(list(queries))
        if len(self.search_calls) == 1:
            return [source("sr_initial", "https://example.com/initial")]
        return [source("sr_follow", "https://example.com/follow")]


class FakeSynthesisChain:
    def __init__(self):
        self.payloads = []

    async def ainvoke(self, payload):
        self.payloads.append(payload)
        result_id = payload["raw_search_results"][-1]["result_id"]
        gaps = []
        if len(self.payloads) == 1:
            gaps = [ResearchGap(gap_id="gap_1", description="methodology gap", priority="high", researchable=True, follow_up_queries=["follow query"])]
        return StructuredSynthesisOutput(
            executive_summary="summary",
            facts=[EvidenceBackedFact(fact_id="fact_1", statement="fact", evidence_result_ids=[result_id], confidence=0.7)],
            research_gaps=gaps,
        )


async def noop_event(*args, **kwargs):
    return None


class ResearchAgentD1IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_batches_planner_enriches_before_synthesis_and_reuses_cache(self):
        agent = ResearchAgent.__new__(ResearchAgent)
        agent.research_utils = FakeResearchUtils()
        agent._chain = FakeSynthesisChain()
        agent.enrichment_planner = FakePlannerChain()
        provider = FakeProvider(failures={"https://example.com/initial"})

        async def fake_custom(search_result, *, budget):
            return ExtractedSource(
                result_id=search_result.result_id,
                title=search_result.title,
                url=search_result.url,
                content_type="html",
                extraction_status="success",
                cleaned_text=f"custom extracted {search_result.result_id}",
                char_count=32,
                truncated=False,
                snippet_fallback_used=False,
            )

        with patch("builtins.open", mock_open()), patch("app.agents.researcher.adispatch_custom_event", noop_event), patch(
            "app.utils.url_safety.socket.getaddrinfo", fake_public_getaddrinfo
        ), patch("app.agents.researcher.TavilyExtractProvider.from_settings", return_value=provider), patch(
            "app.utils.source_enrichment.extract_source", fake_custom
        ):
            update = await agent.research({"user_query": "research"})

        self.assertEqual(len(agent.enrichment_planner.payloads), 2)
        self.assertEqual(len(agent._chain.payloads), 2)
        self.assertEqual([call[2] for call in provider.calls], ["basic", "advanced", "basic"])
        self.assertIn("custom extracted sr_initial", agent._chain.payloads[0]["source_evidence_content"][0]["text"])
        self.assertIn("basic content", agent._chain.payloads[1]["source_evidence_content"][-1]["text"])
        self.assertEqual(update["research"].selected_source_ids, ["sr_initial", "sr_follow"])


if __name__ == "__main__":
    unittest.main()
