"""Tests for POST /run-daily-planner (Phase 10-rev Step 3d).

This route is the per-user fan-out target the pg_cron daily job calls. It
wraps /plan-queue and /check-deferred, recording the outcome to
`curator_job_runs`. Sub-call failures are caught and recorded — they must not
block the other sub-call from running.

Coverage:
  - 401 plumbing.
  - Happy path: both sub-calls succeed; job row finishes with counts.
  - plan_queue raises → row records error; check_deferred still runs.
  - check_deferred raises → row records error; plan_queue counts preserved.
"""

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


def _empty_plan_response() -> str:
    """Sonnet plan with no recommendations — keeps /plan-queue side-effect-free."""
    return json.dumps({"recommendations": [], "observations": ""})


def _prime_minimal_plan_context(supabase: FakeSupabase) -> None:
    """The minimum responders /plan-queue's context loader touches. All return
    empty so the Sonnet call ends up with a sparse but valid input. The
    `plan-queue` call still happens — what we care about here is that
    /run-daily-planner threads the outcome counts into the job row."""
    supabase.respond("surveys", "select", lambda _c: [{"mode_balance": 0.5}])
    supabase.respond("user_interests", "select", lambda _c: [])
    supabase.respond("nodes", "select", lambda _c: [])
    supabase.respond("user_node_states", "select", lambda _c: [])
    supabase.respond("edges", "select", lambda _c: [])
    supabase.respond("attempts", "select", lambda _c: [])
    supabase.respond("paper_engagements", "select", lambda _c: [])
    supabase.respond("papers", "select", lambda _c: [])
    supabase.respond("surfaced_picks", "select", lambda _c: [])
    supabase.respond("user_preferences", "select", lambda _c: [])
    supabase.respond("queue_items", "select", lambda _c: [])
    supabase.respond("llm_calls", "insert", lambda _c: [{"id": str(uuid4())}])


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/run-daily-planner",
        json={"user_id": str(uuid4()), "triggered_by": "cron"},
    )
    assert resp.status_code == 401


def test_invalid_triggered_by_returns_422(client: TestClient) -> None:
    resp = client.post(
        "/run-daily-planner",
        json={"user_id": str(uuid4()), "triggered_by": "bogus"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_writes_job_row_with_counts(
    client: TestClient, fakes
) -> None:
    supabase, anthropic = fakes
    job_run_id = str(uuid4())

    _prime_minimal_plan_context(supabase)
    supabase.respond(
        "curator_job_runs", "insert", lambda _c: [{"id": job_run_id}]
    )
    supabase.respond(
        "curator_job_runs", "update", lambda _c: [{"id": job_run_id}]
    )
    anthropic.queue(_empty_plan_response())

    resp = client.post(
        "/run-daily-planner",
        json={"user_id": str(uuid4()), "triggered_by": "cron"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["job_run_id"] == job_run_id
    assert data["plan_queue_status"] == "ok"
    assert data["plan_queue_items_added"] == 0
    assert data["plan_queue_items_reprioritised"] == 0
    assert data["plan_queue_items_skipped"] == 0
    assert data["check_deferred_requeued"] == 0
    assert data["check_deferred_kept"] == 0
    assert data["error_message"] is None

    # One insert into curator_job_runs (start) + one update (finish).
    inserts = [
        c for c in supabase.calls
        if c.table == "curator_job_runs" and c.op == "insert"
    ]
    updates = [
        c for c in supabase.calls
        if c.table == "curator_job_runs" and c.op == "update"
    ]
    assert len(inserts) == 1
    assert inserts[0].payload["triggered_by"] == "cron"
    assert "started_at" in inserts[0].payload
    assert len(updates) == 1
    finished_payload = updates[0].payload
    assert finished_payload["plan_queue_status"] == "ok"
    assert finished_payload["error_message"] is None
    assert finished_payload["finished_at"] is not None


def test_cold_start_triggered_by_recorded(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    job_run_id = str(uuid4())

    _prime_minimal_plan_context(supabase)
    supabase.respond(
        "curator_job_runs", "insert", lambda _c: [{"id": job_run_id}]
    )
    supabase.respond(
        "curator_job_runs", "update", lambda _c: [{"id": job_run_id}]
    )
    anthropic.queue(_empty_plan_response())

    resp = client.post(
        "/run-daily-planner",
        json={"user_id": str(uuid4()), "triggered_by": "cold_start"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    inserts = [
        c for c in supabase.calls
        if c.table == "curator_job_runs" and c.op == "insert"
    ]
    assert inserts[0].payload["triggered_by"] == "cold_start"


# ---------------------------------------------------------------------------
# Partial failure: plan_queue raises
# ---------------------------------------------------------------------------


def test_plan_queue_failure_still_runs_check_deferred(
    client: TestClient, fakes
) -> None:
    supabase, _ = fakes
    job_run_id = str(uuid4())

    # Force plan-queue's context-build to blow up by making one of its
    # foundational queries raise. user_interests is hit early in
    # build_curator_context — failing here propagates up before Sonnet is
    # called, exercising the outer except.
    _prime_minimal_plan_context(supabase)
    supabase.respond(
        "user_interests",
        "select",
        lambda _c: RuntimeError("simulated supabase failure"),
    )

    supabase.respond(
        "curator_job_runs", "insert", lambda _c: [{"id": job_run_id}]
    )
    supabase.respond(
        "curator_job_runs", "update", lambda _c: [{"id": job_run_id}]
    )
    # check_deferred reads queue_items (already primed as [] above).

    resp = client.post(
        "/run-daily-planner",
        json={"user_id": str(uuid4()), "triggered_by": "cron"},
        headers=AUTH_HEADERS,
    )

    # The route still returns 200 — partial failure is recorded, not raised.
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["plan_queue_status"] == "error"
    assert data["error_message"] is not None
    assert "plan_queue" in data["error_message"]
    # check_deferred still ran on the empty queue.
    assert data["check_deferred_requeued"] == 0
    assert data["check_deferred_kept"] == 0

    updates = [
        c for c in supabase.calls
        if c.table == "curator_job_runs" and c.op == "update"
    ]
    assert len(updates) == 1
    assert updates[0].payload["plan_queue_status"] == "error"
    assert updates[0].payload["finished_at"] is not None


# ---------------------------------------------------------------------------
# Partial failure: check_deferred raises (plan-queue still recorded ok)
# ---------------------------------------------------------------------------


def test_check_deferred_failure_preserves_plan_queue_counts(
    client: TestClient, fakes
) -> None:
    """plan-queue succeeds on an empty context; check-deferred is forced to
    fail when its `problems` lookup raises. Counts and error_message reflect
    the partial outcome."""
    supabase, anthropic = fakes
    job_run_id = str(uuid4())
    deferred_queue_id = str(uuid4())
    deferred_problem_id = str(uuid4())

    _prime_minimal_plan_context(supabase)

    # queue_items dispatcher: tolerate plan-queue's reads (return []) but
    # return a deferred row for check-deferred so its first downstream query
    # against `problems` runs — that's where we inject the failure.
    deferred_calls = {"n": 0}

    def queue_items_responder(call):
        filters = call.filters
        is_deferred_eq = any(
            f[0] == "eq" and f[1] == "state" and f[2] == "deferred"
            for f in filters
        )
        if not is_deferred_eq:
            return []  # plan-queue's queue-summary read
        deferred_calls["n"] += 1
        if deferred_calls["n"] == 1:
            # plan-queue's load_recent_engagement deferred-items pull.
            return []
        # check-deferred's first read.
        return [
            {
                "id": deferred_queue_id,
                "kind": "problem",
                "ref_id": deferred_problem_id,
            }
        ]

    supabase.respond("queue_items", "select", queue_items_responder)
    # plan-queue doesn't touch `problems` on an empty-interest context;
    # check-deferred does (to resolve topic_node_id) — make it raise.
    supabase.respond(
        "problems",
        "select",
        lambda _c: RuntimeError("simulated problems read failure"),
    )

    supabase.respond(
        "curator_job_runs", "insert", lambda _c: [{"id": job_run_id}]
    )
    supabase.respond(
        "curator_job_runs", "update", lambda _c: [{"id": job_run_id}]
    )

    anthropic.queue(_empty_plan_response())

    resp = client.post(
        "/run-daily-planner",
        json={"user_id": str(uuid4()), "triggered_by": "manual"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["plan_queue_status"] == "ok"
    assert data["error_message"] is not None
    assert "check_deferred" in data["error_message"]
    assert data["check_deferred_requeued"] == 0
    assert data["check_deferred_kept"] == 0

    updates = [
        c for c in supabase.calls
        if c.table == "curator_job_runs" and c.op == "update"
    ]
    assert len(updates) == 1
    assert updates[0].payload["plan_queue_status"] == "ok"
    assert "check_deferred" in updates[0].payload["error_message"]


# ---------------------------------------------------------------------------
# p1 — paper top-up after planner
# ---------------------------------------------------------------------------


def _prime_plan_context_with_balance(
    supabase: FakeSupabase, mode_balance: float
) -> None:
    """Like _prime_minimal_plan_context but with a configurable mode_balance."""
    supabase.respond("surveys", "select", lambda _c: [{"mode_balance": mode_balance}])
    supabase.respond("user_interests", "select", lambda _c: [])
    supabase.respond("nodes", "select", lambda _c: [])
    supabase.respond("user_node_states", "select", lambda _c: [])
    supabase.respond("edges", "select", lambda _c: [])
    supabase.respond("attempts", "select", lambda _c: [])
    supabase.respond("paper_engagements", "select", lambda _c: [])
    supabase.respond("papers", "select", lambda _c: [])
    supabase.respond("surfaced_picks", "select", lambda _c: [])
    supabase.respond("user_preferences", "select", lambda _c: [])
    supabase.respond("queue_items", "select", lambda _c: [])
    supabase.respond("notebook_entries", "select", lambda _c: [])
    supabase.respond("llm_calls", "insert", lambda _c: [{"id": str(uuid4())}])


def test_paper_topup_fires_when_balance_high(
    client: TestClient, fakes
) -> None:
    """mode_balance=0.7 → paper top-up calls Sonnet after the planner.

    Two Sonnet responses must be queued: one for plan-queue, one for the
    propose-papers top-up. If topup fires, both are consumed.
    """
    supabase, anthropic = fakes
    job_run_id = str(uuid4())

    _prime_plan_context_with_balance(supabase, 0.7)
    supabase.respond("curator_job_runs", "insert", lambda _c: [{"id": job_run_id}])
    supabase.respond("curator_job_runs", "update", lambda _c: [{"id": job_run_id}])

    # Planner response + propose-papers response (empty candidates OK).
    anthropic.queue(_empty_plan_response())
    anthropic.queue(json.dumps({"candidates": []}))

    resp = client.post(
        "/run-daily-planner",
        json={"user_id": str(uuid4()), "triggered_by": "cron"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    # Both Sonnet responses consumed → topup did fire.
    assert len(anthropic.messages.calls) == 2
    # Planner-no-papers rule: the planner's OWN call should not mention
    # "paper_engagement" in its output (we returned [] recommendations).
    plan_call = anthropic.messages.calls[0]
    assert plan_call is not None  # planner ran
    # Second call was the propose-papers Sonnet call.
    propose_call = anthropic.messages.calls[1]
    assert propose_call is not None


def test_paper_topup_skips_when_balance_low(
    client: TestClient, fakes
) -> None:
    """mode_balance=0.2 < 0.3 → paper top-up skipped; only one Sonnet call."""
    supabase, anthropic = fakes
    job_run_id = str(uuid4())

    _prime_plan_context_with_balance(supabase, 0.2)
    supabase.respond("curator_job_runs", "insert", lambda _c: [{"id": job_run_id}])
    supabase.respond("curator_job_runs", "update", lambda _c: [{"id": job_run_id}])

    # Only one Sonnet response queued — topup should NOT consume a second.
    anthropic.queue(_empty_plan_response())

    resp = client.post(
        "/run-daily-planner",
        json={"user_id": str(uuid4()), "triggered_by": "cron"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert len(anthropic.messages.calls) == 1  # only planner called Sonnet
