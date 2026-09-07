import time
import unittest
from unittest.mock import patch

from app.agents.researcher import ResearchAgent
from app.core.config import setting
from app.models.agents_schemas.research_package_schema import (
    EvidenceBackedFact,
    StructuredSynthesisOutput,
)
from app.models.agents_schemas.search_result_schema import SearchResult


class SlowSemanticVerifier:
    def verify(self, claims):
        time.sleep(0.2)
        return []


class ResearchValidationDegradationTests(unittest.IsolatedAsyncioTestCase):
    async def test_semantic_validation_timeout_degrades_to_deterministic_package(self):
        agent = object.__new__(ResearchAgent)
        agent.semantic_verifier = SlowSemanticVerifier()

        async def noop_emit(name, payload):
            return None

        agent._emit_event = noop_emit

        synthesis = StructuredSynthesisOutput(
            executive_summary="Summary.",
            facts=[
                EvidenceBackedFact(
                    fact_id="fact_1",
                    statement="Central banks held rates steady.",
                    evidence_result_ids=["src_1"],
                    confidence=0.7,
                )
            ],
        )
        sources = [
            SearchResult(
                result_id="src_1",
                title="Central bank statement",
                url="https://example.com/statement",
                domain="example.com",
                snippet="Central banks held rates steady.",
                source_type="official",
            )
        ]

        with patch.object(setting, "RESEARCH_PACKAGE_VALIDATION_TIMEOUT_SECONDS", 0.01):
            package = await agent._assemble_package_with_event(synthesis, sources, {})

        self.assertTrue(package.facts)
        self.assertEqual(package.source_index["src_1"].title, "Central bank statement")
        self.assertEqual(package.semantic_verification_trace.claims_verified, 0)


if __name__ == "__main__":
    unittest.main()
