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

PAPER_ID = str(uuid4())

VALID_ENGAGEMENT_JSON = json.dumps(
    {
        "why_this_md": "This connects to your interests.",
        "orienting_concepts_json": ["gravitational waves", "LIGO"],
        "questions_json": [
            {"id": str(uuid4()), "kind": "comprehension", "prompt_md": "Q1?", "order": 1},
            {"id": str(uuid4()), "kind": "critical", "prompt_md": "Q2?", "order": 2},
            {"id": str(uuid4()), "kind": "connective", "prompt_md": "Q3?", "order": 3},
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


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post("/suggest-papers", json={"user_id": str(uuid4())})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# No papers → empty list (no Haiku call)
# ---------------------------------------------------------------------------


def test_no_papers_returns_empty(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond("papers", "select", lambda _: [])

    resp = client.post(
        "/suggest-papers",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["suggested"] == []
    # Haiku must NOT have been called
    assert anthropic.messages.calls == []


# ---------------------------------------------------------------------------
# Happy path — suggests paper and creates queue item
# ---------------------------------------------------------------------------


def test_happy_path_suggests_and_creates_queue_items(
    client: TestClient, fakes
) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    engagement_id = str(uuid4())
    queue_item_id = str(uuid4())

    supabase.respond("user_interests", "select", lambda _: [{"node_id": str(uuid4())}])
    supabase.respond("nodes", "select", lambda _: [{"title": "Gravitational Waves"}])
    supabase.respond(
        "papers",
        "select",
        lambda _: [
            {
                "id": PAPER_ID,
                "title": "GW Detection",
                "abstract_md": "We detected gravitational waves.",
            }
        ],
    )
    # Haiku relevance response
    anthropic.queue(json.dumps({"relevant_paper_ids": [PAPER_ID]}))
    # No existing engagements
    supabase.respond("paper_engagements", "select", lambda _: [])
    # generate_engagement_for_paper calls: paper select, user_interests select, nodes select,
    # llm_calls insert, paper_engagements insert
    supabase.respond(
        "papers",
        "select",
        lambda _: [
            {
                "id": PAPER_ID,
                "title": "GW Detection",
                "abstract_md": "We detected gravitational waves.",
                "authors_json": ["Abbott, B."],
                "year": 2016,
            }
        ],
    )
    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("paper_engagements", "insert", lambda _: [{"id": engagement_id}])
    # Sonnet engagement generation
    anthropic.queue(VALID_ENGAGEMENT_JSON)
    # queue_items insert
    supabase.respond("queue_items", "insert", lambda _: [{"id": queue_item_id}])

    resp = client.post(
        "/suggest-papers",
        json={"user_id": user_id},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["suggested"]) == 1
    assert data["suggested"][0]["paper_id"] == PAPER_ID
    assert data["suggested"][0]["queue_item_id"] == queue_item_id

    qi_inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(qi_inserts) == 1
    row = qi_inserts[0].payload
    assert row["kind"] == "paper_engagement"
    assert row["ref_id"] == engagement_id


# ---------------------------------------------------------------------------
# Already-suggested paper is skipped
# ---------------------------------------------------------------------------


def test_already_suggested_paper_skipped(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())

    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond(
        "papers",
        "select",
        lambda _: [{"id": PAPER_ID, "title": "GW Detection", "abstract_md": "We detected GW."}],
    )
    anthropic.queue(json.dumps({"relevant_paper_ids": [PAPER_ID]}))
    # Existing engagement for this user+paper
    supabase.respond(
        "paper_engagements", "select", lambda _: [{"paper_id": PAPER_ID}]
    )

    resp = client.post(
        "/suggest-papers",
        json={"user_id": user_id},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200
    assert resp.json()["suggested"] == []
    # No queue items should have been written
    assert not any(c.table == "queue_items" and c.op == "insert" for c in supabase.calls)
