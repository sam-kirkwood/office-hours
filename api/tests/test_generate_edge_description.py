"""Tests for POST /generate-edge-description (Step 6 follow-up)."""

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


@pytest.fixture
def fakes() -> tuple[FakeSupabase, FakeAnthropic]:
    fs = FakeSupabase()
    fa = FakeAnthropic()
    app.dependency_overrides[get_supabase_client] = lambda: fs
    app.dependency_overrides[get_anthropic_client] = lambda: fa
    try:
        yield fs, fa
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(fakes) -> TestClient:  # noqa: ARG001
    return TestClient(app)


def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/generate-edge-description",
        json={"user_id": str(uuid4()), "edge_id": str(uuid4())},
    )
    assert resp.status_code == 401


def test_edge_not_found_returns_404(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("edge_descriptions", "select", lambda _: [])
    supabase.respond("edges", "select", lambda _: [])

    resp = client.post(
        "/generate-edge-description",
        json={"user_id": str(uuid4()), "edge_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


def test_happy_path_generates_and_caches(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    edge_id = str(uuid4())
    source_id = str(uuid4())
    target_id = str(uuid4())

    supabase.respond("edge_descriptions", "select", lambda _: [])
    supabase.respond(
        "edges",
        "select",
        lambda _: [
            {
                "id": edge_id,
                "source_node_id": source_id,
                "target_node_id": target_id,
                "edge_kind": "prerequisite",
            }
        ],
    )
    supabase.respond(
        "nodes",
        "select",
        lambda _: [
            {
                "id": source_id,
                "title": "Solid State Physics",
                "description_md": "Electrons in crystal lattices.",
                "subtopics_json": [{"slug": "band-theory", "title": "Band theory"}],
            },
            {
                "id": target_id,
                "title": "Carbon Nanotubes",
                "description_md": "Rolled graphene.",
                "subtopics_json": ["chirality"],
            },
        ],
    )
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("edge_descriptions", "upsert", lambda _: [{"edge_id": edge_id}])

    anthropic.queue(
        json.dumps(
            {
                "description_md": "Band theory carries forward into nanotube electronic structure."
            }
        )
    )

    resp = client.post(
        "/generate-edge-description",
        json={"user_id": str(uuid4()), "edge_id": edge_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["description_md"].startswith("Band theory")
    assert data["cached"] is False

    upserts = [c for c in supabase.calls if c.table == "edge_descriptions" and c.op == "upsert"]
    assert len(upserts) == 1
    assert upserts[0].payload["edge_id"] == edge_id


def test_cache_hit_returns_without_anthropic_call(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    edge_id = str(uuid4())

    supabase.respond(
        "edge_descriptions",
        "select",
        lambda _: [{"description_md": "Cached description."}],
    )

    resp = client.post(
        "/generate-edge-description",
        json={"user_id": str(uuid4()), "edge_id": edge_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["description_md"] == "Cached description."
    assert data["cached"] is True
    # Anthropic must NOT be touched on a cache hit.
    assert anthropic.messages.calls == []
    # Edges table must NOT be touched either.
    assert not any(c.table == "edges" for c in supabase.calls)
