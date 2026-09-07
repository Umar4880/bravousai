import unittest
from unittest.mock import mock_open, patch

from app.agents.researcher import ResearchAgent
from app.agents.utilities.research_utilities import ResearchUtilities
from app.agents.writer import WriterAgent
from app.models.agents_schemas.research_package_schema import (
    EvidenceBackedFact,
    ResearchTheme,
    StructuredSynthesisOutput,
)
from app.models.agents_schemas.research_plan_schema import ResearchPlan
from app.models.agents_schemas.search_result_schema import SearchResult
from app.utils.research_package_validation import assemble_research_package


async def noop_event(*args, **kwargs):
    return None


async def fake_extract_selected_sources(search_results, selected_result_ids, *, budget):
    return {}


class FakeSearchTool:
    async def ainvoke(self, payload):
        query = payload["user_query"]
        if query == "jobs":
            return {
                "results": [
                    {
                        "title": "Reuters jobs duplicate",
                        "url": "https://www.reuters.com/markets/us/jobs-report?utm_source=x&gclid=abc#section",
                        "content": "Reuters duplicate with tracking.",
                        "score": 0.9,
                        "published_date": "2026-06-01",
                    },
                    {
                        "title": "BLS jobs",
                        "url": "https://www.bls.gov/news.release/empsit.nr0.htm",
                        "content": "Official BLS data.",
                        "score": 0.95,
                        "published_date": "2026-06-06",
                    },
                    {
                        "title": "CNBC markets",
                        "url": "https://www.cnbc.com/2026/06/06/jobs-market.html",
                        "content": "Reputable market coverage.",
                        "score": 0.8,
                        "published_date": "2026-06-05",
                    },
                    {
                        "title": "Low quality post",
                        "url": "https://www.reddit.com/r/economy/comments/example",
                        "content": "Penalized domain.",
                        "score": 0.7,
                    },
                    {
                        "title": "Fresh FT",
                        "url": "https://www.ft.com/content/fresh-report",
                        "content": "Fresh FT coverage.",
                        "score": 0.85,
                        "published_date": "2026-06-06",
                    },
                    {
                        "title": "Old Reuters",
                        "url": "https://www.reuters.com/markets/us/old-report",
                        "content": "Old Reuters coverage.",
                        "score": 0.6,
                        "published_date": "2020-01-01",
                    },
                    {
                        "title": "Trading Economics no date",
                        "url": "https://tradingeconomics.com/united-states/unemployment-rate",
                        "content": "No publication date.",
                        "score": 0.75,
                    },
                ]
            }
        return {
            "results": [
                {
                    "title": "Reuters jobs clean duplicate",
                    "url": "https://www.reuters.com/markets/us/jobs-report",
                    "content": "Reuters duplicate without tracking.",
                    "score": 0.92,
                    "published_date": "2026-06-02",
                }
            ]
        }


class FakeResearchUtils:
    def __init__(self, search_results):
        self.search_results = search_results

    async def generate_research_plan(self, user_query):
        return ResearchPlan(
            topic="Jobs",
            research_depth="detailed",
            research_areas=["labor market"],
            search_queries=["jobs"],
        )

    async def execute_search_queries(self, search_queries, depth):
        return self.search_results


class FakeSynthesisChain:
    def __init__(self):
        self.payload = None

    async def ainvoke(self, payload):
        self.payload = payload
        result_id = payload["raw_search_results"][0]["result_id"]
        return StructuredSynthesisOutput(
            executive_summary="Evidence summary.",
            facts=[
                EvidenceBackedFact(
                    fact_id="fact_1",
                    statement="A sourced labor-market fact.",
                    evidence_result_ids=[result_id],
                    confidence=0.9,
                )
            ],
            themes=[
                ResearchTheme(
                    theme_id="theme_1",
                    title="Labor market",
                    summary="Theme summary.",
                    fact_ids=["fact_1"],
                    interpretation_ids=[],
                    scenario_ids=[],
                )
            ],
            writer_instructions=["Write a grounded report."],
        )


class FakeWriterChain:
    def __init__(self, result_id):
        self.result_id = result_id
        self.payload = None

    async def ainvoke(self, payload):
        self.payload = payload

        class Result:
            content = ""

        result = Result()
        result.content = f"# Report\n\nA sourced claim. [[cite:{self.result_id}]]"
        return result


class PhaseBIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_phase_a_search_execution_normalizes_scores_and_deduplicates(self):
        utilities = ResearchUtilities(llm=None, prompt_manager=None)

        with patch("app.agents.utilities.research_utilities.web_search_tool", FakeSearchTool()), patch(
            "app.agents.utilities.research_utilities.adispatch_custom_event",
            noop_event,
        ):
            results = await utilities.execute_search_queries(["jobs", "markets"], "detailed")

        self.assertEqual(len(results), 7)
        self.assertTrue(all(isinstance(result, SearchResult) for result in results))
        self.assertTrue(all(result.normalized_url for result in results))
        self.assertTrue(all(result.result_id for result in results))

        duplicate = next(result for result in results if "jobs-report" in result.normalized_url)
        self.assertEqual(duplicate.matched_queries, ["jobs", "markets"])

        bls = next(result for result in results if result.domain == "bls.gov")
        cnbc = next(result for result in results if result.domain == "cnbc.com")
        reddit = next(result for result in results if result.domain == "reddit.com")
        fresh_ft = next(result for result in results if result.domain == "ft.com")
        old_reuters = next(result for result in results if "old-report" in result.normalized_url)
        no_date = next(result for result in results if result.domain == "tradingeconomics.com")

        self.assertGreater(bls.source_quality_score, cnbc.source_quality_score)
        self.assertGreater(cnbc.source_quality_score, reddit.source_quality_score)
        self.assertGreater(fresh_ft.freshness_score, old_reuters.freshness_score)
        self.assertEqual(no_date.freshness_score, 0.45)

    async def test_research_to_writer_flow_uses_package_and_valid_citations(self):
        search_result = SearchResult(
            result_id="sr_valid",
            query="jobs",
            title="BLS jobs",
            url="https://www.bls.gov/news.release/empsit.nr0.htm",
            normalized_url="https://www.bls.gov/news.release/empsit.nr0.htm",
            domain="bls.gov",
            snippet="Official BLS data supports a sourced labor-market fact.",
            source_quality_score=1.0,
            freshness_score=1.0,
        )

        research_agent = ResearchAgent.__new__(ResearchAgent)
        research_agent.research_utils = FakeResearchUtils([search_result])
        research_agent._chain = FakeSynthesisChain()

        with patch("app.agents.researcher.adispatch_custom_event", noop_event), patch(
            "builtins.open",
            mock_open(),
        ), patch("app.agents.researcher.extract_selected_sources", fake_extract_selected_sources):
            research_update = await research_agent.research({"user_query": "write a jobs report"})
        research_state = research_update["research"]

        self.assertIsNotNone(research_state.research_package)
        self.assertIn("sr_valid", research_state.research_package.source_index)
        self.assertIn("Research Package", research_state.researched_content)
        self.assertEqual(
            research_agent._chain.payload["raw_search_results"][0]["normalized_url"],
            "https://www.bls.gov/news.release/empsit.nr0.htm",
        )
        self.assertEqual(
            research_agent._chain.payload["source_evidence_content"][0]["evidence_basis"],
            "snippet_only",
        )

        writer = WriterAgent.__new__(WriterAgent)
        writer._chain = FakeWriterChain("sr_valid")

        with patch("builtins.open", mock_open()):
            writer_update = await writer.write(
                {
                    "user_query": "write a jobs report",
                    "workflow_plan": {},
                    "research": research_state,
                    "writing": {},
                }
            )

        self.assertIn("[[cite:sr_valid]]", writer_update["writing"].draft_report)
        self.assertIn("source_index", writer._chain.payload)
        self.assertIn("sr_valid", writer._chain.payload["source_index"])


if __name__ == "__main__":
    unittest.main()
