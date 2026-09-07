import socket
import unittest
from unittest.mock import mock_open, patch

import httpx

from app.agents.researcher import ResearchAgent
from app.models.agents_schemas.research_package_schema import (
    EvidenceBackedFact,
    ResearchGap,
    StructuredSynthesisOutput,
)
from app.models.agents_schemas.research_plan_schema import ResearchPlan
from app.models.agents_schemas.search_result_schema import SearchResult
from app.models.agents_schemas.source_extraction_schema import ExtractedSource, SourceExtractionBudget
from app.utils.source_extraction import (
    _fetch_with_redirects,
    extract_html_text,
    extract_selected_sources,
    extract_source,
)
from app.utils.source_selection import format_sources_for_synthesis, select_sources_for_extraction
from app.utils.url_safety import URLSafetyError, validate_url_for_fetch


def fake_public_getaddrinfo(host, port, *args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def result(
    result_id,
    url,
    *,
    source_type="unknown",
    domain="example.com",
    relevance_score=0.5,
    source_quality_score=0.55,
    freshness_score=0.45,
    query="q",
    scholarly_identifier=None,
    snippet=None,
):
    return SearchResult(
        result_id=result_id,
        query=query,
        matched_queries=[query],
        title=result_id,
        url=url,
        normalized_url=url,
        domain=domain,
        source_type=source_type,
        relevance_score=relevance_score,
        source_quality_score=source_quality_score,
        freshness_score=freshness_score,
        snippet=snippet or f"snippet {result_id}",
        scholarly_identifier=scholarly_identifier,
    )


def client_factory_for(handler):
    transport = httpx.MockTransport(handler)
    return lambda: httpx.AsyncClient(transport=transport, follow_redirects=False)


class SourceSelectionTests(unittest.TestCase):
    def test_quality_relevance_caps_and_stability(self):
        budget = SourceExtractionBudget(max_selected_sources_total=3, max_sources_per_domain=2)
        results = [
            result("sr_vendor", "https://vendor.com/a", source_type="vendor", domain="vendor.com", relevance_score=0.9),
            result(
                "sr_primary",
                "https://arxiv.org/html/1",
                source_type="primary_research",
                domain="arxiv.org",
                relevance_score=0.2,
            ),
            result(
                "sr_doc",
                "https://docs.example.com/a",
                source_type="official_documentation",
                domain="docs.example.com",
                relevance_score=0.4,
            ),
            result("sr_comm", "https://medium.com/a", source_type="community", domain="medium.com", relevance_score=1.0),
        ]

        first = select_sources_for_extraction(results, already_selected_result_ids=set(), budget=budget)
        second = select_sources_for_extraction(list(reversed(results)), already_selected_result_ids=set(), budget=budget)

        self.assertEqual(first[0], "sr_primary")
        self.assertIn("sr_doc", first)
        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 3)
        self.assertIn("sr_comm", {item.result_id for item in results})

    def test_gap_bonus_domain_cap_and_already_selected(self):
        budget = SourceExtractionBudget(max_selected_sources_total=4, max_sources_per_domain=1)
        gap = ResearchGap(
            gap_id="g1",
            description="gap",
            priority="high",
            researchable=True,
            follow_up_queries=["multi hop reliability benchmark"],
        )
        results = [
            result("sr_old", "https://a.com/old", source_type="primary_research", domain="a.com"),
            result("sr_gap", "https://b.com/gap", source_type="vendor", domain="b.com", query="multi hop reliability benchmark"),
            result("sr_same_domain", "https://b.com/other", source_type="primary_research", domain="b.com"),
            result("sr_other", "https://c.com/other", source_type="official", domain="c.com"),
        ]

        selected = select_sources_for_extraction(
            results,
            already_selected_result_ids={"sr_old"},
            budget=budget,
            research_gaps=[gap],
            max_new_sources=2,
        )

        self.assertNotIn("sr_old", selected)
        self.assertLessEqual(len(selected), 2)
        self.assertEqual(len([item for item in selected if item in {"sr_gap", "sr_same_domain"}]), 1)

    def test_duplicate_scholarly_documents_are_not_selected_twice(self):
        budget = SourceExtractionBudget(max_selected_sources_total=5)
        results = [
            result("sr_a", "https://arxiv.org/html/1234.5678v1", source_type="primary_research", scholarly_identifier="arxiv:1234.5678"),
            result("sr_b", "https://arxiv.org/pdf/1234.5678v2.pdf", source_type="primary_research", scholarly_identifier="arxiv:1234.5678"),
        ]

        selected = select_sources_for_extraction(results, already_selected_result_ids=set(), budget=budget)

        self.assertEqual(len(selected), 1)


class URLSafetyTests(unittest.IsolatedAsyncioTestCase):
    def test_public_http_and_https_pass(self):
        validate_url_for_fetch("https://example.com/a", resolver=fake_public_getaddrinfo)
        validate_url_for_fetch("http://example.com/a", resolver=fake_public_getaddrinfo)

    def test_blocked_urls_fail(self):
        blocked = [
            "http://localhost:8000",
            "http://127.0.0.1",
            "http://10.0.0.1",
            "http://169.254.169.254",
            "file:///etc/passwd",
            "ftp://example.com/file",
        ]
        for url in blocked:
            with self.subTest(url=url):
                with self.assertRaises(URLSafetyError):
                    validate_url_for_fetch(url, resolver=fake_public_getaddrinfo)

    async def test_redirect_to_blocked_destination_fails(self):
        async def handler(request):
            return httpx.Response(302, headers={"location": "http://127.0.0.1"})

        with patch("app.utils.url_safety.socket.getaddrinfo", fake_public_getaddrinfo):
            with self.assertRaises(URLSafetyError):
                await _fetch_with_redirects(
                    "https://example.com/start",
                    budget=SourceExtractionBudget(max_redirects=1),
                    client_factory=client_factory_for(handler),
                )


class ExtractionTests(unittest.IsolatedAsyncioTestCase):
    def test_html_cleaning_removes_noise_and_normalizes_whitespace(self):
        html = "<html><style>.x{}</style><script>x()</script><nav>menu</nav><article><h1>Title</h1><p>Hello   world</p></article></html>"

        text = extract_html_text(html)

        self.assertIn("Title", text)
        self.assertIn("Hello world", text)
        self.assertNotIn("menu", text)
        self.assertNotIn("x()", text)

    async def test_html_extraction_truncates_and_hashes(self):
        async def handler(request):
            return httpx.Response(200, headers={"content-type": "text/html"}, text="<p>" + ("a" * 50) + "</p>")

        with patch("app.utils.url_safety.socket.getaddrinfo", fake_public_getaddrinfo):
            extracted = await extract_source(
                result("sr_1", "https://example.com/a"),
                budget=SourceExtractionBudget(max_chars_per_source=10),
                client_factory=client_factory_for(handler),
            )

        self.assertEqual(extracted.extraction_status, "partial")
        self.assertTrue(extracted.truncated)
        self.assertEqual(extracted.char_count, 10)
        self.assertIsNotNone(extracted.content_hash)

    async def test_pdf_routing_success_and_malformed_failure(self):
        async def handler(request):
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")

        with patch("app.utils.url_safety.socket.getaddrinfo", fake_public_getaddrinfo), patch(
            "app.utils.source_extraction.extract_pdf_text",
            lambda content: "PDF text",
        ):
            extracted = await extract_source(
                result("sr_pdf", "https://example.com/a.pdf"),
                budget=SourceExtractionBudget(),
                client_factory=client_factory_for(handler),
            )

        self.assertEqual(extracted.content_type, "pdf")
        self.assertEqual(extracted.cleaned_text, "PDF text")

        with patch("app.utils.url_safety.socket.getaddrinfo", fake_public_getaddrinfo), patch(
            "app.utils.source_extraction.extract_pdf_text",
            side_effect=RuntimeError("bad pdf"),
        ):
            failed = await extract_source(
                result("sr_pdf", "https://example.com/a.pdf"),
                budget=SourceExtractionBudget(),
                client_factory=client_factory_for(handler),
            )

        self.assertEqual(failed.extraction_status, "failed")
        self.assertTrue(failed.snippet_fallback_used)

    async def test_failure_modes_and_concurrency_survival(self):
        def handler(request):
            if str(request.url).endswith("/timeout"):
                raise httpx.TimeoutException("timeout")
            if str(request.url).endswith("/500"):
                return httpx.Response(500, text="error")
            if str(request.url).endswith("/empty"):
                return httpx.Response(200, headers={"content-type": "text/html"}, text="<script>x</script>")
            if str(request.url).endswith("/mime"):
                return httpx.Response(200, headers={"content-type": "image/png"}, content=b"png")
            return httpx.Response(200, headers={"content-type": "text/plain"}, text="ok text")

        results = [
            result("sr_timeout", "https://example.com/timeout"),
            result("sr_500", "https://example.com/500"),
            result("sr_empty", "https://example.com/empty"),
            result("sr_mime", "https://example.com/mime"),
            result("sr_ok", "https://example.com/ok"),
        ]

        with patch("app.utils.url_safety.socket.getaddrinfo", fake_public_getaddrinfo):
            extracted = await extract_selected_sources(
                results,
                [item.result_id for item in results],
                budget=SourceExtractionBudget(),
                client_factory=client_factory_for(handler),
            )

        self.assertEqual(extracted["sr_ok"].extraction_status, "success")
        self.assertEqual(extracted["sr_timeout"].extraction_status, "failed")
        self.assertEqual(extracted["sr_500"].extraction_status, "failed")
        self.assertEqual(extracted["sr_empty"].extraction_status, "failed")
        self.assertEqual(extracted["sr_mime"].extraction_status, "skipped")

    async def test_oversized_pdf_is_rejected(self):
        async def handler(request):
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"x" * 20)

        with patch("app.utils.url_safety.socket.getaddrinfo", fake_public_getaddrinfo):
            extracted = await extract_source(
                result("sr_pdf", "https://example.com/a.pdf"),
                budget=SourceExtractionBudget(max_pdf_bytes=5),
                client_factory=client_factory_for(handler),
            )

        self.assertEqual(extracted.extraction_status, "failed")
        self.assertTrue(extracted.snippet_fallback_used)


class SynthesisFormattingTests(unittest.TestCase):
    def test_extracted_and_fallback_content_are_labelled_and_bounded(self):
        results = [
            result("sr_1", "https://example.com/a", snippet="raw <html> snippet"),
            result("sr_2", "https://example.com/b", snippet="snippet two"),
        ]
        extracted = {
            "sr_1": ExtractedSource(
                result_id="sr_1",
                title="a",
                url="https://example.com/a",
                content_type="html",
                extraction_status="success",
                cleaned_text="clean extracted text",
                char_count=20,
                truncated=False,
                snippet_fallback_used=False,
            )
        }

        formatted = format_sources_for_synthesis(
            results,
            extracted,
            budget=SourceExtractionBudget(max_total_cleaned_chars=25),
        )

        self.assertEqual(formatted[0]["evidence_basis"], "extracted_content")
        self.assertEqual(formatted[1]["evidence_basis"], "snippet_only")
        self.assertIn("extraction_status", formatted[0])
        self.assertNotIn("<html>", formatted[0]["text"])
        self.assertLessEqual(sum(len(item["text"]) for item in formatted), 25)


class FakeResearchUtils:
    def __init__(self):
        self.search_calls = []

    async def generate_research_plan(self, user_query):
        return ResearchPlan(
            topic="topic",
            research_depth="detailed",
            research_areas=["area"],
            search_queries=["initial query"],
        )

    async def execute_search_queries(self, queries, depth):
        self.search_calls.append(list(queries))
        if queries == ["initial query"]:
            return [result("sr_initial", "https://arxiv.org/html/1", source_type="primary_research", domain="arxiv.org", query="initial query")]
        return [result("sr_follow", "https://example.com/follow", source_type="official", domain="example.com", query=queries[0])]


class FakeSynthesisChain:
    def __init__(self):
        self.payloads = []

    async def ainvoke(self, payload):
        self.payloads.append(payload)
        result_id = payload["raw_search_results"][-1]["result_id"]
        gaps = []
        if len(self.payloads) == 1:
            gaps = [
                ResearchGap(
                    gap_id="gap_1",
                    description="gap",
                    priority="high",
                    researchable=True,
                    follow_up_queries=["follow query"],
                )
            ]
        return StructuredSynthesisOutput(
            executive_summary="summary",
            facts=[
                EvidenceBackedFact(
                    fact_id="fact_1",
                    statement="Supported fact.",
                    evidence_result_ids=[result_id],
                    confidence=0.7,
                )
            ],
            research_gaps=gaps,
        )


async def noop_event(*args, **kwargs):
    return None


class ResearchAgentPhaseDIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_extraction_happens_before_each_synthesis_and_respects_budget(self):
        calls = []

        async def fake_extract(search_results, selected_result_ids, *, budget):
            calls.append(("extract", list(selected_result_ids)))
            return {
                result_id: ExtractedSource(
                    result_id=result_id,
                    title=result_id,
                    url="https://example.com",
                    content_type="html",
                    extraction_status="success",
                    cleaned_text=f"extracted {result_id}",
                    char_count=20,
                    truncated=False,
                    snippet_fallback_used=False,
                )
                for result_id in selected_result_ids
            }

        agent = ResearchAgent.__new__(ResearchAgent)
        agent.research_utils = FakeResearchUtils()
        agent._chain = FakeSynthesisChain()

        with patch("builtins.open", mock_open()), patch("app.agents.researcher.adispatch_custom_event", noop_event), patch(
            "app.agents.researcher.extract_selected_sources",
            fake_extract,
        ), patch("app.agents.researcher.setting.SOURCE_EXTRACTION_MAX_SELECTED_SOURCES_TOTAL", 2), patch(
            "app.agents.researcher.setting.SOURCE_EXTRACTION_MAX_NEW_SOURCES_AFTER_FOLLOW_UP",
            1,
        ):
            update = await agent.research({"user_query": "research"})

        self.assertEqual(agent.research_utils.search_calls, [["initial query"], ["follow query"]])
        self.assertEqual(len(agent._chain.payloads), 2)
        self.assertEqual(calls[0], ("extract", ["sr_initial"]))
        self.assertEqual(calls[1], ("extract", ["sr_follow"]))
        self.assertIn("extracted sr_initial", agent._chain.payloads[0]["source_evidence_content"][0]["text"])
        self.assertIn("extracted sr_follow", agent._chain.payloads[1]["source_evidence_content"][-1]["text"])
        self.assertEqual(update["research"].selected_source_ids, ["sr_initial", "sr_follow"])
        self.assertEqual(update["last_agent"], "researcher")


if __name__ == "__main__":
    unittest.main()
