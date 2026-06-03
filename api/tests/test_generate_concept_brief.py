"""Tests for POST /generate-concept-brief (Step 5.5)."""

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
        "/generate-concept-brief",
        json={"user_id": str(uuid4()), "node_id": str(uuid4())},
    )
    assert resp.status_code == 401


def test_node_not_found_returns_404(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("node_concept_briefs", "select", lambda _: [])
    supabase.respond("nodes", "select", lambda _: [])

    resp = client.post(
        "/generate-concept-brief",
        json={"user_id": str(uuid4()), "node_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


def test_happy_path_generates_and_caches(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    node_id = str(uuid4())

    supabase.respond("node_concept_briefs", "select", lambda _: [])
    supabase.respond(
        "nodes",
        "select",
        lambda _: [
            {
                "id": node_id,
                "title": "Group Theory",
                "description_md": "Algebraic structures of symmetry.",
                "subtopics_json": [{"slug": "cosets", "title": "Cosets"}],
            }
        ],
    )
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("node_concept_briefs", "upsert", lambda _: [{"node_id": node_id}])

    anthropic.queue(
        json.dumps(
            {
                "brief_md": "Para 1.\n\nPara 2.\n\nPara 3.",
                "subtopic_glosses_json": [
                    {"slug": "cosets", "title": "Cosets", "gloss_md": "Translated copies of subgroups."}
                ],
            }
        )
    )

    resp = client.post(
        "/generate-concept-brief",
        json={"user_id": str(uuid4()), "node_id": node_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["brief_md"] == "Para 1.\n\nPara 2.\n\nPara 3."
    assert data["subtopic_glosses_json"] == [
        {"slug": "cosets", "title": "Cosets", "gloss_md": "Translated copies of subgroups."}
    ]
    assert data["cached"] is False

    # Brief written to cache.
    upserts = [c for c in supabase.calls if c.table == "node_concept_briefs" and c.op == "upsert"]
    assert len(upserts) == 1
    row = upserts[0].payload
    assert row["node_id"] == node_id
    assert row["brief_md"] == "Para 1.\n\nPara 2.\n\nPara 3."


def test_cache_hit_returns_without_anthropic_call(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    node_id = str(uuid4())

    supabase.respond(
        "node_concept_briefs",
        "select",
        lambda _: [
            {
                "brief_md": "Cached.",
                "subtopic_glosses_json": [
                    {"slug": "x", "title": "X", "gloss_md": "Cached gloss."}
                ],
            }
        ],
    )

    resp = client.post(
        "/generate-concept-brief",
        json={"user_id": str(uuid4()), "node_id": node_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["brief_md"] == "Cached."
    assert data["cached"] is True
    # Anthropic must NOT be touched on a cache hit.
    assert anthropic.messages.calls == []
    # Nodes table must NOT be touched either — cache short-circuits before
    # node lookup.
    assert not any(c.table == "nodes" for c in supabase.calls)
