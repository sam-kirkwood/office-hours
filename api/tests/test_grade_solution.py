"""Tests for POST /grade-solution."""
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

VALID_GRADE_JSON = json.dumps(
    {"response_md": "Good start on the energy conservation argument. However..."}
)


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
def client(fakes) -> TestClient:  # noqa: ARG001 — fakes must be active
    return TestClient(app)


def _prime_full(
    supabase: FakeSupabase,
    *,
    attempt_id: str,
    user_id: str,
    problem_id: str,
    node_id: str,
    solution_md: str = "SOLUTION_KEY_DO_NOT_SEND",
) -> str:
    """Register all responders for a successful grade call. Returns notebook_entry_id."""
    notebook_entry_id = str(uuid4())

    supabase.respond(
        "attempts",
        "select",
        lambda _: [{"id": attempt_id, "user_id": user_id, "problem_id": problem_id}],
    )
    supabase.respond(
        "problems",
        "select",
        lambda _: [
            {
                "statement_md": "Derive the time-dilation formula.",
                "rubric_md": "Uses Lorentz transform; derives $\\Delta t' = \\gamma \\Delta t$.",
                "topic_node_id": node_id,
                # solution_md is present on the DB row but the route must NOT select it
                "solution_md": solution_md,
            }
        ],
    )
    supabase.respond(
        "nodes",
        "select",
        lambda _: [{"title": "Special Relativity", "slug": "special-relativity"}],
    )
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("attempts", "update", lambda _: [{"id": attempt_id}])
    supabase.respond(
        "notebook_entries",
        "insert",
        lambda _: [{"id": notebook_entry_id}],
    )

    return notebook_entry_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    response = client.post(
        "/grade-solution",
        json={
            "user_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "user_edited_markdown": "My work here.",
        },
    )
    assert response.status_code == 401


def test_attempt_not_found_returns_404(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("attempts", "select", lambda _: [])
    response = client.post(
        "/grade-solution",
        json={
            "user_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "user_edited_markdown": "My work here.",
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


def test_user_id_mismatch_returns_403(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    attempt_id = str(uuid4())
    owner_id = str(uuid4())
    supabase.respond(
        "attempts",
        "select",
        lambda _: [{"id": attempt_id, "user_id": owner_id, "problem_id": str(uuid4())}],
    )
    response = client.post(
        "/grade-solution",
        json={
            "user_id": str(uuid4()),  # different from owner_id
            "attempt_id": attempt_id,
            "user_edited_markdown": "My work here.",
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 403


def test_happy_path_grades_and_creates_notebook_entry(
    client: TestClient, fakes
) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    attempt_id = str(uuid4())
    problem_id = str(uuid4())
    node_id = str(uuid4())
    user_work = "I used the Lorentz factor $\\gamma$ to derive..."

    notebook_entry_id = _prime_full(
        supabase,
        attempt_id=attempt_id,
        user_id=user_id,
        problem_id=problem_id,
        node_id=node_id,
    )
    anthropic.queue(VALID_GRADE_JSON)

    response = client.post(
        "/grade-solution",
        json={
            "user_id": user_id,
            "attempt_id": attempt_id,
            "user_edited_markdown": user_work,
        },
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["grade_response_md"] == "Good start on the energy conservation argument. However..."
    assert data["notebook_entry_id"] == notebook_entry_id

    # Sonnet called exactly once.
    assert len(anthropic.messages.calls) == 1

    # llm_calls written.
    llm_inserts = [c for c in supabase.calls if c.table == "llm_calls" and c.op == "insert"]
    assert len(llm_inserts) == 1

    # attempt updated with grade, user work, and submitted_at.
    attempt_updates = [
        c for c in supabase.calls if c.table == "attempts" and c.op == "update"
    ]
    assert len(attempt_updates) == 1
    payload = attempt_updates[0].payload
    assert payload["user_edited_markdown"] == user_work
    assert payload["grade_response_md"] == "Good start on the energy conservation argument. However..."
    assert payload["submitted_at"] is not None
    assert ("eq", "id", attempt_id) in attempt_updates[0].filters

    # notebook entry written with correct shape.
    nb_inserts = [
        c for c in supabase.calls if c.table == "notebook_entries" and c.op == "insert"
    ]
    assert len(nb_inserts) == 1
    nb_payload = nb_inserts[0].payload
    assert nb_payload["user_id"] == user_id
    assert nb_payload["entry_kind"] == "problem_attempt"
    assert nb_payload["ref_id"] == attempt_id
    assert nb_payload["title"] == "Special Relativity — Problem"
    assert nb_payload["topic_node_slugs"] == ["special-relativity"]
    assert "fts_vector" not in nb_payload


def test_solution_md_not_sent_to_claude(client: TestClient, fakes) -> None:
    """solution_md is the answer key — it must never appear in the grading prompt."""
    supabase, anthropic = fakes
    user_id = str(uuid4())
    attempt_id = str(uuid4())
    secret = "SECRET_ANSWER_USE_MAXWELL_EQUATIONS_DIRECTLY"

    _prime_full(
        supabase,
        attempt_id=attempt_id,
        user_id=user_id,
        problem_id=str(uuid4()),
        node_id=str(uuid4()),
        solution_md=secret,
    )
    anthropic.queue(VALID_GRADE_JSON)

    response = client.post(
        "/grade-solution",
        json={
            "user_id": user_id,
            "attempt_id": attempt_id,
            "user_edited_markdown": "My work.",
        },
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    # The secret must not appear anywhere in the Anthropic call.
    call = anthropic.messages.calls[0]
    user_msg = call["messages"][0]["content"]
    assert secret not in user_msg
    system_text = " ".join(
        block["text"] for block in call.get("system", []) if block.get("type") == "text"
    )
    assert secret not in system_text
