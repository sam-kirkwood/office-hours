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


VALID_PROBLEM_JSON = json.dumps(
    {
        "statement_md": "Compute the speed of light.",
        "solution_md": "Use Maxwell's equations to derive $c = 1/\\sqrt{\\mu_0 \\epsilon_0}$.",
        "rubric_md": (
            "- States Maxwell's equations\n"
            "- Identifies c as derived constant\n"
            "- Plugs in values"
        ),
        "hints": [
            "L1: Maxwell's equations relate E and B fields.",
            "L2: The wave equation for E in vacuum.",
            "L3: Compare to a generic wave equation.",
            "L4: Read off the wave-speed coefficient.",
            "L5: Watch SI units on mu_0 and epsilon_0.",
        ],
        "generated_context_md": "Maxwell's 1865 paper unified...",
    }
)


# ---------------------------------------------------------------------------
# Fixtures / wiring
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


def _prime_node_and_survey(
    supabase: FakeSupabase,
    *,
    topic_id: str,
    band: str = "core",
    curve: str = "standard",
    hooks: list[dict] | None = None,
) -> None:
    supabase.respond(
        "plan_nodes",
        "select",
        lambda _call: [
            {
                "id": "plan-node-1",
                "canonical_topic_id": topic_id,
                "canonical_topics": {
                    "id": topic_id,
                    "title": "Special Relativity",
                    "description": "Lorentz invariance and consequences.",
                    "difficulty_band": band,
                    "subtopics": [
                        {"slug": "time-dilation", "title": "Time dilation"},
                        {"slug": "length-contraction", "title": "Length contraction"},
                    ],
                },
            }
        ],
    )
    supabase.respond(
        "surveys",
        "select",
        lambda _call: [{"difficulty_curve": curve}],
    )
    supabase.respond("context_hooks", "select", lambda _call: hooks or [])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    response = client.post(
        "/generate-problem",
        json={"user_id": str(uuid4()), "plan_node_id": str(uuid4())},
    )
    assert response.status_code == 401


def test_wrong_bearer_returns_401(client: TestClient) -> None:
    response = client.post(
        "/generate-problem",
        json={"user_id": str(uuid4()), "plan_node_id": str(uuid4())},
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401


def test_missing_plan_node_returns_404(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("plan_nodes", "select", lambda _call: [])
    response = client.post(
        "/generate-problem",
        json={"user_id": str(uuid4()), "plan_node_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


def test_missing_survey_returns_404(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    topic_id = str(uuid4())
    _prime_node_and_survey(supabase, topic_id=topic_id)
    # override surveys to return empty
    supabase.respond("surveys", "select", lambda _call: [])
    response = client.post(
        "/generate-problem",
        json={"user_id": str(uuid4()), "plan_node_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


def test_cache_hit_skips_anthropic(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    topic_id = str(uuid4())
    cached_problem_id = str(uuid4())
    _prime_node_and_survey(supabase, topic_id=topic_id)
    supabase.respond("problems", "select", lambda _call: [{"id": cached_problem_id}])

    response = client.post(
        "/generate-problem",
        json={"user_id": str(uuid4()), "plan_node_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"problem_id": cached_problem_id}
    assert anthropic.messages.calls == []  # no Sonnet call on cache hit
    # no llm_calls insert either
    assert not any(c.table == "llm_calls" for c in supabase.calls)
    # no problems insert
    assert not any(c.table == "problems" and c.op == "insert" for c in supabase.calls)


def test_happy_path_generates_problem_and_hints(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    topic_id = str(uuid4())
    new_problem_id = str(uuid4())
    _prime_node_and_survey(supabase, topic_id=topic_id)

    # cache miss
    supabase.respond("problems", "select", lambda _call: [])
    # llm_calls insert returns a row id
    supabase.respond("llm_calls", "insert", lambda _call: [{"id": str(uuid4())}])
    # problems insert succeeds
    supabase.respond("problems", "insert", lambda _call: [{"id": new_problem_id}])
    # hints insert returns 5 rows
    supabase.respond(
        "problem_hints",
        "insert",
        lambda call: [{"id": str(uuid4()), **row} for row in call.payload],
    )
    anthropic.queue(VALID_PROBLEM_JSON)

    response = client.post(
        "/generate-problem",
        json={"user_id": str(uuid4()), "plan_node_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"problem_id": new_problem_id}
    assert len(anthropic.messages.calls) == 1
    # llm_calls written exactly once
    llm_inserts = [c for c in supabase.calls if c.table == "llm_calls" and c.op == "insert"]
    assert len(llm_inserts) == 1
    # 5 hints written
    hint_inserts = [c for c in supabase.calls if c.table == "problem_hints" and c.op == "insert"]
    assert len(hint_inserts) == 1
    assert len(hint_inserts[0].payload) == 5
    assert [r["level"] for r in hint_inserts[0].payload] == [1, 2, 3, 4, 5]
    # generated_context_md round-trips into the problems insert (no hook matched
    # in this test → Sonnet writes the context inline)
    problems_insert = next(
        c for c in supabase.calls if c.table == "problems" and c.op == "insert"
    )
    assert problems_insert.payload["generated_context_md"] == "Maxwell's 1865 paper unified..."
    # Sonnet must NOT pin temperature — we want some creativity in problem
    # generation, and the cache eliminates determinism concerns on hits.
    assert "temperature" not in anthropic.messages.calls[0]


def test_retry_on_parse_failure_then_succeeds(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    topic_id = str(uuid4())
    new_problem_id = str(uuid4())
    _prime_node_and_survey(supabase, topic_id=topic_id)
    supabase.respond("problems", "select", lambda _call: [])
    supabase.respond("llm_calls", "insert", lambda _call: [{"id": str(uuid4())}])
    supabase.respond("problems", "insert", lambda _call: [{"id": new_problem_id}])
    supabase.respond(
        "problem_hints",
        "insert",
        lambda call: [{"id": str(uuid4()), **row} for row in call.payload],
    )
    # first response: garbage; second: valid
    anthropic.queue("not json at all {oops")
    anthropic.queue(VALID_PROBLEM_JSON)

    response = client.post(
        "/generate-problem",
        json={"user_id": str(uuid4()), "plan_node_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    # both attempts were logged
    llm_inserts = [c for c in supabase.calls if c.table == "llm_calls" and c.op == "insert"]
    assert len(llm_inserts) == 2
    # second anthropic call carried the correction (3-message conversation)
    assert len(anthropic.messages.calls) == 2
    retry_messages = anthropic.messages.calls[1]["messages"]
    assert len(retry_messages) == 3
    assert retry_messages[1]["role"] == "assistant"
    assert retry_messages[2]["role"] == "user"
    assert "could not be parsed" in retry_messages[2]["content"]


def test_race_lost_returns_existing_row(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    topic_id = str(uuid4())
    existing_problem_id = str(uuid4())
    _prime_node_and_survey(supabase, topic_id=topic_id)

    # First select: cache miss. Second select (after race): existing row.
    select_responses = [[], [{"id": existing_problem_id}]]
    supabase.respond(
        "problems",
        "select",
        lambda _call: select_responses.pop(0) if select_responses else [],
    )
    supabase.respond("llm_calls", "insert", lambda _call: [{"id": str(uuid4())}])

    class FakeUniqueViolation(Exception):
        code = "23505"

    supabase.respond("problems", "insert", lambda _call: FakeUniqueViolation("duplicate key"))
    anthropic.queue(VALID_PROBLEM_JSON)

    response = client.post(
        "/generate-problem",
        json={"user_id": str(uuid4()), "plan_node_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"problem_id": existing_problem_id}
    # no hints written on the race-lost path
    assert not any(c.table == "problem_hints" and c.op == "insert" for c in supabase.calls)


def test_hook_match_passes_summary_into_user_prompt(client: TestClient, fakes) -> None:
    """When Haiku picks a hook, its summary is woven into the Sonnet user
    prompt and the chosen hook id is stored on the new problem row."""
    supabase, anthropic = fakes
    topic_id = str(uuid4())
    hook_id = str(uuid4())
    new_problem_id = str(uuid4())
    _prime_node_and_survey(
        supabase,
        topic_id=topic_id,
        band="core",
        hooks=[
            {
                "id": hook_id,
                "slug": "michelson-morley",
                "title": "Michelson–Morley",
                "summary_md": "1887 interferometer null result.",
                "difficulty_band": "core",
            },
        ],
    )
    supabase.respond("problems", "select", lambda _call: [])
    supabase.respond("llm_calls", "insert", lambda _call: [{"id": str(uuid4())}])
    supabase.respond("problems", "insert", lambda _call: [{"id": new_problem_id}])
    supabase.respond(
        "problem_hints",
        "insert",
        lambda call: [{"id": str(uuid4()), **row} for row in call.payload],
    )
    # Haiku picks the hook, then Sonnet generates the problem.
    anthropic.queue(json.dumps({"hook_slug": "michelson-morley"}))
    anthropic.queue(VALID_PROBLEM_JSON)

    response = client.post(
        "/generate-problem",
        json={"user_id": str(uuid4()), "plan_node_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    assert len(anthropic.messages.calls) == 2  # Haiku, then Sonnet
    sonnet_call = anthropic.messages.calls[1]
    sonnet_user_msg = sonnet_call["messages"][0]["content"]
    assert "1887 interferometer null result." in sonnet_user_msg
    # And the problems insert references the hook
    problems_insert = next(
        c for c in supabase.calls if c.table == "problems" and c.op == "insert"
    )
    assert problems_insert.payload["context_hook_id"] == hook_id


def test_haiku_rejects_hook_falls_back_to_null_cache_key(
    client: TestClient, fakes
) -> None:
    """Even with candidates available, if Haiku verdict is null we generate
    a hook-less problem and the cache key uses context_hook_id=null."""
    supabase, anthropic = fakes
    topic_id = str(uuid4())
    new_problem_id = str(uuid4())
    _prime_node_and_survey(
        supabase,
        topic_id=topic_id,
        band="core",
        hooks=[
            {
                "id": str(uuid4()),
                "slug": "weak-fit",
                "title": "Weak fit",
                "summary_md": "Only loosely related.",
                "difficulty_band": "core",
            },
        ],
    )
    supabase.respond("problems", "select", lambda _call: [])
    supabase.respond("llm_calls", "insert", lambda _call: [{"id": str(uuid4())}])
    supabase.respond("problems", "insert", lambda _call: [{"id": new_problem_id}])
    supabase.respond(
        "problem_hints",
        "insert",
        lambda call: [{"id": str(uuid4()), **row} for row in call.payload],
    )
    anthropic.queue(json.dumps({"hook_slug": None, "reason": "weak match"}))
    anthropic.queue(VALID_PROBLEM_JSON)

    response = client.post(
        "/generate-problem",
        json={"user_id": str(uuid4()), "plan_node_id": str(uuid4())},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    problems_insert = next(
        c for c in supabase.calls if c.table == "problems" and c.op == "insert"
    )
    assert problems_insert.payload["context_hook_id"] is None
    # And the cache lookup used is_null
    cache_lookups = [
        c for c in supabase.calls
        if c.table == "problems" and c.op == "select"
    ]
    assert cache_lookups, "expected at least one cache lookup"
    assert ("is_", "context_hook_id", "null") in cache_lookups[0].filters
