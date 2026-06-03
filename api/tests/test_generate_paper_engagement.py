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

VALID_ENGAGEMENT_JSON = json.dumps(
    {
        "why_this_md": "This paper is directly relevant to your interest in gravitational waves.",
        "orienting_concepts_json": [
            {
                "term": "gravitational wave strain",
                "definition_md": "The fractional change in length a gravitational wave induces in a detector arm.",
            },
            {
                "term": "matched filtering",
                "definition_md": "Cross-correlating data against a template waveform to extract a known signal from noise.",
            },
            {
                "term": "interferometer noise floor",
                "definition_md": "The minimum strain detectable above the instrument's intrinsic noise.",
            },
        ],
        "questions_json": [
            {
                "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "kind": "comprehension",
                "prompt_md": "What is the reported significance of the detection?",
                "order": 1,
            },
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "kind": "critical",
                "prompt_md": "What assumptions underlie the matched filtering approach?",
                "order": 2,
            },
            {
                "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                "kind": "connective",
                "prompt_md": "How does this connect to GR predictions you have studied?",
                "order": 3,
            },
        ],
    }
)


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


def _prime_paper(supabase: FakeSupabase, paper_id: str) -> None:
    supabase.respond(
        "papers",
        "select",
        lambda _: [
            {
                "id": paper_id,
                "title": "Observation of Gravitational Waves",
                "abstract_md": "We report the direct observation of gravitational waves.",
                "authors_json": ["Abbott, B."],
                "year": 2016,
            }
        ],
    )


def _prime_no_interests(supabase: FakeSupabase) -> None:
    supabase.respond("user_interests", "select", lambda _: [])


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/generate-paper-engagement",
        json={"user_id": str(uuid4()), "paper_id": str(uuid4())},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------


def test_paper_not_found_returns_404(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("papers", "select", lambda _: [])
    resp = client.post(
        "/generate-paper-engagement",
        json={"user_id": str(uuid4()), "paper_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_creates_engagement(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    paper_id = str(uuid4())
    engagement_id = str(uuid4())
    _prime_paper(supabase, paper_id)
    _prime_no_interests(supabase)
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("paper_engagements", "insert", lambda _: [{"id": engagement_id}])
    anthropic.queue(VALID_ENGAGEMENT_JSON)

    resp = client.post(
        "/generate-paper-engagement",
        json={"user_id": str(uuid4()), "paper_id": paper_id},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["engagement_id"] == engagement_id

    inserts = [c for c in supabase.calls if c.table == "paper_engagements" and c.op == "insert"]
    assert len(inserts) == 1
    row = inserts[0].payload
    assert row["state"] == "pending"
    assert row["current_question_index"] == 0
    assert len(row["questions_json"]) == 3
    assert len(anthropic.messages.calls) == 1


# ---------------------------------------------------------------------------
# Question count validation
# ---------------------------------------------------------------------------


def test_question_count_out_of_range_returns_500(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    paper_id = str(uuid4())
    _prime_paper(supabase, paper_id)
    _prime_no_interests(supabase)
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])

    bad_json = json.dumps(
        {
            "why_this_md": "Relevant.",
            "orienting_concepts_json": [{"term": "concept", "definition_md": "A concept."}],
            "questions_json": [
                # Only 2 questions — below the minimum of 3
                {"id": str(uuid4()), "kind": "comprehension", "prompt_md": "Q1?", "order": 1},
                {"id": str(uuid4()), "kind": "critical", "prompt_md": "Q2?", "order": 2},
            ],
        }
    )
    anthropic.queue(bad_json)

    resp = client.post(
        "/generate-paper-engagement",
        json={"user_id": str(uuid4()), "paper_id": paper_id},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 500
    assert "out of range" in resp.json()["detail"]
