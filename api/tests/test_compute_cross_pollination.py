"""Tests for POST /compute-cross-pollination."""

from __future__ import annotations

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
def fakes() -> tuple[FakeSupabase, None]:
    fs = FakeSupabase()
    app.dependency_overrides[get_supabase_client] = lambda: fs
    try:
        yield fs, None
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(fakes) -> TestClient:  # noqa: ARG001
    return TestClient(app)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post("/compute-cross-pollination", json={})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Curation gate — no megagraph_snapshots yet
# ---------------------------------------------------------------------------


def test_no_curation_returns_early(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("megagraph_snapshots", "select", lambda _: [])

    resp = client.post("/compute-cross-pollination", json={}, headers=AUTH_HEADERS)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["suggestions_created"] == 0
    assert data["reason"] == "no_curation_yet"


# ---------------------------------------------------------------------------
# Happy path — snapshot exists, frontier node scores > 0.3
#
# Call sequence for the single user:
#   megagraph_snapshots.select → [snapshot]
#   user_interests.select      → [{user_id}]
#   user_node_states.select    → [{node_id: engaged_id}]   (engaged nodes)
#   bookmarks.select           → []
#   edges.select (src)         → [edge engaged→frontier, weight=0.8]
#   edges.select (tgt)         → []
#   edges.select (src, 2-hop)  → []
#   edges.select (tgt, 2-hop)  → []
#   user_node_states.select    → []   (other users for frontier node; 0 other users)
#   queue_items.select         → []   (cooldown check; no recent suggestion)
#   queue_items.insert         → [inserted row]
#
# score = 0.8 * 0.5 + min(0, 5) * 0.1 = 0.4 > 0.3 → suggestion created
# ---------------------------------------------------------------------------


def test_happy_path_creates_suggestion(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    engaged_id = str(uuid4())
    frontier_id = str(uuid4())

    supabase.respond("megagraph_snapshots", "select", lambda _: [{"id": str(uuid4())}])
    supabase.respond("user_interests", "select", lambda _: [{"user_id": user_id}])

    # user_node_states called twice: (1) engaged nodes, (2) other-user count for frontier
    supabase.respond(
        "user_node_states",
        "select",
        _cycler(
            [{"node_id": engaged_id}],  # engaged nodes
            [],                          # other users on frontier_id (none)
        ),
    )
    supabase.respond("bookmarks", "select", lambda _: [])

    # edges.select called 4 times: 1-hop src, 1-hop tgt, 2-hop src, 2-hop tgt
    supabase.respond(
        "edges",
        "select",
        _cycler(
            [{"source_node_id": engaged_id, "target_node_id": frontier_id, "weight": 0.8}],
            [],  # 1-hop tgt
            [],  # 2-hop src
            [],  # 2-hop tgt
        ),
    )

    supabase.respond("queue_items", "select", lambda _: [])   # cooldown check
    supabase.respond("queue_items", "insert", lambda _: [{"id": str(uuid4())}])

    resp = client.post("/compute-cross-pollination", json={}, headers=AUTH_HEADERS)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["suggestions_created"] == 1
    assert data["reason"] == "ok"

    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 1
    payload = inserts[0].payload
    assert payload["kind"] == "suggested_interest"
    assert payload["ref_id"] == frontier_id
    assert payload["user_id"] == user_id
    assert payload["priority_score"] == pytest.approx(0.35)


# ---------------------------------------------------------------------------
# Threshold not met — all frontier candidates score ≤ 0.3
#
# weight=0.0, other_user_count=0 → score=0.0 ≤ 0.3 → no insert
# ---------------------------------------------------------------------------


def test_threshold_not_met_skips(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    engaged_id = str(uuid4())
    frontier_id = str(uuid4())

    supabase.respond("megagraph_snapshots", "select", lambda _: [{"id": str(uuid4())}])
    supabase.respond("user_interests", "select", lambda _: [{"user_id": user_id}])
    supabase.respond(
        "user_node_states",
        "select",
        _cycler(
            [{"node_id": engaged_id}],  # engaged nodes
            [],                          # other users on frontier_id
        ),
    )
    supabase.respond("bookmarks", "select", lambda _: [])
    supabase.respond(
        "edges",
        "select",
        _cycler(
            [{"source_node_id": engaged_id, "target_node_id": frontier_id, "weight": 0.0}],
            [],  # 1-hop tgt
            [],  # 2-hop src
            [],  # 2-hop tgt
        ),
    )
    # cooldown and insert should NOT be called

    resp = client.post("/compute-cross-pollination", json={}, headers=AUTH_HEADERS)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["suggestions_created"] == 0
    assert data["reason"] == "ok"

    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 0


# ---------------------------------------------------------------------------
# Cooldown — recent suggested_interest for same node already exists
# ---------------------------------------------------------------------------



def test_cooldown_prevents_duplicate(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    engaged_id = str(uuid4())
    frontier_id = str(uuid4())

    supabase.respond("megagraph_snapshots", "select", lambda _: [{"id": str(uuid4())}])
    supabase.respond("user_interests", "select", lambda _: [{"user_id": user_id}])
    supabase.respond(
        "user_node_states",
        "select",
        _cycler(
            [{"node_id": engaged_id}],
            [],  # other users
        ),
    )
    supabase.respond("bookmarks", "select", lambda _: [])
    supabase.respond(
        "edges",
        "select",
        _cycler(
            [{"source_node_id": engaged_id, "target_node_id": frontier_id, "weight": 0.8}],
            [],
            [],
            [],
        ),
    )
    # Cooldown check returns an existing queue item → skip
    supabase.respond("queue_items", "select", lambda _: [{"id": str(uuid4())}])

    resp = client.post("/compute-cross-pollination", json={}, headers=AUTH_HEADERS)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["suggestions_created"] == 0
    assert data["reason"] == "ok"

    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 0


# ---------------------------------------------------------------------------
# Already-engaged node not suggested
#
# If the only edge connects two already-engaged nodes, the frontier is empty
# and no suggestion is created.
# ---------------------------------------------------------------------------


def test_already_engaged_node_not_suggested(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    engaged_id_a = str(uuid4())
    engaged_id_b = str(uuid4())

    supabase.respond("megagraph_snapshots", "select", lambda _: [{"id": str(uuid4())}])
    supabase.respond("user_interests", "select", lambda _: [{"user_id": user_id}])
    # Both nodes are in the engaged set
    supabase.respond(
        "user_node_states",
        "select",
        lambda _: [{"node_id": engaged_id_a}, {"node_id": engaged_id_b}],
    )
    supabase.respond("bookmarks", "select", lambda _: [])

    # Edge only connects the two engaged nodes — no frontier reachable
    supabase.respond(
        "edges",
        "select",
        _cycler(
            [{"source_node_id": engaged_id_a, "target_node_id": engaged_id_b, "weight": 0.9}],
            [],  # 1-hop tgt
            [],  # 2-hop src (hop1 is empty so this branch is skipped, but responder consumed)
            [],  # 2-hop tgt
        ),
    )

    resp = client.post("/compute-cross-pollination", json={}, headers=AUTH_HEADERS)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["suggestions_created"] == 0

    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 0


# ---------------------------------------------------------------------------
# Gate opens — megagraph_snapshots row present (taken_by='system' from apply)
#
# The gate check only tests for any row in megagraph_snapshots. Once a system
# snapshot exists the gate should return reason='ok', not 'no_curation_yet'.
# ---------------------------------------------------------------------------


def test_after_snapshot_written_by_system_gate_opens(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("megagraph_snapshots", "select", lambda _: [{"id": str(uuid4())}])
    supabase.respond("user_interests", "select", lambda _: [])  # no users → 0 suggestions

    resp = client.post("/compute-cross-pollination", json={}, headers=AUTH_HEADERS)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["reason"] == "ok"            # gate open, not "no_curation_yet"
    assert data["suggestions_created"] == 0  # no users, but gate is open
