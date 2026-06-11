"""Tests for POST /surface-daily."""

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
# /surface-daily: F17 starter fallback only fires for a genuinely empty account
# (Phase 10.5-rev d16 — the fallback used to re-mint a concept on every empty
# surface, spamming the queue with duplicates).
# ---------------------------------------------------------------------------


def test_f17_skipped_when_user_has_queue_items(client: TestClient, fakes) -> None:
    """Pending is empty but the user has other (e.g. done) queue rows → the
    starter fallback must NOT fire; no insert, plain 404."""
    supabase, _ = fakes

    def queue_items_select(call):
        # The pending load filters on state='pending' → empty.
        if any(f[1] == "state" for f in call.filters):
            return []
        # The "has any rows?" probe → the user does have history.
        return [{"id": str(uuid4())}]

    supabase.respond("queue_items", "select", queue_items_select)

    response = client.post(
        "/surface-daily",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404
    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert not inserts


def test_surface_daily_reports_pending_remaining(client: TestClient, fakes) -> None:
    """pending_remaining = pending items left after this pick. Drives the web
    layer's refill-on-drain."""
    supabase, _ = fakes
    pick_id = str(uuid4())
    items = [
        _item("problem", priority=3.0),
        _item("problem", priority=2.5),
        _item("paper_engagement", priority=2.0),
        _item("problem", priority=1.5),
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
    assert len(body["items"]) == 3
    assert body["pending_remaining"] == 2


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
# /surface-daily: refreshers are concrete items (problem / concept_review /
# paper_engagement) carrying via_refresher=true, resolved at creation time (see
# routes/refresher.py). surface-daily passes the flag through so the daily card
# can render the "Refresher" framing while routing by the item's real kind.
# ---------------------------------------------------------------------------


def _refresher_item(priority: float = 0.9) -> dict:
    return {
        "id": str(uuid4()),
        "kind": "problem",
        "ref_id": str(uuid4()),
        "state": "pending",
        "priority_score": priority,
        "time_estimate_minutes_low": 10,
        "time_estimate_minutes_high": 30,
        "added_reason": "A refresher on this topic.",
        "via_refresher": True,
    }


def test_refresher_item_surfaces_with_flag(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    pick_id = str(uuid4())
    r_item = _refresher_item()

    supabase.respond("queue_items", "select", lambda _: [r_item])
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
    item = body["items"][0]
    # Routes as a problem; the via_refresher flag drives the badge/copy.
    assert item["kind"] == "problem"
    assert item["via_refresher"] is True
    # added_reason is passed through verbatim from the queue_items row.
    assert item["added_reason"] == "A refresher on this topic."


def test_plain_item_is_not_via_refresher(client: TestClient, fakes) -> None:
    """A normal queue item reports via_refresher=false (default)."""
    supabase, _ = fakes
    pick_id = str(uuid4())
    item = _item("problem")

    supabase.respond("queue_items", "select", lambda _: [item])
    supabase.respond("queue_items", "update", lambda _: [])
    supabase.respond("surfaced_picks", "insert", lambda _: [{"id": pick_id}])

    response = client.post(
        "/surface-daily", json={"user_id": str(uuid4())}, headers=AUTH_HEADERS
    )
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["via_refresher"] is False


def test_refresher_priority_above_problem(client: TestClient, fakes) -> None:
    """A high-priority refresher (0.9) surfaces over lower-priority problems."""
    supabase, _ = fakes
    pick_id = str(uuid4())

    r_item = _refresher_item(priority=0.9)
    p1 = _item("problem", priority=0.5)
    p2 = _item("problem", priority=0.3)
    p3 = _item("problem", priority=0.2)

    # Items ordered by priority desc (as the DB query would return)
    supabase.respond("queue_items", "select", lambda _: [r_item, p1, p2, p3])
    supabase.respond("queue_items", "update", lambda _: [])
    supabase.respond("surfaced_picks", "insert", lambda _: [{"id": pick_id}])

    response = client.post(
        "/surface-daily",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    surfaced_ids = [it["queue_item_id"] for it in body["items"]]
    assert r_item["id"] in surfaced_ids
    assert any(it.get("via_refresher") for it in body["items"])




# ---------------------------------------------------------------------------
# Phase 10-rev Step 9a — ref_id dedup in variety filter
# ---------------------------------------------------------------------------


def _item_with_ref(kind: str, ref_id: str, priority: float = 1.0) -> dict:
    return {
        "id": str(uuid4()),
        "kind": kind,
        "ref_id": ref_id,
        "state": "pending",
        "priority_score": priority,
        "time_estimate_minutes_low": 10,
        "time_estimate_minutes_high": 20,
        "added_reason": f"You expressed interest in {kind}.",
    }


def test_surface_daily_dedups_on_ref_id(client: TestClient, fakes) -> None:
    """Two queue items pointing at the same problem (curator dup that
    slipped through the dedup at /plan-queue time) only contribute one
    slot to the daily three. The variety filter now checks ref_id in
    addition to kind."""
    supabase, _ = fakes
    pick_id = str(uuid4())
    shared_ref = str(uuid4())
    other_ref = str(uuid4())
    third_ref = str(uuid4())
    items = [
        _item_with_ref("problem", shared_ref, priority=3.0),
        _item_with_ref("problem", shared_ref, priority=2.0),  # dup
        _item_with_ref("problem", other_ref, priority=1.5),
        _item_with_ref("refresher", third_ref, priority=1.0),
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
    ref_ids = [it["ref_id"] for it in body["items"]]
    # No ref_id appears twice in the daily three.
    assert len(set(ref_ids)) == len(ref_ids)
    # And the second copy of shared_ref didn't displace other_ref or third_ref.
    assert other_ref in ref_ids
    assert third_ref in ref_ids


def test_surface_daily_all_dups_falls_through_gracefully(
    client: TestClient, fakes
) -> None:
    """If every queue item duplicates an already-picked ref_id, the
    variety filter terminates without infinite-looping and surfaces what
    it could pick uniquely. Belt-and-braces guard."""
    supabase, _ = fakes
    pick_id = str(uuid4())
    shared_ref = str(uuid4())
    items = [
        _item_with_ref("problem", shared_ref, priority=3.0),
        _item_with_ref("problem", shared_ref, priority=2.0),
        _item_with_ref("problem", shared_ref, priority=1.5),
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
    # Only one item — the others all duplicated its ref_id.
    assert len(body["items"]) == 1
    assert body["items"][0]["ref_id"] == shared_ref
