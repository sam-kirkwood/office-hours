"""Tests for POST /generate-curation-report."""

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
# Fixtures
# ---------------------------------------------------------------------------

NODE_ID_1 = str(uuid4())
NODE_ID_2 = str(uuid4())
SNAP_ID = str(uuid4())
SNAP_TAKEN_AT = "2026-04-01T00:00:00+00:00"

SAMPLE_NODES = [
    {"id": NODE_ID_1, "slug": "calculus", "title": "Calculus", "kind": "foundation", "domain": "math", "pool_status": "active"},
    {"id": NODE_ID_2, "slug": "fourier-analysis", "title": "Fourier Analysis", "kind": "interest", "domain": "applied", "pool_status": "active"},
]

SAMPLE_EDGES = [
    {"source_node_id": NODE_ID_1, "target_node_id": NODE_ID_2, "edge_kind": "prerequisite", "weight": 0.9},
]


def _two_proposals_json() -> str:
    return json.dumps({
        "proposals": [
            {
                "kind": "merge",
                "payload_json": {
                    "source_node_id": NODE_ID_1,
                    "target_node_id": NODE_ID_2,
                    "source_title": "Calculus",
                    "target_title": "Fourier Analysis",
                    "rationale": "Overlapping content."
                }
            },
            {
                "kind": "rename",
                "payload_json": {
                    "node_id": NODE_ID_2,
                    "old_title": "Fourier Analysis",
                    "new_title": "Fourier Methods",
                    "new_slug": "fourier-methods",
                    "rationale": "Better standard name."
                }
            },
        ]
    })


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


def _prime_empty_megagraph(supabase: FakeSupabase) -> None:
    """Prime all supabase queries to return empty results."""
    for table in ("megagraph_snapshots", "nodes", "edges", "curation_proposals", "user_node_states"):
        supabase.respond(table, "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])


def _prime_full_megagraph(supabase: FakeSupabase) -> None:
    """Prime supabase with two sample nodes, one edge, no snapshots."""
    supabase.respond("megagraph_snapshots", "select", lambda _: [])
    supabase.respond("nodes", "select", lambda _: SAMPLE_NODES)
    supabase.respond("edges", "select", lambda _: SAMPLE_EDGES)
    supabase.respond("curation_proposals", "select", lambda _: [])
    supabase.respond("user_node_states", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("curation_proposals", "insert", lambda _: [{"id": str(uuid4())}])


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    response = client.post("/generate-curation-report", json={})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Empty megagraph — no crash, 0 proposals
# ---------------------------------------------------------------------------


def test_no_nodes_returns_empty(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes

    _prime_empty_megagraph(supabase)
    anthropic.queue(json.dumps({"proposals": []}))

    response = client.post("/generate-curation-report", json={}, headers=AUTH_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["proposals_created"] == 0

    # No curation_proposals inserts.
    inserts = [c for c in supabase.calls if c.table == "curation_proposals" and c.op == "insert"]
    assert len(inserts) == 0


# ---------------------------------------------------------------------------
# Happy path — 2 proposals written
# ---------------------------------------------------------------------------


def test_proposals_written_to_db(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes

    _prime_full_megagraph(supabase)
    anthropic.queue(_two_proposals_json())

    response = client.post("/generate-curation-report", json={}, headers=AUTH_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["proposals_created"] == 2

    inserts = [c for c in supabase.calls if c.table == "curation_proposals" and c.op == "insert"]
    assert len(inserts) == 2
    kinds = {ins.payload["kind"] for ins in inserts}
    assert kinds == {"merge", "rename"}
    # All pending.
    for ins in inserts:
        assert ins.payload["status"] == "pending"


# ---------------------------------------------------------------------------
# Since window: snapshot exists → uses its taken_at
# ---------------------------------------------------------------------------


def test_since_window_uses_last_snapshot(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes

    snap_responses = [{"id": SNAP_ID, "taken_at": SNAP_TAKEN_AT}]

    # Prime in sequence: snapshots returns one row.
    call_count = {"n": 0}
    def snap_responder(_):
        call_count["n"] += 1
        return snap_responses

    supabase.respond("megagraph_snapshots", "select", snap_responder)
    supabase.respond("nodes", "select", lambda _: SAMPLE_NODES)
    supabase.respond("edges", "select", lambda _: SAMPLE_EDGES)
    supabase.respond("curation_proposals", "select", lambda _: [])
    supabase.respond("user_node_states", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("curation_proposals", "insert", lambda _: [{"id": str(uuid4())}])

    anthropic.queue(json.dumps({"proposals": []}))

    response = client.post("/generate-curation-report", json={}, headers=AUTH_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["since"] == SNAP_TAKEN_AT


# ---------------------------------------------------------------------------
# Since window: no snapshot → epoch
# ---------------------------------------------------------------------------


def test_since_window_all_time_when_no_snapshot(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes

    _prime_empty_megagraph(supabase)
    anthropic.queue(json.dumps({"proposals": []}))

    response = client.post("/generate-curation-report", json={}, headers=AUTH_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    # since should be the epoch string
    assert body["since"].startswith("1970-01-01")


# ---------------------------------------------------------------------------
# LLM call logged
# ---------------------------------------------------------------------------


def test_llm_call_logged(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes

    _prime_full_megagraph(supabase)
    anthropic.queue(json.dumps({"proposals": []}))

    client.post("/generate-curation-report", json={}, headers=AUTH_HEADERS)

    llm_inserts = [c for c in supabase.calls if c.table == "llm_calls" and c.op == "insert"]
    assert len(llm_inserts) >= 1
    assert llm_inserts[0].payload["route"] == "/generate-curation-report"


# ---------------------------------------------------------------------------
# Output truncated at 20
# ---------------------------------------------------------------------------


def test_output_truncated_at_20(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes

    _prime_full_megagraph(supabase)
    # We need to prime 25 inserts; re-prime the responder to return something 25 times.
    insert_count = {"n": 0}
    def cp_insert_responder(_):
        insert_count["n"] += 1
        return [{"id": str(uuid4())}]
    supabase.respond("curation_proposals", "insert", cp_insert_responder)

    # Sonnet returns 25 rename proposals.
    proposals_25 = [
        {"kind": "rename", "payload_json": {"node_id": NODE_ID_1, "old_title": "A", "new_title": f"B{i}", "new_slug": f"b{i}", "rationale": "test"}}
        for i in range(25)
    ]
    anthropic.queue(json.dumps({"proposals": proposals_25}))

    response = client.post("/generate-curation-report", json={}, headers=AUTH_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["proposals_created"] == 20

    inserts = [c for c in supabase.calls if c.table == "curation_proposals" and c.op == "insert"]
    assert len(inserts) == 20
