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

VALID_GRADE_JSON = json.dumps({"response_md": "Good attempt — you nailed the detection sigma."})

Q1_ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
Q2_ID = "550e8400-e29b-41d4-a716-446655440000"
Q3_ID = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"

QUESTIONS = [
    {"id": Q1_ID, "kind": "comprehension", "prompt_md": "What is the significance?", "order": 1},
    {"id": Q2_ID, "kind": "critical", "prompt_md": "What assumptions are made?", "order": 2},
    {"id": Q3_ID, "kind": "connective", "prompt_md": "How does this connect to GR?", "order": 3},
]


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


def _prime_engagement(
    supabase: FakeSupabase,
    *,
    engagement_id: str,
    user_id: str,
    paper_id: str,
    questions: list[dict] | None = None,
    current_index: int = 0,
) -> None:
    supabase.respond(
        "paper_engagements",
        "select",
        lambda _: [
            {
                "id": engagement_id,
                "user_id": user_id,
                "paper_id": paper_id,
                "questions_json": questions if questions is not None else QUESTIONS,
                "current_question_index": current_index,
                "state": "pending",
            }
        ],
    )


def _prime_paper(supabase: FakeSupabase, paper_id: str) -> None:
    supabase.respond(
        "papers",
        "select",
        lambda _: [{"abstract_md": "We report the detection of gravitational waves."}],
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/grade-paper-answer",
        json={
            "user_id": str(uuid4()),
            "engagement_id": str(uuid4()),
            "question_id": Q1_ID,
            "user_response_md": "My answer.",
        },
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Not found / forbidden
# ---------------------------------------------------------------------------


def test_engagement_not_found_returns_404(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("paper_engagements", "select", lambda _: [])
    resp = client.post(
        "/grade-paper-answer",
        json={
            "user_id": str(uuid4()),
            "engagement_id": str(uuid4()),
            "question_id": Q1_ID,
            "user_response_md": "My answer.",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


def test_user_id_mismatch_returns_403(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    engagement_id = str(uuid4())
    real_user_id = str(uuid4())
    wrong_user_id = str(uuid4())
    paper_id = str(uuid4())
    _prime_engagement(supabase, engagement_id=engagement_id, user_id=real_user_id, paper_id=paper_id)
    resp = client.post(
        "/grade-paper-answer",
        json={
            "user_id": wrong_user_id,
            "engagement_id": engagement_id,
            "question_id": Q1_ID,
            "user_response_md": "My answer.",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 403


def test_question_not_found_returns_404(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    user_id = str(uuid4())
    engagement_id = str(uuid4())
    paper_id = str(uuid4())
    _prime_engagement(supabase, engagement_id=engagement_id, user_id=user_id, paper_id=paper_id)
    _prime_paper(supabase, paper_id)
    resp = client.post(
        "/grade-paper-answer",
        json={
            "user_id": user_id,
            "engagement_id": engagement_id,
            "question_id": "not-a-real-question-id",
            "user_response_md": "My answer.",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Happy path — advances index
# ---------------------------------------------------------------------------


def test_happy_path_grades_and_advances_index(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    engagement_id = str(uuid4())
    paper_id = str(uuid4())
    _prime_engagement(supabase, engagement_id=engagement_id, user_id=user_id, paper_id=paper_id)
    _prime_paper(supabase, paper_id)
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("paper_answers", "upsert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("paper_engagements", "update", lambda _: [{"id": engagement_id}])
    anthropic.queue(VALID_GRADE_JSON)

    resp = client.post(
        "/grade-paper-answer",
        json={
            "user_id": user_id,
            "engagement_id": engagement_id,
            "question_id": Q1_ID,  # order=1; next should be index 1
            "user_response_md": "5-sigma significance.",
        },
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "Good attempt" in data["claude_response_md"]
    assert data["next_question_index"] == 1  # moved to index of order=2 question

    upserts = [c for c in supabase.calls if c.table == "paper_answers" and c.op == "upsert"]
    assert len(upserts) == 1
    assert upserts[0].payload["question_id"] == Q1_ID

    updates = [c for c in supabase.calls if c.table == "paper_engagements" and c.op == "update"]
    assert len(updates) == 1
    assert updates[0].payload["state"] == "in_progress"
    assert updates[0].payload["current_question_index"] == 1


# ---------------------------------------------------------------------------
# Last question → completed
# ---------------------------------------------------------------------------


def test_last_question_sets_completed(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    engagement_id = str(uuid4())
    paper_id = str(uuid4())
    _prime_engagement(supabase, engagement_id=engagement_id, user_id=user_id, paper_id=paper_id)
    _prime_paper(supabase, paper_id)
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("paper_answers", "upsert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("paper_engagements", "update", lambda _: [{"id": engagement_id}])
    anthropic.queue(VALID_GRADE_JSON)

    resp = client.post(
        "/grade-paper-answer",
        json={
            "user_id": user_id,
            "engagement_id": engagement_id,
            "question_id": Q3_ID,  # order=3 — last question
            "user_response_md": "This connects to the prediction of GR.",
        },
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["next_question_index"] == -1

    updates = [c for c in supabase.calls if c.table == "paper_engagements" and c.op == "update"]
    assert len(updates) == 1
    update_payload = updates[0].payload
    assert update_payload["state"] == "completed"
    assert "completed_at" in update_payload
