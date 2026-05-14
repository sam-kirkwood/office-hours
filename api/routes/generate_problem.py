"""POST /generate-problem — synthesize (or look up) the next problem for a
plan node.

Flow:

  1. Load the plan_node + its canonical_topic.
  2. Load the user's `surveys.difficulty_curve`.
  3. Compute difficulty per `difficulty.difficulty_for`.
  4. Pick a context hook by asking Haiku to choose among the candidates
     tagged to this topic, or null if none is a good fit. With 0 candidates
     the Haiku call is skipped (the answer is unambiguous).
  5. Cache lookup on (canonical_topic_id, difficulty, context_hook_id). On
     hit, return the existing problem id.
  6. Sonnet call (JSON mode + strict pydantic parse + one retry).
  7. Race-safe insert into `problems`; if another worker won the race
     (unique-violation), re-select that row.
  8. Insert 5 `problem_hints` rows (only on the path where we wrote the
     problem ourselves).
  9. Return { problem_id }.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from anthropic_client import call_json, get_anthropic_client
from auth import require_internal_token
from config import HAIKU_MODEL, SONNET_MODEL
from difficulty import difficulty_for
from prompts import hook_match as hook_match_prompts
from prompts.problem import build_system_prompt, build_user_prompt
from schemas import (
    GeneratedProblem,
    GenerateProblemRequest,
    GenerateProblemResponse,
    HookMatch,
)
from supabase_client import get_supabase_client

# Cap on hooks shown to Haiku per the spec ("shortlist of up to ~6").
# Defensive — most topics have 0–3 candidates in practice.
MAX_HOOK_CANDIDATES = 6

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Small helpers — kept module-private so test_cache_lookup.py can exercise
# them against a fake Supabase client without going through HTTP.
# ---------------------------------------------------------------------------

def cache_lookup(
    supabase: Client,
    *,
    canonical_topic_id: UUID | str,
    difficulty: int,
    context_hook_id: UUID | str | None,
) -> str | None:
    """Return the problem id of an existing row that matches the cache key,
    or None if no row matches. The two partial unique indexes on `problems`
    guarantee at most one row matches."""
    query = (
        supabase.table("problems")
        .select("id")
        .eq("canonical_topic_id", str(canonical_topic_id))
        .eq("difficulty", difficulty)
    )
    if context_hook_id is None:
        query = query.is_("context_hook_id", "null")
    else:
        query = query.eq("context_hook_id", str(context_hook_id))
    result = query.limit(1).execute()
    if result.data:
        return result.data[0]["id"]
    return None


def match_hook(
    *,
    client: Anthropic,
    supabase: Client,
    topic_title: str,
    topic_description: str,
    candidate_hooks: list[dict[str, Any]],
    user_id: str | None = None,
) -> dict[str, Any] | None:
    """Ask Haiku to pick the best hook for this topic, or return None if no
    candidate fits. With 0 candidates the call is skipped — the answer is
    unambiguous and we don't want a wasted `llm_calls` row.

    On a model response naming a slug that isn't in `candidate_hooks` (which
    should be impossible per the system prompt, but the model can still err),
    treat as None and log."""
    if not candidate_hooks:
        return None

    shortlist = candidate_hooks[:MAX_HOOK_CANDIDATES]
    decision = call_json(
        client=client,
        supabase=supabase,
        model=HAIKU_MODEL,
        system_prompt=hook_match_prompts.build_system_prompt(),
        user_prompt=hook_match_prompts.build_user_prompt(
            topic_title=topic_title,
            topic_description=topic_description,
            candidate_hooks=shortlist,
        ),
        schema=HookMatch,
        route="/generate-problem:hook-match",
        user_id=user_id,
        request_summary={
            "topic_title": topic_title,
            "candidate_slugs": [h["slug"] for h in shortlist],
        },
        # Classification task — determinism matters for cache-key stability.
        # Without this, Haiku flips between hooks across otherwise-identical
        # requests and the (topic, difficulty, hook) cache misses.
        temperature=0,
    )

    if decision.hook_slug is None:
        return None

    by_slug = {h["slug"]: h for h in shortlist}
    chosen = by_slug.get(decision.hook_slug)
    if chosen is None:
        logger.warning(
            "Haiku returned slug %r not in candidates %r — treating as no match",
            decision.hook_slug,
            list(by_slug.keys()),
        )
        return None
    return chosen


def _subtopic_titles(subtopics_field: Any) -> list[str]:
    """`canonical_topics.subtopics` is a jsonb array of {slug, title}."""
    if not subtopics_field:
        return []
    titles: list[str] = []
    for entry in subtopics_field:
        if isinstance(entry, dict) and "title" in entry:
            titles.append(entry["title"])
    return titles


def _is_unique_violation(exc: Exception) -> bool:
    """supabase-py wraps PostgREST 409s in APIError with code '23505' (PG
    unique_violation). Be defensive — match by attribute and by string."""
    code = getattr(exc, "code", None)
    if code in ("23505", 23505):
        return True
    return "23505" in str(exc) or "duplicate key" in str(exc).lower()


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post(
    "/generate-problem",
    response_model=GenerateProblemResponse,
    dependencies=[Depends(require_internal_token)],
)
def generate_problem(
    body: GenerateProblemRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> GenerateProblemResponse:
    # 1. plan_node + canonical_topic
    node_resp = (
        supabase.table("plan_nodes")
        .select(
            "id, canonical_topic_id, "
            "canonical_topics ( id, title, description, difficulty_band, subtopics )"
        )
        .eq("id", str(body.plan_node_id))
        .limit(1)
        .execute()
    )
    if not node_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="plan_node not found")

    node = node_resp.data[0]
    topic = node.get("canonical_topics")
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="canonical_topic not found for plan_node",
        )
    canonical_topic_id = topic["id"]
    topic_band = topic["difficulty_band"]

    # 2. survey
    survey_resp = (
        supabase.table("surveys")
        .select("difficulty_curve")
        .eq("user_id", str(body.user_id))
        .limit(1)
        .execute()
    )
    if not survey_resp.data or not survey_resp.data[0].get("difficulty_curve"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="survey or difficulty_curve missing for user",
        )
    curve = survey_resp.data[0]["difficulty_curve"]

    # 3. difficulty
    difficulty = difficulty_for(curve, topic_band)

    # 4. hook selection (Haiku — or skipped when there are no candidates)
    hooks_resp = (
        supabase.table("context_hooks")
        .select("id, slug, title, summary_md, difficulty_band")
        .contains("related_topic_ids", [canonical_topic_id])
        .execute()
    )
    hook = match_hook(
        client=anthropic,
        supabase=supabase,
        topic_title=topic["title"],
        topic_description=topic.get("description") or "",
        candidate_hooks=hooks_resp.data or [],
        user_id=str(body.user_id),
    )
    context_hook_id = hook["id"] if hook else None
    context_hook_summary = hook["summary_md"] if hook else None

    # 5. cache lookup
    cached_id = cache_lookup(
        supabase,
        canonical_topic_id=canonical_topic_id,
        difficulty=difficulty,
        context_hook_id=context_hook_id,
    )
    if cached_id is not None:
        return GenerateProblemResponse(problem_id=UUID(cached_id))

    # 6. Sonnet generation
    user_prompt = build_user_prompt(
        topic_title=topic["title"],
        topic_description=topic.get("description") or "",
        subtopics=_subtopic_titles(topic.get("subtopics")),
        difficulty=difficulty,
        context_hook_summary_md=context_hook_summary,
    )
    generated = call_json(
        client=anthropic,
        supabase=supabase,
        model=SONNET_MODEL,
        system_prompt=build_system_prompt(),
        user_prompt=user_prompt,
        schema=GeneratedProblem,
        route="/generate-problem",
        user_id=str(body.user_id),
        request_summary={
            "canonical_topic_id": canonical_topic_id,
            "difficulty": difficulty,
            "context_hook_id": context_hook_id,
        },
    )

    # 7. race-safe insert
    problem_row = {
        "canonical_topic_id": canonical_topic_id,
        "difficulty": difficulty,
        "context_hook_id": context_hook_id,
        "statement_md": generated.statement_md,
        "solution_md": generated.solution_md,
        "rubric_md": generated.rubric_md,
        "generated_context_md": generated.generated_context_md,
    }
    try:
        insert_resp = supabase.table("problems").insert(problem_row).execute()
    except Exception as exc:  # noqa: BLE001 — we narrow inside _is_unique_violation
        if not _is_unique_violation(exc):
            raise
        # Another worker won the race; reuse their row.
        cached_id = cache_lookup(
            supabase,
            canonical_topic_id=canonical_topic_id,
            difficulty=difficulty,
            context_hook_id=context_hook_id,
        )
        if cached_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="unique violation but no cached row found",
            ) from exc
        return GenerateProblemResponse(problem_id=UUID(cached_id))

    problem_id = insert_resp.data[0]["id"]

    # 8. hints (5 rows, levels 1..5)
    hint_rows = [
        {"problem_id": problem_id, "level": i + 1, "text": text}
        for i, text in enumerate(generated.hints)
    ]
    supabase.table("problem_hints").insert(hint_rows).execute()

    return GenerateProblemResponse(problem_id=UUID(problem_id))
