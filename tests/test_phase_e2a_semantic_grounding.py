import unittest
from unittest.mock import mock_open, patch

from pydantic import ValidationError

from app.agents.writer import WriterAgent
from app.models.agents_schemas.research_package_schema import (
    ClaimClassification,
    ClaimEvidenceSupport,
    EvidenceBackedFact,
    StructuredSynthesisOutput,
)
from app.models.agents_schemas.search_result_schema import SearchResult
from app.models.agents_schemas.source_extraction_schema import ExtractedSource
from app.utils.research.research_package_validation import assemble_research_package
from app.utils.research.semantic_grounding import (
    build_citation_support_matrix,
    classify_claim_type,
    select_candidate_evidence_notes,
    writer_visible_package,
)


def source(result_id: str, snippet: str, source_type: str = "official") -> SearchResult:
    return SearchResult(
        result_id=result_id,
        query="q",
        matched_queries=["q"],
        title=result_id,
        url=f"https://example.com/{result_id}",
        normalized_url=f"https://example.com/{result_id}",
        domain="example.com",
        source_type=source_type,
        source_quality_score=0.9,
        freshness_score=0.8,
        snippet=snippet,
    )


def extracted(result_id: str, text: str, fallback: bool = False) -> ExtractedSource:
    return ExtractedSource(
        result_id=result_id,
        title=result_id,
        url=f"https://example.com/{result_id}",
        cleaned_text=text,
        char_count=len(text),
        snippet_fallback_used=fallback,
        provider="mock",
        extraction_depth="custom",
        extraction_status="success",
    )


def synthesis(facts: list[EvidenceBackedFact]) -> StructuredSynthesisOutput:
    return StructuredSynthesisOutput(executive_summary="summary", facts=facts)


class FakeVerifier:
    def __init__(self, supports: list[ClaimEvidenceSupport]):
        self.supports = supports
        self.calls = []

    def verify(self, claims: list[dict]) -> list[ClaimEvidenceSupport]:
        self.calls.append(claims)
        return self.supports


class FailingVerifier:
    def verify(self, claims: list[dict]) -> list[ClaimEvidenceSupport]:
        raise RuntimeError("boom")


class FakeWriterChain:
    def __init__(self):
        self.payload = None

    async def ainvoke(self, payload):
        self.payload = payload

        class Response:
            content = "Supported claim. [[cite:sr_supported]] Unsupported claim. [[cite:sr_unsupported]]"

        return Response()


class ClaimClassificationTests(unittest.TestCase):
    def test_descriptive_claim_classified(self):
        self.assertEqual(classify_claim_type("LangGraph supports persistent agent workflows.")[0], "descriptive")

    def test_comparative_claim_classified(self):
        self.assertEqual(classify_claim_type("Model A outperforms Model B.")[0], "comparative")

    def test_causal_claim_classified(self):
        self.assertEqual(classify_claim_type("The outage caused latency to rise.")[0], "causal")

    def test_numerical_benchmark_retains_both_semantics(self):
        primary, secondary = classify_claim_type("Model A scored 55% on SWE-bench.")
        self.assertEqual(primary, "benchmark")
        self.assertIn("numerical", secondary)

    def test_forecast_remains_non_factual(self):
        self.assertEqual(classify_claim_type("Model A will likely improve next year.")[0], "forecast")

    def test_invalid_llm_label_rejected(self):
        with self.assertRaises(ValidationError):
            ClaimClassification(claim_id="fact_1", claim_type="marketing")


class CandidatePrefilterTests(unittest.TestCase):
    def test_top_relevant_notes_selected_and_limited_stably(self):
        fact = EvidenceBackedFact(
            fact_id="fact_1",
            statement="Model A outperforms Model B on SWE-bench.",
            evidence_result_ids=["sr_1", "sr_2", "sr_3", "sr_4"],
            confidence=0.8,
        )
        package = assemble_research_package(
            synthesis([fact]),
            [
                source("sr_1", "Model A outperforms Model B on SWE-bench."),
                source("sr_2", "Model A and Model B were evaluated on SWE-bench."),
                source("sr_3", "Weather conditions changed this week."),
                source("sr_4", "Model B latency improved."),
            ],
        )

        candidates = select_candidate_evidence_notes(package.facts[0], package.evidence_notes, max_candidates=2)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].evidence_note_id, "en_sr_1")
        self.assertNotIn("en_sr_3", [candidate.evidence_note_id for candidate in candidates])


class SemanticVerifierTests(unittest.TestCase):
    def test_exact_partial_contradict_irrelevant_and_insufficient_supports(self):
        facts = [
            EvidenceBackedFact(fact_id="exact", statement="Model A outperforms Model B.", evidence_result_ids=["sr_exact"], confidence=0.9),
            EvidenceBackedFact(fact_id="partial", statement="Model A scored 55% on SWE-bench.", evidence_result_ids=["sr_partial"], confidence=0.9),
            EvidenceBackedFact(fact_id="contra", statement="Model A outperforms Model B.", evidence_result_ids=["sr_contra"], confidence=0.9),
            EvidenceBackedFact(fact_id="irrelevant", statement="Model A reduces latency.", evidence_result_ids=["sr_irrelevant"], confidence=0.9),
            EvidenceBackedFact(fact_id="insufficient", statement="Model A is safer.", evidence_result_ids=["sr_insufficient"], confidence=0.9),
        ]
        supports = [
            ClaimEvidenceSupport(claim_id="exact", evidence_note_id="en_sr_exact", support_status="supports", confidence=0.95, reason="direct"),
            ClaimEvidenceSupport(claim_id="partial", evidence_note_id="en_sr_partial", support_status="partially_supports", confidence=0.7, reason="missing baseline"),
            ClaimEvidenceSupport(claim_id="contra", evidence_note_id="en_sr_contra", support_status="contradicts", confidence=0.8, reason="opposite"),
            ClaimEvidenceSupport(claim_id="irrelevant", evidence_note_id="en_sr_irrelevant", support_status="not_relevant", confidence=0.9, reason="topic only"),
            ClaimEvidenceSupport(claim_id="insufficient", evidence_note_id="en_sr_insufficient", support_status="insufficient", confidence=0.5, reason="thin"),
        ]
        package = assemble_research_package(
            synthesis(facts),
            [
                source("sr_exact", "Model A outperforms Model B."),
                source("sr_partial", "Model A scored 55% on an evaluation."),
                source("sr_contra", "Model B outperforms Model A."),
                source("sr_irrelevant", "Model A and latency are discussed."),
                source("sr_insufficient", "Model A safety was mentioned."),
            ],
            semantic_verifier=FakeVerifier(supports),
        )

        decisions = {item.claim_id: item.grounding_status for item in package.claim_grounding_decisions}
        self.assertEqual(decisions["exact"], "grounded")
        self.assertEqual(decisions["partial"], "partially_grounded")
        self.assertEqual(decisions["contra"], "contradicted")
        self.assertEqual(decisions["irrelevant"], "unsupported")
        self.assertEqual(decisions["insufficient"], "unsupported")

    def test_lexical_overlap_without_semantic_support_is_not_grounded(self):
        fact = EvidenceBackedFact(
            fact_id="fact_1",
            statement="Model A outperforms Model B on SWE-bench.",
            evidence_result_ids=["sr_1"],
            confidence=0.9,
        )
        package = assemble_research_package(
            synthesis([fact]),
            [source("sr_1", "Model A and Model B were both evaluated on SWE-bench.")],
            semantic_verifier=FakeVerifier(
                [
                    ClaimEvidenceSupport(
                        claim_id="fact_1",
                        evidence_note_id="en_sr_1",
                        support_status="not_relevant",
                        confidence=0.8,
                        reason="co-occurrence without comparison",
                    )
                ]
            ),
        )

        self.assertEqual(package.claim_grounding_decisions[0].grounding_status, "unsupported")

    def test_semantic_support_with_limited_lexical_overlap_can_ground(self):
        fact = EvidenceBackedFact(
            fact_id="fact_1",
            statement="The outage caused latency to rise.",
            evidence_result_ids=["sr_1"],
            confidence=0.9,
        )
        package = assemble_research_package(
            synthesis([fact]),
            [source("sr_1", "After the incident, response times increased because queueing delays grew.")],
            semantic_verifier=FakeVerifier(
                [
                    ClaimEvidenceSupport(
                        claim_id="fact_1",
                        evidence_note_id="en_sr_1",
                        support_status="supports",
                        confidence=0.88,
                        reason="causal wording supports the claim",
                    )
                ]
            ),
        )

        self.assertEqual(package.claim_grounding_decisions[0].grounding_status, "grounded")

    def test_unknown_evidence_id_rejected(self):
        fact = EvidenceBackedFact(fact_id="fact_1", statement="Supported fact.", evidence_result_ids=["sr_1"], confidence=0.8)
        with self.assertRaises(ValueError):
            assemble_research_package(
                synthesis([fact]),
                [source("sr_1", "Supported fact.")],
                semantic_verifier=FakeVerifier(
                    [
                        ClaimEvidenceSupport(
                            claim_id="fact_1",
                            evidence_note_id="en_missing",
                            support_status="supports",
                            confidence=0.9,
                            reason="bad",
                        )
                    ]
                ),
            )

    def test_verifier_failure_downgrades_instead_of_grounding(self):
        fact = EvidenceBackedFact(fact_id="fact_1", statement="Supported fact.", evidence_result_ids=["sr_1"], confidence=0.9)
        package = assemble_research_package(
            synthesis([fact]),
            [source("sr_1", "Supported fact.")],
            semantic_verifier=FailingVerifier(),
        )

        self.assertEqual(package.claim_grounding_decisions[0].grounding_status, "unsupported")
        self.assertEqual(package.semantic_verification_trace.semantic_verifier_failures, 1)


class ClaimTypePolicyTests(unittest.TestCase):
    def test_comparative_claim_fails_without_explicit_comparison(self):
        fact = EvidenceBackedFact(
            fact_id="fact_1",
            statement="Model A outperforms Model B.",
            evidence_result_ids=["sr_1"],
            confidence=0.9,
        )
        package = assemble_research_package(
            synthesis([fact]),
            [source("sr_1", "Model A and Model B were both evaluated.")],
            semantic_verifier=FakeVerifier(
                [ClaimEvidenceSupport(claim_id="fact_1", evidence_note_id="en_sr_1", support_status="supports", confidence=0.9, reason="mock")]
            ),
        )

        self.assertEqual(package.claim_grounding_decisions[0].grounding_status, "partially_grounded")

    def test_causal_claim_fails_on_correlation_only(self):
        fact = EvidenceBackedFact(
            fact_id="fact_1",
            statement="The outage caused latency to rise.",
            evidence_result_ids=["sr_1"],
            confidence=0.9,
        )
        package = assemble_research_package(
            synthesis([fact]),
            [source("sr_1", "The outage and latency increase happened in the same hour.")],
            semantic_verifier=FakeVerifier(
                [ClaimEvidenceSupport(claim_id="fact_1", evidence_note_id="en_sr_1", support_status="supports", confidence=0.9, reason="mock")]
            ),
        )

        self.assertEqual(package.claim_grounding_decisions[0].grounding_status, "partially_grounded")

    def test_numerical_claim_downgrades_without_metric_context(self):
        fact = EvidenceBackedFact(fact_id="fact_1", statement="Model A achieved 55%.", evidence_result_ids=["sr_1"], confidence=0.9)
        package = assemble_research_package(
            synthesis([fact]),
            [source("sr_1", "Model A achieved 55.")],
            semantic_verifier=FakeVerifier(
                [ClaimEvidenceSupport(claim_id="fact_1", evidence_note_id="en_sr_1", support_status="supports", confidence=0.9, reason="mock")]
            ),
        )

        self.assertEqual(package.claim_grounding_decisions[0].grounding_status, "partially_grounded")

    def test_benchmark_claim_downgrades_without_dataset_or_baseline(self):
        fact = EvidenceBackedFact(
            fact_id="fact_1",
            statement="Model A scored 55% on SWE-bench.",
            evidence_result_ids=["sr_1"],
            confidence=0.9,
        )
        package = assemble_research_package(
            synthesis([fact]),
            [source("sr_1", "Model A scored 55%.")],
            semantic_verifier=FakeVerifier(
                [ClaimEvidenceSupport(claim_id="fact_1", evidence_note_id="en_sr_1", support_status="supports", confidence=0.9, reason="mock")]
            ),
        )

        self.assertEqual(package.claim_grounding_decisions[0].grounding_status, "partially_grounded")

    def test_snippet_only_cannot_strongly_ground_benchmark(self):
        fact = EvidenceBackedFact(
            fact_id="fact_1",
            statement="Model A scored 55% on SWE-bench.",
            evidence_result_ids=["sr_1"],
            confidence=0.9,
            evidence_strength="strong",
        )
        package = assemble_research_package(
            synthesis([fact]),
            [source("sr_1", "Model A scored 55% on the SWE-bench benchmark metric.")],
            semantic_verifier=FakeVerifier(
                [ClaimEvidenceSupport(claim_id="fact_1", evidence_note_id="en_sr_1", support_status="supports", confidence=0.9, reason="mock")]
            ),
        )

        self.assertEqual(package.claim_grounding_decisions[0].grounding_status, "partially_grounded")


class CitationSupportMatrixTests(unittest.TestCase):
    def test_valid_matrix_builds_and_duplicates_merge(self):
        fact = EvidenceBackedFact(fact_id="fact_1", statement="Supported fact.", evidence_result_ids=["sr_1"], confidence=0.8)
        package = assemble_research_package(synthesis([fact]), [source("sr_1", "Supported fact.")])
        records = build_citation_support_matrix(
            package,
            [
                ClaimEvidenceSupport(claim_id="fact_1", evidence_note_id="en_sr_1", support_status="partially_supports", confidence=0.5, reason="partial"),
                ClaimEvidenceSupport(claim_id="fact_1", evidence_note_id="en_sr_1", support_status="supports", confidence=0.9, reason="direct"),
            ],
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].support_status, "supports")

    def test_unknown_claim_rejected(self):
        fact = EvidenceBackedFact(fact_id="fact_1", statement="Supported fact.", evidence_result_ids=["sr_1"], confidence=0.8)
        package = assemble_research_package(synthesis([fact]), [source("sr_1", "Supported fact.")])
        with self.assertRaises(ValueError):
            build_citation_support_matrix(
                package,
                [ClaimEvidenceSupport(claim_id="missing", evidence_note_id="en_sr_1", support_status="supports", confidence=0.9, reason="bad")],
            )

    def test_support_confidence_validated(self):
        with self.assertRaises(ValidationError):
            ClaimEvidenceSupport(
                claim_id="fact_1",
                evidence_note_id="en_sr_1",
                support_status="supports",
                confidence=2.0,
                reason="bad",
            )

    def test_writer_visible_package_excludes_unsupported(self):
        facts = [
            EvidenceBackedFact(fact_id="supported", statement="Supported fact.", evidence_result_ids=["sr_supported"], confidence=0.9),
            EvidenceBackedFact(fact_id="unsupported", statement="Unsupported fact.", evidence_result_ids=["sr_unsupported"], confidence=0.9),
        ]
        package = assemble_research_package(
            synthesis(facts),
            [source("sr_supported", "Supported fact."), source("sr_unsupported", "Unrelated text.")],
            semantic_verifier=FakeVerifier(
                [
                    ClaimEvidenceSupport(claim_id="supported", evidence_note_id="en_sr_supported", support_status="supports", confidence=0.9, reason="direct"),
                    ClaimEvidenceSupport(claim_id="unsupported", evidence_note_id="en_sr_unsupported", support_status="not_relevant", confidence=0.8, reason="unrelated"),
                ]
            ),
        )

        visible = writer_visible_package(package)

        self.assertEqual([fact.fact_id for fact in visible.facts], ["supported"])


class PhaseE2AIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_semantic_verification_before_writer_and_unsupported_filtered(self):
        facts = [
            EvidenceBackedFact(fact_id="supported", statement="Supported claim.", evidence_result_ids=["sr_supported"], confidence=0.9),
            EvidenceBackedFact(fact_id="partial", statement="Model A scored 55% on SWE-bench.", evidence_result_ids=["sr_partial"], confidence=0.9),
            EvidenceBackedFact(fact_id="contradicted", statement="Model A is faster.", evidence_result_ids=["sr_contra"], confidence=0.9),
            EvidenceBackedFact(fact_id="unsupported", statement="Unsupported claim.", evidence_result_ids=["sr_unsupported"], confidence=0.9),
        ]
        package = assemble_research_package(
            synthesis(facts),
            [
                source("sr_supported", "Supported claim."),
                source("sr_partial", "Model A scored 55% on an evaluation."),
                source("sr_contra", "Model A is slower."),
                source("sr_unsupported", "Different topic."),
            ],
            semantic_verifier=FakeVerifier(
                [
                    ClaimEvidenceSupport(claim_id="supported", evidence_note_id="en_sr_supported", support_status="supports", confidence=0.9, reason="direct"),
                    ClaimEvidenceSupport(claim_id="partial", evidence_note_id="en_sr_partial", support_status="partially_supports", confidence=0.7, reason="missing benchmark context"),
                    ClaimEvidenceSupport(claim_id="contradicted", evidence_note_id="en_sr_contra", support_status="contradicts", confidence=0.8, reason="opposite"),
                    ClaimEvidenceSupport(claim_id="unsupported", evidence_note_id="en_sr_unsupported", support_status="not_relevant", confidence=0.8, reason="unrelated"),
                ]
            ),
        )
        writer = WriterAgent.__new__(WriterAgent)
        writer._chain = FakeWriterChain()

        with patch("builtins.open", mock_open()):
            update = await writer.write(
                {
                    "user_query": "write",
                    "workflow_plan": {},
                    "research": {"research_package": package},
                    "writing": {},
                }
            )

        payload_text = str(writer._chain.payload["research_package"])
        self.assertIn("supported", payload_text)
        self.assertIn("partial", payload_text)
        self.assertIn("contradicted", payload_text)
        self.assertNotIn("'fact_id': 'unsupported'", payload_text)
        self.assertNotIn("sr_unsupported", payload_text)
        self.assertNotIn("[[cite:sr_unsupported]]", update["writing"].draft_report)
        self.assertEqual(package.semantic_verification_trace.claims_verified, 4)
        partial_decision = next(item for item in package.claim_grounding_decisions if item.claim_id == "partial")
        self.assertTrue(partial_decision.limitations)


if __name__ == "__main__":
    unittest.main()
