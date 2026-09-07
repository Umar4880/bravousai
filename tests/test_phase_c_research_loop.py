import unittest
from unittest.mock import mock_open, patch
import asyncio

from app.agents.researcher import ResearchAgent
from app.agents.writer import WriterAgent
from app.models.agents_schemas.research_loop_schema import ResearchLoopBudget
from app.models.agents_schemas.research_package_schema import (
    EvidenceBackedFact,
    ResearchGap,
    ResearchTheme,
    StructuredSynthesisOutput,
)
from app.models.agents_schemas.research_plan_schema import ResearchPlan
from app.models.agents_schemas.search_result_schema import SearchResult
from app.utils.research_loop import (
    decide_research_loop,
    derive_follow_up_queries_from_gaps,
    merge_search_results,
)
from app.utils.research_package_validation import assemble_research_package


async def noop_event(*args, **kwargs):
    return None


async def slow_event(*args, **kwargs):
    await asyncio.sleep(1)


async def fake_extract_selected_sources(search_results, selected_result_ids, *, budget):
    return {}


def gap(gap_id, priority, queries, researchable=True):
    return ResearchGap(
        gap_id=gap_id,
        description=f"{gap_id} description",
        priority=priority,
        researchable=researchable,
        follow_up_queries=queries,
    )


def result(result_id, url, query="q", source_type="official"):
    return SearchResult(
        result_id=result_id,
        query=query,
        matched_queries=[query],
        title=result_id,
        url=url,
        normalized_url=url,
        domain=url.split("/")[2],
        source_type=source_type,
        snippet=(
            "Supported fact. Vendor-reported benchmark improved by 10%. "
            "This source contains claim-level evidence for the test report."
        ),
    )


def synthesis_with_gap(result_id="sr_1", gaps=None):
    return StructuredSynthesisOutput(
        executive_summary="summary",
        facts=[
            EvidenceBackedFact(
                fact_id="fact_1",
                statement="Supported fact.",
                evidence_result_ids=[result_id],
                confidence=0.7,
                evidence_strength="moderate",
            )
        ],
        themes=[
            ResearchTheme(
                theme_id="theme_1",
                title="Theme",
                summary="Theme summary",
                fact_ids=["fact_1"],
                interpretation_ids=[],
                scenario_ids=[],
            )
        ],
        research_gaps=gaps or [],
    )


class QueryDerivationAndDecisionTests(unittest.TestCase):
    def test_structured_gaps_flatten_deterministically_by_priority(self):
        queries = derive_follow_up_queries_from_gaps(
            [
                gap("low", "low", [" low query "]),
                gap("high", "high", ["High query", ""]),
                gap("medium", "medium", ["Medium query", "HIGH QUERY"]),
            ]
        )

        self.assertEqual(queries, ["High query", "Medium query", "low query"])

    def test_decision_rejects_already_executed_queries(self):
        package = assemble_research_package(
            synthesis_with_gap(gaps=[gap("g1", "high", ["already searched", "new query"])]),
            [result("sr_1", "https://bls.gov/a")],
        )

        decision = decide_research_loop(
            package,
            executed_queries=["Already Searched"],
            follow_up_iteration=0,
            budget=ResearchLoopBudget(),
        )

        self.assertTrue(decision.should_continue)
        self.assertEqual(decision.approved_queries, ["new query"])
        self.assertEqual(decision.rejected_queries, ["already searched"])

    def test_default_budget_approves_no_more_than_three_queries(self):
        package = assemble_research_package(
            synthesis_with_gap(gaps=[gap("g1", "high", ["q1", "q2", "q3", "q4"])]),
            [result("sr_1", "https://bls.gov/a")],
        )

        decision = decide_research_loop(
            package,
            executed_queries=[],
            follow_up_iteration=0,
            budget=ResearchLoopBudget(),
        )

        self.assertEqual(decision.approved_queries, ["q1", "q2", "q3"])
        self.assertEqual(decision.rejected_queries, ["q4"])

    def test_iteration_budget_stops_loop(self):
        package = assemble_research_package(
            synthesis_with_gap(gaps=[gap("g1", "high", ["q1"])]),
            [result("sr_1", "https://bls.gov/a")],
        )

        decision = decide_research_loop(
            package,
            executed_queries=[],
            follow_up_iteration=1,
            budget=ResearchLoopBudget(max_follow_up_iterations=1),
        )

        self.assertFalse(decision.should_continue)
        self.assertEqual(decision.stop_reason, "iteration_limit_reached")

    def test_no_gap_behavior(self):
        package = assemble_research_package(
            synthesis_with_gap(gaps=[]),
            [result("sr_1", "https://bls.gov/a")],
        )

        decision = decide_research_loop(
            package,
            executed_queries=[],
            follow_up_iteration=0,
            budget=ResearchLoopBudget(),
        )

        self.assertFalse(decision.should_continue)
        self.assertEqual(decision.stop_reason, "no_researchable_gaps")


class EvidenceMergeTests(unittest.TestCase):
    def test_merge_preserves_duplicate_and_adds_new_result(self):
        initial = [result("sr_initial", "https://example.com/a", query="initial")]
        follow_up = [
            result("sr_duplicate", "https://example.com/a", query="follow duplicate"),
            result("sr_new", "https://example.com/b", query="follow new"),
        ]

        merged, added, duplicates = merge_search_results(initial, follow_up, follow_up_iteration=1)

        self.assertEqual(len(merged), 2)
        self.assertEqual(added, 1)
        self.assertEqual(duplicates, 1)
        self.assertEqual(merged[0].result_id, "sr_initial")
        self.assertEqual(merged[0].matched_queries, ["initial", "follow duplicate"])
        self.assertEqual(merged[1].first_seen_iteration, 1)


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
            return [result("sr_initial", "https://bls.gov/initial", query="initial query")]
        return [result("sr_follow", "https://bls.gov/follow", query=queries[0])]


class FakeSynthesisChain:
    def __init__(self, always_gap=False):
        self.calls = 0
        self.always_gap = always_gap

    async def ainvoke(self, payload):
        self.calls += 1
        result_id = payload["raw_search_results"][-1]["result_id"]
        if self.calls == 1 or self.always_gap:
            gaps = [gap("gap_1", "high", ["follow query"])]
        else:
            gaps = []
        return synthesis_with_gap(result_id=result_id, gaps=gaps)


class SlowSynthesisChain:
    async def ainvoke(self, payload):
        await asyncio.sleep(1)


class FakeWriterChain:
    def __init__(self, citation_id="sr_follow"):
        self.calls = 0
        self.payload = None
        self.citation_id = citation_id

    async def ainvoke(self, payload):
        self.calls += 1
        self.payload = payload

        class Response:
            content = ""

        Response.content = f"Supported claim. [[cite:{self.citation_id}]]"
        return Response()


class SlowWriterChain:
    async def ainvoke(self, payload):
        await asyncio.sleep(1)


class PhaseCIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_iteration_integration(self):
        agent = ResearchAgent.__new__(ResearchAgent)
        agent.research_utils = FakeResearchUtils()
        agent._chain = FakeSynthesisChain()

        with patch("builtins.open", mock_open()), patch(
            "app.agents.researcher.adispatch_custom_event",
            noop_event,
        ), patch("app.agents.researcher.extract_selected_sources", fake_extract_selected_sources):
            update = await agent.research({"user_query": "research"})

        research_state = update["research"]

        self.assertEqual(agent.research_utils.search_calls, [["initial query"], ["follow query"]])
        self.assertEqual(agent._chain.calls, 2)
        self.assertEqual(len(research_state.raw_search_results), 2)
        self.assertEqual(research_state.iteration_traces[0].canonical_results_added, 1)
        self.assertEqual(research_state.research_package.research_gaps, [])

    async def test_infinite_loop_prevention_stops_after_one_iteration(self):
        researcher = ResearchAgent.__new__(ResearchAgent)
        researcher.research_utils = FakeResearchUtils()
        researcher._chain = FakeSynthesisChain(always_gap=True)

        with patch("builtins.open", mock_open()), patch(
            "app.agents.researcher.adispatch_custom_event",
            noop_event,
        ), patch("app.agents.researcher.extract_selected_sources", fake_extract_selected_sources):
            research_update = await researcher.research({"user_query": "research"})

        writer = WriterAgent.__new__(WriterAgent)
        writer._chain = FakeWriterChain()

        with patch("builtins.open", mock_open()):
            writer_update = await writer.write(
                {
                    "user_query": "research",
                    "workflow_plan": {},
                    "research": research_update["research"],
                    "writing": {},
                }
            )

        self.assertEqual(researcher._chain.calls, 2)
        self.assertEqual(research_update["research"].iteration_traces[0].stop_reason, "iteration_limit_reached")
        self.assertEqual(writer._chain.calls, 1)
        self.assertIn("[[cite:sr_follow]]", writer_update["writing"].draft_report)

    async def test_writer_context_includes_limitations_strength_and_source_type(self):
        package = assemble_research_package(
            StructuredSynthesisOutput(
                executive_summary="summary",
                facts=[
                    EvidenceBackedFact(
                        fact_id="fact_1",
                        statement="Vendor-reported benchmark improved by 10%.",
                        evidence_result_ids=["sr_vendor"],
                        confidence=0.6,
                        evidence_strength="moderate",
                        evidence_limitations=["vendor-reported result"],
                    )
                ],
            ),
            [result("sr_vendor", "https://openai.com/report", source_type="vendor")],
        )
        writer = WriterAgent.__new__(WriterAgent)
        writer._chain = FakeWriterChain(citation_id="sr_vendor")

        with patch("builtins.open", mock_open()):
            await writer.write(
                {
                    "user_query": "write",
                    "workflow_plan": {},
                    "research": {"research_package": package},
                    "writing": {},
                }
            )

        payload = writer._chain.payload
        self.assertIn("evidence_strength", str(payload["research_package"]))
        self.assertIn("evidence_limitations", str(payload["research_package"]))
        self.assertNotIn("source_index", payload["research_package"])
        self.assertIn("source_type", payload["source_index"])
        self.assertIn("vendor-reported result", payload["research_findings"])

    async def test_writer_repairs_invalid_citation_placeholders(self):
        package = assemble_research_package(
            StructuredSynthesisOutput(
                executive_summary="summary",
                facts=[
                    EvidenceBackedFact(
                        fact_id="fact_1",
                        statement="Supported fact.",
                        evidence_result_ids=["sr_vendor"],
                        confidence=0.6,
                    )
                ],
            ),
            [result("sr_vendor", "https://openai.com/report", source_type="vendor")],
        )
        writer = WriterAgent.__new__(WriterAgent)
        writer._chain = FakeWriterChain(citation_id="sr_xxxx")

        with patch("builtins.open", mock_open()):
            update = await writer.write(
                {
                    "user_query": "write",
                    "workflow_plan": {},
                    "research": {"research_package": package},
                    "writing": {},
                }
            )

        self.assertNotIn("[[cite:sr_xxxx]]", update["writing"].draft_report)
        self.assertTrue(update["writing"].is_complete)

    async def test_writer_removes_valid_but_ungrounded_citation(self):
        ungrounded_source = result("sr_vendor", "https://openai.com/report", source_type="vendor")
        ungrounded_source.snippet = "This source is about a different topic."
        package = assemble_research_package(
            StructuredSynthesisOutput(
                executive_summary="summary",
                facts=[
                    EvidenceBackedFact(
                        fact_id="fact_1",
                        statement="Supported fact.",
                        evidence_result_ids=["sr_vendor"],
                        confidence=0.6,
                    )
                ],
            ),
            [ungrounded_source],
        )
        writer = WriterAgent.__new__(WriterAgent)
        writer._chain = FakeWriterChain(citation_id="sr_vendor")

        with patch("builtins.open", mock_open()):
            update = await writer.write(
                {
                    "user_query": "write",
                    "workflow_plan": {},
                    "research": {"research_package": package},
                    "writing": {},
                }
            )

        self.assertNotIn("[[cite:sr_vendor]]", update["writing"].draft_report)
        self.assertEqual(package.facts[0].grounding_status, "context_only")

    async def test_writer_timeout_returns_package_backed_fallback(self):
        package = assemble_research_package(
            StructuredSynthesisOutput(
                executive_summary="summary",
                facts=[
                    EvidenceBackedFact(
                        fact_id="fact_1",
                        statement="Supported fact.",
                        evidence_result_ids=["sr_vendor"],
                        confidence=0.6,
                    )
                ],
            ),
            [result("sr_vendor", "https://openai.com/report", source_type="vendor")],
        )
        writer = WriterAgent.__new__(WriterAgent)
        writer._chain = SlowWriterChain()

        with patch("builtins.open", mock_open()), patch(
            "app.agents.writer.setting.WRITER_TIMEOUT_SECONDS",
            0.01,
        ):
            update = await writer.write(
                {
                    "user_query": "write",
                    "workflow_plan": {},
                    "research": {"research_package": package},
                    "writing": {},
                }
            )

        draft = update["writing"].draft_report
        self.assertIn("writer LLM did not complete", draft)
        self.assertIn("[[cite:sr_vendor]]", draft)
        self.assertTrue(update["writing"].is_complete)

    async def test_research_event_dispatch_timeout_does_not_block(self):
        agent = ResearchAgent.__new__(ResearchAgent)

        with patch("app.agents.researcher.setting.RESEARCH_EVENT_DISPATCH_TIMEOUT_SECONDS", 0.01), patch(
            "app.agents.researcher.adispatch_custom_event",
            slow_event,
        ):
            await asyncio.wait_for(agent._emit_event("research_phase", {"phase": "test"}), timeout=0.2)

    async def test_synthesis_timeout_raises_with_diagnostics(self):
        agent = ResearchAgent.__new__(ResearchAgent)
        agent._chain = SlowSynthesisChain()

        with patch("app.agents.researcher.setting.RESEARCH_SYNTHESIS_TIMEOUT_SECONDS", 0.01):
            with self.assertRaises(asyncio.TimeoutError):
                await agent._synthesize(
                    "compare rag",
                    ResearchPlan(
                        topic="RAG",
                        research_depth="normal",
                        research_areas=["benchmarks"],
                        search_queries=["rag benchmark"],
                    ),
                    [result("sr_initial", "https://bls.gov/initial", query="rag benchmark")],
                )


if __name__ == "__main__":
    unittest.main()
