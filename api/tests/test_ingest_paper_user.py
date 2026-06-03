"""Tests for POST /ingest-paper-user.

External HTTP calls (arXiv, CrossRef) are mocked via unittest.mock.patch so
no real network requests are made during the test run.
"""

import json
from unittest.mock import MagicMock, patch
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
ENGAGEMENT_ID = str(uuid4())
QUEUE_ITEM_ID = str(uuid4())

VALID_ENGAGEMENT_JSON = json.dumps(
    {
        "why_this_md": "This connects to your work on gravitational physics.",
        "orienting_concepts_json": [
            {"term": "general relativity", "definition_md": "Einstein's theory of gravity as spacetime curvature."},
            {"term": "interferometry", "definition_md": "Measuring tiny length differences via wave superposition."},
        ],
        "questions_json": [
            {"id": str(uuid4()), "kind": "comprehension", "prompt_md": "Q1?", "order": 1},
            {"id": str(uuid4()), "kind": "critical", "prompt_md": "Q2?", "order": 2},
            {"id": str(uuid4()), "kind": "connective", "prompt_md": "Q3?", "order": 3},
        ],
    }
)

# Minimal Atom XML response from export.arxiv.org/api/query
ARXIV_ATOM_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Observation of Gravitational Waves from a Binary Black Hole Merger</title>
    <author><name>Abbott, B. P.</name></author>
    <author><name>Abbott, R.</name></author>
    <published>2016-02-11T16:00:00Z</published>
    <summary>We report the first direct observation of gravitational waves.</summary>
  </entry>
</feed>
"""

CROSSREF_JSON = json.dumps(
    {
        "status": "ok",
        "message": {
            "title": ["Detection of Gravitational Waves"],
            "author": [{"family": "Abbott", "given": "B."}],
            "published-print": {"date-parts": [[2016, 2, 11]]},
            "abstract": "We report the first direct observation.",
        },
    }
)


def _make_http_mock(text: str) -> MagicMock:
    """Return a mock that looks like a successful httpx response.

    If text is valid JSON, .json() returns the parsed value; otherwise it
    raises (the route only calls .json() on CrossRef, not arXiv XML).
    """
    mock_resp = MagicMock()
    mock_resp.text = text
    try:
        parsed = json.loads(text)
        mock_resp.json.return_value = parsed
    except json.JSONDecodeError:
        mock_resp.json.side_effect = json.JSONDecodeError("not json", "", 0)
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


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


def _wire_engagement(supabase: FakeSupabase, anthropic: FakeAnthropic) -> None:
    """Register the DB and LLM responses that generate_engagement_for_paper needs."""
    supabase.respond(
        "papers",
        "select",
        lambda _: [
            {
                "id": PAPER_ID,
                "title": "Observation of Gravitational Waves",
                "abstract_md": "We report...",
                "authors_json": ["Abbott, B. P."],
                "year": 2016,
            }
        ],
    )
    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("paper_engagements", "insert", lambda _: [{"id": ENGAGEMENT_ID}])
    anthropic.queue(VALID_ENGAGEMENT_JSON)
    supabase.respond("queue_items", "insert", lambda _: [{"id": QUEUE_ITEM_ID}])


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/ingest-paper-user",
        json={"user_id": str(uuid4()), "raw_input": "2301.07041"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# arXiv ID path
# ---------------------------------------------------------------------------


@patch("routes.ingest_paper_user.httpx.get")
def test_arxiv_id_resolved_and_inserted(
    mock_get: MagicMock, client: TestClient, fakes: tuple
) -> None:
    supabase, anthropic = fakes
    mock_get.return_value = _make_http_mock(ARXIV_ATOM_XML)

    # papers/select: first call = arxiv_id dedup check (returns []),
    # second call = load paper for engagement generation (returns paper row).
    call_count = {"n": 0}

    def papers_select(call):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return []
        return [
            {
                "id": PAPER_ID,
                "title": "Observation of Gravitational Waves",
                "abstract_md": "We report...",
                "authors_json": ["Abbott, B. P."],
                "year": 2016,
            }
        ]

    supabase.respond("papers", "select", papers_select)
    supabase.respond("papers", "insert", lambda _: [{"id": PAPER_ID}])
    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("paper_engagements", "insert", lambda _: [{"id": ENGAGEMENT_ID}])
    anthropic.queue(VALID_ENGAGEMENT_JSON)
    supabase.respond("queue_items", "insert", lambda _: [{"id": QUEUE_ITEM_ID}])

    resp = client.post(
        "/ingest-paper-user",
        json={"user_id": str(uuid4()), "raw_input": "2301.07041"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["paper_id"] == PAPER_ID
    assert data["created"] is True
    assert data["engagement_id"] == ENGAGEMENT_ID
    assert data["queue_item_id"] == QUEUE_ITEM_ID

    inserts = [c for c in supabase.calls if c.table == "papers" and c.op == "insert"]
    assert len(inserts) == 1
    row = inserts[0].payload
    assert row["arxiv_id"] == "2301.07041"

    qi_inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(qi_inserts) == 1
    assert qi_inserts[0].payload["kind"] == "paper_engagement"
    assert qi_inserts[0].payload["priority_score"] == 0.8


# ---------------------------------------------------------------------------
# arXiv URL parsed to ID (same code path)
# ---------------------------------------------------------------------------


@patch("routes.ingest_paper_user.httpx.get")
def test_arxiv_url_parsed_to_id(
    mock_get: MagicMock, client: TestClient, fakes: tuple
) -> None:
    supabase, anthropic = fakes
    mock_get.return_value = _make_http_mock(ARXIV_ATOM_XML)

    call_count = {"n": 0}

    def papers_select(call):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return []
        return [
            {
                "id": PAPER_ID,
                "title": "Observation of Gravitational Waves",
                "abstract_md": "We report...",
                "authors_json": ["Abbott, B. P."],
                "year": 2016,
            }
        ]

    supabase.respond("papers", "select", papers_select)
    supabase.respond("papers", "insert", lambda _: [{"id": PAPER_ID}])
    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("paper_engagements", "insert", lambda _: [{"id": ENGAGEMENT_ID}])
    anthropic.queue(VALID_ENGAGEMENT_JSON)
    supabase.respond("queue_items", "insert", lambda _: [{"id": QUEUE_ITEM_ID}])

    resp = client.post(
        "/ingest-paper-user",
        json={"user_id": str(uuid4()), "raw_input": "https://arxiv.org/abs/2301.07041"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    # Confirm the ID extracted from the URL was used in the arXiv API call
    called_url = mock_get.call_args[0][0]
    assert "2301.07041" in called_url

    inserts = [c for c in supabase.calls if c.table == "papers" and c.op == "insert"]
    assert len(inserts) == 1
    assert inserts[0].payload["arxiv_id"] == "2301.07041"


# ---------------------------------------------------------------------------
# DOI path
# ---------------------------------------------------------------------------


@patch("routes.ingest_paper_user.httpx.get")
def test_doi_resolved_and_inserted(
    mock_get: MagicMock, client: TestClient, fakes: tuple
) -> None:
    supabase, anthropic = fakes
    mock_get.return_value = _make_http_mock(CROSSREF_JSON)

    call_count = {"n": 0}

    def papers_select(call):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return []  # doi dedup check
        return [
            {
                "id": PAPER_ID,
                "title": "Detection of Gravitational Waves",
                "abstract_md": "We report...",
                "authors_json": ["Abbott, B."],
                "year": 2016,
            }
        ]

    supabase.respond("papers", "select", papers_select)
    supabase.respond("papers", "insert", lambda _: [{"id": PAPER_ID}])
    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("paper_engagements", "insert", lambda _: [{"id": ENGAGEMENT_ID}])
    anthropic.queue(VALID_ENGAGEMENT_JSON)
    supabase.respond("queue_items", "insert", lambda _: [{"id": QUEUE_ITEM_ID}])

    resp = client.post(
        "/ingest-paper-user",
        json={"user_id": str(uuid4()), "raw_input": "10.1103/PhysRevLett.116.061102"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["paper_id"] == PAPER_ID
    assert data["created"] is True

    inserts = [c for c in supabase.calls if c.table == "papers" and c.op == "insert"]
    assert len(inserts) == 1
    assert inserts[0].payload["doi"] == "10.1103/PhysRevLett.116.061102"


# ---------------------------------------------------------------------------
# Bare title — existing match
# ---------------------------------------------------------------------------


def test_bare_title_matches_existing(client: TestClient, fakes: tuple) -> None:
    supabase, anthropic = fakes

    # ILIKE match → existing paper found; no insert
    def papers_select(call):
        # First call is the ILIKE bare-title search; return existing row.
        # Second call is the load for engagement generation.
        if any(f[0] == "ilike" for f in call.filters):
            return [{"id": PAPER_ID}]
        return [
            {
                "id": PAPER_ID,
                "title": "Observation of Gravitational Waves",
                "abstract_md": "We report...",
                "authors_json": ["Abbott, B. P."],
                "year": 2016,
            }
        ]

    supabase.respond("papers", "select", papers_select)
    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("paper_engagements", "insert", lambda _: [{"id": ENGAGEMENT_ID}])
    anthropic.queue(VALID_ENGAGEMENT_JSON)
    supabase.respond("queue_items", "insert", lambda _: [{"id": QUEUE_ITEM_ID}])

    resp = client.post(
        "/ingest-paper-user",
        json={"user_id": str(uuid4()), "raw_input": "Observation of Gravitational Waves"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["paper_id"] == PAPER_ID
    assert data["created"] is False

    # No insert should have been attempted
    assert not any(c.table == "papers" and c.op == "insert" for c in supabase.calls)


# ---------------------------------------------------------------------------
# Bare title — no match; sparse insert
# ---------------------------------------------------------------------------


def test_bare_title_inserts_new(client: TestClient, fakes: tuple) -> None:
    supabase, anthropic = fakes

    call_count = {"n": 0}

    def papers_select(call):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return []  # ILIKE: no match
        # Soft-check in ingest_paper (title+year): also no match
        if call_count["n"] == 2:
            return []
        # Load for engagement generation
        return [
            {
                "id": PAPER_ID,
                "title": "Some Very Niche Paper",
                "abstract_md": "",
                "authors_json": [],
                "year": 0,
            }
        ]

    supabase.respond("papers", "select", papers_select)
    supabase.respond("papers", "insert", lambda _: [{"id": PAPER_ID}])
    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("paper_engagements", "insert", lambda _: [{"id": ENGAGEMENT_ID}])
    anthropic.queue(VALID_ENGAGEMENT_JSON)
    supabase.respond("queue_items", "insert", lambda _: [{"id": QUEUE_ITEM_ID}])

    resp = client.post(
        "/ingest-paper-user",
        json={"user_id": str(uuid4()), "raw_input": "Some Very Niche Paper"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["created"] is True

    inserts = [c for c in supabase.calls if c.table == "papers" and c.op == "insert"]
    assert len(inserts) == 1
    assert inserts[0].payload["title"] == "Some Very Niche Paper"
    assert inserts[0].payload["year"] == 0
    assert inserts[0].payload["authors_json"] == []


# ---------------------------------------------------------------------------
# Duplicate arXiv → existing paper but still creates engagement + queue item
# ---------------------------------------------------------------------------


@patch("routes.ingest_paper_user.httpx.get")
def test_duplicate_arxiv_returns_existing_with_queue_item(
    mock_get: MagicMock, client: TestClient, fakes: tuple
) -> None:
    supabase, anthropic = fakes
    mock_get.return_value = _make_http_mock(ARXIV_ATOM_XML)

    # arxiv_id already in papers → dedup returns existing row immediately
    def papers_select(call):
        if any(f[0] == "eq" and f[1] == "arxiv_id" for f in call.filters):
            return [{"id": PAPER_ID}]
        # load for engagement generation
        return [
            {
                "id": PAPER_ID,
                "title": "Observation of Gravitational Waves",
                "abstract_md": "We report...",
                "authors_json": ["Abbott, B. P."],
                "year": 2016,
            }
        ]

    supabase.respond("papers", "select", papers_select)
    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    supabase.respond("paper_engagements", "insert", lambda _: [{"id": ENGAGEMENT_ID}])
    anthropic.queue(VALID_ENGAGEMENT_JSON)
    supabase.respond("queue_items", "insert", lambda _: [{"id": QUEUE_ITEM_ID}])

    resp = client.post(
        "/ingest-paper-user",
        json={"user_id": str(uuid4()), "raw_input": "2301.07041"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["paper_id"] == PAPER_ID
    assert data["created"] is False  # paper already existed
    # Engagement and queue item were still created
    assert data["engagement_id"] == ENGAGEMENT_ID
    assert data["queue_item_id"] == QUEUE_ITEM_ID

    # No papers insert
    assert not any(c.table == "papers" and c.op == "insert" for c in supabase.calls)
    # One queue item insert
    qi_inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(qi_inserts) == 1
