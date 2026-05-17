"""POST /surface-daily — deterministic daily surfacing (no LLM call).

Picks up to 3 varied items from the user's pending queue and writes a
surfaced_picks row. Selection rules (from phase-4-rev-plan.md §Step 8):

  1. Fetch all queue_items for user with state='pending', order by priority_score desc.
  2. F17 fallback: if queue is empty, insert one concept_review pointing to the
     foundation node closest to the user's interests (or calculus-i). Re-query.
  3. Pick at most 3, trying to vary kind.
  4. Fewer than 3 available → surface what exists (length ≤ 3 accepted per F8).
  5. Mark selected items state='surfaced'. Write surfaced_picks.
  6. For refresher items, resolve content title and original queue_item_id.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from auth import require_internal_token
from schemas import SurfaceDailyRequest, SurfaceDailyResponse, SurfacedItem
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_SURFACED = 3


def _resolve_refresher_content(
    supabase: Client, item: dict
) -> tuple[str, str | None, str | None]:
    """Return (added_reason, subject_kind, subject_queue_item_id) for a refresher item.

    Resolves the refresher_schedule row to content title and the original
    queue_item_id so the client can construct a back-link.
    """
    ref_id = item.get("ref_id")
    if not ref_id:
        return "Time to revisit something you've worked on.", None, None

    sched_resp = (
        supabase.table("refresher_schedule")
        .select("subject_kind, subject_ref_id")
        .eq("id", ref_id)
        .execute()
    )
    if not sched_resp.data:
        return "Time to revisit something you've worked on.", None, None

    sched = sched_resp.data[0]
    subject_kind: str = sched.get("subject_kind", "")
    subject_ref_id: str = sched.get("subject_ref_id", "")

    if subject_kind == "attempt":
        att_resp = (
            supabase.table("attempts")
            .select("problem_id, queue_item_id")
            .eq("id", subject_ref_id)
            .execute()
        )
        if not att_resp.data:
            return "Time to revisit a problem.", "attempt", None
        att = att_resp.data[0]
        prob_resp = (
            supabase.table("problems")
            .select("topic_node_id")
            .eq("id", att.get("problem_id", ""))
            .execute()
        )
        if prob_resp.data:
            node_resp = (
                supabase.table("nodes")
                .select("title")
                .eq("id", prob_resp.data[0].get("topic_node_id", ""))
                .execute()
            )
            title = node_resp.data[0]["title"] if node_resp.data else "this topic"
        else:
            title = "this topic"
        return (
            f"A refresher on {title}.",
            "attempt",
            att.get("queue_item_id"),
        )

    elif subject_kind == "engagement":
        eng_resp = (
            supabase.table("paper_engagements")
            .select("paper_id")
            .eq("id", subject_ref_id)
            .execute()
        )
        if not eng_resp.data:
            return "Time to revisit a paper.", "engagement", None
        paper_resp = (
            supabase.table("papers")
            .select("title")
            .eq("id", eng_resp.data[0].get("paper_id", ""))
            .execute()
        )
        title = paper_resp.data[0]["title"] if paper_resp.data else "this paper"
        # Look up the original queue item for the engagement
        qi_resp = (
            supabase.table("queue_items")
            .select("id")
            .eq("kind", "paper_engagement")
            .eq("ref_id", subject_ref_id)
            .limit(1)
            .execute()
        )
        orig_qi_id = qi_resp.data[0]["id"] if qi_resp.data else None
        return f"A refresher on {title}.", "engagement", orig_qi_id

    return "Time to revisit something you've worked on.", subject_kind or None, None


def _load_pending(supabase: Client, user_id: str) -> list[dict]:
    resp = (
        supabase.table("queue_items")
        .select(
            "id, kind, ref_id, state, priority_score, "
            "time_estimate_minutes_low, time_estimate_minutes_high, added_reason"
        )
        .eq("user_id", user_id)
        .eq("state", "pending")
        .order("priority_score", desc=True)
        .execute()
    )
    return resp.data or []


def _closest_foundation(supabase: Client, user_id: str) -> dict | None:
    """Find the foundation node most relevant to the user's interests.

    Falls back to calculus-i slug, then any foundation node.
    Returns None if no foundation nodes exist (shouldn't happen post-seed).
    """
    interests_resp = (
        supabase.table("user_interests")
        .select("node_id")
        .eq("user_id", user_id)
        .execute()
    )
    node_ids = [ui["node_id"] for ui in (interests_resp.data or [])]

    if node_ids:
        interest_nodes_resp = (
            supabase.table("nodes")
            .select("title")
            .in_("id", node_ids)
            .execute()
        )
        for n in interest_nodes_resp.data or []:
            keyword = n["title"].split()[0]
            found = (
                supabase.table("nodes")
                .select("id, title")
                .eq("kind", "foundation")
                .ilike("title", f"%{keyword}%")
                .limit(1)
                .execute()
            )
            if found.data:
                return found.data[0]

    # Fall back to the calculus-i foundation node
    fallback = (
        supabase.table("nodes")
        .select("id, title")
        .eq("slug", "calculus-i")
        .limit(1)
        .execute()
    )
    if fallback.data:
        return fallback.data[0]

    # Last resort: any foundation node
    any_node = (
        supabase.table("nodes")
        .select("id, title")
        .eq("kind", "foundation")
        .limit(1)
        .execute()
    )
    return any_node.data[0] if any_node.data else None


def _pick_varied(items: list[dict]) -> list[dict]:
    """Choose up to MAX_SURFACED items, preferring kind variety.

    Strategy: greedily take the highest-priority item from each kind in round-
    robin order, then fill remaining slots from whatever is left.
    """
    if not items:
        return []
    if len(items) <= MAX_SURFACED:
        return items

    by_kind: dict[str, list[dict]] = {}
    for item in items:
        by_kind.setdefault(item["kind"], []).append(item)

    picked: list[dict] = []
    kinds = list(by_kind.keys())
    kind_idx = 0
    while len(picked) < MAX_SURFACED and any(by_kind.values()):
        kind = kinds[kind_idx % len(kinds)]
        if by_kind.get(kind):
            picked.append(by_kind[kind].pop(0))
        kind_idx += 1

    return picked


@router.post(
    "/surface-daily",
    response_model=SurfaceDailyResponse,
    dependencies=[Depends(require_internal_token)],
)
def surface_daily(
    body: SurfaceDailyRequest,
    supabase: Client = Depends(get_supabase_client),
) -> SurfaceDailyResponse:
    user_id = str(body.user_id)

    # 1. Fetch all pending queue items ordered by priority.
    pending = _load_pending(supabase, user_id)

    # 2. F17 fallback: empty queue → insert one concept_review starter item.
    if not pending:
        foundation = _closest_foundation(supabase, user_id)
        if foundation and foundation.get("id"):
            logger.info(
                "F17 fallback: empty queue for user=%s; inserting concept_review for node=%s",
                user_id,
                foundation["id"],
            )
            supabase.table("queue_items").insert(
                {
                    "user_id": user_id,
                    "kind": "concept_review",
                    "ref_id": foundation["id"],
                    "state": "pending",
                    "priority_score": 0.3,
                    "added_reason": "A starting point while your queue is being built.",
                    "time_estimate_minutes_low": 5,
                    "time_estimate_minutes_high": 15,
                }
            ).execute()
            pending = _load_pending(supabase, user_id)

    if not pending:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no pending queue items for user",
        )

    # 3. Pick up to 3 with kind variety.
    picked = _pick_varied(pending)

    # 4. Mark picked items as 'surfaced'.
    picked_ids = [item["id"] for item in picked]
    for item_id in picked_ids:
        supabase.table("queue_items").update({"state": "surfaced"}).eq("id", item_id).execute()

    # 5. Write surfaced_picks row.
    pick_resp = (
        supabase.table("surfaced_picks")
        .insert({"user_id": user_id, "queue_item_ids": picked_ids})
        .execute()
    )
    pick_id = pick_resp.data[0]["id"]

    items = []
    for item in picked:
        subject_kind: str | None = None
        subject_queue_item_id: str | None = None
        added_reason = item.get("added_reason")

        if item["kind"] == "refresher" and item.get("ref_id"):
            added_reason, subject_kind, subject_queue_item_id = _resolve_refresher_content(
                supabase, item
            )

        items.append(
            SurfacedItem(
                queue_item_id=UUID(item["id"]),
                kind=item["kind"],
                ref_id=UUID(item["ref_id"]) if item.get("ref_id") else None,
                added_reason=added_reason,
                time_estimate_minutes_low=item.get("time_estimate_minutes_low"),
                time_estimate_minutes_high=item.get("time_estimate_minutes_high"),
                subject_kind=subject_kind,
                subject_queue_item_id=UUID(subject_queue_item_id) if subject_queue_item_id else None,
            )
        )

    return SurfaceDailyResponse(pick_id=UUID(pick_id), items=items)
