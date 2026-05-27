from uuid import uuid4

from routes.generate_problem import cache_lookup
from tests.fake_supabase import FakeSupabase


def test_cache_lookup_with_hook_uses_eq() -> None:
    supabase = FakeSupabase()
    topic_node_id = uuid4()
    hook_id = uuid4()
    supabase.respond("problems", "select", lambda _call: [{"id": "deadbeef"}])

    result = cache_lookup(
        supabase,
        topic_node_id=topic_node_id,
        difficulty=3,
        context_hook_id=hook_id,
        intent="teach",
    )

    assert result == "deadbeef"
    assert len(supabase.calls) == 1
    call = supabase.calls[0]
    assert call.table == "problems"
    assert call.op == "select"
    assert ("eq", "topic_node_id", str(topic_node_id)) in call.filters
    assert ("eq", "difficulty", 3) in call.filters
    assert ("eq", "context_hook_id", str(hook_id)) in call.filters
    assert ("eq", "intent", "teach") in call.filters
    # never call is_() in the hook-present branch
    assert not any(f[0] == "is_" for f in call.filters)


def test_cache_lookup_without_hook_uses_is_null() -> None:
    supabase = FakeSupabase()
    topic_node_id = uuid4()
    supabase.respond("problems", "select", lambda _call: [{"id": "abc123"}])

    result = cache_lookup(
        supabase,
        topic_node_id=topic_node_id,
        difficulty=2,
        context_hook_id=None,
        intent="refresh",
    )

    assert result == "abc123"
    call = supabase.calls[0]
    assert ("is_", "context_hook_id", "null") in call.filters
    assert ("eq", "intent", "refresh") in call.filters
    assert not any(f[0] == "eq" and f[1] == "context_hook_id" for f in call.filters)


def test_cache_lookup_no_rows_returns_none() -> None:
    supabase = FakeSupabase()
    supabase.respond("problems", "select", lambda _call: [])
    assert (
        cache_lookup(
            supabase,
            topic_node_id=uuid4(),
            difficulty=3,
            context_hook_id=None,
            intent="teach",
        )
        is None
    )
