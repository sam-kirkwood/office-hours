"""Tests for the Stage-3 survey interest suggestion route.

Focus: the Step 9c-ii change that dropped the padding fallback. The route
must return only the Haiku-ranked suggestions, even when that is fewer than
SUGGESTION_MIN, rather than padding from the unfiltered shortlist with a
rationale that is false when the in-domain pool was thin.
"""

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

NODE_A = {
    "id": str(uuid4()),
    "slug": "phase-transitions-critical-phenomena",
    "title": "Phase Transitions & Critical Phenomena",
    "description_md": "Collective behaviour near the critical point.",
    "domain": "physics",
    "kind": "interest",
}
NODE_B = {
    "id": str(uuid4()),
    "slug": "renormalization-group-fixed-points",
    "title": "Renormalization Group & Fixed Points",
    "description_md": "Scale transformations and universality.",
    "domain": "physics",
    "kind": "interest",
}
NODE_C = {
    "id": str(uuid4()),
    "slug": "special-relativity",
    "title": "Special Relativity",
    "description_md": "Spacetime, Lorentz transformations, and dynamics.",
    "domain": "physics",
    "kind": "interest",
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


def test_suggest_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/survey/suggest-interests",
        json={"user_id": str(uuid4()), "domains": [], "marked_foundation_node_ids": []},
    )
    assert resp.status_code == 401


def test_suggest_interests_returns_only_haiku_ranked_when_shortlist_empty(
    client: TestClient, fakes
) -> None:
    """Three nodes are in the shortlist but Haiku only ranks two as in-domain
    matches. The response must contain exactly those two — no padding row with
    the old 'Adjacent to the foundations you flagged.' rationale."""
    supabase, anthropic = fakes
    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond("nodes", "select", lambda _: [NODE_A, NODE_B, NODE_C])
    supabase.respond("edges", "select", lambda _: [])
    supabase.respond("surveys", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])

    # Haiku ranks only two of the three shortlist nodes.
    anthropic.queue(
        json.dumps(
            {
                "suggestions": [
                    {
                        "slug": "phase-transitions-critical-phenomena",
                        "why_suggested_md": "Builds on the statistical mechanics you flagged.",
                    },
                    {
                        "slug": "renormalization-group-fixed-points",
                        "why_suggested_md": "The modern lens on critical phenomena.",
                    },
                ]
            }
        )
    )

    resp = client.post(
        "/survey/suggest-interests",
        json={
            "user_id": str(uuid4()),
            "domains": [{"key": "physics", "label": "Physics"}],
            "marked_foundation_node_ids": [],
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    suggestions = resp.json()["suggestions"]

    # Exactly the two Haiku-ranked nodes — not padded back up to SUGGESTION_MIN.
    assert len(suggestions) == 2
    slugs = {s["slug"] for s in suggestions}
    assert slugs == {
        "phase-transitions-critical-phenomena",
        "renormalization-group-fixed-points",
    }
    # The dropped padding rationale must not appear.
    assert all(
        s["why_suggested_md"] != "Adjacent to the foundations you flagged."
        for s in suggestions
    )
    # The unranked node is absent.
    assert "special-relativity" not in slugs
