"""POST /generate-sibling — produce an easier, harder, or assume-less sibling
of an existing problem and swap it into the user's queue in-place.

Flow (Phase 12 Step 3 — orientation-and-calibration-design.md §A3):

  1. Load the original queue_item → problem_id.
  2. Load the problem → (topic_node_id, difficulty, intent, context_hook_id, tags).
  3. Load the node → pass full context to the shared generation helper.
  4. Compute target_difficulty:
       easier → max(1, difficulty - 1)   (min-guard: return is_min_difficulty=True)
       harder → min(5, difficulty + 1)   (max-guard: return is_max_difficulty=True)
       assume_less → same difficulty, skip pool lookup, add 'assume-less' tag.
  5. Fetch or generate the sibling problem via fetch_or_generate_problem().
  6. Mark the original queue_item state='superseded'.
  7. Insert a new queue_item for the sibling: priority_score=0.85,
     parent_queue_item_id=original, first-person added_reason.
  8. Return { sibling_problem_id, sibling_queue_item_id }.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from auth import require_internal_token
from curator_inputs import (
    derive_assumed_background_summary,
    derive_feedback_biases,
    derive_intent,
    is_entry_point,
)
from routes.generate_problem import (
    _slugify,
    _subtopics_with_slugs,
    fetch_or_generate_problem,
    match_hook,
)
from schemas import GenerateSiblingRequest, GenerateSiblingResponse
from supabase_client import get_supabase_client
from anthropic_client import get_anthropic_client

logger = logging.getLogger(__name__)

router = APIRouter()

# Absolute difficulty bounds for sibling generation (the normal DIFFICULTY_MAP
# only uses 2–4; siblings can reach 1 or 5 for the easiest/hardest variants).
DIFFICULTY_MIN = 1
DIFFICULTY_MAX = 5

_ASSUME_LESS_BACKGROUND = (
    "Assume minimal background — introduce ALL concepts, notation, and named "
    "results from scratch before using them. Do not presuppose any technical "
    "vocabulary or prior results even if they seem standard. Every symbol must "
    "be defined when first introduced."
)

_SIBLING_REASON = {
    "easier": "You asked for a more accessible version of this problem.",
    "harder": "You asked for a more challenging version of this problem.",
    "assume_less": "You asked for a version that explains more and assumes less.",
}


@router.post(
    "/generate-sibling",
    response_model=GenerateSiblingResponse,
    dependencies=[Depends(require_internal_token)],
)
def generate_sibling(
    body: GenerateSiblingRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> GenerateSiblingResponse:
    user_id = str(body.user_id)

    # 1. Load original queue_item
    qi_resp = (
        supabase.table("queue_items")
        .select("id, ref_id, state")
        .eq("id", str(body.queue_item_id))
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not qi_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="queue_item not found")
    qi = qi_resp.data[0]
    problem_id_orig = qi["ref_id"]

    # 2. Load original problem
    prob_resp = (
        supabase.table("problems")
        .select("id, topic_node_id, difficulty, intent, context_hook_id, tags")
        .eq("id", problem_id_orig)
        .limit(1)
        .execute()
    )
    if not prob_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="problem not found")
    prob = prob_resp.data[0]
    topic_node_id: str = prob["topic_node_id"]
    difficulty: int = prob["difficulty"]
    intent: str = prob.get("intent") or "teach"

    # Reconstruct context_hook_id (may be None)
    context_hook_id: str | None = prob.get("context_hook_id")

    # 3. Early guard — check max/min before any further DB work
    if body.kind == "easier" and difficulty <= DIFFICULTY_MIN:
        return GenerateSiblingResponse(is_min_difficulty=True)
    if body.kind == "harder" and difficulty >= DIFFICULTY_MAX:
        return GenerateSiblingResponse(is_max_difficulty=True)

    # 4. Load node
    node_resp = (
        supabase.table("nodes")
        .select("id, slug, title, description_md, difficulty_hint, subtopics_json")
        .eq("id", topic_node_id)
        .limit(1)
        .execute()
    )
    if not node_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="node not found")
    node = node_resp.data[0]
    topic_slug = node.get("slug") or _slugify(node["title"])

    # 5. Compute target parameters
    kind = body.kind
    skip_pool_lookup = False
    extra_tags: list[str] | None = None

    if kind == "easier":
        target_difficulty = difficulty - 1
    elif kind == "harder":
        target_difficulty = difficulty + 1
    else:  # assume_less
        target_difficulty = difficulty
        skip_pool_lookup = True
        extra_tags = ["assume-less"]

    # 6. Derive generation context (same helpers as /generate-problem)
    assumed_bg = (
        _ASSUME_LESS_BACKGROUND
        if kind == "assume_less"
        else derive_assumed_background_summary(
            supabase,
            user_id=user_id,
            topic_node_id=topic_node_id,
            topic_slug=topic_slug,
        )
    )

    entry_pt = is_entry_point(supabase, user_id=user_id, topic_node_id=topic_node_id)
    feedback_biases = derive_feedback_biases(supabase, user_id=user_id)

    # intent_context from user_interests (best-effort; empty string on miss)
    ui_resp = (
        supabase.table("user_interests")
        .select("intent_context")
        .eq("user_id", user_id)
        .eq("node_id", topic_node_id)
        .limit(1)
        .execute()
    )
    intent_context = (ui_resp.data[0].get("intent_context") or "") if ui_resp.data else ""

    # context_hook metadata — needed by build_user_prompt
    context_hook_summary: str | None = None
    if context_hook_id:
        hook_resp = (
            supabase.table("context_hooks")
            .select("summary_md")
            .eq("id", context_hook_id)
            .limit(1)
            .execute()
        )
        if hook_resp.data:
            context_hook_summary = hook_resp.data[0].get("summary_md")

    # For easier/harder: try to pick a hook for the sibling's own difficulty
    # context. For assume_less the hook stays the same as the original.
    if kind in ("easier", "harder"):
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

    # 7. Fetch or generate the sibling problem
    sibling_problem_id = fetch_or_generate_problem(
        supabase,
        anthropic,
        node=node,
        topic_slug=topic_slug,
        topic_node_id=topic_node_id,
        difficulty=target_difficulty,
        intent=intent,
        assumed_background_summary=assumed_bg,
        is_entry_point=entry_pt,
        intent_context=intent_context,
        feedback_biases=feedback_biases,
        context_hook_id=context_hook_id,
        context_hook_summary=context_hook_summary,
        user_id=user_id,
        skip_pool_lookup=skip_pool_lookup,
        extra_tags=extra_tags,
    )

    # 8. Supersede the original queue_item
    now = datetime.now(tz=timezone.utc).isoformat()
    supabase.table("queue_items").update(
        {"state": "superseded", "updated_at": now}
    ).eq("id", str(body.queue_item_id)).execute()

    # 9. Insert the sibling queue_item
    sibling_row = {
        "user_id": user_id,
        "kind": "problem",
        "ref_id": sibling_problem_id,
        "state": "pending",
        "priority_score": 0.85,
        "parent_queue_item_id": str(body.queue_item_id),
        "added_reason": _SIBLING_REASON[kind],
        "time_estimate_minutes_low": 15,
        "time_estimate_minutes_high": 30,
    }
    qi_resp2 = supabase.table("queue_items").insert(sibling_row).execute()
    sibling_queue_item_id = qi_resp2.data[0]["id"]

    return GenerateSiblingResponse(
        sibling_problem_id=UUID(sibling_problem_id),
        sibling_queue_item_id=UUID(sibling_queue_item_id),
    )
