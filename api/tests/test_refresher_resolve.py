"""Tests for POST /refresher-resolve."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from main import app
from supabase_client import get_supabase_client
from tests.fake_supabase import FakeSupabase

INTERNAL_TOKEN = "test-internal-token"
AUTH_HEADERS = {"Authorization": f"Bearer {INTERNAL_TOKEN}"}


@pytest.fixture
def supabase() -> FakeSupabase:
    fs = FakeSupabase()
    app.dependency_overrides[get_supabase_client] = lambda: fs
    try:
        yield fs
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(supabase) -> TestClient:  # noqa: ARG001
    return TestClient(app)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/refresher-resolve",
        json={"user_id": str(uuid4()), "queue_item_id": str(uuid4())},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_queue_item_not_found_returns_404(
    client: TestClient, supabase: FakeSupabase
) -> None:
    supabase.respond("queue_items", "select", lambda _: [])
    resp = client.post(
        "/refresher-resolve",
        json={"user_id": str(uuid4()), "queue_item_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


def test_wrong_kind_returns_400(client: TestClient, supabase: FakeSupabase) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "problem",
                "ref_id": str(uuid4()),
                "state": "pending",
            }
        ],
    )
    resp = client.post(
        "/refresher-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    assert "refresher" in resp.json()["detail"]


def test_already_done_returns_409(client: TestClient, supabase: FakeSupabase) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "refresher",
                "ref_id": str(uuid4()),
                "state": "done",
            }
        ],
    )
    resp = client.post(
        "/refresher-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Curator-style: ref_id is a node, pool hit → kind='problem'
# ---------------------------------------------------------------------------


def test_curator_pool_hit_enqueues_problem(
    client: TestClient, supabase: FakeSupabase
) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    node_id = str(uuid4())
    problem_id = str(uuid4())
    new_qi_id = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "refresher",
                "ref_id": node_id,
                "state": "pending",
            }
        ],
    )
    # Legacy refresher_schedule miss → falls through to curator-node path
    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond(
        "nodes",
        "select",
        lambda _: [{"id": node_id, "title": "Multivariable Calculus"}],
    )
    supabase.respond(
        "problems",
        "select",
        lambda _: [{"id": problem_id, "tags": []}],
    )
    supabase.respond("queue_items", "insert", lambda _: [{"id": new_qi_id}])
    supabase.respond("queue_items", "update", lambda _: [{"id": qi_id}])

    resp = client.post(
        "/refresher-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "problem"
    assert data["queue_item_id"] == new_qi_id

    # Pool lookup at intent='refresh', difficulty=1
    problem_selects = [c for c in supabase.calls if c.table == "problems" and c.op == "select"]
    assert len(problem_selects) == 1
    assert ("eq", "intent", "refresh") in problem_selects[0].filters
    assert ("eq", "difficulty", 1) in problem_selects[0].filters
    assert ("eq", "topic_node_id", node_id) in problem_selects[0].filters

    # Inserted a problem queue item pointing at the pool problem
    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 1
    assert inserts[0].payload["kind"] == "problem"
    assert inserts[0].payload["ref_id"] == problem_id
    assert inserts[0].payload["state"] == "pending"

    # Original refresher row marked done
    updates = [c for c in supabase.calls if c.table == "queue_items" and c.op == "update"]
    assert len(updates) == 1
    assert updates[0].payload["state"] == "done"
    assert ("eq", "id", qi_id) in updates[0].filters


# ---------------------------------------------------------------------------
# Curator-style: ref_id is a node, pool miss → kind='concept_review'
# ---------------------------------------------------------------------------


def test_curator_pool_miss_enqueues_concept_review(
    client: TestClient, supabase: FakeSupabase
) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    node_id = str(uuid4())
    new_qi_id = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "refresher",
                "ref_id": node_id,
                "state": "pending",
            }
        ],
    )
    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond(
        "nodes",
        "select",
        lambda _: [{"id": node_id, "title": "Statistical Mechanics"}],
    )
    supabase.respond("problems", "select", lambda _: [])  # pool miss
    supabase.respond("queue_items", "insert", lambda _: [{"id": new_qi_id}])
    supabase.respond("queue_items", "update", lambda _: [{"id": qi_id}])

    resp = client.post(
        "/refresher-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "concept_review"
    assert data["queue_item_id"] == new_qi_id

    # Inserted a concept_review queue item pointing at the same node
    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 1
    assert inserts[0].payload["kind"] == "concept_review"
    assert inserts[0].payload["ref_id"] == node_id

    # Original refresher row marked done
    updates = [c for c in supabase.calls if c.table == "queue_items" and c.op == "update"]
    assert len(updates) == 1
    assert updates[0].payload["state"] == "done"


# ---------------------------------------------------------------------------
# Curator-style: ref_id matches neither schedule nor node → 404
# ---------------------------------------------------------------------------


def test_unknown_ref_id_returns_404(
    client: TestClient, supabase: FakeSupabase
) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "refresher",
                "ref_id": str(uuid4()),
                "state": "pending",
            }
        ],
    )
    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("nodes", "select", lambda _: [])

    resp = client.post(
        "/refresher-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Legacy refresher_schedule with subject_kind='attempt' → kind='problem'
# ---------------------------------------------------------------------------


def test_legacy_attempt_subject_enqueues_problem(
    client: TestClient, supabase: FakeSupabase
) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    schedule_id = str(uuid4())
    attempt_id = str(uuid4())
    problem_id = str(uuid4())
    new_qi_id = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "refresher",
                "ref_id": schedule_id,
                "state": "pending",
            }
        ],
    )
    supabase.respond(
        "refresher_schedule",
        "select",
        lambda _: [{"subject_kind": "attempt", "subject_ref_id": attempt_id}],
    )
    supabase.respond(
        "attempts",
        "select",
        lambda _: [{"problem_id": problem_id}],
    )
    supabase.respond("queue_items", "insert", lambda _: [{"id": new_qi_id}])
    supabase.respond("queue_items", "update", lambda _: [{"id": qi_id}])

    resp = client.post(
        "/refresher-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "problem"
    assert data["queue_item_id"] == new_qi_id

    # A fresh problem queue_items row points at the original problem id
    # (not the original queue_item, which would be in state='done').
    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 1
    assert inserts[0].payload["kind"] == "problem"
    assert inserts[0].payload["ref_id"] == problem_id


# ---------------------------------------------------------------------------
# Refresher with no ref_id → 400
# ---------------------------------------------------------------------------


def test_missing_ref_id_returns_400(
    client: TestClient, supabase: FakeSupabase
) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "refresher",
                "ref_id": None,
                "state": "pending",
            }
        ],
    )
    resp = client.post(
        "/refresher-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
