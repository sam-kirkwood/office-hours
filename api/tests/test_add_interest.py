"""Tests for POST /add-interest."""

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from anthropic_client import get_anthropic_client
from main import app
from supabase_client import get_supabase_client
from tests.fake_anthropic import FakeAnthropic
from tests.fake_supabase import FakeSupabase

INTERNAL_TOKEN = "test-internal-token"
AUTH_HEADERS = {"Authorization": f"Bearer {INTERNAL_TOKEN}"}

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

EXISTING_NODE_ID = str(uuid4())
EXISTING_NODE = {
    "id": EXISTING_NODE_ID,
    "slug": "calculus-1",
    "title": "Calculus 1",
    "description_md": "Limits, derivatives, integrals.",
}

VALID_GENERATED_NODE = {
    "title": "Fourier Analysis",
    "slug": "fourier-analysis",
    "description_md": "Decomposing functions into sinusoids.",
    "domain": "math",
    "difficulty_hint": "core",
    "subtopics": ["Fourier series", "Fourier transform", "Convolution"],
    "proposed_prerequisite_slugs": ["calculus-1"],
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


def _base_request(raw_text: str = "I want to learn Fourier analysis") -> dict:
    return {
        "user_id": str(uuid4()),
        "raw_text": raw_text,
        "added_via": "survey",
    }


def _prime_nodes(supabase: FakeSupabase, nodes: list[dict] | None = None) -> None:
    supabase.respond("nodes", "select", lambda _: nodes if nodes is not None else [EXISTING_NODE])


def _prime_llm_calls(supabase: FakeSupabase) -> None:
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    response = client.post("/add-interest", json=_base_request())
    assert response.status_code == 401


def test_wrong_bearer_returns_401(client: TestClient) -> None:
    response = client.post(
        "/add-interest",
        json=_base_request(),
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# same verdict — no Sonnet call, user_interests written
# ---------------------------------------------------------------------------


def test_same_verdict_links_user_no_sonnet(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    ui_id = str(uuid4())

    _prime_nodes(supabase, [EXISTING_NODE])
    _prime_llm_calls(supabase)
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])

    anthropic.queue(
        json.dumps(
            {"verdict": "same", "matched_node_slug": "calculus-1", "reason": "exact match"}
        )
    )

    response = client.post("/add-interest", json=_base_request("calculus"), headers=AUTH_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["node_id"] == EXISTING_NODE_ID
    assert body["node_slug"] == "calculus-1"
    assert body["verdict"] == "same"
    assert body["user_interest_id"] == ui_id

    # Only one Anthropic call (Haiku dedup); Sonnet must NOT be called.
    assert len(anthropic.messages.calls) == 1

    # user_interests must be written.
    ui_inserts = [c for c in supabase.calls if c.table == "user_interests" and c.op == "insert"]
    assert len(ui_inserts) == 1
    assert ui_inserts[0].payload["node_id"] == EXISTING_NODE_ID

    # No new nodes inserted.
    assert not any(c.table == "nodes" and c.op == "insert" for c in supabase.calls)

    # Haiku call used temperature=0 (classification).
    assert anthropic.messages.calls[0].get("temperature") == 0


# ---------------------------------------------------------------------------
# new verdict — Sonnet called, node inserted, edges inserted
# ---------------------------------------------------------------------------


def test_new_verdict_creates_node_and_edges(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    new_node_id = str(uuid4())
    ui_id = str(uuid4())

    _prime_nodes(supabase, [EXISTING_NODE])
    _prime_llm_calls(supabase)
    supabase.respond("nodes", "insert", lambda _: [{"id": new_node_id}])
    supabase.respond("edges", "insert", lambda _: [])
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])

    # Haiku says 'new', Sonnet generates the node.
    anthropic.queue(json.dumps({"verdict": "new", "matched_node_slug": None}))
    anthropic.queue(json.dumps(VALID_GENERATED_NODE))

    response = client.post("/add-interest", json=_base_request(), headers=AUTH_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["node_id"] == new_node_id
    assert body["node_slug"] == "fourier-analysis"
    assert body["verdict"] == "new"

    # Two LLM calls: Haiku dedup + Sonnet generate.
    assert len(anthropic.messages.calls) == 2

    # Node inserted with correct shape.
    node_inserts = [c for c in supabase.calls if c.table == "nodes" and c.op == "insert"]
    assert len(node_inserts) == 1
    payload = node_inserts[0].payload
    assert payload["slug"] == "fourier-analysis"
    assert payload["kind"] == "interest"
    assert payload["domain"] == "math"

    # Prerequisite edge inserted: calculus-1 → fourier-analysis.
    edge_inserts = [c for c in supabase.calls if c.table == "edges" and c.op == "insert"]
    assert len(edge_inserts) == 1
    edges = edge_inserts[0].payload
    assert isinstance(edges, list)
    assert len(edges) == 1
    assert edges[0]["source_node_id"] == EXISTING_NODE_ID
    assert edges[0]["target_node_id"] == new_node_id
    assert edges[0]["edge_kind"] == "prerequisite"

    # Sonnet does NOT pin temperature.
    assert "temperature" not in anthropic.messages.calls[1]


# ---------------------------------------------------------------------------
# slug collision — curation_proposals written, no edges inserted
# ---------------------------------------------------------------------------


def test_slug_collision_writes_curation_proposal(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    existing_id = str(uuid4())
    ui_id = str(uuid4())

    # First nodes select: load candidates. Second: fetch existing node after collision.
    node_select_responses: list[list[dict]] = [
        [EXISTING_NODE],
        [{"id": existing_id, "slug": "fourier-analysis"}],
    ]
    supabase.respond("nodes", "select", lambda _: node_select_responses.pop(0))

    _prime_llm_calls(supabase)
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])
    supabase.respond("curation_proposals", "insert", lambda _: [{"id": str(uuid4())}])

    class FakeUniqueViolation(Exception):
        code = "23505"

    supabase.respond("nodes", "insert", lambda _: FakeUniqueViolation("duplicate key"))

    anthropic.queue(json.dumps({"verdict": "new", "matched_node_slug": None}))
    anthropic.queue(json.dumps(VALID_GENERATED_NODE))

    response = client.post("/add-interest", json=_base_request(), headers=AUTH_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["node_id"] == existing_id

    # Curation proposal written.
    cp_inserts = [c for c in supabase.calls if c.table == "curation_proposals" and c.op == "insert"]
    assert len(cp_inserts) == 1
    assert cp_inserts[0].payload["kind"] == "merge"

    # No edges inserted on race path.
    assert not any(c.table == "edges" and c.op == "insert" for c in supabase.calls)

    # user_interests still written (linked to existing node).
    ui_inserts = [c for c in supabase.calls if c.table == "user_interests" and c.op == "insert"]
    assert len(ui_inserts) == 1
    assert ui_inserts[0].payload["node_id"] == existing_id


# ---------------------------------------------------------------------------
# related verdict — new node with a 'related' edge to the matched node
# ---------------------------------------------------------------------------


def test_related_verdict_creates_node_with_related_edge(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    new_node_id = str(uuid4())
    ui_id = str(uuid4())

    _prime_nodes(supabase, [EXISTING_NODE])
    _prime_llm_calls(supabase)
    supabase.respond("nodes", "insert", lambda _: [{"id": new_node_id}])
    supabase.respond("edges", "insert", lambda _: [])
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])

    # Haiku says 'related' to calculus-1. Sonnet generates a node with no prerequisites.
    anthropic.queue(
        json.dumps({"verdict": "related", "matched_node_slug": "calculus-1", "reason": "nearby"})
    )
    related_node = {**VALID_GENERATED_NODE, "proposed_prerequisite_slugs": []}
    anthropic.queue(json.dumps(related_node))

    response = client.post("/add-interest", json=_base_request(), headers=AUTH_HEADERS)

    assert response.status_code == 200, response.text
    assert response.json()["verdict"] == "related"

    edge_inserts = [c for c in supabase.calls if c.table == "edges" and c.op == "insert"]
    assert len(edge_inserts) == 1
    edges = edge_inserts[0].payload
    assert len(edges) == 1
    assert edges[0]["source_node_id"] == EXISTING_NODE_ID  # related node
    assert edges[0]["target_node_id"] == new_node_id
    assert edges[0]["edge_kind"] == "related"


# ---------------------------------------------------------------------------
# hallucinated slug — falls back to 'new', Sonnet still called
# ---------------------------------------------------------------------------


def test_hallucinated_slug_treated_as_new(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    new_node_id = str(uuid4())
    ui_id = str(uuid4())

    _prime_nodes(supabase, [EXISTING_NODE])
    _prime_llm_calls(supabase)
    supabase.respond("nodes", "insert", lambda _: [{"id": new_node_id}])
    supabase.respond("edges", "insert", lambda _: [])
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])

    # Haiku returns a slug that is not in the candidate set.
    anthropic.queue(
        json.dumps({"verdict": "same", "matched_node_slug": "nonexistent-topic", "reason": "?"})
    )
    # Falls back to 'new'; Sonnet is called.
    anthropic.queue(json.dumps({**VALID_GENERATED_NODE, "proposed_prerequisite_slugs": []}))

    response = client.post("/add-interest", json=_base_request(), headers=AUTH_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    # Treated as 'new' — a new node was created, not linked to the hallucinated slug.
    assert body["node_id"] == new_node_id
    assert body["verdict"] == "new"

    # Sonnet was called (two total: Haiku + Sonnet).
    assert len(anthropic.messages.calls) == 2

    # A new node was inserted (not a user_interest link to an existing one).
    assert any(c.table == "nodes" and c.op == "insert" for c in supabase.calls)
