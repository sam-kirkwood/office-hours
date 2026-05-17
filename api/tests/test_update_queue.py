"""Tests for POST /update-queue."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from anthropic_client import get_anthropic_client
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


def _ts(dt: datetime) -> str:
    return dt.isoformat()


@pytest.fixture
def fakes() -> tuple[FakeSupabase, None]:
    fs = FakeSupabase()
    app.dependency_overrides[get_supabase_client] = lambda: fs
    # update_queue makes no LLM calls — no anthropic override needed
    try:
        yield fs, None
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(fakes) -> TestClient:  # noqa: ARG001
    return TestClient(app)


def _base_body(user_id: str | None = None) -> dict:
    return {
        "user_id": user_id or str(uuid4()),
        "trigger": "attempt_submit",
        "ref_id": str(uuid4()),
    }


def _empty_queue_stubs(supabase: FakeSupabase, user_id: str) -> None:
    """Register no-op responses for all tables touched when queue is empty."""
    supabase.respond("queue_items", "select", lambda _: [])
    supabase.respond("notebook_entries", "select", lambda _: [])
    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("profiles", "select", lambda _: [])
    supabase.respond("queue_items", "delete", lambda _: [])


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post("/update-queue", json=_base_body())
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Empty queue — all counts zero, no errors
# ---------------------------------------------------------------------------


def test_no_items_returns_zeros(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    _empty_queue_stubs(supabase, user_id)

    resp = client.post("/update-queue", json=_base_body(user_id), headers=AUTH_HEADERS)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["items_reweighted"] == 0
    assert data["refreshers_scheduled"] == 0
    assert data["items_pruned"] == 0


# ---------------------------------------------------------------------------
# Refresher scheduling — older than 10 days
# ---------------------------------------------------------------------------


def test_refresher_scheduled_after_10_days(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    ref_id = str(uuid4())
    now = datetime.now(timezone.utc)
    old_created_at = _ts(now - timedelta(days=15))

    supabase.respond("queue_items", "select", lambda _: [])
    supabase.respond(
        "notebook_entries",
        "select",
        lambda _: [{"id": str(uuid4()), "entry_kind": "problem_attempt", "ref_id": ref_id, "created_at": old_created_at}],
    )
    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("profiles", "select", lambda _: [])
    supabase.respond("refresher_schedule", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("queue_items", "delete", lambda _: [])

    resp = client.post("/update-queue", json=_base_body(user_id), headers=AUTH_HEADERS)

    assert resp.status_code == 200, resp.text
    assert resp.json()["refreshers_scheduled"] == 1

    insert_calls = [c for c in supabase.calls if c.table == "refresher_schedule" and c.op == "insert"]
    assert len(insert_calls) == 1
    payload = insert_calls[0].payload
    assert payload["subject_kind"] == "attempt"
    assert payload["subject_ref_id"] == ref_id
    assert payload["user_id"] == user_id


# ---------------------------------------------------------------------------
# Refresher NOT scheduled — entry younger than 10 days
# ---------------------------------------------------------------------------


def test_refresher_not_scheduled_before_10_days(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    ref_id = str(uuid4())
    now = datetime.now(timezone.utc)
    recent_created_at = _ts(now - timedelta(days=5))

    supabase.respond("queue_items", "select", lambda _: [])
    supabase.respond(
        "notebook_entries",
        "select",
        lambda _: [{"id": str(uuid4()), "entry_kind": "problem_attempt", "ref_id": ref_id, "created_at": recent_created_at}],
    )
    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("profiles", "select", lambda _: [])
    supabase.respond("queue_items", "delete", lambda _: [])

    resp = client.post("/update-queue", json=_base_body(user_id), headers=AUTH_HEADERS)

    assert resp.status_code == 200, resp.text
    assert resp.json()["refreshers_scheduled"] == 0

    insert_calls = [c for c in supabase.calls if c.table == "refresher_schedule" and c.op == "insert"]
    assert len(insert_calls) == 0


# ---------------------------------------------------------------------------
# Priority boost — struggling node raises problem score
# ---------------------------------------------------------------------------


def test_struggling_node_boosts_problem_priority(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    problem_id = str(uuid4())
    node_id = str(uuid4())
    item_id = str(uuid4())

    problem_item = {
        "id": item_id,
        "kind": "problem",
        "ref_id": problem_id,
        "priority_score": 0.5,
        "state": "pending",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Step 2: load active items
    supabase.respond(
        "queue_items",
        "select",
        _cycler([problem_item], [problem_item]),  # step 2 + step 6 dedup
    )
    # Step 3: problem → topic_node_id lookup
    supabase.respond("problems", "select", lambda _: [{"topic_node_id": node_id}])
    # Step 3: node state lookup
    supabase.respond("user_node_states", "select", lambda _: [{"state": "struggling"}])
    # Step 3: update priority_score
    supabase.respond("queue_items", "update", lambda _: [])
    # Step 4: notebook entries, schedule, profile
    supabase.respond("notebook_entries", "select", lambda _: [])
    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("profiles", "select", lambda _: [])
    # Step 6: delete and dedup
    supabase.respond("queue_items", "delete", lambda _: [])

    resp = client.post("/update-queue", json=_base_body(user_id), headers=AUTH_HEADERS)

    assert resp.status_code == 200, resp.text
    assert resp.json()["items_reweighted"] == 1

    update_calls = [c for c in supabase.calls if c.table == "queue_items" and c.op == "update"]
    assert len(update_calls) == 1
    assert update_calls[0].payload["priority_score"] == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Prune — done items older than 30 days are deleted
# ---------------------------------------------------------------------------


def test_done_items_pruned_after_30_days(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    old_id = str(uuid4())

    # Step 2: no pending/surfaced items
    supabase.respond(
        "queue_items",
        "select",
        _cycler([], []),  # step 2 + step 6 dedup
    )
    # Step 4
    supabase.respond("notebook_entries", "select", lambda _: [])
    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("profiles", "select", lambda _: [])
    # Step 6: bulk delete returns 1 deleted row
    supabase.respond("queue_items", "delete", lambda _: [{"id": old_id}])

    resp = client.post("/update-queue", json=_base_body(user_id), headers=AUTH_HEADERS)

    assert resp.status_code == 200, resp.text
    assert resp.json()["items_pruned"] == 1

    delete_calls = [c for c in supabase.calls if c.table == "queue_items" and c.op == "delete"]
    assert len(delete_calls) == 1
    filters = {f[1]: f[2] for f in delete_calls[0].filters}
    assert filters.get("user_id") == user_id
    assert "done" in filters.get("state", [])


# ---------------------------------------------------------------------------
# Dedup — duplicate pending items: lower priority one deleted
# ---------------------------------------------------------------------------


def test_duplicate_pending_items_pruned(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    ref_id = str(uuid4())
    item_id_high = str(uuid4())
    item_id_low = str(uuid4())

    item_high = {
        "id": item_id_high,
        "kind": "paper_engagement",
        "ref_id": ref_id,
        "priority_score": 0.6,
        "state": "pending",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    item_low = {
        "id": item_id_low,
        "kind": "paper_engagement",
        "ref_id": ref_id,
        "priority_score": 0.3,
        "state": "pending",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Step 2 and step 6 dedup both call queue_items.select
    supabase.respond(
        "queue_items",
        "select",
        _cycler([item_high, item_low], [item_high, item_low]),
    )
    # Step 3: paper_engagement has no node lookup — just reweight updates
    supabase.respond("queue_items", "update", lambda _: [])
    # Step 4
    supabase.respond("notebook_entries", "select", lambda _: [])
    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("profiles", "select", lambda _: [])
    # Step 6: bulk delete (old done items) returns nothing; dupe delete also registered
    supabase.respond("queue_items", "delete", lambda _: [])

    resp = client.post("/update-queue", json=_base_body(user_id), headers=AUTH_HEADERS)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["items_pruned"] == 1  # one dupe deleted

    # The dupe delete targets the lower-priority item
    delete_calls = [c for c in supabase.calls if c.table == "queue_items" and c.op == "delete"]
    # Last delete call (or the one with eq on "id") is the dupe delete
    dupe_deletes = [
        c for c in delete_calls
        if any(f[1] == "id" for f in c.filters)
    ]
    assert len(dupe_deletes) == 1
    deleted_id = next(f[2] for f in dupe_deletes[0].filters if f[1] == "id")
    assert deleted_id == item_id_low


# ---------------------------------------------------------------------------
# _recompute_node_state — state transitions (step 4)
# ---------------------------------------------------------------------------
#
# All four tests use trigger='attempt_submit' and an explicit ref_id so the
# route exercises the node-state recomputation path. The sequence of
# (table, op) calls for that path is:
#   attempts.select  → {problem_id}          (trigger lookup)
#   problems.select  → {topic_node_id}       (trigger lookup)
#   problems.select  → [{id: problem_id}]    (_recompute: problems for node)
#   attempts.select  → [{hint_levels_used}…] (_recompute: last 5 attempts)
#   user_node_states.select                  (_recompute: current state)
#   user_node_states.upsert                  (_recompute: write new state)


def _node_recompute_body(user_id: str, ref_id: str) -> dict:
    return {"user_id": user_id, "trigger": "attempt_submit", "ref_id": ref_id}


def _common_empty_stubs(supabase: FakeSupabase) -> None:
    """Register stubs for the parts of update_queue that are empty/no-op."""
    supabase.respond("queue_items", "select", lambda _: [])
    supabase.respond("notebook_entries", "select", lambda _: [])
    supabase.respond("profiles", "select", lambda _: [])
    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("queue_items", "delete", lambda _: [])


def test_first_engagement_transitions_unseen_to_active(
    client: TestClient, fakes
) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    attempt_id = str(uuid4())
    problem_id = str(uuid4())
    node_id = str(uuid4())

    _common_empty_stubs(supabase)

    # Trigger lookup: attempt → problem_id; _recompute: problems for node
    supabase.respond(
        "attempts",
        "select",
        _cycler(
            [{"problem_id": problem_id}],   # trigger: attempt_id → problem_id
            [{"hint_levels_used": []}],     # _recompute: 1 clean attempt
        ),
    )
    supabase.respond(
        "problems",
        "select",
        _cycler(
            [{"topic_node_id": node_id}],   # trigger: problem_id → node_id
            [{"id": problem_id}],           # _recompute: problem IDs for node
        ),
    )
    supabase.respond("user_node_states", "select", lambda _: [])  # no existing row
    supabase.respond("user_node_states", "upsert", lambda _: [])

    resp = client.post(
        "/update-queue",
        json=_node_recompute_body(user_id, attempt_id),
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text

    upserts = [c for c in supabase.calls if c.table == "user_node_states" and c.op == "upsert"]
    assert len(upserts) == 1
    payload = upserts[0].payload
    assert payload["state"] == "active"
    assert payload["engagement_count"] == 1
    assert payload["struggle_score"] == pytest.approx(0.0)


def test_high_hint_usage_transitions_to_struggling(
    client: TestClient, fakes
) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    attempt_id = str(uuid4())
    problem_id = str(uuid4())
    node_id = str(uuid4())

    _common_empty_stubs(supabase)

    hinted_attempts = [
        {"hint_levels_used": [1]},
        {"hint_levels_used": [1]},
        {"hint_levels_used": [1]},
        {"hint_levels_used": []},
        {"hint_levels_used": []},
    ]  # 3 of 5 used hints → struggle_score = 0.6

    supabase.respond(
        "attempts",
        "select",
        _cycler([{"problem_id": problem_id}], hinted_attempts),
    )
    supabase.respond(
        "problems",
        "select",
        _cycler([{"topic_node_id": node_id}], [{"id": problem_id}]),
    )
    # Current state: active, engagement_count=1 → after increment: 2
    supabase.respond(
        "user_node_states",
        "select",
        lambda _: [{"state": "active", "engagement_count": 1}],
    )
    supabase.respond("user_node_states", "upsert", lambda _: [])

    resp = client.post(
        "/update-queue",
        json=_node_recompute_body(user_id, attempt_id),
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text

    upserts = [c for c in supabase.calls if c.table == "user_node_states" and c.op == "upsert"]
    assert len(upserts) == 1
    payload = upserts[0].payload
    assert payload["state"] == "struggling"
    assert payload["struggle_score"] == pytest.approx(0.6)
    assert payload["engagement_count"] == 2


def test_clean_attempts_transition_to_comfortable(
    client: TestClient, fakes
) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    attempt_id = str(uuid4())
    problem_id = str(uuid4())
    node_id = str(uuid4())

    _common_empty_stubs(supabase)

    clean_attempts = [{"hint_levels_used": []} for _ in range(4)]
    # struggle_score = 0/4 = 0.0; engagement_count: 3 + 1 = 4 ≥ 3 → comfortable

    supabase.respond(
        "attempts",
        "select",
        _cycler([{"problem_id": problem_id}], clean_attempts),
    )
    supabase.respond(
        "problems",
        "select",
        _cycler([{"topic_node_id": node_id}], [{"id": problem_id}]),
    )
    supabase.respond(
        "user_node_states",
        "select",
        lambda _: [{"state": "active", "engagement_count": 3}],
    )
    supabase.respond("user_node_states", "upsert", lambda _: [])

    resp = client.post(
        "/update-queue",
        json=_node_recompute_body(user_id, attempt_id),
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text

    upserts = [c for c in supabase.calls if c.table == "user_node_states" and c.op == "upsert"]
    assert len(upserts) == 1
    payload = upserts[0].payload
    assert payload["state"] == "comfortable"
    assert payload["struggle_score"] == pytest.approx(0.0)
    assert payload["engagement_count"] == 4


def test_comfortable_not_auto_regressed(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    attempt_id = str(uuid4())
    problem_id = str(uuid4())
    node_id = str(uuid4())

    _common_empty_stubs(supabase)

    # Even with heavy hint usage, comfortable stays comfortable
    supabase.respond(
        "attempts",
        "select",
        _cycler(
            [{"problem_id": problem_id}],
            [{"hint_levels_used": [1, 2, 3]}],
        ),
    )
    supabase.respond(
        "problems",
        "select",
        _cycler([{"topic_node_id": node_id}], [{"id": problem_id}]),
    )
    supabase.respond(
        "user_node_states",
        "select",
        lambda _: [{"state": "comfortable", "engagement_count": 5}],
    )
    supabase.respond("user_node_states", "upsert", lambda _: [])

    resp = client.post(
        "/update-queue",
        json=_node_recompute_body(user_id, attempt_id),
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text

    upserts = [c for c in supabase.calls if c.table == "user_node_states" and c.op == "upsert"]
    assert len(upserts) == 1
    assert upserts[0].payload["state"] == "comfortable"
