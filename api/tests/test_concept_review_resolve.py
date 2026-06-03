"""Tests for POST /concept-review-resolve."""

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


def _cycler(*payloads):
    items = list(payloads)
    idx = [0]

    def _fn(_call):
        if idx[0] < len(items):
            result = items[idx[0]]
            idx[0] += 1
            return result
        return []

    return _fn


def _queue_brief_response(anthropic: FakeAnthropic, subtopic_slugs: list[str]) -> None:
    """Queue a stub concept-brief response on the Fake Anthropic so the
    inline brief generation in /concept-review-resolve's miss path doesn't
    hit the live API. Glosses are keyed by slug so tests can assert
    enrichment behaviour."""
    anthropic.queue(
        json.dumps(
            {
                "brief_md": "Stub brief paragraph.\n\nSecond paragraph.\n\nThird paragraph.",
                "subtopic_glosses_json": [
                    {"slug": slug, "title": slug.replace("-", " ").title(), "gloss_md": f"Gloss for {slug}."}
                    for slug in subtopic_slugs
                ],
            }
        )
    )


@pytest.fixture
def supabase() -> FakeSupabase:
    fs = FakeSupabase()
    app.dependency_overrides[get_supabase_client] = lambda: fs
    try:
        yield fs
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def anthropic() -> FakeAnthropic:
    fa = FakeAnthropic()
    app.dependency_overrides[get_anthropic_client] = lambda: fa
    try:
        yield fa
    finally:
        # cleared by the supabase fixture's finally
        pass


@pytest.fixture
def client(supabase, anthropic) -> TestClient:  # noqa: ARG001
    return TestClient(app)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/concept-review-resolve",
        json={"user_id": str(uuid4()), "queue_item_id": str(uuid4())},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Validation: wrong kind
# ---------------------------------------------------------------------------


def test_wrong_kind_returns_400(client: TestClient, supabase: FakeSupabase) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "problem",
                "ref_id": str(uuid4()),
                "state": "pending",
            }
        ],
    )

    resp = client.post(
        "/concept-review-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    assert "concept_review" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Validation: not found
# ---------------------------------------------------------------------------


def test_queue_item_not_found_returns_404(
    client: TestClient, supabase: FakeSupabase
) -> None:
    supabase.respond("queue_items", "select", lambda _: [])

    resp = client.post(
        "/concept-review-resolve",
        json={"user_id": str(uuid4()), "queue_item_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Already done → 409
# ---------------------------------------------------------------------------


def test_already_done_returns_409(client: TestClient, supabase: FakeSupabase) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "concept_review",
                "ref_id": str(uuid4()),
                "state": "done",
            }
        ],
    )

    resp = client.post(
        "/concept-review-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Pool hit → enqueues kind='problem' + marks concept_review done
# ---------------------------------------------------------------------------


def test_pool_hit_enqueues_problem_and_marks_done(
    client: TestClient, supabase: FakeSupabase
) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    node_id = str(uuid4())
    problem_id = str(uuid4())
    new_qi_id = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "concept_review",
                "ref_id": node_id,
                "state": "pending",
            }
        ],
    )
    supabase.respond(
        "nodes",
        "select",
        lambda _: [
            {
                "id": node_id,
                "slug": "classical-mechanics",
                "title": "Classical Mechanics",
                "description_md": "Newton's laws and friends.",
                "subtopics_json": [
                    {"slug": "power", "title": "Power"},
                    {"slug": "work", "title": "Work"},
                ],
            }
        ],
    )
    # problems.select for the pool lookup → returns one match
    supabase.respond(
        "problems",
        "select",
        lambda _: [{"id": problem_id, "tags": ["classical-mechanics", "power"]}],
    )
    supabase.respond("queue_items", "insert", lambda _: [{"id": new_qi_id}])
    supabase.respond("queue_items", "update", lambda _: [{"id": qi_id}])

    resp = client.post(
        "/concept-review-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "problem"
    assert data["queue_item_id"] == new_qi_id
    assert data["node"] is None

    inserts = [c for c in supabase.calls if c.table == "queue_items" and c.op == "insert"]
    assert len(inserts) == 1
    assert inserts[0].payload["kind"] == "problem"
    assert inserts[0].payload["ref_id"] == problem_id
    assert inserts[0].payload["state"] == "pending"

    updates = [c for c in supabase.calls if c.table == "queue_items" and c.op == "update"]
    assert len(updates) == 1
    assert updates[0].payload["state"] == "done"
    # The update targets the original concept_review row
    assert ("eq", "id", qi_id) in updates[0].filters

    # Pool lookup must have filtered by primary subtopic 'power'
    problem_selects = [c for c in supabase.calls if c.table == "problems" and c.op == "select"]
    assert len(problem_selects) == 1
    assert ("contains", "tags", ["power"]) in problem_selects[0].filters
    assert ("eq", "difficulty", 1) in problem_selects[0].filters
    assert ("eq", "intent", "teach") in problem_selects[0].filters


# ---------------------------------------------------------------------------
# Pool miss → returns reading surface, no mutations
# ---------------------------------------------------------------------------


def test_pool_miss_returns_reading(
    client: TestClient, supabase: FakeSupabase, anthropic: FakeAnthropic
) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    node_id = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "concept_review",
                "ref_id": node_id,
                "state": "pending",
            }
        ],
    )
    supabase.respond(
        "nodes",
        "select",
        lambda _: [
            {
                "id": node_id,
                "slug": "general-relativity",
                "title": "General Relativity",
                "description_md": "Geometry of spacetime.",
                "subtopics_json": [{"slug": "metric-tensor", "title": "Metric tensor"}],
            }
        ],
    )
    # Pool lookup returns nothing
    supabase.respond("problems", "select", lambda _: [])
    # Step 5.5 — brief generation runs inline on the miss path.
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    _queue_brief_response(anthropic, ["metric-tensor"])

    resp = client.post(
        "/concept-review-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "reading"
    assert data["queue_item_id"] is None
    assert data["node"]["slug"] == "general-relativity"
    assert data["node"]["description_md"] == "Geometry of spacetime."
    assert data["node"]["brief_md"] == "Stub brief paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    assert data["node"]["subtopics_json"] == [
        {
            "slug": "metric-tensor",
            "title": "Metric tensor",
            "gloss_md": "Gloss for metric-tensor.",
        }
    ]

    # No state mutation on the queue_item (concept_review stays pending until
    # the user marks it done from the reading view). The brief upsert and the
    # llm_calls insert are expected and not asserted against.
    qi_mutations = [
        c for c in supabase.calls
        if c.table == "queue_items" and c.op in ("insert", "update")
    ]
    assert qi_mutations == []


# ---------------------------------------------------------------------------
# Null / empty subtopics_json → pool lookup runs without subtopic filter
# ---------------------------------------------------------------------------


def test_null_subtopics_runs_pool_lookup_without_filter(
    client: TestClient, supabase: FakeSupabase, anthropic: FakeAnthropic
) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    node_id = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "concept_review",
                "ref_id": node_id,
                "state": "pending",
            }
        ],
    )
    supabase.respond(
        "nodes",
        "select",
        lambda _: [
            {
                "id": node_id,
                "slug": "thermodynamics",
                "title": "Thermodynamics",
                "description_md": "",
                "subtopics_json": None,  # null on this row
            }
        ],
    )
    supabase.respond("problems", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    _queue_brief_response(anthropic, [])

    resp = client.post(
        "/concept-review-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "reading"
    assert data["node"]["subtopics_json"] == []

    problem_selects = [c for c in supabase.calls if c.table == "problems" and c.op == "select"]
    assert len(problem_selects) == 1
    # No `contains` filter applied when subtopic_slug is None
    assert not any(f[0] == "contains" for f in problem_selects[0].filters)


# ---------------------------------------------------------------------------
# Legacy `subtopics_json` stored as list[str] (pre-shape-migration nodes)
# is coerced to [{slug, title}] dicts so the reading-surface UI can render
# without a pydantic validation error.
# ---------------------------------------------------------------------------


def test_legacy_string_subtopics_are_coerced_to_dicts(
    client: TestClient, supabase: FakeSupabase, anthropic: FakeAnthropic
) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    node_id = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "concept_review",
                "ref_id": node_id,
                "state": "pending",
            }
        ],
    )
    supabase.respond(
        "nodes",
        "select",
        lambda _: [
            {
                "id": node_id,
                "slug": "fourier-analysis",
                "title": "Fourier Analysis & Transforms",
                "description_md": "Decomposing signals into frequencies.",
                "subtopics_json": [
                    "Fourier series on finite intervals",
                    "Continuous Fourier transform pairs",
                ],
            }
        ],
    )
    supabase.respond("problems", "select", lambda _: [])
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])
    _queue_brief_response(
        anthropic,
        [
            "fourier-series-on-finite-intervals",
            "continuous-fourier-transform-pairs",
        ],
    )

    resp = client.post(
        "/concept-review-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "reading"
    assert data["node"]["subtopics_json"] == [
        {
            "slug": "fourier-series-on-finite-intervals",
            "title": "Fourier series on finite intervals",
            "gloss_md": "Gloss for fourier-series-on-finite-intervals.",
        },
        {
            "slug": "continuous-fourier-transform-pairs",
            "title": "Continuous Fourier transform pairs",
            "gloss_md": "Gloss for continuous-fourier-transform-pairs.",
        },
    ]


# ---------------------------------------------------------------------------
# Step 5.5 — when a cached brief exists in node_concept_briefs, the route
# reuses it without making an Anthropic call.
# ---------------------------------------------------------------------------


def test_cached_brief_is_reused_without_anthropic_call(
    client: TestClient, supabase: FakeSupabase, anthropic: FakeAnthropic
) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    node_id = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "concept_review",
                "ref_id": node_id,
                "state": "pending",
            }
        ],
    )
    supabase.respond(
        "nodes",
        "select",
        lambda _: [
            {
                "id": node_id,
                "slug": "topology",
                "title": "Topology",
                "description_md": "Shape without measurement.",
                "subtopics_json": [{"slug": "open-sets", "title": "Open sets"}],
            }
        ],
    )
    supabase.respond("problems", "select", lambda _: [])
    # Pre-existing brief in cache — returned directly, no Anthropic call.
    supabase.respond(
        "node_concept_briefs",
        "select",
        lambda _: [
            {
                "brief_md": "Cached brief content.",
                "subtopic_glosses_json": [
                    {"slug": "open-sets", "title": "Open sets", "gloss_md": "Cached gloss."}
                ],
            }
        ],
    )

    resp = client.post(
        "/concept-review-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["node"]["brief_md"] == "Cached brief content."
    assert data["node"]["subtopics_json"][0]["gloss_md"] == "Cached gloss."
    # Anthropic must NOT have been called when a cache row was present.
    assert anthropic.messages.calls == []


# ---------------------------------------------------------------------------
# Step 5.5 — brief generation failure (Anthropic outage) is non-fatal: the
# route still returns a reading surface with the bare description_md.
# ---------------------------------------------------------------------------


def test_brief_generation_failure_falls_back_to_bare_reading(
    client: TestClient, supabase: FakeSupabase, anthropic: FakeAnthropic
) -> None:
    user_id = str(uuid4())
    qi_id = str(uuid4())
    node_id = str(uuid4())

    supabase.respond(
        "queue_items",
        "select",
        lambda _: [
            {
                "id": qi_id,
                "user_id": user_id,
                "kind": "concept_review",
                "ref_id": node_id,
                "state": "pending",
            }
        ],
    )
    supabase.respond(
        "nodes",
        "select",
        lambda _: [
            {
                "id": node_id,
                "slug": "linear-algebra",
                "title": "Linear Algebra",
                "description_md": "Vectors and the maps between them.",
                "subtopics_json": [{"slug": "eigenvalues", "title": "Eigenvalues"}],
            }
        ],
    )
    supabase.respond("problems", "select", lambda _: [])
    # No brief response queued — FakeAnthropic.messages.create will raise on
    # an empty queue, simulating an upstream failure. Route should swallow it
    # and return the bare reading surface.

    resp = client.post(
        "/concept-review-resolve",
        json={"user_id": user_id, "queue_item_id": qi_id},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kind"] == "reading"
    assert data["node"]["brief_md"] is None
    assert data["node"]["description_md"] == "Vectors and the maps between them."
    # Subtopic still surfaced even without gloss.
    assert data["node"]["subtopics_json"] == [
        {"slug": "eigenvalues", "title": "Eigenvalues"}
    ]
