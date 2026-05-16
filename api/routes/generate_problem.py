"""POST /generate-problem — synthesize (or look up) the next problem for a
graph node.

Flow:

  1. Load the node from the `nodes` table by node_id.
  2. Derive difficulty from difficulty_hint via DIFFICULTY_MAP.
  3. Pick a context hook by asking Haiku to choose among the candidates
     tagged to this topic, or null if none is a good fit. With 0 candidates
     the Haiku call is skipped (the answer is unambiguous).
  4. Cache lookup on (topic_node_id, difficulty, context_hook_id). On hit,
     skip to step 8.5 — a new queue item is still written.
  5. Sonnet call (JSON mode + strict pydantic parse + one retry).
  6. Race-safe insert into `problems`; if another worker won the race
     (unique-violation), re-select that row and skip to step 8.5.
  7. Insert 5 `problem_hints` rows (only when we wrote the problem row).
  8. Write a `queue_items` row for this user (always — on cache hit, race
     win, and race loss alike).
  9. Return { problem_id, queue_item_id }.
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
from prompts import hook_match as hook_match_prompts
from prompts.problem import build_system_prompt, build_user_prompt
from schemas import (
    GeneratedProblem,
    GenerateProblemRequest,
    GenerateProblemResponse,
    HookMatch,
)
from supabase_client import get_supabase_client

DIFFICULTY_MAP = {"intro": 2, "core": 3, "advanced": 4}

# Cap on hooks shown to Haiku per the spec ("shortlist of up to ~6").
MAX_HOOK_CANDIDATES = 6

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def cache_lookup(
    supabase: Client,
    *,
    topic_node_id: UUID | str,
    difficulty: int,
    context_hook_id: UUID | str | None,
) -> str | None:
    """Return the problem id of an existing row that matches the cache key,
    or None if no row matches."""
    query = (
        supabase.table("problems")
        .select("id")
        .eq("topic_node_id", str(topic_node_id))
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
    candidate fits. With 0 candidates the call is skipped."""
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
    """Handle both {slug, title} dict (foundation/interest nodes) and bare str
    (new interest nodes from /add-interest)."""
    if not subtopics_field:
        return []
    titles: list[str] = []
    for entry in subtopics_field:
        if isinstance(entry, dict) and "title" in entry:
            titles.append(entry["title"])
        elif isinstance(entry, str):
            titles.append(entry)
    return titles


def _is_unique_violation(exc: Exception) -> bool:
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
    # 1. Load node
    node_resp = (
        supabase.table("nodes")
        .select("id, title, description_md, difficulty_hint, subtopics_json")
        .eq("id", str(body.node_id))
        .limit(1)
        .execute()
    )
    if not node_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="node not found")
    node = node_resp.data[0]

    # 2. Derive difficulty
    difficulty = DIFFICULTY_MAP.get(node["difficulty_hint"], 3)
    topic_node_id = node["id"]

    # 3. Hook selection (Haiku — skipped when there are no candidates)
    hooks_resp = (
        supabase.table("context_hooks")
        .select("id, slug, title, summary_md, difficulty_band")
        .contains("related_topic_ids", [topic_node_id])
        .execute()
    )
    hook = match_hook(
        client=anthropic,
        supabase=supabase,
        topic_title=node["title"],
        topic_description=node.get("description_md") or "",
        candidate_hooks=hooks_resp.data or [],
        user_id=str(body.user_id),
    )
    context_hook_id = hook["id"] if hook else None
    context_hook_summary = hook["summary_md"] if hook else None

    # 4. Cache lookup
    cached_id = cache_lookup(
        supabase,
        topic_node_id=topic_node_id,
        difficulty=difficulty,
        context_hook_id=context_hook_id,
    )

    if cached_id is not None:
        problem_id = cached_id
    else:
        # 5. Sonnet generation
        user_prompt = build_user_prompt(
            topic_title=node["title"],
            topic_description=node.get("description_md") or "",
            subtopics=_subtopic_titles(node.get("subtopics_json")),
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
            max_tokens=8192,
            request_summary={
                "topic_node_id": topic_node_id,
                "difficulty": difficulty,
                "context_hook_id": context_hook_id,
            },
        )

        # 6. Race-safe insert
        problem_row = {
            "topic_node_id": topic_node_id,
            "difficulty": difficulty,
            "context_hook_id": context_hook_id,
            "statement_md": generated.statement_md,
            "solution_md": generated.solution_md,
            "rubric_md": generated.rubric_md,
            "context_md": generated.context_md,
        }
        try:
            insert_resp = supabase.table("problems").insert(problem_row).execute()
        except Exception as exc:  # noqa: BLE001
            if not _is_unique_violation(exc):
                raise
            # Another worker won the race; reuse their row.
            cached_id = cache_lookup(
                supabase,
                topic_node_id=topic_node_id,
                difficulty=difficulty,
                context_hook_id=context_hook_id,
            )
            if cached_id is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="unique violation but no cached row found",
                ) from exc
            problem_id = cached_id
        else:
            problem_id = insert_resp.data[0]["id"]
            # 7. Hints (5 rows, levels 1..5) — only when we won the race
            hint_rows = [
                {"problem_id": problem_id, "level": i + 1, "text": text}
                for i, text in enumerate(generated.hints)
            ]
            supabase.table("problem_hints").insert(hint_rows).execute()

    # 8. Queue item (always written — cache hit, race win, or race loss)
    queue_row = {
        "user_id": str(body.user_id),
        "kind": "problem",
        "ref_id": problem_id,
        "state": "pending",
        "priority_score": 0.5,
        "added_reason": f"A problem on {node['title']}",
        "time_estimate_minutes_low": 15,
        "time_estimate_minutes_high": 30,
    }
    queue_resp = supabase.table("queue_items").insert(queue_row).execute()
    queue_item_id = queue_resp.data[0]["id"]

    return GenerateProblemResponse(
        problem_id=UUID(problem_id),
        queue_item_id=UUID(queue_item_id),
    )
