"""Tests for POST /assess-engagement (Phase 10-rev Step 3a).

Coverage:
  - 400 / 401 / 404 paths.
  - Haiku call wiring (one queued response, one llm_calls row).
  - user_node_states upsert: struggle_score updated, engagement_count
    incremented, last_engaged_at set, state_transition applied.
  - All four immediate_action branches:
      * null               -> no queue write
      * queue_reinforcement -> easier-sibling row written
      * queue_reinforcement (pool miss) -> action_executed=false
      * accelerate         -> next-difficulty pending item priority bumped
      * surface_prerequisite -> refresher queue item written
  - Paper engagement: Haiku still runs, no node-state writes (no node_id).
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
# Fixtures / wiring
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
def client(fakes) -> TestClient:  # noqa: ARG001 — fakes must be active
    return TestClient(app)


def _prime_attempt_load(
    supabase: FakeSupabase,
    *,
    attempt_id: str,
    user_id: str,
    problem_id: str,
    node_id: str,
    subtopic_slug: str = "meissner-effect",
    topic_slug: str = "superconductivity",
    difficulty: int = 3,
    hint_levels: list[int] | None = None,
    requested_easier: bool = False,
    requested_assume_less: bool = False,
    marked_refreshed: bool = False,
    intent: str = "teach",
) -> None:
    """Register the read-side responders the assess-engagement route needs to
    load a problem-attempt's signals."""
    supabase.respond(
        "attempts",
        "select",
        lambda _call: [
            {
                "id": attempt_id,
                "user_id": user_id,
                "problem_id": problem_id,
                "hint_levels_used": hint_levels or [],
                "marked_refreshed": marked_refreshed,
                "requested_easier": requested_easier,
                "requested_harder": False,
                "requested_assume_less": requested_assume_less,
                "grade_response_md": "Solid setup; sign error in the second step.",
            }
        ],
    )
    supabase.respond(
        "problems",
        "select",
        lambda call: _problems_responder(
            call,
            problem_id=problem_id,
            topic_node_id=node_id,
            topic_slug=topic_slug,
            subtopic_slug=subtopic_slug,
            difficulty=difficulty,
            intent=intent,
        ),
    )
    supabase.respond(
        "nodes",
        "select",
        lambda _call: [{"title": "Superconductivity", "slug": topic_slug}],
    )
    supabase.respond("llm_calls", "insert", lambda _call: [{"id": str(uuid4())}])
    supabase.respond("user_node_states", "upsert", lambda _call: [{"node_id": node_id}])


def _problems_responder(
    call,
    *,
    problem_id: str,
    topic_node_id: str,
    topic_slug: str,
    subtopic_slug: str,
    difficulty: int,
    intent: str,
):
    """Two callers select from `problems`:
    1. load_engagement_signals_for_attempt — eq(id, problem_id)
    2. _find_easier_sibling_problem — eq(topic_node_id, ...), eq(difficulty, ...)
    3. _execute_accelerate — in_(id, [...]), eq(topic_node_id, ...), gt(difficulty, ...)
    Dispatch on filters.
    """
    filters = call.filters
    # Sibling pool lookup: has eq(difficulty, ...) but no in_(id, ...)
    has_id_in = any(f[0] == "in_" and f[1] == "id" for f in filters)
    has_difficulty_eq = any(
        f[0] == "eq" and f[1] == "difficulty" for f in filters
    )
    has_difficulty_gt = any(
        f[0] == "gt" and f[1] == "difficulty" for f in filters
    )
    if has_id_in:
        # accelerate path — return next-difficulty problems
        return [{"id": str(uuid4()), "topic_node_id": topic_node_id, "difficulty": difficulty + 1}]
    if has_difficulty_eq:
        # cache / easier-sibling lookup. Caller registers its own override.
        return []
    if has_difficulty_gt:
        return []
    # default: problem load by id
    return [
        {
            "id": problem_id,
            "topic_node_id": topic_node_id,
            "tags": [topic_slug, subtopic_slug],
            "intent": intent,
            "difficulty": difficulty,
        }
    ]


def _haiku_response(
    *,
    updated_struggle_score: float = 0.3,
    state_transition: str | None = None,
    immediate_action: str | None = None,
    reinforcement_target: str | None = None,
    reasoning: str = "User had moderate friction; an easier sibling on the same subtopic will help.",
) -> str:
    return json.dumps(
        {
            "updated_struggle_score": updated_struggle_score,
            "state_transition": state_transition,
            "immediate_action": immediate_action,
            "reinforcement_target": reinforcement_target,
            "reasoning": reasoning,
        }
    )


# ---------------------------------------------------------------------------
# Basic plumbing
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    response = client.post(
        "/assess-engagement",
        json={"user_id": str(uuid4()), "attempt_id": str(uuid4())},
    )
    assert response.status_code == 401


def test_neither_id_returns_400(client: TestClient, fakes) -> None:
    response = client.post(
        "/assess-engagement",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 400


def test_both_ids_returns_400(client: TestClient, fakes) -> None:
    response = client.post(
        "/assess-engagement",
        json={
            "user_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "engagement_id": str(uuid4()),
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 400


def test_missing_attempt_returns_404(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("attempts", "select", lambda _call: [])
    response = client.post(
        "/assess-engagement",
        json={"user_id": str(uuid4()), "attempt_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Haiku call wiring + node-state update
# ---------------------------------------------------------------------------


def test_happy_path_writes_node_state_and_no_queue_action(
    client: TestClient, fakes
) -> None:
    """immediate_action=null: user_node_states is updated, no queue row written."""
    supabase, anthropic = fakes
    user_id = str(uuid4())
    attempt_id = str(uuid4())
    node_id = str(uuid4())
    _prime_attempt_load(
        supabase,
        attempt_id=attempt_id,
        user_id=user_id,
        problem_id=str(uuid4()),
        node_id=node_id,
    )
    supabase.respond(
        "user_node_states",
        "select",
        lambda _call: [
            {
                "state": "active",
                "struggle_score": 0.2,
                "engagement_count": 3,
                "last_engaged_at": "2026-05-20T00:00:00Z",
            }
        ],
    )
    anthropic.queue(
        _haiku_response(
            updated_struggle_score=0.25,
            immediate_action=None,
            reasoning="Clean engagement; mild progress.",
        )
    )

    response = client.post(
        "/assess-engagement",
        json={"user_id": user_id, "attempt_id": attempt_id},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["updated_struggle_score"] == 0.25
    assert data["immediate_action"] is None
    assert data["action_executed"] is False

    upserts = [
        c for c in supabase.calls
        if c.table == "user_node_states" and c.op == "upsert"
    ]
    assert len(upserts) == 1
    payload = upserts[0].payload
    assert payload["user_id"] == user_id
    assert payload["node_id"] == node_id
    assert payload["struggle_score"] == 0.25
    assert payload["engagement_count"] == 4  # prior 3 + 1
    assert "state" not in payload  # no state_transition

    # No queue_items inserts on null immediate_action.
    queue_inserts = [
        c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"
    ]
    assert queue_inserts == []

    # llm_calls written exactly once.
    llm_inserts = [
        c for c in supabase.calls if c.table == "llm_calls" and c.op == "insert"
    ]
    assert len(llm_inserts) == 1


def test_state_transition_is_applied(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    attempt_id = str(uuid4())
    node_id = str(uuid4())
    _prime_attempt_load(
        supabase,
        attempt_id=attempt_id,
        user_id=user_id,
        problem_id=str(uuid4()),
        node_id=node_id,
        hint_levels=[1, 2, 3],
        requested_easier=True,
    )
    supabase.respond(
        "user_node_states",
        "select",
        lambda _call: [
            {
                "state": "active",
                "struggle_score": 0.4,
                "engagement_count": 2,
                "last_engaged_at": "2026-05-20T00:00:00Z",
            }
        ],
    )
    anthropic.queue(
        _haiku_response(
            updated_struggle_score=0.65,
            state_transition="struggling",
            immediate_action=None,
            reasoning="Three hints plus easier request — pulling state to struggling.",
        )
    )

    response = client.post(
        "/assess-engagement",
        json={"user_id": user_id, "attempt_id": attempt_id},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    upsert = next(
        c for c in supabase.calls
        if c.table == "user_node_states" and c.op == "upsert"
    )
    assert upsert.payload["state"] == "struggling"
    assert upsert.payload["struggle_score"] == 0.65


# ---------------------------------------------------------------------------
# immediate_action: queue_reinforcement
# ---------------------------------------------------------------------------


def test_queue_reinforcement_pool_hit_writes_queue_item(
    client: TestClient, fakes
) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    attempt_id = str(uuid4())
    node_id = str(uuid4())
    easier_problem_id = str(uuid4())

    _prime_attempt_load(
        supabase,
        attempt_id=attempt_id,
        user_id=user_id,
        problem_id=str(uuid4()),
        node_id=node_id,
        difficulty=3,
    )
    # No prior node state.
    supabase.respond("user_node_states", "select", lambda _call: [])
    # Override problems.select so the difficulty-eq path (easier sibling) hits.
    def problems_responder(call):
        filters = call.filters
        has_diff_eq = any(
            f[0] == "eq" and f[1] == "difficulty" for f in filters
        )
        if has_diff_eq:
            # easier-sibling pool lookup — return a match
            return [{"id": easier_problem_id, "tags": ["superconductivity", "meissner-effect"]}]
        return [
            {
                "id": str(uuid4()),
                "topic_node_id": node_id,
                "tags": ["superconductivity", "meissner-effect"],
                "intent": "teach",
                "difficulty": 3,
            }
        ]
    supabase.respond("problems", "select", problems_responder)
    supabase.respond("queue_items", "insert", lambda _call: [{"id": str(uuid4())}])
    anthropic.queue(
        _haiku_response(
            updated_struggle_score=0.45,
            immediate_action="queue_reinforcement",
            reinforcement_target="meissner-effect",
            reasoning="Two hints used; surfacing an easier sibling on the Meissner effect.",
        )
    )

    response = client.post(
        "/assess-engagement",
        json={"user_id": user_id, "attempt_id": attempt_id},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["immediate_action"] == "queue_reinforcement"
    assert data["action_executed"] is True

    queue_inserts = [
        c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"
    ]
    assert len(queue_inserts) == 1
    payload = queue_inserts[0].payload
    assert payload["kind"] == "problem"
    assert payload["ref_id"] == easier_problem_id
    assert payload["user_id"] == user_id
    assert payload["state"] == "pending"
    assert payload["added_reason"].startswith("Two hints used")


def test_queue_reinforcement_pool_miss_returns_action_not_executed(
    client: TestClient, fakes
) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    attempt_id = str(uuid4())
    node_id = str(uuid4())
    _prime_attempt_load(
        supabase,
        attempt_id=attempt_id,
        user_id=user_id,
        problem_id=str(uuid4()),
        node_id=node_id,
        difficulty=2,  # difficulty - 1 = 1, an unusual easier target
    )
    supabase.respond("user_node_states", "select", lambda _call: [])
    # The default _prime_attempt_load problems responder returns [] for
    # difficulty-eq queries, so the easier-sibling lookup misses.
    anthropic.queue(
        _haiku_response(
            updated_struggle_score=0.5,
            immediate_action="queue_reinforcement",
            reinforcement_target="meissner-effect",
            reasoning="Friction signal — but no easier sibling exists in the pool yet.",
        )
    )

    response = client.post(
        "/assess-engagement",
        json={"user_id": user_id, "attempt_id": attempt_id},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["immediate_action"] == "queue_reinforcement"
    assert data["action_executed"] is False
    # No queue_items insert on pool miss.
    assert not any(
        c.table == "queue_items" and c.op == "insert" for c in supabase.calls
    )


# ---------------------------------------------------------------------------
# immediate_action: accelerate
# ---------------------------------------------------------------------------


def test_accelerate_bumps_next_difficulty_priority(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    attempt_id = str(uuid4())
    node_id = str(uuid4())
    pending_queue_id = str(uuid4())
    next_diff_problem_id = str(uuid4())

    _prime_attempt_load(
        supabase,
        attempt_id=attempt_id,
        user_id=user_id,
        problem_id=str(uuid4()),
        node_id=node_id,
        difficulty=3,
    )
    supabase.respond("user_node_states", "select", lambda _call: [])

    # pending queue_items for this user
    supabase.respond(
        "queue_items",
        "select",
        lambda _call: [{"id": pending_queue_id, "ref_id": next_diff_problem_id}],
    )

    # The accelerate path queries problems with in_(id, [...]) and gt(difficulty, 3)
    def problems_responder(call):
        filters = call.filters
        has_id_in = any(f[0] == "in_" and f[1] == "id" for f in filters)
        has_diff_eq = any(f[0] == "eq" and f[1] == "difficulty" for f in filters)
        if has_id_in:
            return [
                {
                    "id": next_diff_problem_id,
                    "topic_node_id": node_id,
                    "difficulty": 4,
                }
            ]
        if has_diff_eq:
            return []
        return [
            {
                "id": str(uuid4()),
                "topic_node_id": node_id,
                "tags": ["superconductivity", "meissner-effect"],
                "intent": "teach",
                "difficulty": 3,
            }
        ]

    supabase.respond("problems", "select", problems_responder)
    supabase.respond("queue_items", "update", lambda _call: [{"id": pending_queue_id}])

    anthropic.queue(
        _haiku_response(
            updated_struggle_score=0.05,
            immediate_action="accelerate",
            reasoning="Clean reasoning, no hints. Pushing next-difficulty work up.",
        )
    )

    response = client.post(
        "/assess-engagement",
        json={"user_id": user_id, "attempt_id": attempt_id},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    assert response.json()["action_executed"] is True
    updates = [
        c for c in supabase.calls
        if c.table == "queue_items" and c.op == "update"
    ]
    assert len(updates) == 1
    assert updates[0].payload["priority_score"] == 0.85
    assert ("eq", "id", pending_queue_id) in updates[0].filters


# ---------------------------------------------------------------------------
# immediate_action: surface_prerequisite
# ---------------------------------------------------------------------------


def test_surface_prerequisite_enqueues_refresher(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    attempt_id = str(uuid4())
    topic_node_id = str(uuid4())
    prereq_node_id = str(uuid4())

    _prime_attempt_load(
        supabase,
        attempt_id=attempt_id,
        user_id=user_id,
        problem_id=str(uuid4()),
        node_id=topic_node_id,
    )
    supabase.respond("user_node_states", "select", lambda _call: [])
    # Prerequisite edges
    supabase.respond(
        "edges",
        "select",
        lambda _call: [{"source_node_id": prereq_node_id, "weight": 0.9}],
    )

    # The nodes responder for prereq lookup is different from the topic-node
    # lookup. Use a dispatcher that returns either based on in_ vs eq.
    def nodes_responder(call):
        filters = call.filters
        if any(f[0] == "in_" for f in filters):
            return [
                {
                    "id": prereq_node_id,
                    "slug": "ordinary-differential-equations",
                    "title": "Ordinary Differential Equations",
                }
            ]
        return [{"title": "Superconductivity", "slug": "superconductivity"}]

    supabase.respond("nodes", "select", nodes_responder)
    supabase.respond("queue_items", "insert", lambda _call: [{"id": str(uuid4())}])

    anthropic.queue(
        _haiku_response(
            updated_struggle_score=0.55,
            immediate_action="surface_prerequisite",
            reinforcement_target="ordinary-differential-equations",
            reasoning="ODE recall is shaky — surface a refresher on second-order linear ODEs.",
        )
    )

    response = client.post(
        "/assess-engagement",
        json={"user_id": user_id, "attempt_id": attempt_id},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    assert response.json()["action_executed"] is True
    inserts = [
        c for c in supabase.calls
        if c.table == "queue_items" and c.op == "insert"
    ]
    assert len(inserts) == 1
    payload = inserts[0].payload
    assert payload["kind"] == "refresher"
    assert payload["ref_id"] == prereq_node_id
    assert payload["user_id"] == user_id


# ---------------------------------------------------------------------------
# Paper engagement: Haiku runs but no node-state writes
# ---------------------------------------------------------------------------


def test_paper_engagement_skips_node_state_updates(
    client: TestClient, fakes
) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    engagement_id = str(uuid4())

    supabase.respond(
        "paper_engagements",
        "select",
        lambda _call: [
            {
                "id": engagement_id,
                "user_id": user_id,
                "paper_id": str(uuid4()),
                "questions_json": [{"id": str(uuid4()), "order": 1}],
                "current_question_index": 1,
            }
        ],
    )
    supabase.respond("papers", "select", lambda _call: [{"title": "Topological Insulators"}])
    supabase.respond("llm_calls", "insert", lambda _call: [{"id": str(uuid4())}])
    anthropic.queue(
        _haiku_response(
            updated_struggle_score=0.0,
            immediate_action=None,
            reasoning="Paper completion noted; no node-specific signal.",
        )
    )

    response = client.post(
        "/assess-engagement",
        json={"user_id": user_id, "engagement_id": engagement_id},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    # No user_node_states writes when node_id is absent.
    assert not any(
        c.table == "user_node_states" and c.op == "upsert" for c in supabase.calls
    )
    # Haiku still logged.
    assert sum(
        1 for c in supabase.calls if c.table == "llm_calls" and c.op == "insert"
    ) == 1
