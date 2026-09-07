import asyncio
import unittest
from unittest.mock import patch

from app.agents.utilities.research_utilities import ResearchUtilities


class _Prompt:
    def __or__(self, llm):
        return llm


class _PromptManager:
    def load_agent_system_prompt(self, *args, **kwargs):
        return _Prompt()


class _SlowPlanner:
    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, payload):
        await asyncio.sleep(1)


class _FailingPlanner:
    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, payload):
        raise RuntimeError("planner failed")


class ResearchPlanningTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_planner_timeout_returns_fallback_plan(self):
        utilities = ResearchUtilities(_SlowPlanner(), _PromptManager())

        with patch(
            "app.agents.utilities.research_utilities.setting.RESEARCH_PLAN_TIMEOUT_SECONDS",
            0.01,
        ):
            plan = await utilities.generate_research_plan("Compare agentic RAG benchmarks")

        self.assertEqual(plan.research_depth, "normal")
        self.assertEqual(plan.search_queries, ["Compare agentic RAG benchmarks"])

    async def test_planner_failure_returns_fallback_plan(self):
        utilities = ResearchUtilities(_FailingPlanner(), _PromptManager())

        plan = await utilities.generate_research_plan("Compare traditional RAG and agentic RAG")

        self.assertEqual(plan.research_depth, "normal")
        self.assertEqual(plan.search_queries, ["Compare traditional RAG and agentic RAG"])


if __name__ == "__main__":
    unittest.main()
