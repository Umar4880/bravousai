import json
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import pytest
except ModuleNotFoundError:
    pytest = None

from app.agents.graph.state import ResearchState
from app.agents.researcher import ResearchAgent
from app.core.prompt_loader import PromptManager
from app.models.agents_schemas.research_package_schema import (
    EvidenceBackedFact,
    StructuredSynthesisOutput,
)
from app.utils.source_selection import format_sources_for_synthesis

try:
    from app.core.llm_provider import get_llm
except ModuleNotFoundError as exc:
    raise unittest.SkipTest(f"Live synthesizer diagnostic dependency unavailable: {exc}") from exc

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESEARCHER_JSON = PROJECT_ROOT / "researcher.json"
ALONE_SYNTHESIZE_OUTPUT = PROJECT_ROOT / "alone_synthesize.txt"


def load_researcher_json_state() -> ResearchState:
    with RESEARCHER_JSON.open(encoding="utf-8") as handle:
        return ResearchState.model_validate(json.load(handle))


def payload_stats(payload: dict) -> dict:
    raw_search_results = payload["raw_search_results"]
    source_evidence_content = payload["source_evidence_content"]
    extracted_items = [
        item
        for item in source_evidence_content
        if item.get("evidence_basis") == "extracted_content"
    ]
    snippet_items = [
        item
        for item in source_evidence_content
        if item.get("evidence_basis") in {"snippet_only", "snippet_fallback"}
    ]
    raw_snippet_chars = sum(len(item.get("snippet") or "") for item in raw_search_results)
    evidence_chars = sum(len(item.get("text") or "") for item in source_evidence_content)
    raw_ids_with_snippets = {
        item["result_id"] for item in raw_search_results if item.get("snippet")
    }
    evidence_ids_with_text = {
        item["result_id"] for item in source_evidence_content if item.get("text")
    }

    return {
        "raw_search_results": len(raw_search_results),
        "source_evidence_content_items": len(source_evidence_content),
        "extracted_content_items": len(extracted_items),
        "snippet_or_fallback_items": len(snippet_items),
        "raw_snippet_chars": raw_snippet_chars,
        "source_evidence_chars": evidence_chars,
        "prompt_chars": len(json.dumps(payload, default=str)),
        "duplicated_text_channel_items": len(raw_ids_with_snippets & evidence_ids_with_text),
        "largest_evidence_item_chars": max(
            [len(item.get("text") or "") for item in source_evidence_content],
            default=0,
        ),
    }


class RecordingSynthesisChain:
    def __init__(self):
        self.payload = None

    async def ainvoke(self, payload):
        self.payload = payload
        result_id = payload["raw_search_results"][0]["result_id"]
        return StructuredSynthesisOutput(
            executive_summary="Diagnostic synthesis completed.",
            facts=[
                EvidenceBackedFact(
                    fact_id="fact_diagnostic_1",
                    statement="Diagnostic fact from saved researcher payload.",
                    evidence_result_ids=[result_id],
                    confidence=0.5,
                    evidence_strength="weak",
                )
            ],
        )


class ResearchSynthesizerDiagnosticTests(unittest.IsolatedAsyncioTestCase):
    async def test_synthesizer_replays_researcher_json_payload_shape(self):
        state = load_researcher_json_state()
        from app.core.llm_provider import get_llm
        try:
            llm = get_llm(agent_name="live_research_synthesizer_stream")
        except Exception:
            llm = None
        agent = ResearchAgent(llm, PromptManager())
        chain = RecordingSynthesisChain()
        agent._synthesis_chain_single = chain

        output = await agent._synthesize(
            "diagnostic synthesis replay",
            state.plan,
            state.raw_search_results,
            state.extracted_sources,
            agent._extraction_budget(),
        )

        stats = payload_stats(chain.payload)
        print("\nSYNTHESIS_REPLAY_DIAGNOSTIC")
        print(json.dumps(stats, indent=2))

        self.assertTrue(output.facts)
        self.assertEqual(stats["raw_search_results"], len(state.raw_search_results))
        self.assertEqual(stats["source_evidence_content_items"], len(state.raw_search_results))
        self.assertGreater(stats["source_evidence_chars"], 0)

    async def test_live_synthesizer_streams_real_model_output_from_researcher_json(self):
        state = load_researcher_json_state()

        agent = ResearchAgent(
            get_llm(agent_name="live_research_synthesizer_stream"),
            PromptManager(),
        )

        extraction_budget = agent._extraction_budget()
        from app.agents.research_subgraph import _search_result_dict
        raw_search_results = [
            _search_result_dict(item)
            for item in state.raw_search_results
        ]
        source_evidence_content = format_sources_for_synthesis(
            state.raw_search_results,
            state.extracted_sources,
            budget=extraction_budget,
            max_snippet_chars=500,
        )

        payload = {
            "user_input": "diagnostic synthesis replay",
            "research_plan": state.plan,
            "raw_search_results": raw_search_results,
            "source_evidence_content": source_evidence_content,
        }

        print("\nLIVE_SYNTHESIZER_INPUT_STATS")
        print(json.dumps(payload_stats(payload), indent=2))

        started = time.perf_counter()
        final_output = None

        with ALONE_SYNTHESIZE_OUTPUT.open("w", encoding="utf-8") as stream_file:
            stream_file.write("LIVE_SYNTHESIZER_INPUT_STATS\n")
            stream_file.write(json.dumps(payload_stats(payload), indent=2))
            stream_file.write("\n\nLIVE_SYNTHESIZER_STREAM_START\n\n")
            stream_file.flush()

            async for event in agent._synthesis_chain.astream_events(payload, version="v2"):
                event_type = event.get("event")
                name = event.get("name", "")

                if event_type == "on_chat_model_start":
                    stream_file.write(f"\n[chat_model_start] {name}\n")
                    stream_file.flush()

                elif event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")

                    content = getattr(chunk, "content", None)
                    if content:
                        stream_file.write(content)
                        stream_file.flush()
                        continue

                    additional_kwargs = getattr(chunk, "additional_kwargs", {}) or {}
                    tool_calls = additional_kwargs.get("tool_calls") or []
                    for tool_call in tool_calls:
                        function = tool_call.get("function", {})
                        args = function.get("arguments")
                        if args:
                            stream_file.write(args)
                            stream_file.flush()

                elif event_type == "on_chat_model_end":
                    stream_file.write(f"\n\n[chat_model_end] {name}\n")
                    stream_file.flush()

                elif event_type == "on_chain_end":
                    output = event.get("data", {}).get("output")
                    if isinstance(output, StructuredSynthesisOutput):
                        final_output = output

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

        with ALONE_SYNTHESIZE_OUTPUT.open("a", encoding="utf-8") as stream_file:
            stream_file.write("\n\nLIVE_SYNTHESIZER_STREAM_END\n")
            stream_file.write(json.dumps({"elapsed_ms": elapsed_ms}, indent=2))
            stream_file.write("\n")

            if final_output is not None:
                stream_file.write("\nLIVE_SYNTHESIZER_FINAL_OUTPUT\n")
                stream_file.write(final_output.model_dump_json(indent=2))
                stream_file.write("\n")

        print(f"\nLive synthesizer stream written to: {ALONE_SYNTHESIZE_OUTPUT}")

        self.assertIsNotNone(final_output)
