import unittest
from unittest.mock import mock_open, patch

from langchain_core.messages import AIMessage
from langgraph.graph import END

from app.agents.observer import ObserverAgent
from app.agents.supervisr import SupervisorAgent
from app.agents.utilities.research_utilities import ResearchUtilities
from app.models.agents_schemas.research_package_schema import (
    EvidenceBackedFact,
    ResearchGap,
    StructuredSynthesisOutput,
)
from app.models.agents_schemas.search_result_schema import SearchResult
from app.models.agents_schemas.supervisor_schema import SupervisorResponse
from app.agents.graph.state import WorkflowPlan
from app.utils.evidence_normalization import (
    build_normalized_result_fields,
    classify_source_type,
    deduplicate_result_dicts,
)
from app.utils.research_package_validation import (
    ResearchPackageValidationError,
    assemble_research_package,
)


class EventRecorder:
    def __init__(self):
        self.events = []

    async def __call__(self, name, data):
        self.events.append((name, data))


class FakeSupervisorChain:
    async def ainvoke(self, payload):
        return SupervisorResponse(
            user_visible_message="I will research and write this.",
            intent="report_generation",
            workflow="research_to_report",
            start_node="researcher",
            requires_research=True,
            requires_writing=True,
            requires_observation=False,
            artifact_type="report",
            route_reason="Research-heavy report.",
            confidence=0.93,
        )


class FakeObserverChain:
    async def ainvoke(self, payload):
        class Result:
            def model_dump(self):
                return {
                    "passed": True,
                    "reason": "ok",
                    "missing_requirements": [],
                    "next_agent": "end",
                }

        return Result()


class FakeSearchTool:
    async def ainvoke(self, payload):
        query = payload["user_query"]
        return {
            "results": [
                {
                    "title": f"{query} result 1",
                    "url": f"https://www.reuters.com/{query}/story?utm_source=x",
                    "content": "snippet",
                    "score": 0.8,
                },
                {
                    "title": f"{query} result 2",
                    "url": f"https://www.reuters.com/{query}/story",
                    "content": "duplicate",
                    "score": 0.9,
                },
            ]
        }


class PhaseB1HardeningTests(unittest.IsolatedAsyncioTestCase):
    async def test_supervisor_streams_validated_workflow_plan(self):
        agent = SupervisorAgent.__new__(SupervisorAgent)
        agent._chain = FakeSupervisorChain()
        recorder = EventRecorder()

        with patch("app.agents.supervisr.adispatch_custom_event", recorder), patch("builtins.open", mock_open()):
            result = await agent.supervise(
                {
                    "user_query": "Research the latest developments in agentic RAG systems.",
                    "workflow_plan": WorkflowPlan(mode="extended"),
                }
            )

        plan = result.update["workflow_plan"]
        self.assertTrue(plan.requires_research)
        self.assertTrue(plan.requires_writing)
        self.assertIn("researcher", plan.execution_path)
        self.assertIn("presentation", plan.execution_path)
        self.assertNotIn("writer", plan.execution_path)
        self.assertEqual(recorder.events[0][0], "workflow_plan")
        streamed_plan = recorder.events[0][1]["workflow_plan"]
        self.assertTrue(streamed_plan["requires_research"])
        self.assertTrue(streamed_plan["requires_writing"])
        self.assertIn("researcher", streamed_plan["execution_path"])
        self.assertIn("presentation", streamed_plan["execution_path"])

    async def test_observer_preserves_existing_workflow_plan(self):
        agent = ObserverAgent.__new__(ObserverAgent)
        agent._chain = FakeObserverChain()
        plan = WorkflowPlan(
            intent="report_generation",
            requires_research=True,
            requires_writing=True,
            execution_path=["researcher", "presentation", END],
        )

        result = await agent.observe(
            {
                "user_query": "query",
                "workflow_plan": plan,
                "writing": {"draft_report": "done"},
            }
        )

        self.assertTrue(result["workflow_plan"].requires_research)
        self.assertTrue(result["workflow_plan"].requires_writing)
        self.assertEqual(result["workflow_plan"].execution_path, ["researcher", "presentation", END])
        self.assertEqual(result["workflow_plan"].status, "observed")

    async def test_search_event_counts_for_mocked_tavily_results(self):
        utilities = ResearchUtilities(llm=None, prompt_manager=None)
        recorder = EventRecorder()

        with patch("app.agents.utilities.research_utilities.web_search_tool", FakeSearchTool()), patch(
            "app.agents.utilities.research_utilities.adispatch_custom_event",
            recorder,
        ):
            results = await utilities.execute_search_queries(["alpha", "beta"], "detailed")

        names = [name for name, _ in recorder.events]
        self.assertEqual(names.count("search_query_started"), 2)
        self.assertEqual(names.count("search_query_completed"), 2)
        self.assertEqual(names.count("search_result_found"), 2)
        self.assertEqual(len(results), 2)

    def test_compact_package_event_payload_shape(self):
        from app.agents.researcher import ResearchAgent

        agent = ResearchAgent.__new__(ResearchAgent)
        synthesis = StructuredSynthesisOutput(
            executive_summary="summary",
            facts=[
                EvidenceBackedFact(
                    fact_id="f1",
                    statement="fact",
                    evidence_result_ids=["sr_1"],
                    confidence=0.7,
                )
            ],
            missing_information=["missing"],
            research_gaps=[
                ResearchGap(
                    gap_id="g1",
                    description="gap",
                    priority="high",
                    researchable=True,
                    follow_up_queries=["specific gap query"],
                )
            ],
            follow_up_queries=["specific gap query"],
        )

        summary = agent._synthesis_summary(synthesis, canonical_sources=3)

        self.assertEqual(summary["facts"], 1)
        self.assertEqual(summary["research_gaps"], 1)
        self.assertEqual(summary["follow_up_queries"], 1)
        self.assertEqual(summary["canonical_sources"], 3)


class SourceTypeAndEvidenceTests(unittest.TestCase):
    def test_source_type_classification(self):
        self.assertEqual(classify_source_type("arxiv.org"), "primary_research")
        self.assertEqual(classify_source_type("aclanthology.org"), "primary_research")
        self.assertEqual(classify_source_type("medium.com"), "community")
        self.assertEqual(classify_source_type("linkedin.com"), "community")
        self.assertEqual(classify_source_type("youtube.com"), "social")
        self.assertEqual(classify_source_type("dev.to"), "community")

    def test_strong_fact_with_primary_evidence_passes(self):
        source = SearchResult(result_id="sr_1", domain="arxiv.org", source_type="primary_research")
        output = StructuredSynthesisOutput(
            executive_summary="summary",
            facts=[
                EvidenceBackedFact(
                    fact_id="f1",
                    statement="The paper proposes a memory architecture.",
                    evidence_result_ids=["sr_1"],
                    confidence=0.9,
                    evidence_strength="strong",
                )
            ],
        )

        package = assemble_research_package(output, [source])

        self.assertIn("sr_1", package.source_index)

    def test_strong_fact_supported_only_by_medium_is_downgraded(self):
        source = SearchResult(result_id="sr_1", domain="medium.com", source_type="community")
        output = StructuredSynthesisOutput(
            executive_summary="summary",
            facts=[
                EvidenceBackedFact(
                    fact_id="f1",
                    statement="A community claim.",
                    evidence_result_ids=["sr_1"],
                    confidence=0.7,
                    evidence_strength="strong",
                )
            ],
        )

        package = assemble_research_package(output, [source])

        fact = package.facts[0]
        self.assertEqual(fact.evidence_strength, "weak")
        self.assertLessEqual(fact.confidence, 0.6)
        self.assertIn("weak source types", " ".join(fact.evidence_limitations))

    def test_numerical_benchmark_claim_without_primary_or_vendor_limitation_is_downgraded(self):
        source = SearchResult(result_id="sr_1", domain="medium.com", source_type="community")
        output = StructuredSynthesisOutput(
            executive_summary="summary",
            facts=[
                EvidenceBackedFact(
                    fact_id="f1",
                    statement="The system scored 92% on the benchmark.",
                    evidence_result_ids=["sr_1"],
                    confidence=0.6,
                    evidence_strength="weak",
                )
            ],
        )

        package = assemble_research_package(output, [source])

        fact = package.facts[0]
        self.assertEqual(fact.evidence_strength, "weak")
        self.assertLessEqual(fact.confidence, 0.6)
        self.assertIn("numerical benchmark claim lacks primary evidence", " ".join(fact.evidence_limitations))

    def test_vendor_reported_numerical_claim_with_limitation_passes(self):
        source = SearchResult(result_id="sr_1", domain="openai.com", source_type="vendor")
        output = StructuredSynthesisOutput(
            executive_summary="summary",
            facts=[
                EvidenceBackedFact(
                    fact_id="f1",
                    statement="The system scored 92% on the benchmark.",
                    evidence_result_ids=["sr_1"],
                    confidence=0.6,
                    evidence_strength="moderate",
                    evidence_limitations=["vendor-reported result"],
                )
            ],
        )

        package = assemble_research_package(output, [source])

        self.assertIn("sr_1", package.source_index)

    def test_weak_sources_remain_available_in_source_index(self):
        source = SearchResult(result_id="sr_1", domain="medium.com", source_type="community")
        output = StructuredSynthesisOutput(
            executive_summary="summary",
            facts=[
                EvidenceBackedFact(
                    fact_id="f1",
                    statement="A cautiously stated community observation.",
                    evidence_result_ids=["sr_1"],
                    confidence=0.5,
                    evidence_strength="weak",
                )
            ],
        )

        package = assemble_research_package(output, [source])

        self.assertEqual(package.source_index["sr_1"].source_type, "community")

    def test_high_confidence_weak_source_fact_is_downgraded(self):
        source = SearchResult(result_id="sr_1", domain="medium.com", source_type="community")
        output = StructuredSynthesisOutput(
            executive_summary="summary",
            facts=[
                EvidenceBackedFact(
                    fact_id="f1",
                    statement="A high-confidence community observation.",
                    evidence_result_ids=["sr_1"],
                    confidence=0.9,
                    evidence_strength="moderate",
                )
            ],
        )

        package = assemble_research_package(output, [source])

        self.assertEqual(package.facts[0].confidence, 0.5)
        self.assertEqual(package.facts[0].evidence_strength, "weak")
        self.assertTrue(package.facts[0].evidence_limitations)

    def test_high_priority_researchable_gap_requires_follow_up_query(self):
        source = SearchResult(result_id="sr_1", domain="bls.gov", source_type="official")
        output = StructuredSynthesisOutput(
            executive_summary="summary",
            facts=[
                EvidenceBackedFact(
                    fact_id="f1",
                    statement="Supported fact.",
                    evidence_result_ids=["sr_1"],
                    confidence=0.7,
                )
            ],
            research_gaps=[
                ResearchGap(
                    gap_id="g1",
                    description="Needs more evidence.",
                    priority="high",
                    researchable=True,
                    follow_up_queries=[],
                )
            ],
        )

        with self.assertRaises(ResearchPackageValidationError):
            assemble_research_package(output, [source])

    def test_non_researchable_gap_may_have_no_queries(self):
        source = SearchResult(result_id="sr_1", domain="bls.gov", source_type="official")
        output = StructuredSynthesisOutput(
            executive_summary="summary",
            facts=[
                EvidenceBackedFact(
                    fact_id="f1",
                    statement="Supported fact.",
                    evidence_result_ids=["sr_1"],
                    confidence=0.7,
                )
            ],
            research_gaps=[
                ResearchGap(
                    gap_id="g1",
                    description="Private data unavailable.",
                    priority="high",
                    researchable=False,
                    follow_up_queries=[],
                )
            ],
        )

        package = assemble_research_package(output, [source])

        self.assertEqual(package.research_gaps[0].gap_id, "g1")

    def test_arxiv_versions_and_pdf_html_variants_are_grouped(self):
        first = build_normalized_result_fields(
            query="q1",
            title="Paper v3",
            url="https://arxiv.org/pdf/2401.12345v3.pdf",
            snippet="v3",
        )
        second = build_normalized_result_fields(
            query="q2",
            title="Paper v4",
            url="https://arxiv.org/html/2401.12345v4",
            snippet="v4",
        )

        deduped = deduplicate_result_dicts([first, second])

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["scholarly_identifier"], "arxiv:2401.12345")
        self.assertEqual(deduped[0]["title"], "Paper v4")
        self.assertEqual(deduped[0]["matched_queries"], ["q1", "q2"])


if __name__ == "__main__":
    unittest.main()
