"""Tests for POST /concept-review-resolve."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from main import app
from supabase_client import get_supabase_client
from tests.fake_supabase import FakeSupabase

INTERNAL_TOKEN = "test-internal-token"
AUTH_HEADERS = {"Authorization": f"Bearer {INTERNAL_TOKEN}"}


def _cycler(*payloads):
    items = list(payloads)
    idx = [0]

    def _fn(_call):
        if idx[0] < len(items):
            result = items[idx[0]]
            idx[0] += 1
            return result
        return []

    return _fn


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
        "/concept-review-resolve",
        json={"user_id": str(uuid4()), "queue_item_id": str(uuid4())},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Validation: wrong kind
# ---------------------------------------------------------------------------


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
        "/concept-review-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    assert "concept_review" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Validation: not found
# ---------------------------------------------------------------------------


def test_queue_item_not_found_returns_404(
    client: TestClient, supabase: FakeSupabase
) -> None:
    supabase.respond("queue_items", "select", lambda _: [])

    resp = client.post(
        "/concept-review-resolve",
        json={"user_id": str(uuid4()), "queue_item_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Already done → 409
# ---------------------------------------------------------------------------


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
                "kind": "concept_review",
                "ref_id": str(uuid4()),
                "state": "done",
            }
        ],
    )

    resp = client.post(
        "/concept-review-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Pool hit → enqueues kind='problem' + marks concept_review done
# ---------------------------------------------------------------------------


def test_pool_hit_enqueues_problem_and_marks_done(
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
                "kind": "concept_review",
                "ref_id": node_id,
                "state": "pending",
            }
        ],
    )
    supabase.respond(
        "nodes",
        "select",
        lambda _: [
            {
                "id": node_id,
                "slug": "classical-mechanics",
                "title": "Classical Mechanics",
                "description_md": "Newton's laws and friends.",
                "subtopics_json": [
                    {"slug": "power", "title": "Power"},
                    {"slug": "work", "title": "Work"},
                ],
            }
        ],
    )
    # problems.select for the pool lookup → returns one match
    supabase.respond(
        "problems",
        "select",
        lambda _: [{"id": problem_id, "tags": ["classical-mechanics", "power"]}],
    )
    supabase.respond("queue_items", "insert", lambda _: [{"id": new_qi_id}])
    supabase.respond("queue_items", "update", lambda _: [{"id": qi_id}])

    resp = client.post(
        "/concept-review-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "problem"
    assert data["queue_item_id"] == new_qi_id
    assert data["node"] is None

    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 1
    assert inserts[0].payload["kind"] == "problem"
    assert inserts[0].payload["ref_id"] == problem_id
    assert inserts[0].payload["state"] == "pending"

    updates = [c for c in supabase.calls if c.table == "queue_items" and c.op == "update"]
    assert len(updates) == 1
    assert updates[0].payload["state"] == "done"
    # The update targets the original concept_review row
    assert ("eq", "id", qi_id) in updates[0].filters

    # Pool lookup must have filtered by primary subtopic 'power'
    problem_selects = [c for c in supabase.calls if c.table == "problems" and c.op == "select"]
    assert len(problem_selects) == 1
    assert ("contains", "tags", ["power"]) in problem_selects[0].filters
    assert ("eq", "difficulty", 1) in problem_selects[0].filters
    assert ("eq", "intent", "teach") in problem_selects[0].filters


# ---------------------------------------------------------------------------
# Pool miss → returns reading surface, no mutations
# ---------------------------------------------------------------------------


def test_pool_miss_returns_reading(
    client: TestClient, supabase: FakeSupabase
) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    node_id = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "concept_review",
                "ref_id": node_id,
                "state": "pending",
            }
        ],
    )
    supabase.respond(
        "nodes",
        "select",
        lambda _: [
            {
                "id": node_id,
                "slug": "general-relativity",
                "title": "General Relativity",
                "description_md": "Geometry of spacetime.",
                "subtopics_json": [{"slug": "metric-tensor", "title": "Metric tensor"}],
            }
        ],
    )
    # Pool lookup returns nothing
    supabase.respond("problems", "select", lambda _: [])

    resp = client.post(
        "/concept-review-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "reading"
    assert data["queue_item_id"] is None
    assert data["node"]["slug"] == "general-relativity"
    assert data["node"]["description_md"] == "Geometry of spacetime."
    assert data["node"]["subtopics_json"] == [
        {"slug": "metric-tensor", "title": "Metric tensor"}
    ]

    # No mutations on miss
    assert not any(c.op in ("insert", "update") for c in supabase.calls)


# ---------------------------------------------------------------------------
# Null / empty subtopics_json → pool lookup runs without subtopic filter
# ---------------------------------------------------------------------------


def test_null_subtopics_runs_pool_lookup_without_filter(
    client: TestClient, supabase: FakeSupabase
) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    node_id = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "concept_review",
                "ref_id": node_id,
                "state": "pending",
            }
        ],
    )
    supabase.respond(
        "nodes",
        "select",
        lambda _: [
            {
                "id": node_id,
                "slug": "thermodynamics",
                "title": "Thermodynamics",
                "description_md": "",
                "subtopics_json": None,  # null on this row
            }
        ],
    )
    supabase.respond("problems", "select", lambda _: [])

    resp = client.post(
        "/concept-review-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "reading"
    assert data["node"]["subtopics_json"] == []

    problem_selects = [c for c in supabase.calls if c.table == "problems" and c.op == "select"]
    assert len(problem_selects) == 1
    # No `contains` filter applied when subtopic_slug is None
    assert not any(f[0] == "contains" for f in problem_selects[0].filters)
