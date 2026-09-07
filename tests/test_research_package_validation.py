import unittest

from pydantic import ValidationError

from app.models.agents_schemas.research_package_schema import (
    Contradiction,
    EvidenceBackedFact,
    Interpretation,
    ResearchTheme,
    Scenario,
    StructuredSynthesisOutput,
)
from app.models.agents_schemas.search_result_schema import SearchResult
from app.models.agents_schemas.source_extraction_schema import ExtractedSource
from app.utils.research_package_validation import (
    ResearchPackageValidationError,
    assemble_research_package,
)


def source(result_id: str = "sr_1") -> SearchResult:
    return SearchResult(
        result_id=result_id,
        query="q",
        title="Source",
        url=f"https://example.com/{result_id}",
        normalized_url=f"https://example.com/{result_id}",
        domain="bls.gov",
        source_type="official",
        snippet="snippet",
    )


def synthesis(**overrides) -> StructuredSynthesisOutput:
    data = {
        "executive_summary": "Summary",
        "facts": [
            EvidenceBackedFact(
                fact_id="fact_1",
                statement="Supported fact.",
                evidence_result_ids=["sr_1"],
                confidence=0.9,
            )
        ],
        "interpretations": [
            Interpretation(
                interpretation_id="int_1",
                statement="Analysis.",
                based_on_fact_ids=["fact_1"],
                confidence=0.8,
            )
        ],
        "scenarios": [
            Scenario(
                scenario_id="scn_1",
                title="Scenario",
                description="Conditional outcome.",
                conditions=["Condition"],
                implications=["Implication"],
                based_on_fact_ids=["fact_1"],
            )
        ],
        "contradictions": [
            Contradiction(
                contradiction_id="con_1",
                topic="Topic",
                description="Conflicting evidence.",
                evidence_result_ids=["sr_1"],
                resolution_status="unresolved",
            )
        ],
        "themes": [
            ResearchTheme(
                theme_id="theme_1",
                title="Theme",
                summary="Theme summary.",
                fact_ids=["fact_1"],
                interpretation_ids=["int_1"],
                scenario_ids=["scn_1"],
            )
        ],
    }
    data.update(overrides)
    return StructuredSynthesisOutput(**data)


class ResearchPackageValidationTests(unittest.TestCase):
    def test_fact_with_valid_evidence_passes_and_source_index_is_attached(self):
        package = assemble_research_package(synthesis(), [source("sr_1")])

        self.assertIn("sr_1", package.source_index)
        self.assertEqual(package.source_index["sr_1"].url, "https://example.com/sr_1")

    def test_fact_without_evidence_fails_schema_validation(self):
        with self.assertRaises(ValidationError):
            EvidenceBackedFact(
                fact_id="fact_1",
                statement="Unsupported fact.",
                evidence_result_ids=[],
                confidence=0.9,
            )

    def test_invalid_confidence_fails_schema_validation(self):
        with self.assertRaises(ValidationError):
            EvidenceBackedFact(
                fact_id="fact_1",
                statement="Fact.",
                evidence_result_ids=["sr_1"],
                confidence=1.5,
            )

    def test_interpretation_referencing_unknown_fact_is_pruned(self):
        output = synthesis(
            interpretations=[
                Interpretation(
                    interpretation_id="int_1",
                    statement="Analysis.",
                    based_on_fact_ids=["missing_fact"],
                    confidence=0.8,
                )
            ]
        )

        package = assemble_research_package(output, [source("sr_1")])

        self.assertEqual(package.interpretations, [])

    def test_interpretation_source_id_reference_is_mapped_to_citing_fact(self):
        output = synthesis(
            interpretations=[
                Interpretation(
                    interpretation_id="int_1",
                    statement="Analysis.",
                    based_on_fact_ids=["sr_1"],
                    confidence=0.8,
                )
            ]
        )

        package = assemble_research_package(output, [source("sr_1")])

        self.assertEqual(package.interpretations[0].based_on_fact_ids, ["fact_1"])

    def test_scenario_referencing_unknown_fact_is_pruned(self):
        output = synthesis(
            scenarios=[
                Scenario(
                    scenario_id="scn_1",
                    title="Scenario",
                    description="Conditional.",
                    based_on_fact_ids=["missing_fact"],
                )
            ]
        )

        package = assemble_research_package(output, [source("sr_1")])

        self.assertEqual(package.scenarios, [])

    def test_contradiction_referencing_unknown_result_is_pruned(self):
        output = synthesis(
            contradictions=[
                Contradiction(
                    contradiction_id="con_1",
                    topic="Topic",
                    description="Conflict.",
                    evidence_result_ids=["missing_source"],
                    resolution_status="unresolved",
                )
            ]
        )

        package = assemble_research_package(output, [source("sr_1")])

        self.assertEqual(package.contradictions, [])

    def test_duplicate_ids_fail(self):
        output = synthesis(
            facts=[
                EvidenceBackedFact(
                    fact_id="fact_1",
                    statement="Fact one.",
                    evidence_result_ids=["sr_1"],
                    confidence=0.9,
                ),
                EvidenceBackedFact(
                    fact_id="fact_1",
                    statement="Fact two.",
                    evidence_result_ids=["sr_1"],
                    confidence=0.8,
                ),
            ]
        )

        with self.assertRaises(ResearchPackageValidationError):
            assemble_research_package(output, [source("sr_1")])

    def test_unknown_result_id_is_rejected_and_llm_cannot_inject_url(self):
        output = synthesis(
            facts=[
                EvidenceBackedFact(
                    fact_id="fact_1",
                    statement="Fact.",
                    evidence_result_ids=["fabricated_source"],
                    confidence=0.8,
                )
            ]
        )

        with self.assertRaises(ResearchPackageValidationError):
            assemble_research_package(output, [source("sr_1")])

    def test_source_index_retains_all_normalized_results_by_policy(self):
        package = assemble_research_package(synthesis(), [source("sr_1"), source("sr_2")])

        self.assertEqual(set(package.source_index), {"sr_1", "sr_2"})

    def test_extracted_content_creates_evidence_note_and_attaches_to_fact(self):
        extracted = {
            "sr_1": ExtractedSource(
                result_id="sr_1",
                title="Source",
                url="https://example.com/sr_1",
                content_type="html",
                extraction_status="success",
                cleaned_text="The source directly says the supported fact with enough surrounding context.",
                char_count=76,
                snippet_fallback_used=False,
                provider="custom_http",
                extraction_depth="custom",
            )
        }

        package = assemble_research_package(synthesis(), [source("sr_1")], extracted)

        self.assertEqual(package.facts[0].evidence_note_ids, ["en_sr_1"])
        self.assertEqual(package.evidence_notes["en_sr_1"].evidence_basis, "extracted_content")
        self.assertIn("directly says", package.evidence_notes["en_sr_1"].quote)

    def test_extracted_content_creates_claim_level_supporting_span(self):
        extracted = {
            "sr_1": ExtractedSource(
                result_id="sr_1",
                title="Source",
                url="https://example.com/sr_1",
                content_type="html",
                extraction_status="success",
                cleaned_text="The source directly says the supported fact with enough surrounding context.",
                char_count=76,
                snippet_fallback_used=False,
                provider="custom_http",
                extraction_depth="custom",
            )
        }

        package = assemble_research_package(synthesis(), [source("sr_1")], extracted)

        fact = package.facts[0]
        self.assertEqual(fact.grounding_status, "supported")
        self.assertEqual(fact.evidence_span_ids, ["es_fact_1_en_sr_1"])
        span = package.evidence_spans["es_fact_1_en_sr_1"]
        self.assertEqual(span.support_status, "supports")
        self.assertEqual(span.result_id, "sr_1")
        self.assertIn("supported", span.match_terms)

    def test_context_only_span_downgrades_fact_grounding(self):
        extracted = {
            "sr_1": ExtractedSource(
                result_id="sr_1",
                title="Source",
                url="https://example.com/sr_1",
                content_type="html",
                extraction_status="success",
                cleaned_text="This article discusses an unrelated market overview and does not address the claim.",
                char_count=82,
                snippet_fallback_used=False,
                provider="custom_http",
                extraction_depth="custom",
            )
        }

        package = assemble_research_package(synthesis(), [source("sr_1")], extracted)

        fact = package.facts[0]
        self.assertEqual(fact.grounding_status, "context_only")
        self.assertEqual(fact.evidence_strength, "weak")
        self.assertLessEqual(fact.confidence, 0.55)
        self.assertIn("claim-level evidence spans provide context", " ".join(fact.evidence_limitations))

    def test_snippet_only_note_downgrades_overconfident_fact(self):
        package = assemble_research_package(synthesis(), [source("sr_1")])

        self.assertEqual(package.facts[0].evidence_note_ids, ["en_sr_1"])
        self.assertEqual(package.evidence_notes["en_sr_1"].evidence_basis, "snippet_only")
        self.assertEqual(package.facts[0].evidence_strength, "weak")
        self.assertLessEqual(package.facts[0].confidence, 0.65)
        self.assertIn("fact is grounded only in snippet-level evidence notes", package.facts[0].evidence_limitations)

    def test_missing_readable_evidence_note_marks_fact_weak(self):
        blank_source = source("sr_1")
        blank_source.snippet = ""

        package = assemble_research_package(synthesis(), [blank_source])

        self.assertEqual(package.facts[0].evidence_note_ids, [])
        self.assertEqual(package.facts[0].evidence_strength, "weak")
        self.assertIn("no evidence note with readable text was available for this fact", package.facts[0].evidence_limitations)


if __name__ == "__main__":
    unittest.main()
