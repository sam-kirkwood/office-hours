"""POST /generate-problem — synthesize (or look up) the next problem for a
graph node.

Flow (Phase 10-rev Step 2f — three-dial discipline):

  1. Load the node (now also returns `slug` for the required `tags`).
  2. Derive the three dials:
       - difficulty: DIFFICULTY_MAP[node.difficulty_hint] (unchanged).
       - intent: request body override OR string-match on
                 user_interests.intent_context for this (user, node). Default
                 'teach' when no interest row exists (e.g. concept_review
                 paths on a non-interest node).
       - assumed background: derived narrative from user_node_states for the
                 topic + its prerequisites + surveys.comfort_responses_json.
                 Passed to the prompt as a paragraph, not a numeric.
  3. is_entry_point: True iff this user has no prior attempts on this topic.
  4. feedback_biases: read from user_preferences (the profile-page toggles).
  5. Pick a context hook by asking Haiku to choose among the candidates
     tagged to this topic, or null if none is a good fit.
  6. Cache lookup on (topic_node_id, difficulty, context_hook_id, intent).
     Intent is now part of the cache key — same topic+difficulty+hook with
     different intents are stored as separate rows.
  7. Sonnet call (JSON mode + strict pydantic parse + one retry). The
     prompt enforces required subtopic-level tags and the entry-point /
     practical-generation-test discipline.
  8. Validate tags: must contain the topic slug AND len >= 2.
  9. Race-safe insert with tags + intent populated.
 10. Insert 5 problem_hints rows (only when we wrote the problem row).
 11. Write a queue_items row for this user.
 12. Return { problem_id, queue_item_id }.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from anthropic_client import call_json, get_anthropic_client
from auth import require_internal_token
from config import HAIKU_MODEL, SONNET_MODEL
from curator_inputs import (
    FEEDBACK_KEYS,  # noqa: F401  — re-exported for back-compat with tests
    derive_assumed_background_summary,
    derive_feedback_biases,
    derive_intent,
    find_pending_queue_item,
    is_entry_point,
)
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

VALID_INTENTS = {"teach", "refresh", "consolidate"}

logger = logging.getLogger(__name__)

router = APIRouter()

_SLUG_PUNCT_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUG_PUNCT_RE.sub("-", text.lower()).strip("-") or "untitled"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def cache_lookup(
    supabase: Client,
    *,
    topic_node_id: UUID | str,
    difficulty: int,
    context_hook_id: UUID | str | None,
    intent: str,
) -> str | None:
    """Return the problem id of an existing row that matches the cache key,
    or None if no row matches. Intent is now part of the key.

    Excludes problems tagged 'assume-less' so assume-less siblings never
    satisfy a regular pool lookup (and vice-versa)."""
    query = (
        supabase.table("problems")
        .select("id")
        .eq("topic_node_id", str(topic_node_id))
        .eq("difficulty", difficulty)
        .eq("intent", intent)
        .not_.cs("tags", ["assume-less"])
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


def _subtopics_with_slugs(subtopics_field: Any) -> list[dict[str, str]]:
    """Return a list of {slug, title} dicts for the prompt.

    Handles both shapes stored in nodes.subtopics_json:
      - {"slug": ..., "title": ...} (curated foundation / interest nodes)
      - bare string (newer interest nodes from /add-interest)

    For bare strings we synthesize a slug from the title.
    """
    if not subtopics_field:
        return []
    out: list[dict[str, str]] = []
    for entry in subtopics_field:
        if isinstance(entry, dict):
            title = entry.get("title") or entry.get("name") or entry.get("slug")
            if not title:
                continue
            slug = entry.get("slug") or _slugify(str(title))
            out.append({"slug": str(slug), "title": str(title)})
        elif isinstance(entry, str):
            out.append({"slug": _slugify(entry), "title": entry})
    return out


def _is_unique_violation(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if code in ("23505", 23505):
        return True
    return "23505" in str(exc) or "duplicate key" in str(exc).lower()


# ---------------------------------------------------------------------------
# Tag validation
# ---------------------------------------------------------------------------


def _validate_tags(tags: list[str], topic_slug: str) -> tuple[bool, str | None]:
    """Return (ok, reason). Tags must include the topic slug and have len >= 2."""
    if not tags:
        return False, "tags is empty — must contain topic slug + at least one subtopic slug"
    if len(tags) < 2:
        return False, "tags must contain at least 2 entries (topic + 1 subtopic)"
    if topic_slug not in tags:
        return (
            False,
            f"tags must include the topic slug {topic_slug!r}; got {tags!r}",
        )
    return True, None


# ---------------------------------------------------------------------------
# Shared generation helper (also used by /generate-sibling)
# ---------------------------------------------------------------------------


def fetch_or_generate_problem(
    supabase: Client,
    anthropic: Anthropic,
    *,
    node: dict[str, Any],
    topic_slug: str,
    topic_node_id: str,
    difficulty: int,
    intent: str,
    assumed_background_summary: str,
    is_entry_point: bool,
    intent_context: str,
    feedback_biases: dict[str, bool],
    context_hook_id: str | None,
    context_hook_summary: str | None,
    user_id: str,
    skip_pool_lookup: bool = False,
    extra_tags: list[str] | None = None,
) -> str:
    """Fetch from pool (cache_lookup) or generate via Sonnet, insert the
    problem row + hints, and return the problem_id string.

    skip_pool_lookup=True is used for assume-less siblings — always generate
    fresh; the result is tagged 'assume-less' via extra_tags and excluded from
    regular cache_lookup by the not_.cs filter.

    extra_tags are appended to the model-generated tags before insert.
    """
    cached_id: str | None = None
    if not skip_pool_lookup:
        cached_id = cache_lookup(
            supabase,
            topic_node_id=topic_node_id,
            difficulty=difficulty,
            context_hook_id=context_hook_id,
            intent=intent,
        )

    if cached_id is not None:
        return cached_id

    # Sonnet generation
    subtopics = _subtopics_with_slugs(node.get("subtopics_json"))
    user_prompt = build_user_prompt(
        topic_title=node["title"],
        topic_slug=topic_slug,
        topic_description=node.get("description_md") or "",
        subtopics=subtopics,
        difficulty=difficulty,
        intent=intent,
        assumed_background_summary=assumed_background_summary,
        is_entry_point=is_entry_point,
        intent_context=intent_context,
        feedback_biases=feedback_biases,
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
        user_id=user_id,
        max_tokens=8192,
        request_summary={
            "topic_node_id": topic_node_id,
            "difficulty": difficulty,
            "intent": intent,
            "context_hook_id": context_hook_id,
            "entry_point": is_entry_point,
        },
    )

    # Merge extra_tags before validation (e.g. 'assume-less' for siblings)
    tags = list(generated.tags)
    if extra_tags:
        for t in extra_tags:
            if t not in tags:
                tags.append(t)

    # Validate: topic slug present + at least one subtopic.
    # For assume-less siblings the 'assume-less' marker is internal — only
    # validate against the topic-slug + subtopic requirement on the rest.
    non_marker_tags = [t for t in tags if t not in (extra_tags or [])]
    ok, reason = _validate_tags(non_marker_tags if extra_tags else tags, topic_slug)
    if not ok:
        logger.warning(
            "Sonnet returned invalid tags %r for topic %r — %s",
            tags,
            topic_slug,
            reason,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"generator returned invalid tags: {reason}",
        )

    # Race-safe insert
    problem_row = {
        "topic_node_id": topic_node_id,
        "difficulty": difficulty,
        "intent": intent,
        "context_hook_id": context_hook_id,
        "title": generated.title,
        "statement_md": generated.statement_md,
        "solution_md": generated.solution_md,
        "rubric_md": generated.rubric_md,
        "context_md": generated.context_md,
        "tags": tags,
    }
    try:
        insert_resp = supabase.table("problems").insert(problem_row).execute()
    except Exception as exc:  # noqa: BLE001
        if not _is_unique_violation(exc):
            raise
        # Race: another worker inserted first. Fall back to a cache lookup
        # (only safe for non-assume-less paths; for assume-less just re-raise
        # since the unique constraint fires on a different key).
        if skip_pool_lookup:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="concurrent insert on assume-less problem",
            ) from exc
        fallen_id = cache_lookup(
            supabase,
            topic_node_id=topic_node_id,
            difficulty=difficulty,
            context_hook_id=context_hook_id,
            intent=intent,
        )
        if fallen_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="unique violation but no cached row found",
            ) from exc
        return fallen_id

    problem_id = insert_resp.data[0]["id"]
    # Hints (5 rows, levels 1..5) — only when we won the race
    hint_rows = [
        {
            "problem_id": problem_id,
            "level": i + 1,
            "text": hint.text,
            "part_label": hint.part_label,
        }
        for i, hint in enumerate(generated.hints)
    ]
    supabase.table("problem_hints").insert(hint_rows).execute()
    return problem_id


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
    # 1. Load node (now includes slug for the tags requirement)
    node_resp = (
        supabase.table("nodes")
        .select("id, slug, title, description_md, difficulty_hint, subtopics_json")
        .eq("id", str(body.node_id))
        .limit(1)
        .execute()
    )
    if not node_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="node not found")
    node = node_resp.data[0]

    user_id = str(body.user_id)
    topic_node_id = node["id"]
    topic_slug = node.get("slug") or _slugify(node["title"])

    # 2. Derive three dials (intent from body or intent_context; difficulty
    # from node; assumed background from engagement signals)
    difficulty = DIFFICULTY_MAP.get(node["difficulty_hint"], 3)

    intent = body.intent
    if intent is not None and intent not in VALID_INTENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"intent must be one of {sorted(VALID_INTENTS)}",
        )
    if intent is None:
        intent = derive_intent(supabase, user_id=user_id, node_id=topic_node_id)

    entry_point = is_entry_point(
        supabase, user_id=user_id, topic_node_id=topic_node_id
    )

    assumed_background_summary = derive_assumed_background_summary(
        supabase,
        user_id=user_id,
        topic_node_id=topic_node_id,
        topic_slug=topic_slug,
    )

    # intent_context — pulled into the prompt verbatim (separate from intent).
    intent_context = ""
    ui_resp = (
        supabase.table("user_interests")
        .select("id, intent_context")
        .eq("user_id", user_id)
        .eq("node_id", topic_node_id)
        .limit(1)
        .execute()
    )
    if ui_resp.data:
        intent_context = ui_resp.data[0].get("intent_context") or ""
    is_direct_interest = bool(ui_resp.data)

    # 3. Feedback biases (request body override OR DB)
    feedback_biases = body.feedback_bias
    if feedback_biases is None:
        feedback_biases = derive_feedback_biases(supabase, user_id=user_id)

    # 4. Hook selection (Haiku — skipped when there are no candidates)
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
        user_id=user_id,
    )
    context_hook_id = hook["id"] if hook else None
    context_hook_summary = hook["summary_md"] if hook else None

    # 5–9. Cache lookup / generation / insert / hints — shared with sibling route.
    problem_id = fetch_or_generate_problem(
        supabase,
        anthropic,
        node=node,
        topic_slug=topic_slug,
        topic_node_id=topic_node_id,
        difficulty=difficulty,
        intent=intent,
        assumed_background_summary=assumed_background_summary,
        is_entry_point=entry_point,
        intent_context=intent_context,
        feedback_biases=feedback_biases,
        context_hook_id=context_hook_id,
        context_hook_summary=context_hook_summary,
        user_id=user_id,
    )

    # 10. Queue item — dedup against existing pending/surfaced rows first.
    # Without this check, the curator's pool-miss → generate-problem
    # cache-hit path can produce multiple queue rows pointing at the same
    # problem under different recommendation rationales (Phase 10-rev §9a).
    existing_queue_id = find_pending_queue_item(
        supabase, user_id=user_id, kind="problem", ref_id=problem_id
    )
    if existing_queue_id is not None:
        return GenerateProblemResponse(
            problem_id=UUID(problem_id),
            queue_item_id=UUID(existing_queue_id),
        )

    added_reason = (
        f"Practice for your interest in {node['title']}."
        if is_direct_interest
        else f"A problem on {node['title']}."
    )
    queue_row = {
        "user_id": user_id,
        "kind": "problem",
        "ref_id": problem_id,
        "state": "pending",
        "priority_score": 0.5,
        "added_reason": added_reason,
        "time_estimate_minutes_low": 15,
        "time_estimate_minutes_high": 30,
    }
    queue_resp = supabase.table("queue_items").insert(queue_row).execute()
    queue_item_id = queue_resp.data[0]["id"]

    return GenerateProblemResponse(
        problem_id=UUID(problem_id),
        queue_item_id=UUID(queue_item_id),
    )
