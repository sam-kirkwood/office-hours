"""Tests for POST /parse-solution."""
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
def client(fakes) -> TestClient:  # noqa: ARG001 — fakes must be active
    return TestClient(app)


def _prime_attempt(
    supabase: FakeSupabase, *, attempt_id: str, user_id: str
) -> None:
    supabase.respond(
        "attempts",
        "select",
        lambda _: [{"id": attempt_id, "user_id": user_id}],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    response = client.post(
        "/parse-solution",
        json={"user_id": str(uuid4()), "attempt_id": str(uuid4()), "image_urls": []},
    )
    assert response.status_code == 401


def test_wrong_bearer_returns_401(client: TestClient) -> None:
    response = client.post(
        "/parse-solution",
        json={"user_id": str(uuid4()), "attempt_id": str(uuid4()), "image_urls": []},
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401


def test_attempt_not_found_returns_404(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("attempts", "select", lambda _: [])
    response = client.post(
        "/parse-solution",
        json={"user_id": str(uuid4()), "attempt_id": str(uuid4()), "image_urls": []},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


def test_user_id_mismatch_returns_403(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    attempt_id = str(uuid4())
    owner_id = str(uuid4())
    _prime_attempt(supabase, attempt_id=attempt_id, user_id=owner_id)
    response = client.post(
        "/parse-solution",
        json={
            "user_id": str(uuid4()),  # different from owner_id
            "attempt_id": attempt_id,
            "image_urls": [],
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 403


def test_happy_path_parses_and_updates_attempt(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    attempt_id = str(uuid4())
    llm_call_id = str(uuid4())

    _prime_attempt(supabase, attempt_id=attempt_id, user_id=user_id)
    supabase.respond("llm_calls", "insert", lambda _: [{"id": llm_call_id}])
    supabase.respond("attempts", "update", lambda _: [{"id": attempt_id}])

    anthropic.queue("## Solution\n\nThe answer is $x = 2$.")

    response = client.post(
        "/parse-solution",
        json={
            "user_id": user_id,
            "attempt_id": attempt_id,
            "image_urls": ["https://example.com/solution.jpg"],
        },
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["attempt_id"] == attempt_id
    assert data["parse_status"] == "parsed"
    assert "Solution" in data["parsed_markdown"]

    # Anthropic was called exactly once with an image content block.
    assert len(anthropic.messages.calls) == 1
    call = anthropic.messages.calls[0]
    user_content = call["messages"][0]["content"]
    assert any(block["type"] == "image" for block in user_content)
    assert any(block["type"] == "text" for block in user_content)

    # llm_calls row was written.
    llm_inserts = [c for c in supabase.calls if c.table == "llm_calls" and c.op == "insert"]
    assert len(llm_inserts) == 1

    # attempts row was updated with the right fields.
    attempt_updates = [
        c for c in supabase.calls if c.table == "attempts" and c.op == "update"
    ]
    assert len(attempt_updates) == 1
    payload = attempt_updates[0].payload
    assert payload["parse_status"] == "parsed"
    assert "Solution" in payload["parsed_markdown"]
    assert payload["parsed_by_llm_call_id"] == llm_call_id
    # The update must target the correct attempt row.
    assert ("eq", "id", attempt_id) in attempt_updates[0].filters


def test_empty_response_sets_failed_status(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    attempt_id = str(uuid4())

    _prime_attempt(supabase, attempt_id=attempt_id, user_id=user_id)
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("attempts", "update", lambda _: [{"id": attempt_id}])

    anthropic.queue("short")  # 5 chars — below the 10-char threshold

    response = client.post(
        "/parse-solution",
        json={
            "user_id": user_id,
            "attempt_id": attempt_id,
            "image_urls": [],
        },
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["parse_status"] == "failed"

    attempt_updates = [
        c for c in supabase.calls if c.table == "attempts" and c.op == "update"
    ]
    assert len(attempt_updates) == 1
    assert attempt_updates[0].payload["parse_status"] == "failed"
