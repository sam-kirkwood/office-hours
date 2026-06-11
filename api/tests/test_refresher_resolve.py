"""Tests for refresher resolution (POST /create-refresher and the shared
resolve_refresher_to_content helper).

A refresher is resolved to concrete content at creation time: a directly-
routable queue item carrying via_refresher=true. There is no click-time
resolver and nothing is ever marked 'done' here — resolution only *creates*.
"""

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


def _post(client: TestClient, **body) -> object:
    return client.post("/create-refresher", json=body, headers=AUTH_HEADERS)


def _has_concept_filter(call) -> bool:
    return ("eq", "kind", "concept_review") in call.filters


def _has_problem_filter(call) -> bool:
    return ("eq", "kind", "problem") in call.filters


def _basis(supabase: FakeSupabase) -> None:
    """Register a user_node_states row that grants a refresh basis (the user has
    engaged / marked this node), so the node path resolves to a real refresher
    rather than downgrading to groundwork."""
    supabase.respond(
        "user_node_states",
        "select",
        lambda _: [{"state": "active", "engagement_count": 1}],
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/create-refresher",
        json={"user_id": str(uuid4()), "ref_id": str(uuid4())},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Curator-style: ref_id is a node, pool hit → kind='problem', via_refresher
# ---------------------------------------------------------------------------


def test_curator_pool_hit_enqueues_problem(
    client: TestClient, supabase: FakeSupabase
) -> None:
    user_id = str(uuid4())
    node_id = str(uuid4())
    problem_id = str(uuid4())
    new_qi_id = str(uuid4())

    # Legacy refresher_schedule miss → falls through to curator-node path.
    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond(
        "nodes",
        "select",
        lambda _: [{"id": node_id, "title": "Multivariable Calculus"}],
    )
    _basis(supabase)
    supabase.respond("problems", "select", lambda _: [{"id": problem_id, "tags": []}])
    # No existing queue item for the pooled problem (dedup probe).
    supabase.respond("queue_items", "select", lambda _: [])
    supabase.respond("queue_items", "insert", lambda _: [{"id": new_qi_id}])

    resp = _post(client, user_id=user_id, ref_id=node_id, reason="Bring it back.")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "problem"
    assert data["queue_item_id"] == new_qi_id

    # Pool lookup at intent='refresh', difficulty=1 on the node.
    problem_selects = [
        c for c in supabase.calls if c.table == "problems" and c.op == "select"
    ]
    assert len(problem_selects) == 1
    assert ("eq", "intent", "refresh") in problem_selects[0].filters
    assert ("eq", "difficulty", 1) in problem_selects[0].filters
    assert ("eq", "topic_node_id", node_id) in problem_selects[0].filters

    # Inserted a via_refresher problem pointing at the pool problem.
    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 1
    assert inserts[0].payload["kind"] == "problem"
    assert inserts[0].payload["ref_id"] == problem_id
    assert inserts[0].payload["state"] == "pending"
    assert inserts[0].payload["via_refresher"] is True
    assert inserts[0].payload["added_reason"] == "Bring it back."

    # Nothing is marked done — resolution only creates.
    updates = [c for c in supabase.calls if c.table == "queue_items" and c.op == "update"]
    assert not any((u.payload or {}).get("state") == "done" for u in updates)


def test_curator_pool_hit_duplicate_falls_back_to_concept(
    client: TestClient, supabase: FakeSupabase
) -> None:
    """If the user already has the pooled problem queued, don't stack a second
    one — fall back to a concept read on the node."""
    user_id = str(uuid4())
    node_id = str(uuid4())
    problem_id = str(uuid4())
    concept_qi_id = str(uuid4())

    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("nodes", "select", lambda _: [{"id": node_id, "title": "Calc"}])
    _basis(supabase)
    supabase.respond("problems", "select", lambda _: [{"id": problem_id, "tags": []}])

    def queue_items_select(call):
        if _has_problem_filter(call):
            return [{"id": str(uuid4())}]  # dup of the pooled problem exists
        return []  # no existing concept

    supabase.respond("queue_items", "select", queue_items_select)
    supabase.respond("queue_items", "insert", lambda _: [{"id": concept_qi_id}])

    resp = _post(client, user_id=user_id, ref_id=node_id)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "concept_review"
    assert data["queue_item_id"] == concept_qi_id

    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 1
    assert inserts[0].payload["kind"] == "concept_review"
    assert inserts[0].payload["via_refresher"] is True


# ---------------------------------------------------------------------------
# No refresh basis → groundwork, not a refresher.
# A "refresher" on a node the user has never engaged (and didn't mark) is a
# misnomer; it downgrades to a plain orientation read (via_refresher=false) so
# the daily card reads as a Concept, not "look at this again".
# ---------------------------------------------------------------------------


def test_no_basis_node_downgrades_to_groundwork_concept(
    client: TestClient, supabase: FakeSupabase
) -> None:
    user_id = str(uuid4())
    node_id = str(uuid4())
    new_qi_id = str(uuid4())

    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond(
        "nodes", "select", lambda _: [{"id": node_id, "title": "Linear Algebra"}]
    )
    # No user_node_states row → no basis to refresh.
    supabase.respond("user_node_states", "select", lambda _: [])
    supabase.respond("queue_items", "select", lambda _: [])  # no existing concept
    supabase.respond("queue_items", "insert", lambda _: [{"id": new_qi_id}])

    resp = _post(
        client,
        user_id=user_id,
        ref_id=node_id,
        reason="You'll need eigenvalues for the spin-operator work.",
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "concept_review"
    assert data["queue_item_id"] == new_qi_id

    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 1
    # Crucially: a Concept card, NOT a Refresher — and no problem was generated.
    assert inserts[0].payload["kind"] == "concept_review"
    assert inserts[0].payload["via_refresher"] is False
    # The curator's context-rich reason is preserved on the groundwork card.
    assert "eigenvalues" in inserts[0].payload["added_reason"]
    # Pool lookup / generation never ran — basis gate short-circuits first.
    assert not [c for c in supabase.calls if c.table == "problems"]


def test_engaged_node_with_zero_count_but_active_state_is_a_refresher(
    client: TestClient, supabase: FakeSupabase
) -> None:
    """A Stage-2 'refresh' mark writes state='active' with engagement_count=0.
    That explicit signal is a valid basis → a real refresher."""
    user_id = str(uuid4())
    node_id = str(uuid4())
    problem_id = str(uuid4())
    new_qi_id = str(uuid4())

    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("nodes", "select", lambda _: [{"id": node_id, "title": "ODEs"}])
    supabase.respond(
        "user_node_states",
        "select",
        lambda _: [{"state": "active", "engagement_count": 0}],
    )
    supabase.respond("problems", "select", lambda _: [{"id": problem_id, "tags": []}])
    supabase.respond("queue_items", "select", lambda _: [])
    supabase.respond("queue_items", "insert", lambda _: [{"id": new_qi_id}])

    resp = _post(client, user_id=user_id, ref_id=node_id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["kind"] == "problem"
    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert inserts[0].payload["via_refresher"] is True


# ---------------------------------------------------------------------------
# Curator-style: pool miss → generate a fresh refresh-intent problem (d5).
# ---------------------------------------------------------------------------


def test_curator_pool_miss_generates_refresh_problem(
    client: TestClient, supabase: FakeSupabase, monkeypatch
) -> None:
    import routes.generate_problem as gp
    from schemas import GenerateProblemResponse

    user_id = str(uuid4())
    node_id = str(uuid4())
    gen_problem_id = str(uuid4())
    gen_qi_id = str(uuid4())

    captured: dict = {}

    def fake_generate_problem(*, body, supabase, anthropic):  # noqa: ARG001
        captured["intent"] = body.intent
        captured["node_id"] = str(body.node_id)
        return GenerateProblemResponse(problem_id=gen_problem_id, queue_item_id=gen_qi_id)

    monkeypatch.setattr(gp, "generate_problem", fake_generate_problem)

    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("nodes", "select", lambda _: [{"id": node_id, "title": "Stat Mech"}])
    _basis(supabase)
    supabase.respond("problems", "select", lambda _: [])  # pool miss
    supabase.respond("queue_items", "update", lambda _: [{"id": gen_qi_id}])

    resp = _post(client, user_id=user_id, ref_id=node_id, reason="Recall this.")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "problem"
    assert data["queue_item_id"] == gen_qi_id

    # Generated with refresh intent on the refresher's node.
    assert captured["intent"] == "refresh"
    assert captured["node_id"] == node_id

    # No concept_review was enqueued.
    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert all(c.payload.get("kind") != "concept_review" for c in inserts)

    # The generated row was stamped via_refresher with the curator's reason; no
    # done-marking occurs.
    updates = [c for c in supabase.calls if c.table == "queue_items" and c.op == "update"]
    stamp = [u for u in updates if "via_refresher" in (u.payload or {})]
    assert stamp and stamp[0].payload["via_refresher"] is True
    assert stamp[0].payload["added_reason"] == "Recall this."
    assert ("eq", "id", gen_qi_id) in stamp[0].filters
    assert not any((u.payload or {}).get("state") == "done" for u in updates)


def test_curator_pool_miss_generation_failure_falls_back_to_concept(
    client: TestClient, supabase: FakeSupabase, monkeypatch
) -> None:
    import routes.generate_problem as gp

    user_id = str(uuid4())
    node_id = str(uuid4())
    new_qi_id = str(uuid4())

    def boom(*, body, supabase, anthropic):  # noqa: ARG001
        raise RuntimeError("generation failed")

    monkeypatch.setattr(gp, "generate_problem", boom)

    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("nodes", "select", lambda _: [{"id": node_id, "title": "Stat Mech"}])
    _basis(supabase)
    supabase.respond("problems", "select", lambda _: [])  # pool miss
    supabase.respond("queue_items", "select", lambda _: [])  # no existing concept
    supabase.respond("queue_items", "insert", lambda _: [{"id": new_qi_id}])

    resp = _post(client, user_id=user_id, ref_id=node_id)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "concept_review"
    assert data["queue_item_id"] == new_qi_id

    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 1
    assert inserts[0].payload["kind"] == "concept_review"
    assert inserts[0].payload["ref_id"] == node_id
    assert inserts[0].payload["via_refresher"] is True


def test_curator_pool_miss_reuses_existing_concept(
    client: TestClient, supabase: FakeSupabase, monkeypatch
) -> None:
    """When generation fails and the user already has a concept card for this
    node, reuse it rather than minting a duplicate brief (d5)."""
    import routes.generate_problem as gp

    user_id = str(uuid4())
    node_id = str(uuid4())
    existing_concept_qi = str(uuid4())

    def boom(*, body, supabase, anthropic):  # noqa: ARG001
        raise RuntimeError("generation failed")

    monkeypatch.setattr(gp, "generate_problem", boom)

    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("nodes", "select", lambda _: [{"id": node_id, "title": "Stat Mech"}])
    _basis(supabase)
    supabase.respond("problems", "select", lambda _: [])  # pool miss

    def queue_items_select(call):
        if _has_concept_filter(call):
            return [{"id": existing_concept_qi}]
        return []

    supabase.respond("queue_items", "select", queue_items_select)

    resp = _post(client, user_id=user_id, ref_id=node_id)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "concept_review"
    assert data["queue_item_id"] == existing_concept_qi

    # No new concept_review row was inserted — the existing one is reused.
    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert not inserts


# ---------------------------------------------------------------------------
# Curator-style: ref_id matches neither schedule nor node → 404
# ---------------------------------------------------------------------------


def test_unknown_ref_id_returns_404(client: TestClient, supabase: FakeSupabase) -> None:
    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("nodes", "select", lambda _: [])

    resp = _post(client, user_id=str(uuid4()), ref_id=str(uuid4()))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Legacy refresher_schedule
# ---------------------------------------------------------------------------


def test_legacy_attempt_subject_enqueues_problem(
    client: TestClient, supabase: FakeSupabase
) -> None:
    user_id = str(uuid4())
    schedule_id = str(uuid4())
    attempt_id = str(uuid4())
    problem_id = str(uuid4())
    new_qi_id = str(uuid4())

    supabase.respond(
        "refresher_schedule",
        "select",
        lambda _: [{"subject_kind": "attempt", "subject_ref_id": attempt_id}],
    )
    supabase.respond("attempts", "select", lambda _: [{"problem_id": problem_id}])
    supabase.respond("queue_items", "insert", lambda _: [{"id": new_qi_id}])

    resp = _post(client, user_id=user_id, ref_id=schedule_id)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "problem"
    assert data["queue_item_id"] == new_qi_id

    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 1
    assert inserts[0].payload["kind"] == "problem"
    assert inserts[0].payload["ref_id"] == problem_id
    assert inserts[0].payload["via_refresher"] is True


def test_legacy_engagement_subject_enqueues_paper(
    client: TestClient, supabase: FakeSupabase
) -> None:
    user_id = str(uuid4())
    schedule_id = str(uuid4())
    engagement_id = str(uuid4())
    new_qi_id = str(uuid4())

    supabase.respond(
        "refresher_schedule",
        "select",
        lambda _: [{"subject_kind": "engagement", "subject_ref_id": engagement_id}],
    )
    supabase.respond("queue_items", "insert", lambda _: [{"id": new_qi_id}])

    resp = _post(client, user_id=user_id, ref_id=schedule_id)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "paper_engagement"
    assert data["queue_item_id"] == new_qi_id

    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 1
    assert inserts[0].payload["kind"] == "paper_engagement"
    assert inserts[0].payload["ref_id"] == engagement_id
    assert inserts[0].payload["via_refresher"] is True


# ---------------------------------------------------------------------------
# parent_queue_item_id lineage is recorded (g2 back-link support)
# ---------------------------------------------------------------------------


def test_parent_queue_item_id_is_recorded(
    client: TestClient, supabase: FakeSupabase
) -> None:
    user_id = str(uuid4())
    node_id = str(uuid4())
    problem_id = str(uuid4())
    parent_id = str(uuid4())

    supabase.respond("refresher_schedule", "select", lambda _: [])
    supabase.respond("nodes", "select", lambda _: [{"id": node_id, "title": "Calc"}])
    _basis(supabase)
    supabase.respond("problems", "select", lambda _: [{"id": problem_id, "tags": []}])
    supabase.respond("queue_items", "select", lambda _: [])
    supabase.respond("queue_items", "insert", lambda _: [{"id": str(uuid4())}])

    resp = _post(
        client, user_id=user_id, ref_id=node_id, parent_queue_item_id=parent_id
    )
    assert resp.status_code == 200, resp.text

    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert inserts[0].payload["parent_queue_item_id"] == parent_id
