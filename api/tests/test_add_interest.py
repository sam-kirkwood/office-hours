"""Tests for the add-interest dialog endpoints.

Covers the happy paths and the contract the next UI session depends on:
  - /parse: auth, single-segment specific, single-segment ambiguous.
  - /resolve: auth, link-to-existing path, generate-new path with concept tour.

Full edge-case coverage (slug-collision races, title collision into existing
node, hallucinated dedup slugs, multi-interest splitting) will be added when
the UI sessions wire the dialog up — see docs/phase-plans/phase-10-rev-plan.md.
"""

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from anthropic_client import get_anthropic_client
from main import app
from prompts import add_interest as prompts
from supabase_client import get_supabase_client
from tests.fake_anthropic import FakeAnthropic
from tests.fake_supabase import FakeSupabase

INTERNAL_TOKEN = "test-internal-token"
AUTH_HEADERS = {"Authorization": f"Bearer {INTERNAL_TOKEN}"}

CALCULUS_ID = str(uuid4())
LINALG_ID = str(uuid4())
CALCULUS_NODE = {
    "id": CALCULUS_ID,
    "slug": "calculus-1",
    "title": "Calculus 1",
    "kind": "foundation",
    "description_md": "Limits, derivatives, integrals.",
    "subtopics_json": [
        "Rules for differentiation",
        "Integration techniques",
        "Sequences and series",
    ],
}
LINALG_NODE = {
    "id": LINALG_ID,
    "slug": "linear-algebra",
    "title": "Linear Algebra",
    "kind": "foundation",
    "description_md": "Vectors, matrices, eigenstructure.",
    "subtopics_json": [
        {"slug": "matrix-multiplication", "title": "Matrix multiplication"},
        {"slug": "eigenvalues", "title": "Eigenvalues and eigenvectors"},
    ],
}


@pytest.fixture
def fakes() -> tuple[FakeSupabase, FakeAnthropic]:
    fake_supabase = FakeSupabase()
    fake_anthropic = FakeAnthropic()
    app.dependency_overrides[get_supabase_client] = lambda: fake_supabase
    app.dependency_overrides[get_anthropic_client] = lambda: fake_anthropic
    try:
        yield fake_supabase, fake_anthropic
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(fakes) -> TestClient:  # noqa: ARG001
    return TestClient(app)


def _prime_llm_calls(supabase: FakeSupabase) -> None:
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])


# ---------------------------------------------------------------------------
# /add-interest/parse
# ---------------------------------------------------------------------------


def test_parse_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/add-interest/parse",
        json={"user_id": str(uuid4()), "raw_text": "hi", "added_via": "survey"},
    )
    assert resp.status_code == 401


def test_parse_system_prompt_classifies_denial_of_mastery_as_teach() -> None:
    """Step 9c-i: explicit denial of mastery + want-to-learn language should
    route to 'teach', not 'consolidate'. The rule lives in the parser system
    prompt; this guards it against regression. Maya's verbatim input ('I want
    to actually understand bifurcations and attractors instead of just dropping
    the words') is the motivating case."""
    # Collapse the prompt's line-continuation whitespace so substring checks
    # don't depend on the source indentation.
    normalized = " ".join(prompts.build_parse_system_prompt().lower().split())
    # The rule names the teach mapping explicitly.
    assert "i want to actually understand" in normalized
    assert "all teach" in normalized
    # And it scopes consolidate away from denial-of-mastery phrasing.
    assert "consolidate is reserved for users who assert existing mastery" in normalized


def test_parse_specific_segment_returns_mirror_back_and_followup(
    client: TestClient, fakes
) -> None:
    supabase, anthropic = fakes
    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    _prime_llm_calls(supabase)

    anthropic.queue(
        json.dumps(
            {
                "segments": [
                    {
                        "raw_text_segment": "I want my calculus back",
                        "specificity": "specific",
                        "implicit_intent": "refresh",
                        "mirror_back_md": "Got it — refreshing calculus.",
                        "optional_followup_md": "Want to tell me more?",
                        "path_options": [],
                        "dedup": {
                            "verdict": "same",
                            "matched_node_slug": "calculus-1",
                        },
                        "draft_intent_context": "refresh calculus foundations",
                    }
                ]
            }
        )
    )

    resp = client.post(
        "/add-interest/parse",
        json={
            "user_id": str(uuid4()),
            "raw_text": "I want my calculus back",
            "added_via": "survey",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["segments"]) == 1
    seg = body["segments"][0]
    assert seg["specificity"] == "specific"
    assert seg["implicit_intent"] == "refresh"
    assert seg["optional_followup_md"] == "Want to tell me more?"
    assert seg["path_options"] == []
    assert seg["dedup"]["verdict"] == "same"
    assert seg["dedup"]["matched_node_slug"] == "calculus-1"
    assert seg["draft_intent_context"] == "refresh calculus foundations"

    # Haiku call pinned to temperature=0 (classification).
    assert len(anthropic.messages.calls) == 1
    assert anthropic.messages.calls[0].get("temperature") == 0


def test_parse_ambiguous_segment_returns_path_options(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    _prime_llm_calls(supabase)

    anthropic.queue(
        json.dumps(
            {
                "segments": [
                    {
                        "raw_text_segment": "I want to learn semiconductors",
                        "specificity": "ambiguous",
                        "implicit_intent": "teach",
                        "mirror_back_md": "That covers a few angles — which sounds closest?",
                        "optional_followup_md": None,
                        "path_options": [
                            {
                                "key": "transistors-and-circuits",
                                "label_md": "How transistors and circuits actually work",
                                "draft_intent_context": "devices-and-circuits angle, teach intent",
                            },
                            {
                                "key": "deeper-physics",
                                "label_md": "The deeper physics of why semiconductors behave this way",
                                "draft_intent_context": "solid-state-physics angle, teach intent",
                            },
                        ],
                        "dedup": {"verdict": "new", "matched_node_slug": None},
                        "draft_intent_context": "semiconductors, teach intent",
                    }
                ]
            }
        )
    )

    resp = client.post(
        "/add-interest/parse",
        json={
            "user_id": str(uuid4()),
            "raw_text": "I want to learn semiconductors",
            "added_via": "survey",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    seg = resp.json()["segments"][0]
    assert seg["specificity"] == "ambiguous"
    assert seg["optional_followup_md"] is None
    assert len(seg["path_options"]) == 2
    assert seg["path_options"][0]["key"] == "transistors-and-circuits"
    assert seg["dedup"]["verdict"] == "new"
    assert seg["dedup"]["matched_node_slug"] is None


def test_parse_drops_hallucinated_dedup_slug(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    _prime_llm_calls(supabase)

    anthropic.queue(
        json.dumps(
            {
                "segments": [
                    {
                        "raw_text_segment": "foo",
                        "specificity": "specific",
                        "implicit_intent": "teach",
                        "mirror_back_md": "...",
                        "optional_followup_md": "Want to tell me more?",
                        "path_options": [],
                        "dedup": {
                            "verdict": "same",
                            "matched_node_slug": "does-not-exist",
                        },
                        "draft_intent_context": "...",
                    }
                ]
            }
        )
    )

    resp = client.post(
        "/add-interest/parse",
        json={"user_id": str(uuid4()), "raw_text": "foo", "added_via": "survey"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    seg = resp.json()["segments"][0]
    assert seg["dedup"]["verdict"] == "new"
    assert seg["dedup"]["matched_node_slug"] is None


# ---------------------------------------------------------------------------
# /add-interest/resolve
# ---------------------------------------------------------------------------


def test_resolve_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "survey",
            "raw_text": "x",
            "final_intent_text": "x",
            "intent_context": "x",
        },
    )
    assert resp.status_code == 401


def test_resolve_existing_slug_links_without_sonnet(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    ui_id = str(uuid4())

    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    # Concept tour: prereq edges for the linked node — none in this minimal fixture.
    supabase.respond("edges", "select", lambda _: [])
    _prime_llm_calls(supabase)
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "survey",
            "raw_text": "I want my calculus back",
            "final_intent_text": "Refresh calculus foundations",
            "intent_context": "refresh calculus foundations",
            "existing_node_slug": "calculus-1",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user_interest_id"] == ui_id
    assert body["node_id"] == CALCULUS_ID
    assert body["node_slug"] == "calculus-1"
    assert body["verdict"] == "same"
    assert body["intent_context"] == "refresh calculus foundations"
    assert body["starter_preview_md"].startswith("Your first item will be:")

    # No Anthropic calls — link path skips Sonnet.
    assert anthropic.messages.calls == []

    # user_interests insert carries intent_context.
    ui_inserts = [c for c in supabase.calls if c.table == "user_interests" and c.op == "insert"]
    assert len(ui_inserts) == 1
    payload = ui_inserts[0].payload
    assert payload["node_id"] == CALCULUS_ID
    assert payload["intent_context"] == "refresh calculus foundations"
    assert payload["added_via"] == "survey"


def test_resolve_unknown_existing_slug_returns_400(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    _prime_llm_calls(supabase)

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "survey",
            "raw_text": "x",
            "final_intent_text": "x",
            "intent_context": "x",
            "existing_node_slug": "no-such-node",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400


def test_resolve_new_node_writes_intent_context_and_tour(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    new_node_id = str(uuid4())
    ui_id = str(uuid4())

    supabase.respond(
        "nodes",
        "select",
        lambda _: [CALCULUS_NODE, LINALG_NODE],
    )
    supabase.respond("nodes", "insert", lambda _: [{"id": new_node_id}])
    supabase.respond("edges", "insert", lambda _: [])
    supabase.respond(
        "edges",
        "select",
        lambda _: [
            {
                "source_node_id": CALCULUS_ID,
                "edge_kind": "prerequisite",
                "target_node_id": new_node_id,
            },
            {
                "source_node_id": LINALG_ID,
                "edge_kind": "prerequisite",
                "target_node_id": new_node_id,
            },
        ],
    )
    _prime_llm_calls(supabase)
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])

    anthropic.queue(
        json.dumps(
            {
                "title": "Kalman Filters",
                "slug": "kalman-filters",
                "description_md": "Recursive state estimators.",
                "domain": "applied",
                "difficulty_hint": "core",
                "subtopics": [
                    "Linear-Gaussian model",
                    "Kalman gain",
                    "Extended Kalman filter",
                ],
                "proposed_prerequisite_slugs": ["calculus-1", "linear-algebra"],
                "entry_point_preview_md": (
                    "a conceptual entrance to recursive state estimation"
                ),
            }
        )
    )

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "explicit_request",
            "raw_text": "I want to learn Kalman filters",
            "final_intent_text": "Learn Kalman filters for state estimation",
            "intent_context": "applied-engineering angle, teach intent",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["node_id"] == new_node_id
    assert body["node_slug"] == "kalman-filters"
    assert body["verdict"] == "new"
    assert body["intent_context"] == "applied-engineering angle, teach intent"
    assert "recursive state estimation" in body["starter_preview_md"]

    # Sonnet called once.
    assert len(anthropic.messages.calls) == 1

    # Node was inserted with kind='interest' and the generated payload.
    node_inserts = [c for c in supabase.calls if c.table == "nodes" and c.op == "insert"]
    assert len(node_inserts) == 1
    assert node_inserts[0].payload["slug"] == "kalman-filters"
    assert node_inserts[0].payload["kind"] == "interest"

    # Prerequisite edges inserted per-row: calculus-1 → new, linear-algebra → new.
    edge_inserts = [c for c in supabase.calls if c.table == "edges" and c.op == "insert"]
    assert len(edge_inserts) == 2
    edges = [c.payload for c in edge_inserts]
    assert {e["source_node_id"] for e in edges} == {CALCULUS_ID, LINALG_ID}
    assert all(e["edge_kind"] == "prerequisite" for e in edges)

    # user_interests row carries intent_context.
    ui_inserts = [c for c in supabase.calls if c.table == "user_interests" and c.op == "insert"]
    assert len(ui_inserts) == 1
    assert ui_inserts[0].payload["intent_context"] == "applied-engineering angle, teach intent"
    assert ui_inserts[0].payload["added_via"] == "explicit_request"

    # Concept tour: tiles from both foundation prerequisites, mixed string and dict
    # subtopic shapes both resolved to {name, gloss}.
    tour = body["concept_tour"]
    assert len(tour) >= 1
    names = {t["name"] for t in tour}
    assert "Rules for differentiation" in names           # string-shape subtopics
    assert "Matrix multiplication" in names               # dict-shape subtopics
    # subtopic_key is slugified.
    diff_tile = next(t for t in tour if t["name"] == "Rules for differentiation")
    assert diff_tile["subtopic_key"] == "rules-for-differentiation"
    assert diff_tile["node_slug"] == "calculus-1"


def test_resolve_related_slug_writes_related_edge(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    new_node_id = str(uuid4())
    ui_id = str(uuid4())

    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    supabase.respond("nodes", "insert", lambda _: [{"id": new_node_id}])
    supabase.respond("edges", "insert", lambda _: [])
    supabase.respond("edges", "select", lambda _: [])  # empty prereqs → empty tour
    _prime_llm_calls(supabase)
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])

    anthropic.queue(
        json.dumps(
            {
                "title": "Fourier Analysis",
                "slug": "fourier-analysis",
                "description_md": "Decomposing functions into sinusoids.",
                "domain": "math",
                "difficulty_hint": "core",
                "subtopics": ["Fourier series", "Fourier transform"],
                "proposed_prerequisite_slugs": [],
                "entry_point_preview_md": "a conceptual entrance to Fourier methods",
            }
        )
    )

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "survey",
            "raw_text": "fourier",
            "final_intent_text": "Learn Fourier analysis",
            "intent_context": "math angle, teach intent",
            "related_node_slug": "calculus-1",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verdict"] == "related"

    edge_inserts = [c for c in supabase.calls if c.table == "edges" and c.op == "insert"]
    assert len(edge_inserts) == 1
    edges = [c.payload for c in edge_inserts]
    assert any(
        e["source_node_id"] == CALCULUS_ID
        and e["target_node_id"] == new_node_id
        and e["edge_kind"] == "related"
        for e in edges
    )


def test_resolve_writes_edges_when_related_slug_overlaps_prereqs(
    client: TestClient, fakes
) -> None:
    """Regression for the orphaned-node bug: when the resolved related_slug also
    appears in Sonnet's proposed_prerequisite_slugs, the two edge rows collide on
    the (source, target) uniqueness constraint. A batched insert rolled the whole
    batch back, leaving the node with no edges. Per-row inserts must keep the
    surviving edge instead of dropping both."""
    supabase, anthropic = fakes
    new_node_id = str(uuid4())
    ui_id = str(uuid4())

    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    supabase.respond("nodes", "insert", lambda _: [{"id": new_node_id}])
    supabase.respond("edges", "select", lambda _: [])
    _prime_llm_calls(supabase)
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])

    # Simulate the DB uniqueness constraint: the prerequisite edge inserts
    # cleanly, but the duplicate (source, target) 'related' edge raises 23505.
    def edges_insert(call):
        if call.payload.get("edge_kind") == "related":
            return Exception("duplicate key value violates unique constraint (23505)")
        return []

    supabase.respond("edges", "insert", edges_insert)

    anthropic.queue(
        json.dumps(
            {
                "title": "Fourier Analysis",
                "slug": "fourier-analysis",
                "description_md": "Decomposing functions into sinusoids.",
                "domain": "math",
                "difficulty_hint": "core",
                "subtopics": ["Fourier series", "Fourier transform"],
                # Sonnet redundantly lists the related slug as a prerequisite too.
                "proposed_prerequisite_slugs": ["calculus-1"],
                "entry_point_preview_md": "a conceptual entrance to Fourier methods",
            }
        )
    )

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "survey",
            "raw_text": "fourier",
            "final_intent_text": "Learn Fourier analysis",
            "intent_context": "math angle, teach intent",
            "related_node_slug": "calculus-1",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["verdict"] == "related"

    # Both rows were attempted per-row; the prerequisite survived even though
    # the related edge collided. The batch was NOT rolled back wholesale.
    edge_inserts = [c for c in supabase.calls if c.table == "edges" and c.op == "insert"]
    assert len(edge_inserts) == 2
    kinds = [c.payload["edge_kind"] for c in edge_inserts]
    assert "prerequisite" in kinds
    assert "related" in kinds


def test_resolve_rejects_both_existing_and_related(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    _prime_llm_calls(supabase)

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "survey",
            "raw_text": "x",
            "final_intent_text": "x",
            "intent_context": "x",
            "existing_node_slug": "calculus-1",
            "related_node_slug": "calculus-1",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
