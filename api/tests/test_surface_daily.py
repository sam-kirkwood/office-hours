"""Tests for POST /surface-daily and POST /update-queue."""

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


def _item(kind: str = "problem", priority: float = 1.0) -> dict:
    return {
        "id": str(uuid4()),
        "kind": kind,
        "ref_id": str(uuid4()),
        "state": "pending",
        "priority_score": priority,
        "time_estimate_minutes_low": 10,
        "time_estimate_minutes_high": 20,
        "added_reason": f"You expressed interest in {kind}.",
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


# ---------------------------------------------------------------------------
# /surface-daily auth
# ---------------------------------------------------------------------------


def test_surface_daily_missing_bearer_returns_401(client: TestClient) -> None:
    response = client.post("/surface-daily", json={"user_id": str(uuid4())})
    assert response.status_code == 401


def test_surface_daily_wrong_bearer_returns_401(client: TestClient) -> None:
    response = client.post(
        "/surface-daily",
        json={"user_id": str(uuid4())},
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# /surface-daily: no pending items → 404
# ---------------------------------------------------------------------------


def test_surface_daily_no_pending_items_returns_404(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("queue_items", "select", lambda _: [])

    response = client.post(
        "/surface-daily",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /surface-daily: happy path — 3 items surfaced with kind variety
# ---------------------------------------------------------------------------


def test_surface_daily_surfaces_up_to_three_with_variety(
    client: TestClient, fakes
) -> None:
    supabase, _ = fakes
    pick_id = str(uuid4())
    items = [
        _item("problem", priority=3.0),
        _item("problem", priority=2.0),
        _item("paper_engagement", priority=1.5),
        _item("concept_review", priority=1.0),
    ]
    supabase.respond("queue_items", "select", lambda _: items)
    supabase.respond("queue_items", "update", lambda _: [])
    supabase.respond("surfaced_picks", "insert", lambda _: [{"id": pick_id}])

    response = client.post(
        "/surface-daily",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pick_id"] == pick_id
    # At most 3 items surfaced.
    assert len(body["items"]) <= 3
    # Kind variety: we should not get only 'problem' if other kinds were available.
    kinds = {it["kind"] for it in body["items"]}
    assert len(kinds) >= 2


# ---------------------------------------------------------------------------
# /surface-daily: fewer than 3 items — surfaces all available
# ---------------------------------------------------------------------------


def test_surface_daily_fewer_than_three_surfaces_all(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    pick_id = str(uuid4())
    items = [_item("problem"), _item("paper_engagement")]
    supabase.respond("queue_items", "select", lambda _: items)
    supabase.respond("queue_items", "update", lambda _: [])
    supabase.respond("surfaced_picks", "insert", lambda _: [{"id": pick_id}])

    response = client.post(
        "/surface-daily",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == 2


# ---------------------------------------------------------------------------
# /surface-daily: selected items are marked 'surfaced'
# ---------------------------------------------------------------------------


def test_surface_daily_marks_items_surfaced(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    pick_id = str(uuid4())
    item = _item("problem")
    supabase.respond("queue_items", "select", lambda _: [item])
    supabase.respond("queue_items", "update", lambda _: [])
    supabase.respond("surfaced_picks", "insert", lambda _: [{"id": pick_id}])

    client.post("/surface-daily", json={"user_id": str(uuid4())}, headers=AUTH_HEADERS)

    update_calls = [c for c in supabase.calls if c.table == "queue_items" and c.op == "update"]
    assert len(update_calls) == 1
    assert update_calls[0].payload == {"state": "surfaced"}
    assert ("eq", "id", item["id"]) in update_calls[0].filters


# ---------------------------------------------------------------------------
# /surface-daily: surfaced_picks row written with correct queue_item_ids
# ---------------------------------------------------------------------------


def test_surface_daily_writes_surfaced_picks_row(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    pick_id = str(uuid4())
    item = _item("problem")
    supabase.respond("queue_items", "select", lambda _: [item])
    supabase.respond("queue_items", "update", lambda _: [])
    supabase.respond("surfaced_picks", "insert", lambda _: [{"id": pick_id}])

    response = client.post(
        "/surface-daily", json={"user_id": str(uuid4())}, headers=AUTH_HEADERS
    )

    assert response.status_code == 200
    sp_inserts = [c for c in supabase.calls if c.table == "surfaced_picks" and c.op == "insert"]
    assert len(sp_inserts) == 1
    assert sp_inserts[0].payload["queue_item_ids"] == [item["id"]]


# ---------------------------------------------------------------------------
# /surface-daily: refresher resolution (step 5)
# ---------------------------------------------------------------------------


def _refresher_item(priority: float = 0.9) -> dict:
    return {
        "id": str(uuid4()),
        "kind": "refresher",
        "ref_id": str(uuid4()),
        "state": "pending",
        "priority_score": priority,
        "time_estimate_minutes_low": 10,
        "time_estimate_minutes_high": 30,
        "added_reason": None,
    }


def test_refresher_item_appears_when_due(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    pick_id = str(uuid4())
    sched_id = str(uuid4())
    attempt_id = str(uuid4())
    problem_id = str(uuid4())
    node_id = str(uuid4())
    orig_qi_id = str(uuid4())

    r_item = _refresher_item()
    r_item["ref_id"] = sched_id

    supabase.respond("queue_items", "select", lambda _: [r_item])
    supabase.respond(
        "refresher_schedule", "select",
        lambda _: [{"subject_kind": "attempt", "subject_ref_id": attempt_id}],
    )
    supabase.respond(
        "attempts", "select",
        lambda _: [{"problem_id": problem_id, "queue_item_id": orig_qi_id}],
    )
    supabase.respond("problems", "select", lambda _: [{"topic_node_id": node_id}])
    supabase.respond("nodes", "select", lambda _: [{"title": "Real Analysis"}])
    supabase.respond("queue_items", "update", lambda _: [])
    supabase.respond("surfaced_picks", "insert", lambda _: [{"id": pick_id}])

    response = client.post(
        "/surface-daily",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["kind"] == "refresher"


def test_refresher_resolved_to_content_title(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    pick_id = str(uuid4())
    sched_id = str(uuid4())
    attempt_id = str(uuid4())
    problem_id = str(uuid4())
    node_id = str(uuid4())
    orig_qi_id = str(uuid4())

    r_item = _refresher_item()
    r_item["ref_id"] = sched_id

    supabase.respond("queue_items", "select", lambda _: [r_item])
    supabase.respond(
        "refresher_schedule", "select",
        lambda _: [{"subject_kind": "attempt", "subject_ref_id": attempt_id}],
    )
    supabase.respond(
        "attempts", "select",
        lambda _: [{"problem_id": problem_id, "queue_item_id": orig_qi_id}],
    )
    supabase.respond("problems", "select", lambda _: [{"topic_node_id": node_id}])
    supabase.respond("nodes", "select", lambda _: [{"title": "Complex Analysis"}])
    supabase.respond("queue_items", "update", lambda _: [])
    supabase.respond("surfaced_picks", "insert", lambda _: [{"id": pick_id}])

    response = client.post(
        "/surface-daily",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["added_reason"] == "A refresher on Complex Analysis."
    assert item["subject_kind"] == "attempt"
    assert item["subject_queue_item_id"] == orig_qi_id


def test_refresher_priority_above_problem(client: TestClient, fakes) -> None:
    """Refresher (0.9) surfaces when competing with problems (0.5/0.3/0.2)."""
    supabase, _ = fakes
    pick_id = str(uuid4())
    sched_id = str(uuid4())
    attempt_id = str(uuid4())
    problem_id = str(uuid4())
    node_id = str(uuid4())
    orig_qi_id = str(uuid4())

    r_item = _refresher_item(priority=0.9)
    r_item["ref_id"] = sched_id
    p1 = _item("problem", priority=0.5)
    p2 = _item("problem", priority=0.3)
    p3 = _item("problem", priority=0.2)

    # Items ordered by priority desc (as the DB query would return)
    supabase.respond("queue_items", "select", lambda _: [r_item, p1, p2, p3])
    supabase.respond(
        "refresher_schedule", "select",
        lambda _: [{"subject_kind": "attempt", "subject_ref_id": attempt_id}],
    )
    supabase.respond(
        "attempts", "select",
        lambda _: [{"problem_id": problem_id, "queue_item_id": orig_qi_id}],
    )
    supabase.respond("problems", "select", lambda _: [{"topic_node_id": node_id}])
    supabase.respond("nodes", "select", lambda _: [{"title": "Topology"}])
    supabase.respond("queue_items", "update", lambda _: [])
    supabase.respond("surfaced_picks", "insert", lambda _: [{"id": pick_id}])

    response = client.post(
        "/surface-daily",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    kinds = [it["kind"] for it in body["items"]]
    assert "refresher" in kinds


# ---------------------------------------------------------------------------
# /update-queue smoke tests (full coverage in test_update_queue.py)
# ---------------------------------------------------------------------------


def test_update_queue_missing_bearer_returns_401(client: TestClient) -> None:
    response = client.post(
        "/update-queue",
        json={"user_id": str(uuid4()), "trigger": "interest_add"},
    )
    assert response.status_code == 401


def test_update_queue_returns_ok(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    supabase.respond("queue_items", "select", lambda _: [])
    supabase.respond("notebook_entries", "select", lambda _: [])
    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("profiles", "select", lambda _: [])
    supabase.respond("queue_items", "delete", lambda _: [])

    response = client.post(
        "/update-queue",
        json={"user_id": user_id, "trigger": "interest_add"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items_reweighted"] == 0
    assert data["refreshers_scheduled"] == 0
    assert data["items_pruned"] == 0
