"""Tests for POST /plan-queue (Phase 10-rev Step 3b).

Coverage:
  - 401 / minimal-context plumbing.
  - Add problem with pool hit -> single queue_items insert; no second Sonnet call.
  - Add problem with pool miss -> /generate-problem called inline; the
    generator's queue row is updated to the curator's reason + priority.
  - Add refresher -> resolve_refresher_to_content called with the routed node.
  - Reprioritise -> queue_items update with mapped priority_score.
  - Paper-engagement rec -> ignored (no write); counted as skipped.
  - added_reason from the curator's `reason` field flows through verbatim.

These tests deliberately register only the responders each scenario needs;
unmocked tables return [] which is fine for the context-loading queries.
"""

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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
# Helpers
# ---------------------------------------------------------------------------


def _prime_minimal_context(
    supabase: FakeSupabase,
    *,
    interest_node_id: str,
    interest_title: str = "Superconductivity",
    interest_slug: str = "superconductivity",
) -> None:
    """Register the responders that produce a minimal but valid §4.2 context:
    one interest, no foundations, no recent engagement, empty queue.
    """
    supabase.respond("surveys", "select", lambda _c: [{"mode_balance": 0.5}])
    supabase.respond(
        "user_interests",
        "select",
        lambda _c: [{"node_id": interest_node_id, "intent_context": "Reconnecting with physics."}],
    )

    # nodes.select is hit many times: in_, ilike, eq. One responder dispatches.
    full_row = {
        "id": interest_node_id,
        "slug": interest_slug,
        "title": interest_title,
        "kind": "interest",
        "subtopics_json": [{"slug": "meissner-effect", "title": "Meissner effect"}],
        "description_md": "Superconductivity overview.",
        "difficulty_hint": "core",
    }

    def nodes_responder(call):
        for op, col, val in call.filters:
            if op == "in_" and col == "id":
                return [full_row]
            if op == "ilike" and col == "title":
                if str(val).lower() == interest_title.lower():
                    return [full_row]
                return []
            if op == "eq" and col == "id":
                if val == interest_node_id:
                    return [full_row]
                return []
        return []

    supabase.respond("nodes", "select", nodes_responder)
    supabase.respond(
        "user_node_states",
        "select",
        lambda _c: [
            {
                "node_id": interest_node_id,
                "state": "active",
                "struggle_score": 0.1,
                "engagement_count": 1,
                "last_engaged_at": "2026-05-20T00:00:00Z",
            }
        ],
    )
    # Default empties; specific tests override as needed.
    supabase.respond("edges", "select", lambda _c: [])
    supabase.respond("attempts", "select", lambda _c: [])
    supabase.respond("paper_engagements", "select", lambda _c: [])
    supabase.respond("papers", "select", lambda _c: [])
    supabase.respond("surfaced_picks", "select", lambda _c: [])
    supabase.respond("user_preferences", "select", lambda _c: [])
    supabase.respond("queue_items", "select", lambda _c: [])
    supabase.respond("llm_calls", "insert", lambda _c: [{"id": str(uuid4())}])


def _plan_response(recommendations: list[dict], observations: str = "") -> str:
    return json.dumps(
        {"recommendations": recommendations, "observations": observations}
    )


def _capture_refresher(monkeypatch) -> list[dict]:
    """Patch resolve_refresher_to_content so the planner's refresher *routing*
    (which node it targets) can be asserted in isolation from resolution
    (pool lookup / generation), which has its own tests in
    test_refresher_resolve.py. Returns the list of captured calls."""
    import routes.refresher as rr
    from schemas import RefresherResolveResponse

    calls: list[dict] = []

    def fake(  # noqa: PLR0913
        supabase,
        anthropic,
        *,
        user_id,
        ref_id,
        reason=None,
        priority_score=0.55,
        parent_queue_item_id=None,
    ):
        calls.append(
            {
                "ref_id": ref_id,
                "reason": reason,
                "priority_score": priority_score,
                "user_id": user_id,
            }
        )
        return RefresherResolveResponse(kind="problem", queue_item_id=str(uuid4()))

    monkeypatch.setattr(rr, "resolve_refresher_to_content", fake)
    return calls


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/plan-queue", json={"user_id": str(uuid4())}
    )
    assert resp.status_code == 401


def test_curator_prompt_routes_refreshers_to_foundation_titles() -> None:
    """Step 9c-iii: the upstream fix for refresher mis-routing is a prompt
    instruction telling the curator to put the foundation node title in
    `interest_node` for foundation-skill refreshers, rather than relying solely
    on the dispatch-layer token matcher. Guard the instruction against
    regression."""
    from prompts.curator_plan import build_system_prompt

    prompt = build_system_prompt()
    lowered = prompt.lower()
    assert 'kind: "refresher"' in prompt
    assert "put the foundation node title in `interest_node`" in lowered
    # The worked example anchors the rule on a concrete foundation/interest pair.
    assert "statistical mechanics" in lowered


def test_empty_recommendations_is_a_valid_response(
    client: TestClient, fakes
) -> None:
    supabase, anthropic = fakes
    interest_node_id = str(uuid4())
    _prime_minimal_context(supabase, interest_node_id=interest_node_id)
    anthropic.queue(_plan_response([], observations="Nothing pressing."))

    resp = client.post(
        "/plan-queue",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["recommendations_received"] == 0
    assert data["items_added"] == 0
    assert data["items_reprioritised"] == 0
    assert data["items_skipped"] == 0
    assert data["observations"] == "Nothing pressing."

    # Exactly one Sonnet call (the plan). No /generate-problem.
    assert len(anthropic.messages.calls) == 1
    # llm_calls written once.
    llm_inserts = [
        c for c in supabase.calls if c.table == "llm_calls" and c.op == "insert"
    ]
    assert len(llm_inserts) == 1


# ---------------------------------------------------------------------------
# Add: problem (pool hit)
# ---------------------------------------------------------------------------


def test_add_problem_pool_hit_skips_generation(
    client: TestClient, fakes
) -> None:
    supabase, anthropic = fakes
    interest_node_id = str(uuid4())
    cached_problem_id = str(uuid4())

    _prime_minimal_context(supabase, interest_node_id=interest_node_id)

    # Problems pool: a matching cached row exists.
    def problems_responder(call):
        # Pool lookup uses eq(topic_node_id), eq(difficulty), eq(intent),
        # and contains(tags, [subtopic]) when subtopic provided.
        return [{"id": cached_problem_id, "tags": ["superconductivity", "meissner-effect"]}]

    supabase.respond("problems", "select", problems_responder)

    # queue_items.select: the "already exists" probe returns [].
    supabase.respond(
        "queue_items",
        "select",
        lambda call: (
            []
            if any(f[0] == "eq" and f[1] == "ref_id" for f in call.filters)
            else []
        ),
    )
    supabase.respond("queue_items", "insert", lambda _c: [{"id": str(uuid4())}])

    anthropic.queue(
        _plan_response(
            [
                {
                    "action": "add",
                    "interest_node": "Superconductivity",
                    "kind": "problem",
                    "intent": "teach",
                    "subtopic": "Meissner effect",
                    "depth": "conceptual",
                    "assumed_background": ["EM basics"],
                    "priority": "high",
                    "reason": "Practice for your interest in superconductivity. Builds on the Meissner effect work.",
                }
            ]
        )
    )

    resp = client.post(
        "/plan-queue",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["recommendations_received"] == 1
    assert data["items_added"] == 1
    assert data["items_skipped"] == 0

    # Only one anthropic call (no generation — pool hit).
    assert len(anthropic.messages.calls) == 1

    inserts = [
        c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"
    ]
    assert len(inserts) == 1
    payload = inserts[0].payload
    assert payload["kind"] == "problem"
    assert payload["ref_id"] == cached_problem_id
    assert payload["priority_score"] == 0.85  # "high"
    # added_reason flows through verbatim from the curator.
    assert payload["added_reason"].startswith(
        "Practice for your interest in superconductivity."
    )


# ---------------------------------------------------------------------------
# Add: problem (pool miss → /generate-problem inline)
# ---------------------------------------------------------------------------


VALID_GEN_PROBLEM_JSON = json.dumps(
    {
        "title": "First Meissner effect problem",
        "statement_md": "Conceptual entry-point problem.",
        "solution_md": "Worked solution.",
        "rubric_md": "- Names the Meissner effect.\n- Connects to flux expulsion.",
        "hints": [
            {"text": "L1: Recall what a superconductor expels.", "part_label": "Whole problem"},
            {"text": "L2: Think about magnetic field lines inside the material.", "part_label": "Whole problem"},
            {"text": "L3: Connect to flux quantisation.", "part_label": "Whole problem"},
            {"text": "L4: What changes at the critical temperature?", "part_label": "Whole problem"},
            {"text": "L5: Edge effect: thin-film behaviour differs.", "part_label": "Whole problem"},
        ],
        "context_md": "Discovered by Meissner and Ochsenfeld in 1933.",
        "tags": ["superconductivity", "meissner-effect"],
    }
)


def test_add_problem_pool_miss_triggers_generation(
    client: TestClient, fakes
) -> None:
    supabase, anthropic = fakes
    interest_node_id = str(uuid4())
    new_problem_id = str(uuid4())
    generated_queue_item_id = str(uuid4())

    _prime_minimal_context(
        supabase, interest_node_id=interest_node_id
    )

    # Problems.select dispatcher:
    # - Pool lookup for the curator rec (eq topic_node_id, eq difficulty, eq intent, contains tags) → [] (miss)
    # - is_entry_point follow-up (in_ id) → []
    # - cache_lookup inside generate-problem (eq difficulty, eq intent, is_ context_hook_id) → []
    supabase.respond("problems", "select", lambda _c: [])
    supabase.respond("problems", "insert", lambda _c: [{"id": new_problem_id}])
    supabase.respond(
        "problem_hints",
        "insert",
        lambda call: [{"id": str(uuid4()), **row} for row in call.payload],
    )
    supabase.respond("context_hooks", "select", lambda _c: [])
    supabase.respond("attempts", "select", lambda _c: [])  # entry-point check

    # queue_items.insert is called twice: once by generate-problem, once by
    # NOTHING in plan-queue — plan-queue updates the row generate-problem
    # already wrote. So expect exactly one insert, plus one update.
    supabase.respond(
        "queue_items", "insert", lambda _c: [{"id": generated_queue_item_id}]
    )
    supabase.respond(
        "queue_items", "update", lambda _c: [{"id": generated_queue_item_id}]
    )

    # Two Sonnet calls: the plan, then the generation.
    anthropic.queue(
        _plan_response(
            [
                {
                    "action": "add",
                    "interest_node": "Superconductivity",
                    "kind": "problem",
                    "intent": "teach",
                    "subtopic": "Meissner effect",
                    "depth": "foundational",
                    "assumed_background": ["EM basics"],
                    "priority": "high",
                    "reason": "Curator's reason — should overwrite the generator default.",
                }
            ]
        )
    )
    anthropic.queue(VALID_GEN_PROBLEM_JSON)

    resp = client.post(
        "/plan-queue",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["items_added"] == 1

    # Two Sonnet calls.
    assert len(anthropic.messages.calls) == 2

    # The generator's queue row was updated to the curator's reason + priority.
    updates = [
        c for c in supabase.calls if c.table == "queue_items" and c.op == "update"
    ]
    # First update may be the curator's overwrite — assert at least one had the
    # curator's added_reason.
    curator_updates = [
        u for u in updates
        if u.payload.get("added_reason")
        and "Curator's reason" in u.payload["added_reason"]
    ]
    assert len(curator_updates) == 1
    assert curator_updates[0].payload["priority_score"] == 0.85


# ---------------------------------------------------------------------------
# Add: refresher
# ---------------------------------------------------------------------------


def test_add_refresher_resolves_to_content(
    client: TestClient, fakes, monkeypatch
) -> None:
    """A refresher rec resolves to concrete content via
    resolve_refresher_to_content (a via_refresher problem/concept), passing the
    routed node id, the curator's reason, and the mapped priority."""
    supabase, anthropic = fakes
    interest_node_id = str(uuid4())
    _prime_minimal_context(supabase, interest_node_id=interest_node_id)
    calls = _capture_refresher(monkeypatch)

    anthropic.queue(
        _plan_response(
            [
                {
                    "action": "add",
                    "interest_node": "Superconductivity",
                    "kind": "refresher",
                    "intent": "refresh",
                    "subtopic": "ODE basics",
                    "depth": "foundational",
                    "assumed_background": [],
                    "priority": "medium",
                    "reason": "Refresh on ODEs before BCS theory.",
                }
            ]
        )
    )

    resp = client.post(
        "/plan-queue",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["items_added"] == 1

    assert len(calls) == 1
    assert calls[0]["ref_id"] == interest_node_id
    assert calls[0]["reason"] == "Refresh on ODEs before BCS theory."
    assert calls[0]["priority_score"] == 0.6  # "medium"


# ---------------------------------------------------------------------------
# Reprioritise
# ---------------------------------------------------------------------------


def test_reprioritise_updates_priority_score(
    client: TestClient, fakes
) -> None:
    supabase, anthropic = fakes
    interest_node_id = str(uuid4())
    target_queue_id = str(uuid4())
    _prime_minimal_context(supabase, interest_node_id=interest_node_id)
    supabase.respond(
        "queue_items",
        "update",
        lambda _c: [{"id": target_queue_id, "priority_score": 0.4}],
    )

    anthropic.queue(
        _plan_response(
            [
                {
                    "action": "reprioritise",
                    "queue_item_id": target_queue_id,
                    "new_priority": "low",
                    "reason": "Hold the deferred BCS item back; prereqs come first.",
                }
            ]
        )
    )

    resp = client.post(
        "/plan-queue",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["items_reprioritised"] == 1
    assert data["items_added"] == 0

    updates = [
        c for c in supabase.calls
        if c.table == "queue_items" and c.op == "update"
    ]
    assert len(updates) == 1
    assert updates[0].payload["priority_score"] == 0.4  # "low"
    assert ("eq", "id", target_queue_id) in updates[0].filters


# ---------------------------------------------------------------------------
# paper_engagement: ignored
# ---------------------------------------------------------------------------


def test_paper_engagement_recommendation_is_skipped(
    client: TestClient, fakes
) -> None:
    supabase, anthropic = fakes
    interest_node_id = str(uuid4())
    _prime_minimal_context(supabase, interest_node_id=interest_node_id)

    anthropic.queue(
        _plan_response(
            [
                {
                    "action": "add",
                    "interest_node": "Superconductivity",
                    "kind": "paper_engagement",
                    "intent": "teach",
                    "subtopic": None,
                    "depth": "intermediate",
                    "assumed_background": [],
                    "priority": "medium",
                    "reason": "Reading would suit the user.",
                }
            ]
        )
    )

    resp = client.post(
        "/plan-queue",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["recommendations_received"] == 1
    assert data["items_added"] == 0
    assert data["items_skipped"] == 1
    # No queue_items insert.
    assert not any(
        c.table == "queue_items" and c.op == "insert" for c in supabase.calls
    )


# ---------------------------------------------------------------------------
# Already-pending duplicate
# ---------------------------------------------------------------------------


def test_pool_hit_with_existing_pending_item_is_skipped(
    client: TestClient, fakes
) -> None:
    """If the user already has a pending queue row referencing the same
    problem, don't double-enqueue."""
    supabase, anthropic = fakes
    interest_node_id = str(uuid4())
    cached_problem_id = str(uuid4())
    _prime_minimal_context(supabase, interest_node_id=interest_node_id)
    supabase.respond(
        "problems",
        "select",
        lambda _c: [{"id": cached_problem_id, "tags": ["superconductivity", "meissner-effect"]}],
    )

    # The already-exists probe (eq ref_id, in_ state) returns a row.
    def queue_select(call):
        if any(f[0] == "eq" and f[1] == "ref_id" for f in call.filters):
            return [{"id": str(uuid4())}]
        return []

    supabase.respond("queue_items", "select", queue_select)

    anthropic.queue(
        _plan_response(
            [
                {
                    "action": "add",
                    "interest_node": "Superconductivity",
                    "kind": "problem",
                    "intent": "teach",
                    "subtopic": "Meissner effect",
                    "depth": "conceptual",
                    "assumed_background": [],
                    "priority": "medium",
                    "reason": "Already in queue — would be a duplicate.",
                }
            ]
        )
    )

    resp = client.post(
        "/plan-queue",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["items_added"] == 0
    assert resp.json()["items_skipped"] == 1
    # No insert.
    assert not any(
        c.table == "queue_items" and c.op == "insert" for c in supabase.calls
    )


# ---------------------------------------------------------------------------
# Phase 10.5-rev Step 1 — queue cap (MAX_ON_DECK)
# ---------------------------------------------------------------------------


def test_add_recs_skipped_when_queue_at_cap(client: TestClient, fakes) -> None:
    """When non-terminal stock is already at the cap, `add` recs are held
    (skipped) while `reprioritise` recs still apply (curriculum-curator-design
    §11.1 / §13.4, Phase 10.5-rev Q1)."""
    supabase, anthropic = fakes
    interest_node_id = str(uuid4())
    target_queue_id = str(uuid4())
    _prime_minimal_context(supabase, interest_node_id=interest_node_id)

    def queue_items_select(call):
        for op, col, val in call.filters:
            if op == "in_" and col == "state":
                # _count_on_deck includes 'deferred'; report a full queue.
                if "deferred" in val:
                    return [{"id": str(uuid4())} for _ in range(15)]
                # load_current_queue_summary (pending, surfaced) — keep cheap.
                return []
        return []

    supabase.respond("queue_items", "select", queue_items_select)
    supabase.respond("queue_items", "insert", lambda _c: [{"id": str(uuid4())}])
    supabase.respond(
        "queue_items", "update", lambda _c: [{"id": target_queue_id}]
    )

    anthropic.queue(
        _plan_response(
            [
                {
                    "action": "add",
                    "interest_node": "Superconductivity",
                    "kind": "refresher",
                    "intent": "refresh",
                    "subtopic": "ODE basics",
                    "depth": "foundational",
                    "assumed_background": [],
                    "priority": "medium",
                    "reason": "Would add — but the queue is full.",
                },
                {
                    "action": "reprioritise",
                    "queue_item_id": target_queue_id,
                    "new_priority": "high",
                    "reason": "Bump the most relevant pending item instead.",
                },
            ]
        )
    )

    resp = client.post(
        "/plan-queue",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["items_added"] == 0
    assert data["items_skipped"] == 1
    assert data["items_reprioritised"] == 1

    # The capped add wrote no queue row...
    assert not any(
        c.table == "queue_items" and c.op == "insert" for c in supabase.calls
    )
    # ...but the reprioritise still updated priority_score.
    updates = [
        c for c in supabase.calls if c.table == "queue_items" and c.op == "update"
    ]
    assert len(updates) == 1
    assert updates[0].payload["priority_score"] == 0.85  # "high"


# ---------------------------------------------------------------------------
# Phase 10-rev Step 9a — refresher kind routes to foundation
# ---------------------------------------------------------------------------


def test_refresher_routes_to_foundation_when_subtopic_matches(
    client: TestClient, fakes, monkeypatch
) -> None:
    """When the curator emits a refresher rec whose subtopic matches a
    foundation node's subtopics_json entry, the refresher is resolved against
    the FOUNDATION node, not the interest_node the rec was emitted under.

    Mirrors the phase-transitions → partition-function-manipulations →
    statistical-mechanics routing the persona walkthroughs identified as
    the canonical case for this fix.
    """
    supabase, anthropic = fakes
    interest_node_id = str(uuid4())
    foundation_node_id = str(uuid4())
    calls = _capture_refresher(monkeypatch)

    # Minimal context for the planner's input — set up the interest node
    # responder, but DON'T register a fallback foundation responder yet so
    # we can dispatch on the eq("kind", "foundation") filter precisely.
    supabase.respond("surveys", "select", lambda _c: [{"mode_balance": 0.5}])
    supabase.respond(
        "user_interests",
        "select",
        lambda _c: [{"node_id": interest_node_id, "intent_context": "Studying phase transitions."}],
    )

    interest_row = {
        "id": interest_node_id,
        "slug": "phase-transitions",
        "title": "Phase Transitions",
        "kind": "interest",
        "subtopics_json": [{"slug": "ising-1d", "title": "1D Ising model"}],
        "description_md": "Phase transitions and critical phenomena.",
        "difficulty_hint": "advanced",
    }
    foundation_row = {
        "id": foundation_node_id,
        "slug": "statistical-mechanics",
        "title": "Statistical Mechanics",
        "kind": "foundation",
        "subtopics_json": [
            {"slug": "partition-function-manipulations", "title": "Partition function manipulations"},
            {"slug": "boltzmann-distribution", "title": "Boltzmann distribution"},
        ],
    }

    def nodes_responder(call):
        for op, col, val in call.filters:
            if op == "eq" and col == "kind" and val == "foundation":
                return [foundation_row]
            if op == "in_" and col == "id":
                return [interest_row]
            if op == "ilike" and col == "title":
                if str(val).lower() == "phase transitions":
                    return [interest_row]
                return []
        return []

    supabase.respond("nodes", "select", nodes_responder)
    supabase.respond(
        "user_node_states",
        "select",
        lambda _c: [{
            "node_id": interest_node_id,
            "state": "active",
            "struggle_score": 0.1,
            "engagement_count": 0,
            "last_engaged_at": None,
        }],
    )
    supabase.respond("edges", "select", lambda _c: [])
    supabase.respond("attempts", "select", lambda _c: [])
    supabase.respond("paper_engagements", "select", lambda _c: [])
    supabase.respond("papers", "select", lambda _c: [])
    supabase.respond("surfaced_picks", "select", lambda _c: [])
    supabase.respond("user_preferences", "select", lambda _c: [])
    supabase.respond("queue_items", "select", lambda _c: [])
    supabase.respond("llm_calls", "insert", lambda _c: [{"id": str(uuid4())}])
    supabase.respond("queue_items", "insert", lambda _c: [{"id": str(uuid4())}])

    anthropic.queue(
        _plan_response(
            [{
                "action": "add",
                "interest_node": "Phase Transitions",
                "kind": "refresher",
                "intent": "refresh",
                "subtopic": "Partition function manipulations",
                "depth": "foundational",
                "assumed_background": [],
                "priority": "medium",
                "reason": "Refresh partition function manipulations before the Ising work.",
            }]
        )
    )

    resp = client.post(
        "/plan-queue",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["items_added"] == 1

    assert len(calls) == 1
    # The critical assertion: ref_id is the FOUNDATION, not the interest_node.
    assert calls[0]["ref_id"] == foundation_node_id
    assert calls[0]["ref_id"] != interest_node_id


def test_refresher_falls_back_to_interest_when_no_foundation_owns_subtopic(
    client: TestClient, fakes, monkeypatch
) -> None:
    """When no foundation owns the rec's subtopic, the refresher routes
    to the interest_node as before. Preserves existing behaviour for
    truly interest-level refresher recs."""
    supabase, anthropic = fakes
    interest_node_id = str(uuid4())

    _prime_minimal_context(supabase, interest_node_id=interest_node_id)
    calls = _capture_refresher(monkeypatch)

    anthropic.queue(
        _plan_response(
            [{
                "action": "add",
                "interest_node": "Superconductivity",
                "kind": "refresher",
                "intent": "refresh",
                "subtopic": "Some subtopic no foundation owns",
                "depth": "foundational",
                "assumed_background": [],
                "priority": "medium",
                "reason": "Targets a topic-level concept that's not in any foundation.",
            }]
        )
    )

    resp = client.post(
        "/plan-queue",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["items_added"] == 1
    assert len(calls) == 1
    # Falls back to the interest node.
    assert calls[0]["ref_id"] == interest_node_id


def test_find_foundation_owning_subtopic_ignores_overloaded_tokens(fakes) -> None:
    """B1 stopword guard: a subtopic whose only overlap with a foundation is an
    overloaded token must NOT match — "phase relationships" should not route to
    ODEs just because ODEs lists "Phase plane analysis". A distinctive token
    ("partition") must still match."""
    from curator_inputs import find_foundation_owning_subtopic

    supabase, _ = fakes
    odes_row = {
        "id": str(uuid4()),
        "slug": "odes",
        "title": "Ordinary Differential Equations",
        "subtopics_json": [
            {"slug": "phase-plane-analysis", "title": "Phase plane analysis"},
            {"slug": "laplace-transforms", "title": "Laplace transforms"},
        ],
    }
    statmech_row = {
        "id": str(uuid4()),
        "slug": "statistical-mechanics",
        "title": "Statistical Mechanics",
        "subtopics_json": [
            {"slug": "partition-function", "title": "Partition function manipulations"},
        ],
    }
    supabase.respond("nodes", "select", lambda _c: [odes_row, statmech_row])

    # Overloaded-only overlap ("phase") → no match.
    assert find_foundation_owning_subtopic(
        supabase, subtopic_slug="phase-relationships"
    ) is None
    # Distinctive overlap ("partition") → still matches.
    matched = find_foundation_owning_subtopic(
        supabase, subtopic_slug="partition-function-manipulations"
    )
    assert matched is not None and matched["slug"] == "statistical-mechanics"


def test_refresher_trusts_foundation_named_interest_node(
    client: TestClient, fakes, monkeypatch
) -> None:
    """B1: when the curator names a FOUNDATION directly in interest_node (per
    Step 9c-iii), route the refresher there — even if rec.subtopic would
    token-match a *different* foundation. Guards the persona-walkthrough
    mis-route where a wave/phase refresher landed on ODEs."""
    supabase, anthropic = fakes
    interest_node_id = str(uuid4())
    waves_id = str(uuid4())
    odes_id = str(uuid4())
    calls = _capture_refresher(monkeypatch)

    supabase.respond("surveys", "select", lambda _c: [{"mode_balance": 0.5}])
    supabase.respond(
        "user_interests",
        "select",
        lambda _c: [{"node_id": interest_node_id, "intent_context": "Interferometry."}],
    )

    interest_row = {
        "id": interest_node_id,
        "slug": "interferometry",
        "title": "Interferometry",
        "kind": "interest",
        "subtopics_json": [{"slug": "fringe-visibility", "title": "Fringe visibility"}],
        "description_md": "Interferometry overview.",
        "difficulty_hint": "core",
    }
    waves_row = {
        "id": waves_id,
        "slug": "waves-oscillations",
        "title": "Waves & Oscillations",
        "kind": "foundation",
        "subtopics_json": [{"slug": "wave-superposition", "title": "Wave superposition"}],
    }
    odes_row = {
        "id": odes_id,
        "slug": "odes",
        "title": "Ordinary Differential Equations",
        "kind": "foundation",
        "subtopics_json": [{"slug": "laplace-transforms", "title": "Laplace transforms"}],
    }

    def nodes_responder(call):
        for op, col, val in call.filters:
            if op == "eq" and col == "kind" and val == "foundation":
                return [waves_row, odes_row]
            if op == "in_" and col == "id":
                return [interest_row]
            if op == "ilike" and col == "title":
                v = str(val).lower()
                if v == "waves & oscillations":
                    return [waves_row]
                if v == "interferometry":
                    return [interest_row]
                return []
        return []

    supabase.respond("nodes", "select", nodes_responder)
    supabase.respond(
        "user_node_states",
        "select",
        lambda _c: [{
            "node_id": interest_node_id,
            "state": "active",
            "struggle_score": 0.1,
            "engagement_count": 0,
            "last_engaged_at": None,
        }],
    )
    supabase.respond("edges", "select", lambda _c: [])
    supabase.respond("attempts", "select", lambda _c: [])
    supabase.respond("paper_engagements", "select", lambda _c: [])
    supabase.respond("papers", "select", lambda _c: [])
    supabase.respond("surfaced_picks", "select", lambda _c: [])
    supabase.respond("user_preferences", "select", lambda _c: [])
    supabase.respond("queue_items", "select", lambda _c: [])
    supabase.respond("llm_calls", "insert", lambda _c: [{"id": str(uuid4())}])
    supabase.respond("queue_items", "insert", lambda _c: [{"id": str(uuid4())}])

    anthropic.queue(
        _plan_response(
            [{
                "action": "add",
                "interest_node": "Waves & Oscillations",  # foundation named directly
                "kind": "refresher",
                "intent": "refresh",
                # This subtopic genuinely token-matches ODES ("laplace"), but the
                # explicit foundation name must win.
                "subtopic": "Laplace transform methods",
                "depth": "foundational",
                "assumed_background": [],
                "priority": "high",
                "reason": "Sharpen wave superposition before interferometry.",
            }]
        )
    )

    resp = client.post(
        "/plan-queue",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["items_added"] == 1
    assert len(calls) == 1
    # Routed to the named foundation, NOT the one the subtopic token-matched.
    assert calls[0]["ref_id"] == waves_id
    assert calls[0]["ref_id"] != odes_id
