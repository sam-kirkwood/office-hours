"""Refresher resolution.

A "refresher" is not a content kind — it is a *framing* applied to a concrete
queue item (problem / concept_review / paper_engagement) that was chosen for
spaced revisiting. Resolution happens once, at creation time (the curator
planner, the post-engagement prerequisite path, or an on-demand request), and
writes a directly-routable queue item with `via_refresher = true`. The daily
queue then treats it like any other item; there is no click-time resolver page.

`resolve_refresher_to_content` is the single entry point. Two ref shapes:

  (a) Legacy/deterministic — ref_id is a refresher_schedule.id whose subject is
      a prior attempt or paper engagement. Resolves to a fresh problem /
      paper_engagement queue item pointing at the same content.

  (b) Curator-style — ref_id is a nodes.id. Pool-lookup at
      (topic_node_id, intent='refresh', difficulty=1). On hit, enqueue a
      kind='problem' row pointing at the cached problem. On miss, GENERATE a
      fresh refresh-intent problem so the refresher is active-recall content
      distinct from the node's concept brief (d5). Only if generation fails do
      we fall back to a concept_review — reusing an existing non-terminal
      concept for the node rather than minting a duplicate.

Returns None when nothing resolves (unknown ref_id, or a schedule whose subject
has vanished) so callers skip creating a dead row (prevent-at-source, d18).

`POST /create-refresher` is a thin HTTP wrapper for the Next.js request route;
the in-process callers (api/routes/curator.py) call the function directly.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from anthropic_client import get_anthropic_client
from auth import require_internal_token
from routes.curator import (
    _pool_lookup_for_recommendation,
    _queue_item_already_exists,
)
from schemas import (
    CreateRefresherRequest,
    GenerateProblemRequest,
    RefresherResolveResponse,
)
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_PRIORITY = 0.55


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _insert_content_item(
    supabase: Client,
    *,
    user_id: str,
    kind: str,
    ref_id: str,
    reason: str,
    priority_score: float,
    parent_queue_item_id: str | None,
    via_refresher: bool = True,
) -> str | None:
    """Insert a concrete queue item. Returns its id (or None). `via_refresher`
    is False for groundwork items (a prerequisite on a node the user has never
    engaged — see _has_refresh_basis)."""
    insert_resp = (
        supabase.table("queue_items")
        .insert(
            {
                "user_id": user_id,
                "kind": kind,
                "ref_id": ref_id,
                "state": "pending",
                "priority_score": priority_score,
                "added_reason": reason,
                "via_refresher": via_refresher,
                "parent_queue_item_id": parent_queue_item_id,
            }
        )
        .execute()
    )
    return insert_resp.data[0]["id"] if insert_resp.data else None


# A refresher implies the user has *something to refresh*. The basis for that is
# a relationship with the node: real engagement (engagement_count > 0) or an
# explicit signal that they know it — a Stage-2 foundation marked "refresh"
# (which writes state='active'), or concept-tour familiarity (state bumped to
# 'active'/'comfortable'). Without a basis, a "refresher" is a misnomer; the
# item is surfaced as groundwork instead (Phase 10.5-rev Step 2 follow-up).
_REFRESH_BASIS_STATES = ("active", "struggling", "comfortable")


def _has_refresh_basis(supabase: Client, *, user_id: str, node_id: str) -> bool:
    resp = (
        supabase.table("user_node_states")
        .select("state, engagement_count")
        .eq("user_id", user_id)
        .eq("node_id", node_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return False
    row = resp.data[0]
    if (row.get("engagement_count") or 0) > 0:
        return True
    return row.get("state") in _REFRESH_BASIS_STATES


def _resolve_schedule(
    supabase: Client,
    *,
    user_id: str,
    ref_id: str,
    reason: str | None,
    priority_score: float,
    parent_queue_item_id: str | None,
) -> RefresherResolveResponse | None:
    """Legacy refresher_schedule path. Returns None if ref_id doesn't match a
    refresher_schedule row (so the caller falls through to the node path).

    Both subject shapes (attempt → problem, engagement → paper) get a fresh
    queue_items row pointing at the same content, framed as a refresher.
    """
    sched_resp = (
        supabase.table("refresher_schedule")
        .select("subject_kind, subject_ref_id")
        .eq("id", ref_id)
        .execute()
    )
    if not sched_resp.data:
        return None

    sched = sched_resp.data[0]
    subject_kind = sched.get("subject_kind", "")
    subject_ref_id = sched.get("subject_ref_id", "")

    if subject_kind == "attempt":
        att_resp = (
            supabase.table("attempts")
            .select("problem_id")
            .eq("id", subject_ref_id)
            .execute()
        )
        if att_resp.data and att_resp.data[0].get("problem_id"):
            new_id = _insert_content_item(
                supabase,
                user_id=user_id,
                kind="problem",
                ref_id=att_resp.data[0]["problem_id"],
                reason=reason or "Revisiting this to reinforce it.",
                priority_score=priority_score,
                parent_queue_item_id=parent_queue_item_id,
            )
            if new_id:
                return RefresherResolveResponse(kind="problem", queue_item_id=new_id)

    elif subject_kind == "engagement":
        new_id = _insert_content_item(
            supabase,
            user_id=user_id,
            kind="paper_engagement",
            ref_id=subject_ref_id,
            reason=reason or "Revisiting this paper to reinforce it.",
            priority_score=priority_score,
            parent_queue_item_id=parent_queue_item_id,
        )
        if new_id:
            return RefresherResolveResponse(
                kind="paper_engagement", queue_item_id=new_id
            )

    return None


def _existing_concept_review(
    supabase: Client, *, user_id: str, node_id: str
) -> str | None:
    """Return the id of a non-terminal concept_review queue item the user
    already has for this node, or None. Used so the concept fallback reuses an
    existing card instead of minting a duplicate brief (d5)."""
    resp = (
        supabase.table("queue_items")
        .select("id")
        .eq("user_id", user_id)
        .eq("kind", "concept_review")
        .eq("ref_id", node_id)
        .in_("state", ["pending", "surfaced"])
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0]["id"] if rows else None


def _enqueue_concept_fallback(
    supabase: Client,
    *,
    user_id: str,
    node_id: str,
    reason: str | None,
    priority_score: float,
    parent_queue_item_id: str | None,
    via_refresher: bool = True,
) -> RefresherResolveResponse:
    """Land the user on the node's concept brief. Reuses an existing non-terminal
    concept_review for the node if one exists. `via_refresher=False` is used for
    groundwork (a node the user has never engaged), so the card reads as a plain
    Concept rather than a Refresher."""
    existing = _existing_concept_review(supabase, user_id=user_id, node_id=node_id)
    if existing is not None:
        return RefresherResolveResponse(kind="concept_review", queue_item_id=existing)

    new_id = _insert_content_item(
        supabase,
        user_id=user_id,
        kind="concept_review",
        ref_id=node_id,
        reason=reason or "A short read to refresh this topic.",
        priority_score=priority_score,
        parent_queue_item_id=parent_queue_item_id,
        via_refresher=via_refresher,
    )
    if not new_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to enqueue refresher concept_review row",
        )
    return RefresherResolveResponse(kind="concept_review", queue_item_id=new_id)


def _resolve_curator_node(
    supabase: Client,
    anthropic: Anthropic,
    *,
    user_id: str,
    node_id: str,
    reason: str | None,
    priority_score: float,
    parent_queue_item_id: str | None,
) -> RefresherResolveResponse | None:
    """Curator-style refresher: ref_id is a node. Pool-lookup a refresh-intent
    problem; on miss, generate one; only on generation failure fall back to a
    concept_review on the same node. Returns None if ref_id is not a node."""
    node_resp = (
        supabase.table("nodes")
        .select("id, title")
        .eq("id", node_id)
        .limit(1)
        .execute()
    )
    if not node_resp.data:
        return None

    # A refresher needs a basis — the user must have engaged this node or told
    # us they know it. Without one, this is a prerequisite they haven't met, so
    # surface honest groundwork (an orientation read) rather than a "Refresher /
    # look at this again" card on something they've never seen. The reason copy
    # is left as the curator authored it (it explains why the groundwork helps);
    # only the framing changes (via_refresher=False → Concept badge).
    if not _has_refresh_basis(supabase, user_id=user_id, node_id=node_id):
        return _enqueue_concept_fallback(
            supabase,
            user_id=user_id,
            node_id=node_id,
            reason=reason or "Worth getting solid before the topics that build on it.",
            priority_score=priority_score,
            parent_queue_item_id=parent_queue_item_id,
            via_refresher=False,
        )

    cached_problem_id = _pool_lookup_for_recommendation(
        supabase,
        topic_node_id=node_id,
        difficulty=1,
        intent="refresh",
        subtopic_slug=None,
    )

    if cached_problem_id is not None:
        # Don't stack a second refresher pointing at the same pooled problem.
        if _queue_item_already_exists(
            supabase, user_id=user_id, kind="problem", ref_id=cached_problem_id
        ):
            return _enqueue_concept_fallback(
                supabase,
                user_id=user_id,
                node_id=node_id,
                reason=reason,
                priority_score=priority_score,
                parent_queue_item_id=parent_queue_item_id,
            )
        new_id = _insert_content_item(
            supabase,
            user_id=user_id,
            kind="problem",
            ref_id=cached_problem_id,
            reason=reason or "A refresher problem picked from the pool.",
            priority_score=priority_score,
            parent_queue_item_id=parent_queue_item_id,
        )
        if not new_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="failed to enqueue refresher problem row",
            )
        return RefresherResolveResponse(kind="problem", queue_item_id=new_id)

    # Pool miss → generate a fresh refresh-intent problem. /generate-problem
    # writes its own queue_items row (kind='problem', state='pending'); we then
    # stamp it with the refresher framing. This keeps the refresher distinct
    # from the node's concept brief (d5).
    from routes.generate_problem import generate_problem  # local import: cycles

    try:
        gen_resp = generate_problem(
            body=GenerateProblemRequest(
                user_id=user_id, node_id=node_id, intent="refresh"
            ),
            supabase=supabase,
            anthropic=anthropic,
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "create-refresher: generate-problem failed for node=%s — "
            "falling back to concept brief",
            node_id,
        )
        return _enqueue_concept_fallback(
            supabase,
            user_id=user_id,
            node_id=node_id,
            reason=reason,
            priority_score=priority_score,
            parent_queue_item_id=parent_queue_item_id,
        )

    supabase.table("queue_items").update(
        {
            "added_reason": reason or "A refresher problem to bring this back.",
            "priority_score": priority_score,
            "via_refresher": True,
            "parent_queue_item_id": parent_queue_item_id,
            "updated_at": _now_iso(),
        }
    ).eq("id", str(gen_resp.queue_item_id)).execute()
    return RefresherResolveResponse(
        kind="problem", queue_item_id=str(gen_resp.queue_item_id)
    )


def resolve_refresher_to_content(
    supabase: Client,
    anthropic: Anthropic,
    *,
    user_id: str,
    ref_id: str,
    reason: str | None = None,
    priority_score: float = DEFAULT_PRIORITY,
    parent_queue_item_id: str | None = None,
) -> RefresherResolveResponse | None:
    """Resolve a refresher reference (a refresher_schedule.id or a nodes.id) to
    a concrete, directly-routable queue item with via_refresher=true.

    Returns None when nothing resolves so callers can skip creating a dead row.
    """
    resolved = _resolve_schedule(
        supabase,
        user_id=user_id,
        ref_id=ref_id,
        reason=reason,
        priority_score=priority_score,
        parent_queue_item_id=parent_queue_item_id,
    )
    if resolved is not None:
        return resolved
    return _resolve_curator_node(
        supabase,
        anthropic,
        user_id=user_id,
        node_id=ref_id,
        reason=reason,
        priority_score=priority_score,
        parent_queue_item_id=parent_queue_item_id,
    )


@router.post(
    "/create-refresher",
    response_model=RefresherResolveResponse,
    dependencies=[Depends(require_internal_token)],
)
def create_refresher(
    body: CreateRefresherRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> RefresherResolveResponse:
    """HTTP wrapper over resolve_refresher_to_content for the Next.js request
    route (on-demand refreshers triggered from a paper or the skill tree)."""
    resolved = resolve_refresher_to_content(
        supabase,
        anthropic,
        user_id=str(body.user_id),
        ref_id=str(body.ref_id),
        reason=body.reason,
        priority_score=body.priority_score
        if body.priority_score is not None
        else DEFAULT_PRIORITY,
        parent_queue_item_id=(
            str(body.parent_queue_item_id) if body.parent_queue_item_id else None
        ),
    )
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="refresher ref_id resolves to neither a refresher_schedule nor a node",
        )
    return resolved
