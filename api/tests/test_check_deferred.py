"""Tests for POST /check-deferred (Phase 10-rev Step 3c).

Deterministic, no LLM. Coverage:
  - 401 plumbing.
  - Empty queue → no writes.
  - All prereqs addressed (comfortable) → re-queue.
  - All prereqs addressed (struggle_score < 0.3, engagement_count >= 2) → re-queue.
  - One unaddressed prereq → stays deferred.
  - Zero prerequisite edges → re-queue unconditionally.
"""

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
    resp = client.post("/check-deferred", json={"user_id": str(uuid4())})
    assert resp.status_code == 401


def test_no_deferred_items_returns_zero(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("queue_items", "select", lambda _c: [])
    resp = client.post(
        "/check-deferred",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"requeued_count": 0, "kept_deferred_count": 0}


def test_all_prereqs_comfortable_requeues(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    deferred_queue_id = str(uuid4())
    problem_id = str(uuid4())
    topic_node_id = str(uuid4())
    prereq_a = str(uuid4())
    prereq_b = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _c: [{"id": deferred_queue_id, "kind": "problem", "ref_id": problem_id}],
    )
    supabase.respond(
        "problems",
        "select",
        lambda _c: [{"id": problem_id, "topic_node_id": topic_node_id}],
    )
    supabase.respond(
        "edges",
        "select",
        lambda _c: [
            {"source_node_id": prereq_a},
            {"source_node_id": prereq_b},
        ],
    )
    supabase.respond(
        "user_node_states",
        "select",
        lambda _c: [
            {
                "node_id": prereq_a,
                "state": "comfortable",
                "struggle_score": 0.05,
                "engagement_count": 4,
            },
            {
                "node_id": prereq_b,
                "state": "comfortable",
                "struggle_score": 0.1,
                "engagement_count": 3,
            },
        ],
    )
    supabase.respond(
        "queue_items", "update", lambda _c: [{"id": deferred_queue_id}]
    )

    resp = client.post(
        "/check-deferred",
        json={"user_id": user_id},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"requeued_count": 1, "kept_deferred_count": 0}

    updates = [
        c for c in supabase.calls if c.table == "queue_items" and c.op == "update"
    ]
    assert len(updates) == 1
    assert updates[0].payload["state"] == "pending"
    assert updates[0].payload["priority_score"] == 0.55
    # deferred_at is preserved (not in the update payload).
    assert "deferred_at" not in updates[0].payload
    assert ("eq", "id", deferred_queue_id) in updates[0].filters


def test_addressed_via_struggle_threshold(client: TestClient, fakes) -> None:
    """active state with struggle_score<0.3 + engagement_count>=2 counts."""
    supabase, _ = fakes
    deferred_queue_id = str(uuid4())
    problem_id = str(uuid4())
    topic_node_id = str(uuid4())
    prereq = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _c: [{"id": deferred_queue_id, "kind": "problem", "ref_id": problem_id}],
    )
    supabase.respond(
        "problems",
        "select",
        lambda _c: [{"id": problem_id, "topic_node_id": topic_node_id}],
    )
    supabase.respond("edges", "select", lambda _c: [{"source_node_id": prereq}])
    supabase.respond(
        "user_node_states",
        "select",
        lambda _c: [
            {
                "node_id": prereq,
                "state": "active",  # not 'comfortable'
                "struggle_score": 0.25,  # < 0.3
                "engagement_count": 3,   # >= 2
            }
        ],
    )
    supabase.respond(
        "queue_items", "update", lambda _c: [{"id": deferred_queue_id}]
    )

    resp = client.post(
        "/check-deferred",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"requeued_count": 1, "kept_deferred_count": 0}


def test_one_unaddressed_prereq_keeps_deferred(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    deferred_queue_id = str(uuid4())
    problem_id = str(uuid4())
    topic_node_id = str(uuid4())
    prereq_a = str(uuid4())
    prereq_b = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _c: [{"id": deferred_queue_id, "kind": "problem", "ref_id": problem_id}],
    )
    supabase.respond(
        "problems",
        "select",
        lambda _c: [{"id": problem_id, "topic_node_id": topic_node_id}],
    )
    supabase.respond(
        "edges",
        "select",
        lambda _c: [
            {"source_node_id": prereq_a},
            {"source_node_id": prereq_b},
        ],
    )
    supabase.respond(
        "user_node_states",
        "select",
        lambda _c: [
            {
                "node_id": prereq_a,
                "state": "comfortable",
                "struggle_score": 0.05,
                "engagement_count": 5,
            },
            # prereq_b: no row → not addressed (defaults absent)
        ],
    )

    resp = client.post(
        "/check-deferred",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"requeued_count": 0, "kept_deferred_count": 1}

    updates = [
        c for c in supabase.calls if c.table == "queue_items" and c.op == "update"
    ]
    assert updates == []


def test_no_prereq_edges_requeues_unconditionally(
    client: TestClient, fakes
) -> None:
    """A deferred problem on a topic with no prerequisite edges has nothing
    blocking it — re-queue."""
    supabase, _ = fakes
    deferred_queue_id = str(uuid4())
    problem_id = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _c: [{"id": deferred_queue_id, "kind": "problem", "ref_id": problem_id}],
    )
    supabase.respond(
        "problems",
        "select",
        lambda _c: [{"id": problem_id, "topic_node_id": str(uuid4())}],
    )
    supabase.respond("edges", "select", lambda _c: [])  # zero prereq edges
    supabase.respond(
        "queue_items", "update", lambda _c: [{"id": deferred_queue_id}]
    )

    resp = client.post(
        "/check-deferred",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"requeued_count": 1, "kept_deferred_count": 0}


def test_no_llm_call_made(client: TestClient, fakes) -> None:
    """/check-deferred is deterministic — no anthropic call, ever."""
    supabase, anthropic = fakes
    supabase.respond("queue_items", "select", lambda _c: [])

    resp = client.post(
        "/check-deferred",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert anthropic.messages.calls == []
    assert not any(c.table == "llm_calls" for c in supabase.calls)
