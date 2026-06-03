"""Curriculum curator routes.

Step 3 of Phase 10-rev. This module hosts four handlers that together
replace the placeholder /update-queue:

- POST /assess-engagement — Haiku, post-engagement              (Step 3a)
- POST /plan-queue        — Sonnet, daily per-user              (Step 3b)
- POST /check-deferred    — deterministic re-queue check        (Step 3c)
- POST /run-daily-planner — wrapper that calls /plan-queue then
                            /check-deferred and logs the run    (Step 3d)

The shared system prompts are cache-eligible and live in api/prompts/. The
shared input-derivation helpers are in api/curator_inputs.py so the curator
and /generate-problem can both reach for them.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from anthropic_client import call_json, get_anthropic_client
from auth import require_internal_token
from config import HAIKU_MODEL, SONNET_MODEL
from curator_inputs import (
    build_curator_context,
    find_foundation_owning_subtopic,
    load_engagement_signals_for_attempt,
    load_engagement_signals_for_paper,
    load_node_state,
)
from prompts.curator_plan import (
    build_system_prompt as curator_plan_system_prompt,
)
from prompts.curator_plan import (
    build_user_prompt as curator_plan_user_prompt,
)
from prompts.engagement_assess import (
    build_system_prompt as engagement_assess_system_prompt,
)
from prompts.engagement_assess import (
    build_user_prompt as engagement_assess_user_prompt,
)
from schemas import (
    AssessEngagementRequest,
    AssessEngagementResponse,
    AssessEngagementResult,
    CheckDeferredRequest,
    CheckDeferredResponse,
    CuratorPlanLLMOutput,
    CuratorRecommendation,
    GenerateProblemRequest,
    PlanQueueRequest,
    PlanQueueResponse,
    RunDailyPlannerRequest,
    RunDailyPlannerResponse,
)
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# user_node_states upsert
# ---------------------------------------------------------------------------


def _upsert_node_state(
    supabase: Client,
    *,
    user_id: str,
    node_id: str,
    new_struggle_score: float,
    state_transition: str | None,
    prior_engagement_count: int,
) -> None:
    """Persist the post-engagement state update.

    Always bumps engagement_count and last_engaged_at. Applies the new
    struggle_score (clamped to [0,1]) and the optional state_transition.
    """
    clamped = max(0.0, min(1.0, float(new_struggle_score)))
    row: dict[str, Any] = {
        "user_id": user_id,
        "node_id": node_id,
        "struggle_score": clamped,
        "engagement_count": prior_engagement_count + 1,
        "last_engaged_at": _now_iso(),
    }
    if state_transition is not None:
        row["state"] = state_transition
    supabase.table("user_node_states").upsert(
        row, on_conflict="user_id,node_id"
    ).execute()


# ---------------------------------------------------------------------------
# immediate_action execution
# ---------------------------------------------------------------------------


def _find_easier_sibling_problem(
    supabase: Client,
    *,
    topic_node_id: str,
    subtopic_slug: str | None,
    current_difficulty: int,
) -> str | None:
    """Pool lookup for a problem on the same topic, one difficulty step
    easier, tagged with the same subtopic. Returns the problem id, or None
    if nothing suitable is in the pool yet.
    """
    target_difficulty = max(1, current_difficulty - 1)
    query = (
        supabase.table("problems")
        .select("id, tags")
        .eq("topic_node_id", topic_node_id)
        .eq("difficulty", target_difficulty)
    )
    if subtopic_slug:
        query = query.contains("tags", [subtopic_slug])
    resp = query.limit(1).execute()
    if not resp.data:
        return None
    return resp.data[0]["id"]


def _execute_queue_reinforcement(
    supabase: Client,
    *,
    user_id: str,
    engagement: dict[str, Any],
    reinforcement_target: str | None,
    reasoning: str,
) -> bool:
    """Try to enqueue an easier sibling. Returns True iff a queue row was
    written; False on pool miss (the daily plan will pick up the signal).
    """
    topic_node_id = engagement.get("node_id")
    if not topic_node_id:
        return False
    sibling_id = _find_easier_sibling_problem(
        supabase,
        topic_node_id=str(topic_node_id),
        subtopic_slug=reinforcement_target or engagement.get("subtopic"),
        current_difficulty=int(engagement.get("difficulty") or 3),
    )
    if sibling_id is None:
        return False

    supabase.table("queue_items").insert(
        {
            "user_id": user_id,
            "kind": "problem",
            "ref_id": sibling_id,
            "state": "pending",
            "priority_score": 0.7,
            "added_reason": reasoning,
            "time_estimate_minutes_low": 10,
            "time_estimate_minutes_high": 20,
        }
    ).execute()
    return True


def _execute_accelerate(
    supabase: Client,
    *,
    user_id: str,
    engagement: dict[str, Any],
) -> bool:
    """Bump priority_score on the highest-priority pending item for this
    topic at a difficulty above the engagement's difficulty.
    """
    topic_node_id = engagement.get("node_id")
    if not topic_node_id:
        return False
    current_difficulty = int(engagement.get("difficulty") or 3)

    # Pull the user's pending problem queue items for this topic, then
    # filter by difficulty via the problems join (no native join in the
    # supabase-py builder — two-step query).
    pending = (
        supabase.table("queue_items")
        .select("id, ref_id")
        .eq("user_id", user_id)
        .eq("kind", "problem")
        .eq("state", "pending")
        .execute()
    )
    candidate_ref_ids = [r["ref_id"] for r in (pending.data or []) if r.get("ref_id")]
    if not candidate_ref_ids:
        return False

    problems = (
        supabase.table("problems")
        .select("id, topic_node_id, difficulty")
        .in_("id", candidate_ref_ids)
        .eq("topic_node_id", str(topic_node_id))
        .gt("difficulty", current_difficulty)
        .execute()
    )
    if not problems.data:
        return False

    next_problem_ids = {p["id"] for p in problems.data}
    targets = [r for r in pending.data if r.get("ref_id") in next_problem_ids]
    if not targets:
        return False

    # Bump them all — typically there's just one or two pending at the
    # next difficulty step.
    for row in targets:
        supabase.table("queue_items").update(
            {"priority_score": 0.85, "updated_at": _now_iso()}
        ).eq("id", row["id"]).execute()
    return True


def _execute_surface_prerequisite(
    supabase: Client,
    *,
    user_id: str,
    engagement: dict[str, Any],
    reinforcement_target: str | None,
    reasoning: str,
) -> bool:
    """Enqueue a refresher on a prerequisite of the engagement's topic.

    `reinforcement_target` should be the prerequisite subtopic or node slug.
    If we can match it to a prerequisite edge, we queue a refresher item
    for that node; otherwise we queue the highest-weight prerequisite.
    """
    topic_node_id = engagement.get("node_id")
    if not topic_node_id:
        return False

    edges = (
        supabase.table("edges")
        .select("source_node_id, weight")
        .eq("target_node_id", str(topic_node_id))
        .eq("edge_kind", "prerequisite")
        .execute()
    )
    if not edges.data:
        return False

    source_ids = [e["source_node_id"] for e in edges.data]
    nodes = (
        supabase.table("nodes")
        .select("id, slug, title")
        .in_("id", source_ids)
        .execute()
    )
    by_slug = {n["slug"]: n for n in (nodes.data or [])}

    chosen_node: dict[str, Any] | None = None
    if reinforcement_target and reinforcement_target in by_slug:
        chosen_node = by_slug[reinforcement_target]
    else:
        # Fall back to the highest-weight prerequisite edge.
        weighted = sorted(
            edges.data, key=lambda e: float(e.get("weight") or 0), reverse=True
        )
        for edge in weighted:
            node = next(
                (n for n in (nodes.data or []) if n["id"] == edge["source_node_id"]),
                None,
            )
            if node is not None:
                chosen_node = node
                break

    if chosen_node is None:
        return False

    supabase.table("queue_items").insert(
        {
            "user_id": user_id,
            "kind": "refresher",
            "ref_id": chosen_node["id"],
            "state": "pending",
            "priority_score": 0.75,
            "added_reason": reasoning,
            "time_estimate_minutes_low": 10,
            "time_estimate_minutes_high": 20,
        }
    ).execute()
    return True


def _execute_immediate_action(
    supabase: Client,
    *,
    user_id: str,
    engagement: dict[str, Any],
    assessment: AssessEngagementResult,
) -> bool:
    """Dispatch on immediate_action. Returns True iff an action was executed
    (i.e. wrote a row); False for null, pool-miss, or paper-engagement
    (which can't be attributed to a node)."""
    action = assessment.immediate_action
    if action is None:
        return False
    if action == "queue_reinforcement":
        return _execute_queue_reinforcement(
            supabase,
            user_id=user_id,
            engagement=engagement,
            reinforcement_target=assessment.reinforcement_target,
            reasoning=assessment.reasoning,
        )
    if action == "accelerate":
        return _execute_accelerate(
            supabase, user_id=user_id, engagement=engagement
        )
    if action == "surface_prerequisite":
        return _execute_surface_prerequisite(
            supabase,
            user_id=user_id,
            engagement=engagement,
            reinforcement_target=assessment.reinforcement_target,
            reasoning=assessment.reasoning,
        )
    logger.warning("unknown immediate_action %r — skipping", action)
    return False


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


def run_assess_engagement(
    *,
    supabase: Client,
    anthropic: Anthropic,
    user_id: str,
    attempt_id: str | None = None,
    engagement_id: str | None = None,
) -> AssessEngagementResponse:
    """Service-level entry point used by both the HTTP route and the
    in-process callers (/grade-solution and /grade-paper-answer).

    Either `attempt_id` or `engagement_id` must be set, not both.
    """
    if (attempt_id is None) == (engagement_id is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="exactly one of attempt_id or engagement_id is required",
        )

    # 1. Load engagement signals.
    if attempt_id is not None:
        try:
            engagement = load_engagement_signals_for_attempt(
                supabase, attempt_id=attempt_id
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
    else:
        try:
            engagement = load_engagement_signals_for_paper(
                supabase, engagement_id=engagement_id  # type: ignore[arg-type]
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc

    node_id = engagement.get("node_id")
    if node_id:
        current_state = load_node_state(
            supabase, user_id=user_id, node_id=str(node_id)
        )
    else:
        # Paper engagement without a resolvable node — pass defaults so the
        # Haiku call can still run for logging, but skip state writes below.
        current_state = {
            "state": "unseen",
            "struggle_score": 0.0,
            "engagement_count": 0,
            "last_engaged_at": None,
        }

    # 2. Haiku call.
    assessment = call_json(
        client=anthropic,
        supabase=supabase,
        model=HAIKU_MODEL,
        system_prompt=engagement_assess_system_prompt(),
        user_prompt=engagement_assess_user_prompt(
            engagement=engagement, current_node_state=current_state
        ),
        schema=AssessEngagementResult,
        route="/assess-engagement",
        user_id=user_id,
        request_summary={
            "engagement_kind": engagement.get("kind"),
            "node_id": str(node_id) if node_id else None,
            "subtopic": engagement.get("subtopic"),
            "attempt_id": attempt_id,
            "paper_engagement_id": engagement_id,
        },
        max_tokens=1024,
        temperature=0,
    )

    # 3. Persist the node-state update (skip if we don't have a node).
    if node_id:
        _upsert_node_state(
            supabase,
            user_id=user_id,
            node_id=str(node_id),
            new_struggle_score=assessment.updated_struggle_score,
            state_transition=assessment.state_transition,
            prior_engagement_count=int(current_state.get("engagement_count") or 0),
        )

    # 4. Execute immediate_action.
    action_executed = _execute_immediate_action(
        supabase,
        user_id=user_id,
        engagement=engagement,
        assessment=assessment,
    )

    return AssessEngagementResponse(
        updated_struggle_score=assessment.updated_struggle_score,
        state_transition=assessment.state_transition,
        immediate_action=assessment.immediate_action,
        action_executed=action_executed,
        reasoning=assessment.reasoning,
    )


@router.post(
    "/assess-engagement",
    response_model=AssessEngagementResponse,
    dependencies=[Depends(require_internal_token)],
)
def assess_engagement(
    body: AssessEngagementRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> AssessEngagementResponse:
    return run_assess_engagement(
        supabase=supabase,
        anthropic=anthropic,
        user_id=str(body.user_id),
        attempt_id=str(body.attempt_id) if body.attempt_id else None,
        engagement_id=str(body.engagement_id) if body.engagement_id else None,
    )


# ---------------------------------------------------------------------------
# /plan-queue (Step 3b)
# ---------------------------------------------------------------------------


_PRIORITY_SCORE_MAP = {"low": 0.4, "medium": 0.6, "high": 0.85}
_DEPTH_DIFFICULTY_MAP = {
    "conceptual": 1,
    "foundational": 2,
    "intermediate": 3,
    "advanced": 4,
}


def _slugify_phrase(text: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "untitled"


def _resolve_interest_node(
    supabase: Client, *, title: str
) -> dict[str, Any] | None:
    """Look up a node by its title (case-insensitive). Returns the row dict
    with id, slug, title, kind — or None if no match."""
    if not title:
        return None
    resp = (
        supabase.table("nodes")
        .select("id, slug, title, kind, subtopics_json")
        .ilike("title", title)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    return resp.data[0]


def _pool_lookup_for_recommendation(
    supabase: Client,
    *,
    topic_node_id: str,
    difficulty: int,
    intent: str,
    subtopic_slug: str | None,
) -> str | None:
    """Return a problem id matching the rec's (topic, difficulty, intent, +
    optional subtopic tag), or None if nothing in the pool fits.
    """
    query = (
        supabase.table("problems")
        .select("id, tags")
        .eq("topic_node_id", topic_node_id)
        .eq("difficulty", difficulty)
        .eq("intent", intent)
    )
    if subtopic_slug:
        query = query.contains("tags", [subtopic_slug])
    resp = query.limit(1).execute()
    if not resp.data:
        return None
    return resp.data[0]["id"]


def _queue_item_already_exists(
    supabase: Client, *, user_id: str, kind: str, ref_id: str
) -> bool:
    """Skip add when the user already has a pending/surfaced item with the
    same (kind, ref_id). Prevents duplicate problem refs from accumulating
    across daily runs."""
    resp = (
        supabase.table("queue_items")
        .select("id")
        .eq("user_id", user_id)
        .eq("kind", kind)
        .eq("ref_id", ref_id)
        .in_("state", ["pending", "surfaced"])
        .limit(1)
        .execute()
    )
    return bool(resp.data)


def _execute_add_problem(
    supabase: Client,
    anthropic: Anthropic,
    *,
    user_id: str,
    rec: CuratorRecommendation,
) -> bool:
    """Resolve interest_node → node_id, pool-lookup or generate, write a
    queue_items row. Returns True if a row was written."""
    node = _resolve_interest_node(supabase, title=rec.interest_node or "")
    if node is None:
        logger.warning(
            "plan-queue: could not resolve interest_node=%r — skipping rec",
            rec.interest_node,
        )
        return False

    difficulty = _DEPTH_DIFFICULTY_MAP.get(rec.depth or "intermediate", 3)
    intent = rec.intent or "teach"
    subtopic_slug = _slugify_phrase(rec.subtopic) if rec.subtopic else None
    priority_score = _PRIORITY_SCORE_MAP.get(rec.priority or "medium", 0.6)

    cached_id = _pool_lookup_for_recommendation(
        supabase,
        topic_node_id=node["id"],
        difficulty=difficulty,
        intent=intent,
        subtopic_slug=subtopic_slug,
    )

    if cached_id is not None:
        if _queue_item_already_exists(
            supabase, user_id=user_id, kind="problem", ref_id=cached_id
        ):
            return False
        supabase.table("queue_items").insert(
            {
                "user_id": user_id,
                "kind": "problem",
                "ref_id": cached_id,
                "state": "pending",
                "priority_score": priority_score,
                "added_reason": rec.reason,
                "time_estimate_minutes_low": 15,
                "time_estimate_minutes_high": 30,
            }
        ).execute()
        return True

    # Pool miss → call /generate-problem inline. The generator writes a
    # queue_items row of its own with a default reason; we overwrite that
    # reason afterwards so the curator's wording wins.
    from routes.generate_problem import generate_problem  # local import: cycles

    body = GenerateProblemRequest(
        user_id=user_id,
        node_id=node["id"],
        intent=intent,
    )
    try:
        gen_resp = generate_problem(
            body=body, supabase=supabase, anthropic=anthropic
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "plan-queue: /generate-problem failed for node=%s — skipping rec",
            node["id"],
        )
        return False

    # Overwrite added_reason + priority_score with the curator's values.
    supabase.table("queue_items").update(
        {
            "added_reason": rec.reason,
            "priority_score": priority_score,
            "updated_at": _now_iso(),
        }
    ).eq("id", str(gen_resp.queue_item_id)).execute()
    return True


def _execute_add_refresher(
    supabase: Client,
    *,
    user_id: str,
    rec: CuratorRecommendation,
) -> bool:
    """Add a refresher queue item.

    Routing (Phase 10-rev §9a): when rec.subtopic matches a subtopic of a
    foundation node (e.g. "partition function manipulations" →
    statistical-mechanics), set ref_id to that foundation. The refresher
    then resolves to refresher/concept-review content on the foundation
    rather than on the interest node, which is what the added_reason
    typically promises.

    Falls back to rec.interest_node when no foundation owns the subtopic.
    """
    ref_node: dict | None = None
    if rec.subtopic:
        ref_node = find_foundation_owning_subtopic(
            supabase, subtopic_slug=_slugify_phrase(rec.subtopic)
        )
    if ref_node is None:
        ref_node = _resolve_interest_node(supabase, title=rec.interest_node or "")
    if ref_node is None:
        logger.warning(
            "plan-queue: could not resolve refresher node "
            "(subtopic=%r, interest_node=%r) — skipping",
            rec.subtopic,
            rec.interest_node,
        )
        return False
    if _queue_item_already_exists(
        supabase, user_id=user_id, kind="refresher", ref_id=ref_node["id"]
    ):
        return False
    priority_score = _PRIORITY_SCORE_MAP.get(rec.priority or "medium", 0.6)
    supabase.table("queue_items").insert(
        {
            "user_id": user_id,
            "kind": "refresher",
            "ref_id": ref_node["id"],
            "state": "pending",
            "priority_score": priority_score,
            "added_reason": rec.reason,
            "time_estimate_minutes_low": 10,
            "time_estimate_minutes_high": 20,
        }
    ).execute()
    return True


def _execute_reprioritise(
    supabase: Client,
    *,
    user_id: str,
    rec: CuratorRecommendation,
) -> bool:
    """Update priority_score on the given queue_item, scoped to this user."""
    if rec.queue_item_id is None or rec.new_priority is None:
        return False
    new_score = _PRIORITY_SCORE_MAP.get(rec.new_priority, 0.6)
    resp = (
        supabase.table("queue_items")
        .update({"priority_score": new_score, "updated_at": _now_iso()})
        .eq("id", str(rec.queue_item_id))
        .eq("user_id", user_id)
        .execute()
    )
    return bool(resp.data)


def run_plan_queue(
    *,
    supabase: Client,
    anthropic: Anthropic,
    user_id: str,
) -> PlanQueueResponse:
    """Service-level entry point. Pulls the full user context, calls Sonnet,
    executes recommendations. Used by the HTTP route and (later) the daily
    background job's per-user fan-out."""
    context = build_curator_context(supabase, user_id=user_id)

    plan = call_json(
        client=anthropic,
        supabase=supabase,
        model=SONNET_MODEL,
        system_prompt=curator_plan_system_prompt(),
        user_prompt=curator_plan_user_prompt(context),
        schema=CuratorPlanLLMOutput,
        route="/plan-queue",
        user_id=user_id,
        max_tokens=4096,
        request_summary={
            "active_interests": len(context["user_context"]["active_interests"]),
            "pending_queue_count": context["current_queue"]["pending_count"],
            "recent_engagements": len(
                context["recent_engagement"]["last_14_days"]
            ),
        },
    )

    items_added = 0
    items_reprioritised = 0
    items_skipped = 0

    for rec in plan.recommendations:
        try:
            if rec.action == "add":
                if rec.kind == "problem":
                    ok = _execute_add_problem(
                        supabase, anthropic, user_id=user_id, rec=rec
                    )
                elif rec.kind == "refresher":
                    ok = _execute_add_refresher(
                        supabase, user_id=user_id, rec=rec
                    )
                elif rec.kind == "paper_engagement":
                    logger.info(
                        "plan-queue: paper_engagement rec ignored "
                        "(handled by /propose-papers)"
                    )
                    ok = False
                else:
                    logger.warning(
                        "plan-queue: unknown add kind=%r — skipping", rec.kind
                    )
                    ok = False
                if ok:
                    items_added += 1
                else:
                    items_skipped += 1
            elif rec.action == "reprioritise":
                ok = _execute_reprioritise(
                    supabase, user_id=user_id, rec=rec
                )
                if ok:
                    items_reprioritised += 1
                else:
                    items_skipped += 1
        except Exception:  # noqa: BLE001
            logger.exception("plan-queue: recommendation execution failed")
            items_skipped += 1

    return PlanQueueResponse(
        recommendations_received=len(plan.recommendations),
        items_added=items_added,
        items_reprioritised=items_reprioritised,
        items_skipped=items_skipped,
        observations=plan.observations,
    )


@router.post(
    "/plan-queue",
    response_model=PlanQueueResponse,
    dependencies=[Depends(require_internal_token)],
)
def plan_queue(
    body: PlanQueueRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> PlanQueueResponse:
    return run_plan_queue(
        supabase=supabase,
        anthropic=anthropic,
        user_id=str(body.user_id),
    )


# ---------------------------------------------------------------------------
# /check-deferred (Step 3c — deterministic, no LLM)
# ---------------------------------------------------------------------------


def _is_prereq_addressed(state_row: dict[str, Any] | None) -> bool:
    """Spec §8: a prerequisite node is 'addressed' when the user's
    user_node_states row has state='comfortable' OR
    (struggle_score < 0.3 AND engagement_count >= 2)."""
    if not state_row:
        return False
    if state_row.get("state") == "comfortable":
        return True
    struggle = float(state_row.get("struggle_score") or 0.0)
    count = int(state_row.get("engagement_count") or 0)
    return struggle < 0.3 and count >= 2


def run_check_deferred(
    *, supabase: Client, user_id: str
) -> CheckDeferredResponse:
    """Service entry point. Walks all of the user's deferred queue items,
    re-queues each whose blocking prerequisites are addressed.

    Deterministic — no LLM call. Preserves `deferred_at` for analytics; the
    state transition and `updated_at` bump are the only writes."""
    deferred_resp = (
        supabase.table("queue_items")
        .select("id, kind, ref_id")
        .eq("user_id", user_id)
        .eq("state", "deferred")
        .execute()
    )
    deferred_rows = list(deferred_resp.data or [])
    if not deferred_rows:
        return CheckDeferredResponse(requeued_count=0, kept_deferred_count=0)

    # Map each deferred problem ref_id → topic_node_id.
    problem_ref_ids = [
        r["ref_id"] for r in deferred_rows
        if r.get("kind") == "problem" and r.get("ref_id")
    ]
    problem_by_id: dict[str, dict[str, Any]] = {}
    if problem_ref_ids:
        p_resp = (
            supabase.table("problems")
            .select("id, topic_node_id")
            .in_("id", problem_ref_ids)
            .execute()
        )
        problem_by_id = {p["id"]: p for p in (p_resp.data or [])}

    requeued = 0
    kept = 0

    for row in deferred_rows:
        if row.get("kind") != "problem":
            # Only problem deferrals are auto-re-queued in this pass — other
            # kinds shouldn't be in state='deferred' under the current spec.
            kept += 1
            continue
        problem = problem_by_id.get(row.get("ref_id") or "")
        if problem is None:
            kept += 1
            continue
        topic_node_id = problem.get("topic_node_id")
        if not topic_node_id:
            # Orphaned problem; nothing to check against. Re-queue defensively
            # so it doesn't sit stranded.
            _requeue(supabase, queue_item_id=row["id"])
            requeued += 1
            continue

        # Prerequisite edges into the topic.
        edges_resp = (
            supabase.table("edges")
            .select("source_node_id")
            .eq("target_node_id", str(topic_node_id))
            .eq("edge_kind", "prerequisite")
            .execute()
        )
        prereq_ids = [
            e["source_node_id"] for e in (edges_resp.data or [])
        ]
        if not prereq_ids:
            # No prerequisites mean nothing is blocking — re-queue.
            _requeue(supabase, queue_item_id=row["id"])
            requeued += 1
            continue

        # Pull this user's state for those prerequisites.
        states_resp = (
            supabase.table("user_node_states")
            .select("node_id, state, struggle_score, engagement_count")
            .eq("user_id", user_id)
            .in_("node_id", prereq_ids)
            .execute()
        )
        states_by_id = {r["node_id"]: r for r in (states_resp.data or [])}

        all_addressed = all(
            _is_prereq_addressed(states_by_id.get(pid)) for pid in prereq_ids
        )

        if all_addressed:
            _requeue(supabase, queue_item_id=row["id"])
            requeued += 1
        else:
            kept += 1

    return CheckDeferredResponse(
        requeued_count=requeued, kept_deferred_count=kept
    )


def _requeue(supabase: Client, *, queue_item_id: str) -> None:
    """Transition a deferred queue item back to 'pending' with a mid-tier
    priority. `deferred_at` is intentionally NOT cleared — it's kept for
    analytics. The next /plan-queue pass will set a final priority_score."""
    supabase.table("queue_items").update(
        {
            "state": "pending",
            "priority_score": 0.55,
            "updated_at": _now_iso(),
        }
    ).eq("id", queue_item_id).execute()


@router.post(
    "/check-deferred",
    response_model=CheckDeferredResponse,
    dependencies=[Depends(require_internal_token)],
)
def check_deferred(
    body: CheckDeferredRequest,
    supabase: Client = Depends(get_supabase_client),
) -> CheckDeferredResponse:
    return run_check_deferred(supabase=supabase, user_id=str(body.user_id))


# ---------------------------------------------------------------------------
# /run-daily-planner (Step 3d — daily cron fan-out target + cold start)
# ---------------------------------------------------------------------------


def _start_job_run(
    supabase: Client, *, user_id: str, triggered_by: str
) -> str:
    """Insert a curator_job_runs row and return its id. Falls back to a
    locally-generated UUID if the insert response is empty (older
    postgrest-py builders don't always echo `returning='representation'`)."""
    from uuid import uuid4

    resp = (
        supabase.table("curator_job_runs")
        .insert(
            {
                "user_id": user_id,
                "triggered_by": triggered_by,
                "started_at": _now_iso(),
            }
        )
        .execute()
    )
    rows = resp.data or []
    if rows and rows[0].get("id"):
        return str(rows[0]["id"])
    return str(uuid4())


def _finish_job_run(
    supabase: Client,
    *,
    job_run_id: str,
    plan_queue_status: str,
    plan_queue_items_added: int,
    plan_queue_items_reprioritised: int,
    plan_queue_items_skipped: int,
    check_deferred_requeued: int,
    check_deferred_kept: int,
    error_message: str | None,
) -> None:
    supabase.table("curator_job_runs").update(
        {
            "plan_queue_status": plan_queue_status,
            "plan_queue_items_added": plan_queue_items_added,
            "plan_queue_items_reprioritised": plan_queue_items_reprioritised,
            "plan_queue_items_skipped": plan_queue_items_skipped,
            "check_deferred_requeued": check_deferred_requeued,
            "check_deferred_kept": check_deferred_kept,
            "error_message": error_message,
            "finished_at": _now_iso(),
        }
    ).eq("id", job_run_id).execute()


def run_daily_planner(
    *,
    supabase: Client,
    anthropic: Anthropic,
    user_id: str,
    triggered_by: str,
) -> RunDailyPlannerResponse:
    """Per-user wrapper: plan-queue then check-deferred. Records the run to
    `curator_job_runs`. Partial failures are recorded in `error_message`
    rather than raised, so the cron job can see them and the next sub-call
    still runs."""
    job_run_id = _start_job_run(
        supabase, user_id=user_id, triggered_by=triggered_by
    )

    plan_queue_status = "ok"
    plan_queue_items_added = 0
    plan_queue_items_reprioritised = 0
    plan_queue_items_skipped = 0
    check_deferred_requeued = 0
    check_deferred_kept = 0
    error_message: str | None = None

    try:
        plan_resp = run_plan_queue(
            supabase=supabase, anthropic=anthropic, user_id=user_id
        )
        plan_queue_items_added = plan_resp.items_added
        plan_queue_items_reprioritised = plan_resp.items_reprioritised
        plan_queue_items_skipped = plan_resp.items_skipped
    except Exception as exc:  # noqa: BLE001
        plan_queue_status = "error"
        error_message = f"plan_queue: {exc}"
        logger.exception("run_daily_planner: plan_queue failed")

    try:
        deferred_resp = run_check_deferred(supabase=supabase, user_id=user_id)
        check_deferred_requeued = deferred_resp.requeued_count
        check_deferred_kept = deferred_resp.kept_deferred_count
    except Exception as exc:  # noqa: BLE001
        suffix = f"check_deferred: {exc}"
        error_message = f"{error_message}; {suffix}" if error_message else suffix
        logger.exception("run_daily_planner: check_deferred failed")

    _finish_job_run(
        supabase,
        job_run_id=job_run_id,
        plan_queue_status=plan_queue_status,
        plan_queue_items_added=plan_queue_items_added,
        plan_queue_items_reprioritised=plan_queue_items_reprioritised,
        plan_queue_items_skipped=plan_queue_items_skipped,
        check_deferred_requeued=check_deferred_requeued,
        check_deferred_kept=check_deferred_kept,
        error_message=error_message,
    )

    return RunDailyPlannerResponse(
        job_run_id=job_run_id,
        plan_queue_status=plan_queue_status,
        plan_queue_items_added=plan_queue_items_added,
        plan_queue_items_reprioritised=plan_queue_items_reprioritised,
        plan_queue_items_skipped=plan_queue_items_skipped,
        check_deferred_requeued=check_deferred_requeued,
        check_deferred_kept=check_deferred_kept,
        error_message=error_message,
    )


@router.post(
    "/run-daily-planner",
    response_model=RunDailyPlannerResponse,
    dependencies=[Depends(require_internal_token)],
)
def run_daily_planner_route(
    body: RunDailyPlannerRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> RunDailyPlannerResponse:
    return run_daily_planner(
        supabase=supabase,
        anthropic=anthropic,
        user_id=str(body.user_id),
        triggered_by=body.triggered_by,
    )
