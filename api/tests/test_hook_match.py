"""Unit tests for `match_hook` — the Haiku-based context-hook selector.

Tests exercise the helper directly with fake clients rather than going through
the HTTP route, so they don't have to re-prime plan_nodes / surveys / problems.
"""

import json

from routes.generate_problem import match_hook
from tests.fake_anthropic import FakeAnthropic
from tests.fake_supabase import FakeSupabase

HOOK_A = {
    "id": "hook-a-id",
    "slug": "michelson-morley",
    "title": "Michelson–Morley",
    "summary_md": "1887 interferometer null result.",
    "difficulty_band": "core",
}
HOOK_B = {
    "id": "hook-b-id",
    "slug": "lorentz-transformation",
    "title": "Lorentz transformation",
    "summary_md": "Coordinate transformation preserving Maxwell's equations.",
    "difficulty_band": "core",
}


def test_match_hook_no_candidates_skips_haiku() -> None:
    supabase = FakeSupabase()
    anthropic = FakeAnthropic()

    result = match_hook(
        client=anthropic,
        supabase=supabase,
        topic_title="Anything",
        topic_description="No hooks tagged.",
        candidate_hooks=[],
    )

    assert result is None
    assert anthropic.messages.calls == []  # no Haiku call
    # and no llm_calls insert
    assert not any(c.table == "llm_calls" for c in supabase.calls)


def test_match_hook_returns_picked_hook_dict() -> None:
    supabase = FakeSupabase()
    supabase.respond("llm_calls", "insert", lambda _call: [{"id": "log-1"}])
    anthropic = FakeAnthropic()
    anthropic.queue(json.dumps({"hook_slug": "lorentz-transformation"}))

    result = match_hook(
        client=anthropic,
        supabase=supabase,
        topic_title="Special Relativity",
        topic_description="Lorentz invariance and its consequences.",
        candidate_hooks=[HOOK_A, HOOK_B],
    )

    assert result == HOOK_B
    assert len(anthropic.messages.calls) == 1
    # llm_calls logged once with the hook-match route tag
    llm_inserts = [c for c in supabase.calls if c.table == "llm_calls" and c.op == "insert"]
    assert len(llm_inserts) == 1
    assert llm_inserts[0].payload["route"] == "/generate-problem:hook-match"
    # Haiku must run with temperature=0 — classification needs determinism so
    # the (topic, difficulty, hook) cache key is stable across calls.
    assert anthropic.messages.calls[0]["temperature"] == 0


def test_match_hook_null_verdict_returns_none() -> None:
    supabase = FakeSupabase()
    supabase.respond("llm_calls", "insert", lambda _call: [{"id": "log-1"}])
    anthropic = FakeAnthropic()
    anthropic.queue(json.dumps({"hook_slug": None, "reason": "no good fit"}))

    result = match_hook(
        client=anthropic,
        supabase=supabase,
        topic_title="Special Relativity",
        topic_description="...",
        candidate_hooks=[HOOK_A],
    )

    assert result is None
    # but the call was still logged
    assert any(c.table == "llm_calls" and c.op == "insert" for c in supabase.calls)


def test_match_hook_invalid_slug_falls_back_to_none() -> None:
    """Defensive: if Haiku hallucinates a slug not in the shortlist, treat as
    no match rather than crashing on a KeyError."""
    supabase = FakeSupabase()
    supabase.respond("llm_calls", "insert", lambda _call: [{"id": "log-1"}])
    anthropic = FakeAnthropic()
    anthropic.queue(json.dumps({"hook_slug": "fabricated-slug"}))

    result = match_hook(
        client=anthropic,
        supabase=supabase,
        topic_title="Special Relativity",
        topic_description="...",
        candidate_hooks=[HOOK_A, HOOK_B],
    )

    assert result is None


def test_match_hook_caps_candidates_at_six() -> None:
    """Defensive cap — keep the Haiku context window predictable."""
    supabase = FakeSupabase()
    supabase.respond("llm_calls", "insert", lambda _call: [{"id": "log-1"}])
    anthropic = FakeAnthropic()
    anthropic.queue(json.dumps({"hook_slug": "slug-1"}))

    many = [
        {
            "id": f"id-{i}",
            "slug": f"slug-{i}",
            "title": f"hook {i}",
            "summary_md": "summary",
            "difficulty_band": "core",
        }
        for i in range(10)
    ]

    result = match_hook(
        client=anthropic,
        supabase=supabase,
        topic_title="Topic",
        topic_description="",
        candidate_hooks=many,
    )

    assert result == many[1]  # slug-1
    user_msg = anthropic.messages.calls[0]["messages"][0]["content"]
    # First 6 slugs present, 7th onward absent
    assert "slug-5" in user_msg
    assert "slug-6" not in user_msg
