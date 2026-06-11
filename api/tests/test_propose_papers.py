"""Tests for POST /propose-papers."""

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


def _make_engagement_json() -> str:
    return json.dumps(
        {
            "why_this_md": "Relevant to your interests.",
            "orienting_concepts_json": [
                {"term": "concept A", "definition_md": "A definition."},
                {"term": "concept B", "definition_md": "Another definition."},
            ],
            "questions_json": [
                {"id": str(uuid4()), "kind": "comprehension", "prompt_md": "Q1?", "order": 1},
                {"id": str(uuid4()), "kind": "critical", "prompt_md": "Q2?", "order": 2},
                {"id": str(uuid4()), "kind": "connective", "prompt_md": "Q3?", "order": 3},
            ],
        }
    )


def _cycler(*payloads):
    """Returns each payload in turn; returns [] once all are exhausted."""
    items = list(payloads)
    idx = [0]

    def _fn(_call):
        if idx[0] < len(items):
            result = items[idx[0]]
            idx[0] += 1
            return result
        return []

    return _fn


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
    resp = client.post("/propose-papers", json={"user_id": str(uuid4())})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# No interests → Sonnet still called; returns 0 counts if candidates=[]
# ---------------------------------------------------------------------------


def test_no_interests_returns_empty(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes

    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond("notebook_entries", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])

    anthropic.queue(json.dumps({"candidates": []}))

    resp = client.post(
        "/propose-papers",
        json={"user_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["papers_added"] == 0
    assert data["papers_reused"] == 0
    assert data["queue_items_added"] == 0
    # Sonnet must have been called
    assert len(anthropic.messages.calls) == 1


# ---------------------------------------------------------------------------
# Happy path — 3 candidates → 3 papers inserted, 3 queue items written
# ---------------------------------------------------------------------------


def test_happy_path_inserts_papers_and_queue_items(
    client: TestClient, fakes
) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    node_id = str(uuid4())
    paper_ids = [str(uuid4()), str(uuid4()), str(uuid4())]
    engagement_ids = [str(uuid4()), str(uuid4()), str(uuid4())]
    queue_item_ids = [str(uuid4()), str(uuid4()), str(uuid4())]

    candidates_json = json.dumps(
        {
            "candidates": [
                {
                    "title": f"Paper {i + 1}",
                    "authors": [f"Author {chr(65 + i)}"],
                    "year": 2020 + i,
                    "arxiv_id": f"2301.0000{i + 1}",
                    "doi": None,
                    "rationale": f"Directly relevant to interest {i + 1}.",
                }
                for i in range(3)
            ]
        }
    )

    # Main route: user interests and notebook context
    supabase.respond("user_interests", "select", lambda _: [{"node_id": node_id}])
    supabase.respond("nodes", "select", lambda _: [{"title": "Differential Geometry"}])
    supabase.respond("notebook_entries", "select", lambda _: [])
    # llm_calls logged once per Claude call (1 propose + 3 engagement generation)
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])

    # papers.select cycles: per candidate → arxiv_id dedup check (→ []) then
    # generate_engagement_for_paper load (→ paper data)
    supabase.respond(
        "papers",
        "select",
        _cycler(
            [],
            [{"id": paper_ids[0], "title": "Paper 1", "authors_json": ["Author A"], "year": 2020, "abstract_md": ""}],
            [],
            [{"id": paper_ids[1], "title": "Paper 2", "authors_json": ["Author B"], "year": 2021, "abstract_md": ""}],
            [],
            [{"id": paper_ids[2], "title": "Paper 3", "authors_json": ["Author C"], "year": 2022, "abstract_md": ""}],
        ),
    )
    supabase.respond(
        "papers",
        "insert",
        _cycler(
            [{"id": paper_ids[0]}],
            [{"id": paper_ids[1]}],
            [{"id": paper_ids[2]}],
        ),
    )
    supabase.respond("paper_engagements", "select", lambda _: [])
    supabase.respond(
        "paper_engagements",
        "insert",
        _cycler(
            [{"id": engagement_ids[0]}],
            [{"id": engagement_ids[1]}],
            [{"id": engagement_ids[2]}],
        ),
    )
    supabase.respond(
        "queue_items",
        "insert",
        _cycler(
            [{"id": queue_item_ids[0]}],
            [{"id": queue_item_ids[1]}],
            [{"id": queue_item_ids[2]}],
        ),
    )

    # Sonnet: 1 propose call + 3 engagement generation calls
    anthropic.queue(candidates_json)
    for _ in range(3):
        anthropic.queue(_make_engagement_json())

    resp = client.post(
        "/propose-papers",
        json={"user_id": user_id},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["papers_added"] == 3
    assert data["papers_reused"] == 0
    assert data["queue_items_added"] == 3

    qi_inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(qi_inserts) == 3
    for qi in qi_inserts:
        assert qi.payload["kind"] == "paper_engagement"
        assert qi.payload["priority_score"] == 0.4
        assert qi.payload["state"] == "pending"


# ---------------------------------------------------------------------------
# Topic association — interest_titles echo resolves to papers.topic_node_ids
# ---------------------------------------------------------------------------


def test_paper_associated_with_interest_node(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    node_id = str(uuid4())
    paper_id = str(uuid4())
    engagement_id = str(uuid4())

    supabase.respond("user_interests", "select", lambda _: [{"node_id": node_id}])
    # nodes.select now returns id + title so the echo-back can resolve to a node
    supabase.respond("nodes", "select", lambda _: [{"id": node_id, "title": "Quantum Field Theory"}])
    supabase.respond("notebook_entries", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])

    anthropic.queue(
        json.dumps(
            {
                "candidates": [
                    {
                        "title": "On Gauge Invariance",
                        "authors": ["Yang, C."],
                        "year": 1954,
                        "arxiv_id": "5401.00001",
                        "doi": None,
                        "rationale": "Foundational gauge theory.",
                        # echoes the provided interest title verbatim
                        "interest_titles": ["Quantum Field Theory"],
                    }
                ]
            }
        )
    )

    # papers.select cycles: arxiv dedup (miss) → topic union read → engagement load
    supabase.respond(
        "papers",
        "select",
        _cycler(
            [],  # arxiv_id dedup → miss
            [{"topic_node_ids": []}],  # _associate_topics current-read
            [{"id": paper_id, "title": "On Gauge Invariance", "authors_json": ["Yang, C."], "year": 1954, "abstract_md": ""}],
        ),
    )
    supabase.respond("papers", "insert", lambda _: [{"id": paper_id}])
    supabase.respond("papers", "update", lambda _: [{"id": paper_id}])
    supabase.respond("paper_engagements", "select", lambda _: [])
    supabase.respond("paper_engagements", "insert", lambda _: [{"id": engagement_id}])
    supabase.respond("queue_items", "insert", lambda _: [{"id": str(uuid4())}])

    anthropic.queue(_make_engagement_json())

    resp = client.post(
        "/propose-papers",
        json={"user_id": user_id},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    # The paper was updated with the resolved node id.
    paper_updates = [c for c in supabase.calls if c.table == "papers" and c.op == "update"]
    assert len(paper_updates) == 1
    assert paper_updates[0].payload["topic_node_ids"] == [node_id]


# ---------------------------------------------------------------------------
# Existing engagement → queue item skipped
# ---------------------------------------------------------------------------


def test_existing_engagement_skipped(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    paper_id = str(uuid4())

    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond("notebook_entries", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])

    anthropic.queue(
        json.dumps(
            {
                "candidates": [
                    {
                        "title": "A Paper",
                        "authors": ["Smith, J."],
                        "year": 2021,
                        "arxiv_id": "2101.00001",
                        "doi": None,
                        "rationale": "Foundational work on the topic.",
                    }
                ]
            }
        )
    )

    # arxiv_id check → not found → insert succeeds
    supabase.respond("papers", "select", _cycler([]))
    supabase.respond("papers", "insert", lambda _: [{"id": paper_id}])
    # Existing engagement for this user+paper → skip generation
    supabase.respond("paper_engagements", "select", lambda _: [{"id": str(uuid4())}])

    resp = client.post(
        "/propose-papers",
        json={"user_id": user_id},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["papers_added"] == 1
    assert data["papers_reused"] == 0
    assert data["queue_items_added"] == 0
    assert not any(c.table == "queue_items" and c.op == "insert" for c in supabase.calls)


# ---------------------------------------------------------------------------
# Duplicate paper (arxiv_id already in papers) → reused, engagement still created
# ---------------------------------------------------------------------------


def test_duplicate_paper_reused(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    user_id = str(uuid4())
    paper_id = str(uuid4())
    engagement_id = str(uuid4())
    queue_item_id = str(uuid4())

    supabase.respond("user_interests", "select", lambda _: [])
    supabase.respond("notebook_entries", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])

    anthropic.queue(
        json.dumps(
            {
                "candidates": [
                    {
                        "title": "Known Paper",
                        "authors": ["Jones, R."],
                        "year": 2019,
                        "arxiv_id": "1901.00001",
                        "doi": None,
                        "rationale": "Classic result in this area.",
                    }
                ]
            }
        )
    )

    # arxiv_id dedup hit → returns existing paper_id (no insert)
    # then generate_engagement_for_paper loads the paper
    supabase.respond(
        "papers",
        "select",
        _cycler(
            [{"id": paper_id}],  # arxiv_id check: existing found → early return
            [{"id": paper_id, "title": "Known Paper", "authors_json": ["Jones, R."], "year": 2019, "abstract_md": ""}],
        ),
    )

    supabase.respond("paper_engagements", "select", lambda _: [])
    supabase.respond("paper_engagements", "insert", lambda _: [{"id": engagement_id}])
    supabase.respond("queue_items", "insert", lambda _: [{"id": queue_item_id}])

    anthropic.queue(_make_engagement_json())

    resp = client.post(
        "/propose-papers",
        json={"user_id": user_id},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["papers_added"] == 0
    assert data["papers_reused"] == 1
    assert data["queue_items_added"] == 1

    # No papers.insert should have been called
    assert not any(c.table == "papers" and c.op == "insert" for c in supabase.calls)
