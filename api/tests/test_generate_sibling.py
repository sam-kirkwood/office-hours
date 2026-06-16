"""Tests for POST /generate-sibling (Phase 12 Step 3 — §A3 correction loop)."""

from __future__ import annotations

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

VALID_PROBLEM_JSON = json.dumps(
    {
        "title": "A Harder Problem",
        "statement_md": "## Setup\nGiven X.\n\n## The problem\nDerive Y.",
        "solution_md": "Use Z.",
        "rubric_md": "- Correct approach\n- Units",
        "hints": [
            {"text": "Hint 1.", "part_label": "Whole problem"},
            {"text": "Hint 2.", "part_label": "Whole problem"},
            {"text": "Hint 3.", "part_label": "Whole problem"},
            {"text": "Hint 4.", "part_label": "Whole problem"},
            {"text": "Hint 5.", "part_label": "Whole problem"},
        ],
        "context_md": "Historical context.",
        "tags": ["special-relativity", "time-dilation"],
    }
)


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


# ---------------------------------------------------------------------------
# Shared priming helpers
# ---------------------------------------------------------------------------


def _prime_queue_item(
    supabase: FakeSupabase,
    *,
    queue_item_id: str,
    problem_id: str,
) -> None:
    supabase.respond(
        "queue_items",
        "select",
        lambda _call: [{"id": queue_item_id, "ref_id": problem_id, "state": "surfaced"}],
    )


def _prime_problem(
    supabase: FakeSupabase,
    *,
    problem_id: str,
    node_id: str,
    difficulty: int = 3,
    intent: str = "teach",
    context_hook_id: str | None = None,
    tags: list[str] | None = None,
    pool_hit_id: str | None = None,
) -> None:
    """Register a smart problems/select responder.

    The route calls problems/select twice:
      1. Load original problem (filter: id == problem_id)
      2. Pool lookup (filter: topic_node_id == ...)

    pool_hit_id: the problem_id to return for pool lookups (pass None for a
    pool miss, i.e. return []).
    """
    original_row = {
        "id": problem_id,
        "topic_node_id": node_id,
        "difficulty": difficulty,
        "intent": intent,
        "context_hook_id": context_hook_id,
        "tags": tags or ["special-relativity", "time-dilation"],
    }

    def responder(call):
        # If any filter targets "id", it's the original-problem load.
        if any(f[0] == "eq" and f[1] == "id" for f in call.filters):
            return [original_row]
        # Otherwise it's a pool lookup.
        return [{"id": pool_hit_id}] if pool_hit_id else []

    supabase.respond("problems", "select", responder)


def _prime_node(supabase: FakeSupabase, *, node_id: str) -> None:
    supabase.respond(
        "nodes",
        "select",
        lambda _call: [
            {
                "id": node_id,
                "slug": "special-relativity",
                "title": "Special Relativity",
                "description_md": "Lorentz invariance.",
                "difficulty_hint": "core",
                "subtopics_json": [
                    {"slug": "time-dilation", "title": "Time dilation"},
                    {"slug": "length-contraction", "title": "Length contraction"},
                ],
            }
        ],
    )


def _prime_user_context(supabase: FakeSupabase) -> None:
    """Prime the user-context tables with empty/default responses."""
    supabase.respond("user_node_states", "select", lambda _call: [])
    supabase.respond("user_interests", "select", lambda _call: [])
    supabase.respond("user_preferences", "select", lambda _call: [])
    supabase.respond("attempts", "select", lambda _call: [])
    supabase.respond("context_hooks", "select", lambda _call: [])
    supabase.respond("surveys", "select", lambda _call: [])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_harder_pool_hit_returns_sibling(client: TestClient, fakes) -> None:
    """When a harder problem already exists in the pool, no Sonnet call needed."""
    supabase, anthropic = fakes
    user_id = str(uuid4())
    node_id = str(uuid4())
    problem_id = str(uuid4())
    sibling_problem_id = str(uuid4())
    queue_item_id = str(uuid4())
    new_queue_item_id = str(uuid4())

    _prime_queue_item(supabase, queue_item_id=queue_item_id, problem_id=problem_id)
    _prime_problem(supabase, problem_id=problem_id, node_id=node_id, difficulty=3, pool_hit_id=sibling_problem_id)
    _prime_node(supabase, node_id=node_id)
    _prime_user_context(supabase)
    supabase.respond("queue_items", "update", lambda _call: [])
    supabase.respond("queue_items", "insert", lambda _call: [{"id": new_queue_item_id}])

    resp = client.post(
        "/generate-sibling",
        json={"user_id": user_id, "queue_item_id": queue_item_id, "kind": "harder"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["sibling_problem_id"] == sibling_problem_id
    assert data["sibling_queue_item_id"] == new_queue_item_id
    assert not data["is_max_difficulty"]
    assert not data["is_min_difficulty"]
    # No Sonnet call on pool hit
    assert anthropic.messages.calls == []


def test_harder_pool_miss_generates_and_inserts(client: TestClient, fakes) -> None:
    """Pool miss triggers Sonnet generation; problem + hints + sibling queue_item inserted."""
    supabase, anthropic = fakes
    user_id = str(uuid4())
    node_id = str(uuid4())
    problem_id = str(uuid4())
    sibling_problem_id = str(uuid4())
    queue_item_id = str(uuid4())
    new_queue_item_id = str(uuid4())

    _prime_queue_item(supabase, queue_item_id=queue_item_id, problem_id=problem_id)
    _prime_problem(supabase, problem_id=problem_id, node_id=node_id, difficulty=3, pool_hit_id=None)
    _prime_node(supabase, node_id=node_id)
    _prime_user_context(supabase)
    supabase.respond("llm_calls", "insert", lambda _call: [{"id": str(uuid4())}])
    supabase.respond("problems", "insert", lambda _call: [{"id": sibling_problem_id}])
    supabase.respond("problem_hints", "insert", lambda call: [{"id": str(uuid4()), **r} for r in call.payload])
    supabase.respond("queue_items", "update", lambda _call: [])
    supabase.respond("queue_items", "insert", lambda _call: [{"id": new_queue_item_id}])
    anthropic.queue(VALID_PROBLEM_JSON)

    resp = client.post(
        "/generate-sibling",
        json={"user_id": user_id, "queue_item_id": queue_item_id, "kind": "harder"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["sibling_problem_id"] == sibling_problem_id
    assert len(anthropic.messages.calls) == 1  # exactly one Sonnet call

    # Verify the problem was inserted at the target difficulty (4)
    prob_inserts = [c for c in supabase.calls if c.table == "problems" and c.op == "insert"]
    assert len(prob_inserts) == 1
    assert prob_inserts[0].payload["difficulty"] == 4

    # 5 hints written
    hint_inserts = [c for c in supabase.calls if c.table == "problem_hints" and c.op == "insert"]
    assert len(hint_inserts) == 1
    assert len(hint_inserts[0].payload) == 5


def test_easier_at_min_difficulty_returns_guard(client: TestClient, fakes) -> None:
    """When the original is already at difficulty=1, return is_min_difficulty=True."""
    supabase, anthropic = fakes
    user_id = str(uuid4())
    node_id = str(uuid4())
    problem_id = str(uuid4())
    queue_item_id = str(uuid4())

    _prime_queue_item(supabase, queue_item_id=queue_item_id, problem_id=problem_id)
    _prime_problem(supabase, problem_id=problem_id, node_id=node_id, difficulty=1)

    resp = client.post(
        "/generate-sibling",
        json={"user_id": user_id, "queue_item_id": queue_item_id, "kind": "easier"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["is_min_difficulty"] is True
    assert data["sibling_queue_item_id"] is None
    # No node fetch, no Sonnet call, no queue mutation
    assert anthropic.messages.calls == []
    assert not any(c.table == "queue_items" and c.op in ("update", "insert") for c in supabase.calls)


def test_harder_at_max_difficulty_returns_guard(client: TestClient, fakes) -> None:
    """When the original is at difficulty=5, return is_max_difficulty=True."""
    supabase, anthropic = fakes
    user_id = str(uuid4())
    node_id = str(uuid4())
    problem_id = str(uuid4())
    queue_item_id = str(uuid4())

    _prime_queue_item(supabase, queue_item_id=queue_item_id, problem_id=problem_id)
    _prime_problem(supabase, problem_id=problem_id, node_id=node_id, difficulty=5)

    resp = client.post(
        "/generate-sibling",
        json={"user_id": user_id, "queue_item_id": queue_item_id, "kind": "harder"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["is_max_difficulty"] is True
    assert data["sibling_queue_item_id"] is None
    assert anthropic.messages.calls == []


def test_assume_less_always_generates_skipping_pool(client: TestClient, fakes) -> None:
    """assume_less bypasses pool lookup (always generates) and tags result 'assume-less'."""
    supabase, anthropic = fakes
    user_id = str(uuid4())
    node_id = str(uuid4())
    problem_id = str(uuid4())
    sibling_problem_id = str(uuid4())
    queue_item_id = str(uuid4())
    new_queue_item_id = str(uuid4())

    # pool_hit_id is set (pool has a result) but assume_less must skip it
    _prime_queue_item(supabase, queue_item_id=queue_item_id, problem_id=problem_id)
    _prime_problem(supabase, problem_id=problem_id, node_id=node_id, difficulty=3, pool_hit_id=str(uuid4()))
    _prime_node(supabase, node_id=node_id)
    _prime_user_context(supabase)
    supabase.respond("llm_calls", "insert", lambda _call: [{"id": str(uuid4())}])
    supabase.respond("problems", "insert", lambda _call: [{"id": sibling_problem_id}])
    supabase.respond("problem_hints", "insert", lambda call: [{"id": str(uuid4()), **r} for r in call.payload])
    supabase.respond("queue_items", "update", lambda _call: [])
    supabase.respond("queue_items", "insert", lambda _call: [{"id": new_queue_item_id}])
    anthropic.queue(VALID_PROBLEM_JSON)

    resp = client.post(
        "/generate-sibling",
        json={"user_id": user_id, "queue_item_id": queue_item_id, "kind": "assume_less"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["sibling_problem_id"] == sibling_problem_id
    # Sonnet was called (pool was skipped)
    assert len(anthropic.messages.calls) == 1

    # The inserted problem must carry the 'assume-less' tag
    prob_inserts = [c for c in supabase.calls if c.table == "problems" and c.op == "insert"]
    assert len(prob_inserts) == 1
    assert "assume-less" in prob_inserts[0].payload["tags"]

    # Difficulty is unchanged (same as original)
    assert prob_inserts[0].payload["difficulty"] == 3


def test_original_queue_item_superseded_on_success(client: TestClient, fakes) -> None:
    """On successful sibling creation, the original queue_item is set to 'superseded'."""
    supabase, anthropic = fakes
    user_id = str(uuid4())
    node_id = str(uuid4())
    problem_id = str(uuid4())
    sibling_problem_id = str(uuid4())
    queue_item_id = str(uuid4())
    new_queue_item_id = str(uuid4())

    _prime_queue_item(supabase, queue_item_id=queue_item_id, problem_id=problem_id)
    _prime_problem(supabase, problem_id=problem_id, node_id=node_id, difficulty=3, pool_hit_id=sibling_problem_id)
    _prime_node(supabase, node_id=node_id)
    _prime_user_context(supabase)
    supabase.respond("queue_items", "update", lambda _call: [])
    supabase.respond("queue_items", "insert", lambda _call: [{"id": new_queue_item_id}])

    resp = client.post(
        "/generate-sibling",
        json={"user_id": user_id, "queue_item_id": queue_item_id, "kind": "easier"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text

    update_calls = [c for c in supabase.calls if c.table == "queue_items" and c.op == "update"]
    assert len(update_calls) == 1
    assert update_calls[0].payload["state"] == "superseded"

    # Sibling queue_item carries parent_queue_item_id
    insert_calls = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(insert_calls) == 1
    assert insert_calls[0].payload["parent_queue_item_id"] == queue_item_id
    assert insert_calls[0].payload["priority_score"] == 0.85


def test_missing_queue_item_returns_404(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("queue_items", "select", lambda _call: [])

    resp = client.post(
        "/generate-sibling",
        json={"user_id": str(uuid4()), "queue_item_id": str(uuid4()), "kind": "harder"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# §A6 — Sibling queue_item is pinned
# ---------------------------------------------------------------------------


def test_sibling_queue_item_is_pinned(client: TestClient, fakes) -> None:
    """The queue_item inserted for a sibling must have pinned=True so that it
    survives rerolls and surfaces with the 'Requested' badge (§A6)."""
    supabase, _ = fakes
    user_id = str(uuid4())
    node_id = str(uuid4())
    problem_id = str(uuid4())
    sibling_problem_id = str(uuid4())
    queue_item_id = str(uuid4())
    new_queue_item_id = str(uuid4())

    _prime_queue_item(supabase, queue_item_id=queue_item_id, problem_id=problem_id)
    _prime_problem(
        supabase, problem_id=problem_id, node_id=node_id, difficulty=3,
        pool_hit_id=sibling_problem_id,
    )
    _prime_node(supabase, node_id=node_id)
    _prime_user_context(supabase)
    supabase.respond("queue_items", "update", lambda _call: [])
    supabase.respond("queue_items", "insert", lambda _call: [{"id": new_queue_item_id}])

    resp = client.post(
        "/generate-sibling",
        json={"user_id": user_id, "queue_item_id": queue_item_id, "kind": "harder"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text

    insert_calls = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(insert_calls) == 1
    assert insert_calls[0].payload.get("pinned") is True
