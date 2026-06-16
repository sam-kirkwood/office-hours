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


def _item(kind: str = "problem", priority: float = 1.0, **kwargs) -> dict:
    return {
        "id": str(uuid4()),
        "kind": kind,
        "ref_id": str(uuid4()),
        "state": "pending",
        "priority_score": priority,
        "time_estimate_minutes_low": 10,
        "time_estimate_minutes_high": 20,
        "added_reason": f"You expressed interest in {kind}.",
        "pinned": False,
        "via_refresher": False,
        **kwargs,
    }


def _pinned_surfaced_item(kind: str = "problem") -> dict:
    """A pinned item that is already state='surfaced' (survived a reroll)."""
    return {
        "id": str(uuid4()),
        "kind": kind,
        "ref_id": str(uuid4()),
        "state": "surfaced",
        "priority_score": 0.85,
        "time_estimate_minutes_low": 15,
        "time_estimate_minutes_high": 30,
        "added_reason": "You asked for a more challenging version of this problem.",
        "pinned": True,
        "via_refresher": False,
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


# ---------------------------------------------------------------------------
# §A6 — Pinned items survive reroll and claim their slot first
# ---------------------------------------------------------------------------


def _is_pinned_select(call) -> bool:
    """True if the select is the _load_pinned_surfaced query."""
    return any(f == ("eq", "state", "surfaced") for f in call.filters) and any(
        f == ("eq", "pinned", True) for f in call.filters
    )


def _is_pending_select(call) -> bool:
    """True if the select is the _load_pending query."""
    return any(f == ("eq", "state", "pending") for f in call.filters)


def test_pinned_surfaced_item_included_in_pick(client: TestClient, fakes) -> None:
    """A pinned item that survived a reroll (state='surfaced', pinned=True)
    is included in the pick without consuming a pending slot.

    Setup: 1 pinned surfaced item + 3 pending items → the pick should contain
    all 4 collapsed to MAX_SURFACED=3: the pinned item + 2 new picks.
    """
    supabase, _ = fakes
    pick_id = str(uuid4())
    pinned = _pinned_surfaced_item("problem")
    p1 = _item("problem", priority=2.0)
    p2 = _item("paper_engagement", priority=1.5)
    p3 = _item("concept_review", priority=1.0)

    def queue_items_select(call):
        if _is_pinned_select(call):
            return [pinned]
        if _is_pending_select(call):
            return [p1, p2, p3]
        return []

    supabase.respond("queue_items", "select", queue_items_select)
    supabase.respond("queue_items", "update", lambda _: [])
    supabase.respond("surfaced_picks", "insert", lambda _: [{"id": pick_id}])

    response = client.post(
        "/surface-daily",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    ids = [it["queue_item_id"] for it in body["items"]]
    # Pinned item must be in the result.
    assert pinned["id"] in ids
    # Total picks capped at MAX_SURFACED=3.
    assert len(body["items"]) == 3
    # pending_remaining = 3 pending - 2 new picks = 1.
    assert body["pending_remaining"] == 1


def test_pinned_item_does_not_occupy_update_call(client: TestClient, fakes) -> None:
    """Pinned surfaced items must NOT be marked state='surfaced' again (they
    already are). Only the newly-picked pending items should be updated."""
    supabase, _ = fakes
    pick_id = str(uuid4())
    pinned = _pinned_surfaced_item("problem")
    p1 = _item("paper_engagement", priority=1.0)

    def queue_items_select(call):
        if _is_pinned_select(call):
            return [pinned]
        if _is_pending_select(call):
            return [p1]
        return []

    supabase.respond("queue_items", "select", queue_items_select)
    supabase.respond("queue_items", "update", lambda _: [])
    supabase.respond("surfaced_picks", "insert", lambda _: [{"id": pick_id}])

    client.post(
        "/surface-daily",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    update_calls = [c for c in supabase.calls if c.table == "queue_items" and c.op == "update"]
    updated_ids = [c.filters for c in update_calls]
    # The pinned item's id must not appear in any update call.
    for filters in updated_ids:
        assert not any(f == ("eq", "id", pinned["id"]) for f in filters)
    # The pending item IS updated to surfaced.
    assert any(
        any(f == ("eq", "id", p1["id"]) for f in c.filters)
        for c in update_calls
    )


def test_pinned_item_carries_pinned_flag_in_response(client: TestClient, fakes) -> None:
    """The SurfacedItem for a pinned item has pinned=True in the response."""
    supabase, _ = fakes
    pick_id = str(uuid4())
    pinned = _pinned_surfaced_item("problem")

    def queue_items_select(call):
        if _is_pinned_select(call):
            return [pinned]
        return []  # no pending items

    supabase.respond("queue_items", "select", queue_items_select)
    supabase.respond("queue_items", "update", lambda _: [])
    supabase.respond("surfaced_picks", "insert", lambda _: [{"id": pick_id}])

    response = client.post(
        "/surface-daily",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["pinned"] is True
    assert items[0]["queue_item_id"] == pinned["id"]


# ---------------------------------------------------------------------------
# §A5 — Steering hint filters
# ---------------------------------------------------------------------------


def _setup_steer(supabase, fakes_pick_id, pending_items, *, pinned_items=None):
    """Wire a queue_items select responder for steer tests."""
    pinned_items = pinned_items or []

    def queue_items_select(call):
        if _is_pinned_select(call):
            return pinned_items
        if _is_pending_select(call):
            return pending_items
        return []

    supabase.respond("queue_items", "select", queue_items_select)
    supabase.respond("queue_items", "update", lambda _: [])
    supabase.respond("surfaced_picks", "insert", lambda _: [{"id": fakes_pick_id}])


def test_steer_shorter_prefers_short_items(client: TestClient, fakes) -> None:
    """steer='shorter' should surface short items (time_high ≤ 20)
    and not the long item (time_high=60) when short alternatives exist."""
    supabase, _ = fakes
    pick_id = str(uuid4())
    short = _item("problem", priority=0.5, time_estimate_minutes_high=15)
    long_ = _item("problem", priority=2.0, time_estimate_minutes_high=60)
    _setup_steer(supabase, pick_id, [long_, short])

    response = client.post(
        "/surface-daily",
        json={"user_id": str(uuid4()), "steer": "shorter"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200, response.text
    ids = [it["queue_item_id"] for it in response.json()["items"]]
    assert short["id"] in ids
    assert long_["id"] not in ids


def test_steer_more_papers_brings_papers_first(client: TestClient, fakes) -> None:
    """steer='more_papers' puts paper_engagement items ahead of problems."""
    supabase, _ = fakes
    pick_id = str(uuid4())
    paper = _item("paper_engagement", priority=0.5)
    p1 = _item("problem", priority=3.0)
    p2 = _item("problem", priority=2.0)
    _setup_steer(supabase, pick_id, [p1, p2, paper])

    response = client.post(
        "/surface-daily",
        json={"user_id": str(uuid4()), "steer": "more_papers"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200, response.text
    ids = [it["queue_item_id"] for it in response.json()["items"]]
    assert paper["id"] in ids


def test_steer_different_excludes_seen_refs(client: TestClient, fakes) -> None:
    """steer='different' with steer_excluded_ref_ids skips those ref_ids."""
    supabase, _ = fakes
    pick_id = str(uuid4())
    seen = _item("problem", priority=3.0)
    fresh = _item("problem", priority=1.0)
    _setup_steer(supabase, pick_id, [seen, fresh])

    response = client.post(
        "/surface-daily",
        json={
            "user_id": str(uuid4()),
            "steer": "different",
            "steer_excluded_ref_ids": [seen["ref_id"]],
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200, response.text
    ids = [it["queue_item_id"] for it in response.json()["items"]]
    assert seen["id"] not in ids
    assert fresh["id"] in ids


def test_steer_less_topic_excludes_topic_problems(client: TestClient, fakes) -> None:
    """steer='less_topic' with steer_topic_node_id excludes problems from that topic.

    The route does a secondary problems/select to find the topic's problem ref_ids,
    then filters them out of the pending pick.
    """
    supabase, _ = fakes
    pick_id = str(uuid4())
    topic_node_id = str(uuid4())
    topic_problem_ref = str(uuid4())

    topic_problem = _item("problem", priority=3.0)
    topic_problem["ref_id"] = topic_problem_ref
    other_problem = _item("problem", priority=1.0)

    _setup_steer(supabase, pick_id, [topic_problem, other_problem])
    # problems/select → return the topic's problem id for the exclusion query.
    supabase.respond(
        "problems",
        "select",
        lambda _call: [{"id": topic_problem_ref}],
    )

    response = client.post(
        "/surface-daily",
        json={
            "user_id": str(uuid4()),
            "steer": "less_topic",
            "steer_topic_node_id": topic_node_id,
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200, response.text
    ids = [it["queue_item_id"] for it in response.json()["items"]]
    assert topic_problem["id"] not in ids
    assert other_problem["id"] in ids


def test_steer_falls_back_to_full_pool_when_filter_empties_it(
    client: TestClient, fakes
) -> None:
    """When a steer filter would empty the pool, fall back to the full pool
    rather than stranding the user with 0 items."""
    supabase, _ = fakes
    pick_id = str(uuid4())
    only_item = _item("problem", priority=1.0, time_estimate_minutes_high=60)
    _setup_steer(supabase, pick_id, [only_item])

    response = client.post(
        "/surface-daily",
        json={"user_id": str(uuid4()), "steer": "shorter"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200, response.text
    ids = [it["queue_item_id"] for it in response.json()["items"]]
    # Falls back — the long item surfaces rather than nothing.
    assert only_item["id"] in ids


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


# ---------------------------------------------------------------------------
# §A6 clamp — more pinned items than MAX_SURFACED must not produce a
# negative slots_remaining (which would then cause _pick_varied to be called
# with max_count < 0 and silently return nothing).
# ---------------------------------------------------------------------------


def test_slots_remaining_clamped_when_pinned_fills_all_slots(
    client: TestClient, fakes
) -> None:
    """When MAX_SURFACED+1 items are already pinned+surfaced the route must
    not crash or produce a negative slot count; it should surface only the
    pinned items and not attempt to add more from pending."""
    supabase, _ = fakes
    pick_id = str(uuid4())
    # One more pinned item than MAX_SURFACED=3.
    pinned_items = [_pinned_surfaced_item("problem") for _ in range(4)]
    p1 = _item("problem", priority=1.0)

    def queue_items_select(call):
        if _is_pinned_select(call):
            return pinned_items
        if _is_pending_select(call):
            return [p1]
        return []

    supabase.respond("queue_items", "select", queue_items_select)
    supabase.respond("queue_items", "update", lambda _: [])
    supabase.respond("surfaced_picks", "insert", lambda _: [{"id": pick_id}])

    response = client.post(
        "/surface-daily",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # All 4 pinned items are returned; no crash from negative slot count.
    assert len(body["items"]) == 4
    # The pending item was not picked (slots_remaining was clamped to 0).
    ids = [it["queue_item_id"] for it in body["items"]]
    assert p1["id"] not in ids
