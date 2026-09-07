import unittest

from app.models.agents_schemas.research_depth import (
    normalize_research_depth,
    tavily_options_for_depth,
)
from app.models.agents_schemas.research_plan_schema import ResearchPlan


class ResearchDepthTests(unittest.TestCase):
    def test_detailed_depth_uses_advanced_tavily_behavior(self):
        self.assertEqual(
            tavily_options_for_depth("detailed"),
            {
                "max_results": 5,
                "search_depth": "advanced",
            },
        )


    def test_legacy_advance_depth_is_explicitly_normalized(self):
        self.assertEqual(normalize_research_depth("advance"), "detailed")
        self.assertEqual(normalize_research_depth("advanced"), "detailed")


    def test_invalid_depth_is_rejected_by_normalizer(self):
        with self.assertRaises(ValueError):
            normalize_research_depth("deep")


    def test_research_plan_schema_rejects_invalid_depth_values(self):
        with self.assertRaises(ValueError):
            ResearchPlan(
                topic="AI",
                research_depth="advance",
                research_areas=["models"],
                search_queries=["latest AI models"],
            )


if __name__ == "__main__":
    unittest.main()
