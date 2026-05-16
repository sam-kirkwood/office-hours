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

CLAUDE_RESPONSE = "Great question! The strain amplitude represents the fractional change in length."


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


def _prime(
    supabase: FakeSupabase,
    *,
    engagement_id: str,
    user_id: str,
    paper_id: str,
    prior_turns: list[dict] | None = None,
) -> None:
    supabase.respond(
        "paper_engagements",
        "select",
        lambda _: [{"id": engagement_id, "user_id": user_id, "paper_id": paper_id}],
    )
    supabase.respond(
        "papers",
        "select",
        lambda _: [
            {
                "title": "Observation of Gravitational Waves",
                "abstract_md": "We report the detection.",
                "year": 2016,
            }
        ],
    )
    supabase.respond("paper_qa", "select", lambda _: prior_turns or [])


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/paper-question",
        json={
            "user_id": str(uuid4()),
            "engagement_id": str(uuid4()),
            "user_message_md": "What is strain?",
        },
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------


def test_engagement_not_found_returns_404(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("paper_engagements", "select", lambda _: [])
    resp = client.post(
        "/paper-question",
        json={
            "user_id": str(uuid4()),
            "engagement_id": str(uuid4()),
            "user_message_md": "What is strain?",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Happy path — first turn
# ---------------------------------------------------------------------------


def test_happy_path_creates_qa_turn(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    engagement_id = str(uuid4())
    paper_id = str(uuid4())
    _prime(supabase, engagement_id=engagement_id, user_id=user_id, paper_id=paper_id)
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("paper_qa", "insert", lambda _: [{"id": str(uuid4())}])
    anthropic.queue(CLAUDE_RESPONSE)

    resp = client.post(
        "/paper-question",
        json={
            "user_id": user_id,
            "engagement_id": engagement_id,
            "user_message_md": "What is gravitational wave strain?",
        },
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["claude_response_md"] == CLAUDE_RESPONSE
    assert data["turn_index"] == 0  # first turn

    inserts = [c for c in supabase.calls if c.table == "paper_qa" and c.op == "insert"]
    assert len(inserts) == 1
    row = inserts[0].payload
    assert row["turn_index"] == 0
    assert row["user_message_md"] == "What is gravitational wave strain?"
    assert row["claude_response_md"] == CLAUDE_RESPONSE

    assert len(anthropic.messages.calls) == 1


# ---------------------------------------------------------------------------
# Prior turns included in message history
# ---------------------------------------------------------------------------


def test_conversation_history_included(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    engagement_id = str(uuid4())
    paper_id = str(uuid4())
    prior_turns = [
        {
            "turn_index": 0,
            "user_message_md": "What is strain?",
            "claude_response_md": "Strain is the fractional length change.",
        }
    ]
    _prime(
        supabase,
        engagement_id=engagement_id,
        user_id=user_id,
        paper_id=paper_id,
        prior_turns=prior_turns,
    )
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("paper_qa", "insert", lambda _: [{"id": str(uuid4())}])
    anthropic.queue("Follow-up answer.")

    resp = client.post(
        "/paper-question",
        json={
            "user_id": user_id,
            "engagement_id": engagement_id,
            "user_message_md": "Can you expand on that?",
        },
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["turn_index"] == 1

    call_kwargs = anthropic.messages.calls[0]
    messages = call_kwargs["messages"]
    # history: [prior user, prior assistant, new user] = 3 messages
    assert len(messages) == 3
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "What is strain?"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "Can you expand on that?"
