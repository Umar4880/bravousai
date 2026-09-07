import json
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.presentation import PresentationAgent
from app.api.v1.artifact_routes import router as artifact_router
from app.models.agents_schemas.presentation_schema import (
    ArtifactBundle,
    ArtifactInputPackage,
    ArtifactSpec,
    ArtifactValidationReport,
    BuildArtifactResult,
    PresentationPlan,
)
from app.models.agents_schemas.research_package_schema import (
    Contradiction,
    EvidenceBackedFact,
    ResearchPackage,
    Scenario,
)
from app.models.agents_schemas.search_result_schema import SearchResult
from app.services.presentation_artifact_service import PresentationArtifactService
from app.utils.presentation.artifact_validation import (
    ArtifactValidationError,
    csp_header,
    render_standalone_html,
    validate_artifact_bundle,
)


class FakeStructuredChain:
    def __init__(self, result):
        self.result = result

    def with_retry(self, stop_after_attempt=1):
        return self

    async def ainvoke(self, payload):
        self.payload = payload
        return self.result


class FakeLLM:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.schemas = []
        self.chains = []

    def with_structured_output(self, schema):
        self.schemas.append(schema)
        chain = FakeStructuredChain(self.results.pop(0))
        self.chains.append(chain)
        return chain


class FakePersister:
    def __init__(self):
        self.calls = []

    async def persist_artifact_version(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            id=uuid.uuid4(),
            artifact_id=uuid.uuid4(),
            version=1,
        )


class FakeReportComposer:
    def __init__(self):
        self.formal_calls = []
        self.notes_calls = []
        self.chat_calls = []

    async def compose_formal_report(self, **kwargs):
        self.formal_calls.append(kwargs)
        return "# Formal Report\n\nReport body."

    def compose_markdown_notes(self, **kwargs):
        self.notes_calls.append(kwargs)
        return "# Research Notes\n\n- Note"

    def compose_chat_answer(self, **kwargs):
        self.chat_calls.append(kwargs)
        return "Short answer."


def package_with_facts(*, fact_count=3, scenarios=0, contradictions=0):
    source = SearchResult(
        result_id="src_1",
        title="Validated Source",
        url="https://example.com/report",
        domain="example.com",
        snippet="raw snippet should not pass to artifact input",
    )
    facts = [
        EvidenceBackedFact(
            fact_id=f"fact_{index}",
            statement=f"Validated claim {index}",
            evidence_result_ids=["src_1"],
            grounding_status="supported",
            confidence=0.8,
        )
        for index in range(fact_count)
    ]
    return ResearchPackage(
        executive_summary="Summary",
        facts=facts,
        scenarios=[
            Scenario(
                scenario_id=f"scenario_{index}",
                title=f"Scenario {index}",
                description="Scenario description",
                based_on_fact_ids=["fact_0"],
            )
            for index in range(scenarios)
        ],
        contradictions=[
            Contradiction(
                contradiction_id=f"contradiction_{index}",
                topic="Topic",
                description="Contradiction description",
                evidence_result_ids=["src_1"],
                resolution_status="unresolved",
            )
            for index in range(contradictions)
        ],
        source_index={"src_1": source},
    )


class PresentationAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_user_format_respected(self):
        agent = PresentationAgent(llm=FakeLLM())
        plan = await agent.plan_presentation(
            user_query="Please make this as markdown notes",
            final_report="Report",
            package=package_with_facts(fact_count=5),
        )
        self.assertEqual(plan.mode, "markdown_notes")
        self.assertEqual(plan.artifact_kind, "none")

    async def test_unspecified_research_defaults_to_formal_report(self):
        agent = PresentationAgent(llm=FakeLLM())
        plan = await agent.plan_presentation(
            user_query="What is this?",
            final_report="Short answer.",
            package=package_with_facts(fact_count=1),
        )
        self.assertEqual(plan.mode, "formal_report")

    async def test_explicit_visual_comparison_selects_artifact_without_llm_router(self):
        llm = FakeLLM()
        agent = PresentationAgent(llm=llm)
        plan = await agent.plan_presentation(
            user_query="Create a visual comparison artifact",
            final_report="Long report" * 400,
            package=package_with_facts(fact_count=5),
        )
        self.assertEqual(plan.mode, "artifact")
        self.assertEqual(plan.artifact_kind, "comparison")
        self.assertEqual(llm.schemas, [])

    async def test_artifact_dashboard_not_report_wins_over_report_word(self):
        llm = FakeLLM()
        agent = PresentationAgent(llm=llm)
        plan = await agent.plan_presentation(
            user_query="Give me an artifact dashboards not report!!!",
            package=package_with_facts(fact_count=5),
        )
        self.assertEqual(plan.mode, "artifact")
        self.assertEqual(plan.artifact_kind, "research_dashboard")
        self.assertEqual(llm.schemas, [])

    async def test_visualization_request_selects_artifact(self):
        agent = PresentationAgent(llm=FakeLLM())
        plan = await agent.plan_presentation(
            user_query="Build a visualization of the findings",
            package=package_with_facts(fact_count=5),
        )
        self.assertEqual(plan.mode, "artifact")
        self.assertEqual(plan.artifact_kind, "research_dashboard")

    async def test_presentation_modes_call_only_needed_composer_or_artifact_tool(self):
        calls = []

        async def fake_tool(**kwargs):
            calls.append(kwargs)
            return BuildArtifactResult(
                artifact_id=str(uuid.uuid4()),
                version_id=str(uuid.uuid4()),
                render_url="/api/v1/artifacts/version/render",
                version=1,
                validation_report=ArtifactValidationReport(
                    html_ok=True,
                    css_ok=True,
                    javascript_ok=True,
                    citations_ok=True,
                ),
            )

        composer = FakeReportComposer()
        agent = PresentationAgent(llm=FakeLLM(), build_artifact_tool=fake_tool, report_composer=composer)
        formal = await agent.present(
            {
                "user_query": "Research this topic",
                "user_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "research": {"research_package": package_with_facts(fact_count=1).model_dump(mode="json")},
            }
        )
        self.assertEqual(formal["presentation"].mode, "formal_report")
        self.assertEqual(len(composer.formal_calls), 1)
        self.assertEqual(len(calls), 0)

        await agent.present(
            {
                "user_query": "Create a comparison table artifact",
                "user_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "writing": {"draft_report": "Detailed report"},
                "research": {"research_package": package_with_facts(fact_count=5).model_dump(mode="json")},
            }
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(composer.formal_calls), 1)

        notes = await agent.present({"user_query": "Give me bullet notes", "research": {"research_package": package_with_facts().model_dump(mode="json")}})
        chat = await agent.present({"user_query": "quick answer please", "research": {"research_package": package_with_facts().model_dump(mode="json")}})
        self.assertEqual(notes["presentation"].mode, "markdown_notes")
        self.assertEqual(chat["presentation"].mode, "chat")
        self.assertEqual(len(composer.notes_calls), 1)
        self.assertEqual(len(composer.chat_calls), 1)


class ArtifactServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_skill_always_loaded_and_version_persisted(self):
        spec = ArtifactSpec(
            artifact_kind="comparison",
            title="Comparison",
            layout="comparison",
            sections=[{"heading": "Summary"}],
            citation_ids=["src_1"],
        )
        bundle = ArtifactBundle(
            html_body="<main><h1>Comparison</h1><p data-citation-id=\"src_1\">Claim</p></main>",
            css="main { color: #111; }",
        )
        persister = FakePersister()
        service = PresentationArtifactService(
            llm=FakeLLM([spec, bundle]),
            persister=persister,
        )
        with patch.object(service, "load_frontend_design_skill", wraps=service.load_frontend_design_skill) as loaded:
            result = await service.build_artifact(
                input_package=ArtifactInputPackage.from_research_package(
                    user_query="Compare",
                    final_report="Report",
                    package=package_with_facts(fact_count=3),
                ),
                plan=PresentationPlan(
                    mode="artifact",
                    artifact_kind="comparison",
                    interaction_level="static",
                    title="Comparison",
                    rationale="Useful",
                ),
                conversation_id=uuid.uuid4(),
                user_id=str(uuid.uuid4()),
            )
        self.assertEqual(loaded.call_count, 1)
        self.assertEqual(len(persister.calls), 1)
        self.assertEqual(result.version, 1)

    async def test_raw_source_content_excluded_from_llm_payload(self):
        spec = ArtifactSpec(
            artifact_kind="briefing",
            title="Briefing",
            layout="single_column",
            sections=[],
            citation_ids=["src_1"],
        )
        bundle = ArtifactBundle(html_body="<main></main>", css="main { color: #111; }")
        llm = FakeLLM([spec, bundle])
        service = PresentationArtifactService(llm=llm, persister=FakePersister())
        await service.build_artifact(
            input_package=ArtifactInputPackage.from_research_package(
                user_query="Brief",
                final_report="Report",
                package=package_with_facts(fact_count=1),
            ),
            plan=PresentationPlan(
                mode="artifact",
                artifact_kind="briefing",
                interaction_level="static",
                title="Briefing",
                rationale="Useful",
            ),
            conversation_id=uuid.uuid4(),
            user_id=str(uuid.uuid4()),
        )
        payload_text = repr(llm.chains[0].payload) + repr(llm.chains[1].payload)
        self.assertNotIn("raw snippet should not pass", payload_text)

    async def test_artifact_llm_payloads_are_serialized_not_raw_dicts(self):
        spec = ArtifactSpec(
            artifact_kind="briefing",
            title="Briefing",
            layout="single_column",
            sections=[],
            citation_ids=["src_1"],
        )
        bundle = ArtifactBundle(html_body="<main></main>", css="main { color: #111; }")
        llm = FakeLLM([spec, bundle])
        service = PresentationArtifactService(llm=llm, persister=FakePersister())

        await service.build_artifact(
            input_package=ArtifactInputPackage.from_research_package(
                user_query="Brief",
                final_report="Report",
                package=package_with_facts(fact_count=1),
            ),
            plan=PresentationPlan(
                mode="artifact",
                artifact_kind="briefing",
                interaction_level="static",
                title="Briefing",
                rationale="Useful",
            ),
            conversation_id=uuid.uuid4(),
            user_id=str(uuid.uuid4()),
        )

        self.assertEqual(len(llm.chains), 2)
        for chain in llm.chains:
            self.assertIsInstance(chain.payload, str)
            parsed = json.loads(chain.payload)
            self.assertIsInstance(parsed, dict)
            self.assertIn("task", parsed)

        self.assertEqual(json.loads(llm.chains[0].payload)["task"], "Generate an ArtifactSpec only.")
        self.assertEqual(json.loads(llm.chains[1].payload)["task"], "Generate an ArtifactBundle only.")
        self.assertIn("artifact_input_package", json.loads(llm.chains[0].payload))
        bundle_payload = json.loads(llm.chains[1].payload)
        self.assertIn("artifact_data", bundle_payload)
        self.assertNotIn("artifact_input_package", bundle_payload)
        self.assertNotIn("final_report", bundle_payload["artifact_data"])

    async def test_report_like_artifact_body_uses_emergency_template(self):
        spec = ArtifactSpec(
            artifact_kind="research_dashboard",
            title="Dashboard",
            layout="dashboard",
            sections=[],
            interactions=[],
            citation_ids=["src_1"],
        )
        bundle = ArtifactBundle(
            html_body=(
                "<main><h1>Artifact Specification: Interactive Dashboard</h1>"
                "<h2>Executive Summary</h2>"
                "<p>This artifact is designed as an interactive visualization.</p>"
                "<h2>Implementation Roadmap</h2>"
                "<p>Upload the CSV to Flourish.studio.</p></main>"
            ),
            css="main { color: #111; }",
        )
        persister = FakePersister()
        service = PresentationArtifactService(llm=FakeLLM([spec, bundle, bundle]), persister=persister)

        await service.build_artifact(
            input_package=ArtifactInputPackage.from_research_package(
                user_query="Create an interactive artifact",
                package=package_with_facts(fact_count=1),
            ),
            plan=PresentationPlan(
                mode="artifact",
                artifact_kind="research_dashboard",
                interaction_level="light_interactive",
                title="Dashboard",
                rationale="Useful",
            ),
            conversation_id=uuid.uuid4(),
            user_id=str(uuid.uuid4()),
        )

        persisted = persister.calls[0]
        self.assertIn("claim-card", persisted["bundle"].html_body)
        self.assertTrue(any("Emergency static artifact template" in warning for warning in persisted["validation_report"].warnings))

    async def test_artifact_regeneration_occurs_once_before_persisting(self):
        spec = ArtifactSpec(
            artifact_kind="briefing",
            title="Briefing",
            layout="single_column",
            sections=[],
            citation_ids=[],
        )
        bundle = ArtifactBundle(
            html_body="<main><h1>Briefing</h1></main>",
            css="main { color: #111; }",
            javascript="const run = Function('return 1');",
        )
        persister = FakePersister()
        repaired_bundle = bundle.model_copy(
            update={
                "html_body": "<main><h1>Briefing</h1><button type=\"button\">Toggle</button></main>",
                "javascript": "document.querySelector('button').addEventListener('click', () => document.body.dataset.ready = 'true');",
            }
        )
        llm = FakeLLM([spec, bundle, repaired_bundle])
        service = PresentationArtifactService(llm=llm, persister=persister)

        result = await service.build_artifact(
            input_package=ArtifactInputPackage.from_research_package(
                user_query="Brief",
                final_report="Report",
                package=package_with_facts(fact_count=1),
            ),
                plan=PresentationPlan(
                    mode="artifact",
                    artifact_kind="briefing",
                    interaction_level="static",
                    title="Briefing",
                    rationale="Useful",
                ),
            conversation_id=uuid.uuid4(),
            user_id=str(uuid.uuid4()),
        )

        self.assertEqual(result.version, 1)
        self.assertEqual(len(persister.calls), 1)
        self.assertEqual(len(llm.chains), 3)
        self.assertIsNotNone(persister.calls[0]["bundle"].javascript)
        self.assertTrue(persister.calls[0]["validation_report"].javascript_ok)
        self.assertIn("regenerated", persister.calls[0]["validation_report"].warnings[0])

    async def test_persistent_invalid_javascript_falls_back_to_static_artifact(self):
        spec = ArtifactSpec(
            artifact_kind="briefing",
            title="Briefing",
            layout="single_column",
            sections=[],
            citation_ids=["src_1"],
        )
        bundle = ArtifactBundle(
            html_body="<main><p data-citation-id=\"src_1\">Allowed claim</p></main>",
            css="main { color: #111; }",
            javascript="const build = Function('return document.body');",
        )
        persister = FakePersister()
        service = PresentationArtifactService(llm=FakeLLM([spec, bundle, bundle]), persister=persister)

        await service.build_artifact(
            input_package=ArtifactInputPackage.from_research_package(
                user_query="Brief",
                final_report="Report",
                package=package_with_facts(fact_count=1),
            ),
            plan=PresentationPlan(
                mode="artifact",
                artifact_kind="briefing",
                interaction_level="light_interactive",
                title="Briefing",
                rationale="Useful",
            ),
            conversation_id=uuid.uuid4(),
            user_id=str(uuid.uuid4()),
        )

        persisted = persister.calls[0]
        self.assertEqual(persisted["spec"].citation_ids, ["src_1"])
        self.assertIsNone(persisted["bundle"].javascript)
        self.assertIn('data-citation-id="src_1"', persisted["bundle"].html_body)
        self.assertFalse(persisted["validation_report"].javascript_ok)
        self.assertTrue(persisted["validation_report"].citations_ok)
        self.assertEqual(len(persisted["validation_report"].warnings), 2)

    async def test_invalid_html_css_still_fails_after_one_regeneration(self):
        spec = ArtifactSpec(artifact_kind="briefing", title="Briefing", layout="single_column", sections=[], citation_ids=[])
        bad = ArtifactBundle(html_body="<iframe></iframe>", css="body {}", javascript=None)
        service = PresentationArtifactService(llm=FakeLLM([spec, bad, bad]), persister=FakePersister())
        with self.assertRaises(ArtifactValidationError):
            await service.build_artifact(
                input_package=ArtifactInputPackage.from_research_package(user_query="Brief", package=package_with_facts(fact_count=1)),
                plan=PresentationPlan(mode="artifact", artifact_kind="briefing", interaction_level="static", title="Briefing", rationale="Useful"),
                conversation_id=uuid.uuid4(),
                user_id=str(uuid.uuid4()),
            )


class ArtifactValidationTests(unittest.TestCase):
    def test_valid_html_artifact_passes(self):
        spec = ArtifactSpec(
            artifact_kind="briefing",
            title="Briefing",
            layout="single_column",
            sections=[],
            citation_ids=["src_1"],
        )
        bundle, report = validate_artifact_bundle(
            spec=spec,
            bundle=ArtifactBundle(
                html_body="<main><p data-citation-id=\"src_1\">Claim</p></main>",
                css="main { display: block; }",
                javascript="document.querySelector('main').classList.add('ready');",
            ),
            allowed_citation_ids={"src_1"},
        )
        self.assertTrue(report.html_ok)
        self.assertIn("main", bundle.html_body)

    def test_iife_javascript_allowed_but_function_constructor_rejected(self):
        spec = ArtifactSpec(
            artifact_kind="briefing",
            title="Briefing",
            layout="single_column",
            sections=[],
            citation_ids=[],
        )
        bundle, report = validate_artifact_bundle(
            spec=spec,
            bundle=ArtifactBundle(
                html_body="<main></main>",
                css="body {}",
                javascript="(function() { 'use strict'; document.body.classList.add('ready'); })();",
            ),
            allowed_citation_ids=set(),
        )
        self.assertTrue(report.javascript_ok)

        with self.assertRaises(ArtifactValidationError) as ctx:
            validate_artifact_bundle(
                spec=spec,
                bundle=ArtifactBundle(
                    html_body="<main></main>",
                    css="body {}",
                    javascript="const build = Function('return document.body');",
                ),
                allowed_citation_ids=set(),
            )
        self.assertIn("Function", str(ctx.exception))

    def test_forbidden_html_css_js_rejected(self):
        spec = ArtifactSpec(
            artifact_kind="briefing",
            title="Briefing",
            layout="single_column",
            sections=[],
            citation_ids=[],
        )
        cases = [
            ArtifactBundle(html_body="<iframe></iframe>", css="body {}", javascript=None),
            ArtifactBundle(html_body="<main></main>", css="@import url('https://x.test/a.css');", javascript=None),
            ArtifactBundle(html_body="<main></main>", css="body {}", javascript="fetch('/x')"),
        ]
        for bundle in cases:
            with self.assertRaises(ArtifactValidationError):
                validate_artifact_bundle(
                    spec=spec,
                    bundle=bundle,
                    allowed_citation_ids=set(),
                )

    def test_js_layout_top_property_allowed_but_frame_top_rejected(self):
        spec = ArtifactSpec(
            artifact_kind="briefing",
            title="Briefing",
            layout="single_column",
            sections=[],
            citation_ids=[],
        )
        bundle, report = validate_artifact_bundle(
            spec=spec,
            bundle=ArtifactBundle(
                html_body="<main></main>",
                css="body {}",
                javascript=(
                    "const rect = document.querySelector('main').getBoundingClientRect();"
                    "const position = { top: rect.top, left: rect.left };"
                    "document.body.dataset.topPosition = String(position.top);"
                ),
            ),
            allowed_citation_ids=set(),
        )
        self.assertTrue(report.javascript_ok)
        self.assertIn("rect.top", bundle.javascript or "")

        for javascript in (
            "tooltip.style.top = '10px';",
            "element.scrollTo({ top: 0 });",
            "const parent = node.parent;",
            "const cookieNotice = 'Cookie settings';",
        ):
            _, safe_report = validate_artifact_bundle(
                spec=spec,
                bundle=ArtifactBundle(html_body="<main></main>", css="body {}", javascript=javascript),
                allowed_citation_ids=set(),
            )
            self.assertTrue(safe_report.javascript_ok)

        for javascript in (
            "window.top.location = 'https://example.com';",
            "top.location.href = 'https://example.com';",
            "window.parent.document.body;",
            "document.cookie = 'x=y';",
            "top.document.body;",
            "parent.postMessage('x', '*');",
            "opener.location.href = 'https://example.com';",
            "eval('1 + 1');",
        ):
            with self.assertRaises(ArtifactValidationError):
                validate_artifact_bundle(
                    spec=spec,
                    bundle=ArtifactBundle(html_body="<main></main>", css="body {}", javascript=javascript),
                    allowed_citation_ids=set(),
                )

    def test_unknown_citation_id_rejected(self):
        spec = ArtifactSpec(
            artifact_kind="briefing",
            title="Briefing",
            layout="single_column",
            sections=[],
            citation_ids=["missing"],
        )
        with self.assertRaises(ArtifactValidationError):
            validate_artifact_bundle(
                spec=spec,
                bundle=ArtifactBundle(html_body="<main></main>", css="body {}"),
                allowed_citation_ids={"src_1"},
            )

    def test_approved_js_receives_nonce(self):
        html = render_standalone_html(
            bundle=ArtifactBundle(
                html_body="<main></main>",
                css="body {}",
                javascript="document.body.dataset.ready = 'true';",
            ),
            title="Artifact",
            nonce="abc123",
        )
        self.assertIn('<script nonce="abc123">', html)
        self.assertIn("script-src 'nonce-abc123';", csp_header("abc123"))


class ArtifactRenderEndpointTests(unittest.TestCase):
    def test_render_endpoint_includes_csp(self):
        version_id = uuid.uuid4()

        class FakeArtifacts:
            async def get_version_by_id(self, *, version_id):
                return SimpleNamespace(
                    html_body="<main></main>",
                    css="body {}",
                    javascript="document.body.dataset.ready = 'true';",
                    spec_json={"title": "Artifact"},
                )

        class FakeUow:
            async def __aenter__(self):
                self.artifacts = FakeArtifacts()
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

        app = FastAPI()
        app.include_router(artifact_router)
        with patch("app.api.v1.artifact_routes.UnitOfWork", FakeUow):
            response = TestClient(app).get(f"/artifacts/{version_id}/render")

        self.assertEqual(response.status_code, 200)
        csp = response.headers["content-security-policy"]
        self.assertIn("default-src 'none'", csp)
        self.assertIn("connect-src 'none'", csp)
        self.assertIn("script-src 'nonce-", csp)
        self.assertIn("<script nonce=", response.text)


class GraphRoutingTests(unittest.TestCase):
    def test_graph_routes_researcher_to_presentation_without_writer_node(self):
        source = Path("app/graph/research_graph.py").read_text(encoding="utf-8")
        self.assertIn('graph.add_node("presentation"', source)
        self.assertNotIn('graph.add_node("writer"', source)
        self.assertNotIn('graph.add_edge("writer", "presentation")', source)
        supervisor = Path("app/agents/supervisr.py").read_text(encoding="utf-8")
        self.assertIn('path.append("researcher")', supervisor)
        self.assertIn('path.append("presentation")', supervisor)


if __name__ == "__main__":
    unittest.main()
