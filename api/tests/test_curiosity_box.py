"""Tests for POST /curiosity-box (Phase 12 Step 4c-i/follow-ups — §A4 classifier + routes)."""

from __future__ import annotations

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

USER_ID = str(uuid4())

# Valid GeneratedProblem JSON for mocking Sonnet generation calls.
VALID_PROBLEM_JSON = json.dumps(
    {
        "title": "A Neat Problem",
        "statement_md": "## Setup\nGiven X.\n\n## The problem\nDerive Y.",
        "solution_md": "Use Z.",
        "rubric_md": "- Correct approach\n- Units",
        "hints": [
            {"text": "Hint 1.", "part_label": "Whole problem"},
            {"text": "Hint 2.", "part_label": "Whole problem"},
            {"text": "Hint 3.", "part_label": "Whole problem"},
            {"text": "Hint 4.", "part_label": "Whole problem"},
            {"text": "Hint 5.", "part_label": "Whole problem"},
        ],
        "context_md": "Historical context.",
        "tags": ["integration-by-parts", "u-substitution"],
    }
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _classify_json(
    *,
    kind: str,
    confidence: str = "high",
    normalized_topic: str | None = None,
    paper_ref: str | None = None,
    added_reason: str = "You asked for this.",
    clarification_md: str = "Did you mean a drill or a topic?",
) -> str:
    return json.dumps(
        {
            "kind": kind,
            "confidence": confidence,
            "normalized_topic": normalized_topic,
            "paper_ref": paper_ref,
            "added_reason": added_reason,
            "clarification_md": clarification_md,
        }
    )


def _answer_json(
    answer_md: str = "The sky is blue because of Rayleigh scattering.",
    followon_topic_hint: str = "Rayleigh scattering",
) -> str:
    return json.dumps(
        {"answer_md": answer_md, "followon_topic_hint": followon_topic_hint}
    )


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


def _post(client: TestClient, raw_text: str) -> dict:
    resp = client.post(
        "/curiosity-box",
        json={"user_id": USER_ID, "raw_text": raw_text},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post("/curiosity-box", json={"user_id": USER_ID, "raw_text": "hi"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# mood → redirect_steer
# ---------------------------------------------------------------------------


def test_mood_returns_redirect_steer(client: TestClient, fakes) -> None:
    _, anthropic = fakes
    anthropic.queue(_classify_json(kind="mood"))

    body = _post(client, "something shorter please")
    assert body["action"] == "redirect_steer"
    assert "steering" in body["message_md"].lower() or "chips" in body["message_md"].lower()


# ---------------------------------------------------------------------------
# feedback → redirect_feedback
# ---------------------------------------------------------------------------


def test_feedback_returns_redirect_feedback(client: TestClient, fakes) -> None:
    _, anthropic = fakes
    anthropic.queue(_classify_json(kind="feedback"))

    body = _post(client, "that problem was wrong")
    assert body["action"] == "redirect_feedback"
    assert "feedback" in body["message_md"].lower()


# ---------------------------------------------------------------------------
# probe → graceful
# ---------------------------------------------------------------------------


def test_probe_returns_graceful(client: TestClient, fakes) -> None:
    _, anthropic = fakes
    anthropic.queue(_classify_json(kind="probe"))

    body = _post(client, "are you smart?")
    assert body["action"] == "graceful"


# ---------------------------------------------------------------------------
# question → answer + follow-on offer
# ---------------------------------------------------------------------------


def test_question_returns_answer_with_followon(client: TestClient, fakes) -> None:
    _, anthropic = fakes
    anthropic.queue(_classify_json(kind="question"))
    anthropic.queue(_answer_json())

    body = _post(client, "why is the sky blue?")
    assert body["action"] == "answer"
    assert body["answer_md"] is not None
    assert "Rayleigh" in body["answer_md"]
    assert body["followon_topic_hint"] == "Rayleigh scattering"


# ---------------------------------------------------------------------------
# paper → ingest_paper with paper_ref
# ---------------------------------------------------------------------------


def test_paper_returns_ingest_paper(client: TestClient, fakes) -> None:
    _, anthropic = fakes
    ref = "arxiv.org/abs/1706.03762"
    anthropic.queue(_classify_json(kind="paper", paper_ref=ref))

    body = _post(client, ref)
    assert body["action"] == "ingest_paper"
    assert body["paper_ref"] == ref


def test_paper_falls_back_to_raw_text_when_no_ref(client: TestClient, fakes) -> None:
    """If Haiku returns no paper_ref, the route falls back to raw_text."""
    _, anthropic = fakes
    anthropic.queue(_classify_json(kind="paper", paper_ref=None))

    body = _post(client, "10.1038/nature12345")
    assert body["action"] == "ingest_paper"
    assert body["paper_ref"] == "10.1038/nature12345"


# ---------------------------------------------------------------------------
# topic_new — explore-by-default (§A4)
# ---------------------------------------------------------------------------


def test_topic_new_one_off_queues_no_interest(client: TestClient, fakes) -> None:
    """Node found → one-off item queued → topic_new_explored; NO user_interests write."""
    supabase, anthropic = fakes
    node_id = str(uuid4())
    problem_id = str(uuid4())
    qi_id = str(uuid4())

    # _resolve_node_for_topic: user_interests (user may have none — that's fine)
    supabase.respond("user_interests", "select", lambda _: [])
    # global node search returns a hit
    supabase.respond(
        "nodes",
        "select",
        lambda _: [{"id": node_id, "slug": "topology", "title": "Topology"}],
    )
    # _pool_lookup_problem: pool hit
    supabase.respond("problems", "select", lambda _: [{"id": problem_id}])
    # _insert_pinned_queue_item
    supabase.respond("queue_items", "insert", lambda _: [{"id": qi_id}])

    anthropic.queue(
        _classify_json(
            kind="topic_new",
            normalized_topic="topology",
            added_reason="You asked for a one-off problem on topology.",
        )
    )

    body = _post(client, "I want to learn topology")
    assert body["action"] == "topic_new_explored"
    assert body["queue_item_id"] == qi_id
    assert body["topic_hint"] == "topology"
    assert "Topology" in body["message_md"]
    assert "one-off" in body["message_md"] or "hasn't been added" in body["message_md"]

    # Confirm NO user_interests write occurred.
    ui_inserts = [c for c in supabase.calls if c.table == "user_interests" and c.op == "insert"]
    assert not ui_inserts

    # Confirm queue_items insert was pinned.
    qi_inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(qi_inserts) == 1
    assert qi_inserts[0].payload["pinned"] is True


def test_topic_new_novel_falls_back_to_stub(client: TestClient, fakes) -> None:
    """No matching node in megagraph → topic_new_stub; nothing queued."""
    supabase, anthropic = fakes
    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond("nodes", "select", lambda _: [])  # no match

    anthropic.queue(
        _classify_json(kind="topic_new", normalized_topic="obscure new topic xyz")
    )

    body = _post(client, "I want to learn obscure new topic xyz")
    assert body["action"] == "topic_new_stub"
    assert body["queue_item_id"] is None
    assert "obscure new topic xyz" in body["message_md"]

    qi_inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert not qi_inserts


def test_topic_new_pool_miss_generates_inline(client: TestClient, fakes) -> None:
    """Pool miss on topic_new one-off → generate inline → topic_new_explored."""
    supabase, anthropic = fakes
    node_id = str(uuid4())
    problem_id = str(uuid4())
    qi_id = str(uuid4())

    # Tags must include the topic slug or the validator rejects the generation.
    topology_problem_json = json.dumps(
        {
            "title": "Open Sets in Topology",
            "statement_md": "## Setup\nLet X be a topological space.\n\n## The problem\nProve X is open.",
            "solution_md": "By definition of open sets.",
            "rubric_md": "- Correct definition\n- Valid proof",
            "hints": [
                {"text": "Hint 1.", "part_label": "Whole problem"},
                {"text": "Hint 2.", "part_label": "Whole problem"},
                {"text": "Hint 3.", "part_label": "Whole problem"},
                {"text": "Hint 4.", "part_label": "Whole problem"},
                {"text": "Hint 5.", "part_label": "Whole problem"},
            ],
            "context_md": "Topology context.",
            "tags": ["topology", "open-sets"],
        }
    )

    # _resolve_node_for_topic: interest-node path (user has this node)
    supabase.respond(
        "user_interests",
        "select",
        lambda _: [{"node_id": node_id, "intent_context": ""}],
    )
    supabase.respond(
        "nodes",
        "select",
        lambda _: [
            {
                "id": node_id,
                "slug": "topology",
                "title": "Topology",
                "description_md": "Point-set topology.",
                "difficulty_hint": "core",
                "subtopics_json": [],
            }
        ],
    )
    # pool miss everywhere, then generation
    supabase.respond("problems", "select", lambda _: [])
    supabase.respond("attempts", "select", lambda _: [])
    supabase.respond("edges", "select", lambda _: [])
    supabase.respond("user_node_states", "select", lambda _: [])
    supabase.respond("surveys", "select", lambda _: [])
    supabase.respond("user_preferences", "select", lambda _: [])
    supabase.respond("problems", "insert", lambda _: [{"id": problem_id}])
    supabase.respond("problem_hints", "insert", lambda _: [])
    supabase.respond("queue_items", "insert", lambda _: [{"id": qi_id}])

    anthropic.queue(_classify_json(kind="topic_new", normalized_topic="topology"))
    anthropic.queue(topology_problem_json)

    body = _post(client, "topology")
    assert body["action"] == "topic_new_explored"
    assert body["queue_item_id"] == qi_id

    problem_inserts = [c for c in supabase.calls if c.table == "problems" and c.op == "insert"]
    assert len(problem_inserts) == 1

    ui_inserts = [c for c in supabase.calls if c.table == "user_interests" and c.op == "insert"]
    assert not ui_inserts


def test_topic_new_generation_failure_returns_graceful(client: TestClient, fakes) -> None:
    """Node found but pool miss AND generation fails → graceful "try again", not stub.

    This checks that when we find the node in the megagraph but the Sonnet
    problem-generation call fails (no queued response → AssertionError caught
    inside _resolve_and_queue_one_off), the route returns action="graceful"
    rather than action="topic_new_stub" ("isn't in my library yet"), which would
    be wrong when the topic IS in the library.
    """
    supabase, anthropic = fakes
    node_id = str(uuid4())

    # _resolve_node_for_topic: no user interests → global ilike search finds the node.
    # Single responder for all nodes.select calls (covers both the global search and
    # the node-fetch inside _generate_problem_for_node).
    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond(
        "nodes",
        "select",
        lambda _: [
            {
                "id": node_id,
                "slug": "topology",
                "title": "Topology",
                "description_md": "Point-set topology.",
                "difficulty_hint": "core",
                "subtopics_json": [],
            }
        ],
    )
    # Pool miss — no problem in pool. FakeSupabase returns [] for unregistered
    # ops by default, so this is enough.
    supabase.respond("problems", "select", lambda _: [])

    # Classify → topic_new. NO second response queued for problem generation, so
    # FakeMessages.create raises AssertionError, caught inside _resolve_and_queue_one_off.
    anthropic.queue(_classify_json(kind="topic_new", normalized_topic="topology"))

    body = _post(client, "I want to learn topology")

    # Should NOT fall through to topic_new_stub ("isn't in my library yet").
    assert body["action"] == "graceful"
    assert "try again" in body["message_md"].lower()
    assert "Topology" in body["message_md"]

    qi_inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert not qi_inserts


# ---------------------------------------------------------------------------
# low confidence → clarify (no execution)
# ---------------------------------------------------------------------------


def test_low_confidence_returns_clarify(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    anthropic.queue(
        _classify_json(
            kind="drill",
            confidence="low",
            normalized_topic="quantum mechanics",
            clarification_md="Did you mean a specific technique, or more problems on quantum in general?",
        )
    )

    body = _post(client, "more quantum")
    assert body["action"] == "clarify"
    assert body["clarification_md"] is not None
    # Must NOT have queued anything.
    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert not inserts


# ---------------------------------------------------------------------------
# drill (pool hit) → queued_pinned with pinned queue_item
# ---------------------------------------------------------------------------


def _prime_drill_pool_hit(supabase: FakeSupabase) -> tuple[str, str, str]:
    """Set up nodes + user_interests + problems + queue_items for a pool-hit drill.

    Returns (interest_node_id, problem_id, expected_queue_item_id).
    """
    node_id = str(uuid4())
    problem_id = str(uuid4())
    qi_id = str(uuid4())

    # _resolve_node_for_topic: user_interests select → node_ids
    supabase.respond(
        "user_interests",
        "select",
        lambda _: [{"node_id": node_id}],
    )
    # _resolve_node_for_topic: nodes select (in_ by node_ids)
    supabase.respond(
        "nodes",
        "select",
        lambda _: [{"id": node_id, "slug": "integration-by-parts", "title": "Integration by Parts"}],
    )
    # _pool_lookup_problem: problems select
    supabase.respond(
        "problems",
        "select",
        lambda _: [{"id": problem_id}],
    )
    # _insert_pinned_queue_item: queue_items insert
    supabase.respond(
        "queue_items",
        "insert",
        lambda _: [{"id": qi_id}],
    )
    return node_id, problem_id, qi_id


def test_drill_pool_hit_queues_pinned_item(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    _, problem_id, qi_id = _prime_drill_pool_hit(supabase)
    anthropic.queue(
        _classify_json(
            kind="drill",
            normalized_topic="integration by parts",
            added_reason="You asked for a problem on integration by parts.",
        )
    )

    body = _post(client, "more integration by parts")
    assert body["action"] == "queued_pinned"
    assert body["queue_item_id"] == qi_id

    # Verify the queue_items insert wrote pinned=True with the right problem_id.
    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 1
    payload = inserts[0].payload
    assert payload["pinned"] is True
    assert payload["ref_id"] == problem_id
    assert payload["added_reason"] == "You asked for a problem on integration by parts."


# ---------------------------------------------------------------------------
# drill (pool miss) → generate inline → queued_pinned
# ---------------------------------------------------------------------------


def _prime_for_generate(
    supabase: FakeSupabase,
    *,
    node_id: str,
    problem_id: str,
    qi_id: str,
) -> None:
    """Prime all supabase tables needed for inline generation on pool miss.

    All curator-input helpers (derive_intent, is_entry_point,
    derive_assumed_background_summary, derive_feedback_biases) return empty /
    default data, which the helpers handle gracefully.
    """
    full_node = {
        "id": node_id,
        "slug": "integration-by-parts",
        "title": "Integration by Parts",
        "description_md": "IBP technique.",
        "difficulty_hint": "core",
        "subtopics_json": [],
    }
    supabase.respond(
        "user_interests",
        "select",
        lambda _: [{"node_id": node_id, "intent_context": ""}],
    )
    supabase.respond("nodes", "select", lambda _: [full_node])
    supabase.respond("problems", "select", lambda _: [])   # pool miss everywhere
    supabase.respond("attempts", "select", lambda _: [])   # is_entry_point
    supabase.respond("edges", "select", lambda _: [])      # assumed_background prereqs
    supabase.respond("user_node_states", "select", lambda _: [])
    supabase.respond("surveys", "select", lambda _: [])
    supabase.respond("user_preferences", "select", lambda _: [])
    supabase.respond("problems", "insert", lambda _: [{"id": problem_id}])
    supabase.respond("problem_hints", "insert", lambda _: [])
    supabase.respond("queue_items", "insert", lambda _: [{"id": qi_id}])


def test_drill_pool_miss_generates_problem(client: TestClient, fakes) -> None:
    """On pool miss, the route generates a problem inline and queues it pinned."""
    supabase, anthropic = fakes
    node_id = str(uuid4())
    problem_id = str(uuid4())
    qi_id = str(uuid4())

    _prime_for_generate(supabase, node_id=node_id, problem_id=problem_id, qi_id=qi_id)

    # Haiku classify, then Sonnet generate.
    anthropic.queue(_classify_json(kind="drill", normalized_topic="integration by parts"))
    anthropic.queue(VALID_PROBLEM_JSON)

    body = _post(client, "more integration by parts")
    assert body["action"] == "queued_pinned"
    assert body["queue_item_id"] == qi_id

    # Verify a problem was inserted.
    problem_inserts = [c for c in supabase.calls if c.table == "problems" and c.op == "insert"]
    assert len(problem_inserts) == 1

    # Verify the queue_item is pinned.
    qi_inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(qi_inserts) == 1
    assert qi_inserts[0].payload["pinned"] is True
    assert qi_inserts[0].payload["ref_id"] == problem_id

    # Generated-path message should indicate it was freshly built.
    assert "built" in body["message_md"].lower() or "fresh" in body["message_md"].lower()


# ---------------------------------------------------------------------------
# existing_interest → queued_pinned (same pool-lookup path as drill)
# ---------------------------------------------------------------------------


def test_existing_interest_queues_pinned_item(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    _, _, qi_id = _prime_drill_pool_hit(supabase)
    anthropic.queue(
        _classify_json(
            kind="existing_interest",
            normalized_topic="integration by parts",
            added_reason="You wanted more integration by parts.",
        )
    )

    body = _post(client, "more IBP")
    assert body["action"] == "queued_pinned"
    assert body["queue_item_id"] == qi_id

    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert inserts[0].payload["pinned"] is True


# ---------------------------------------------------------------------------
# no node match → graceful
# ---------------------------------------------------------------------------


def test_no_node_match_returns_graceful(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    # user_interests empty, global search empty
    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond("nodes", "select", lambda _: [])

    anthropic.queue(
        _classify_json(kind="drill", normalized_topic="obscure topic xyz")
    )

    body = _post(client, "more obscure topic xyz")
    assert body["action"] == "graceful"


# ---------------------------------------------------------------------------
# Fix 1: overloaded-prefix guard — a lone generic token must NOT match
# ---------------------------------------------------------------------------


def test_overloaded_token_does_not_match_unrelated_node(
    client: TestClient, fakes
) -> None:
    """'phase' alone is an overloaded token (Phase 10.5-rev §9 false positive).

    topic_match_tokens("phase") → empty set → no node match → graceful,
    even though the user has 'Phase Plane Analysis' as an interest.
    """
    supabase, anthropic = fakes
    node_id = str(uuid4())

    # User has a node whose title contains the overloaded word.
    supabase.respond(
        "user_interests",
        "select",
        lambda _: [{"node_id": node_id, "intent_context": ""}],
    )
    supabase.respond(
        "nodes",
        "select",
        lambda _: [{"id": node_id, "slug": "phase-plane-analysis", "title": "Phase Plane Analysis"}],
    )

    anthropic.queue(
        _classify_json(
            kind="drill",
            normalized_topic="phase",  # single overloaded token → empty after filtering
        )
    )

    body = _post(client, "more phase stuff")
    # No distinctive tokens → no node match → graceful.
    assert body["action"] == "graceful"
    # Nothing should have been queued.
    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert not inserts


def test_distinctive_token_still_matches(client: TestClient, fakes) -> None:
    """A topic whose tokens include a distinctive non-overloaded prefix must match.

    "quantum mechanics" → tokens include "quant" (not overloaded) → matches
    the "Quantum Mechanics" node title. Contrast with "phase" (overloaded →
    empty → no match in the preceding test).
    """
    supabase, anthropic = fakes
    node_id = str(uuid4())
    problem_id = str(uuid4())
    qi_id = str(uuid4())

    supabase.respond(
        "user_interests",
        "select",
        lambda _: [{"node_id": node_id, "intent_context": ""}],
    )
    supabase.respond(
        "nodes",
        "select",
        lambda _: [{"id": node_id, "slug": "quantum-mechanics", "title": "Quantum Mechanics"}],
    )
    supabase.respond("problems", "select", lambda _: [{"id": problem_id}])
    supabase.respond("queue_items", "insert", lambda _: [{"id": qi_id}])

    anthropic.queue(
        _classify_json(
            kind="existing_interest",
            normalized_topic="quantum mechanics",  # "quant" and "mecha" are NOT overloaded
            added_reason="You wanted more quantum mechanics.",
        )
    )

    body = _post(client, "more quantum")
    assert body["action"] == "queued_pinned"
    assert body["queue_item_id"] == qi_id
