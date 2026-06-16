"""POST /surface-daily — deterministic daily surfacing (no LLM call).

Picks up to 3 varied items from the user's pending queue and writes a
surfaced_picks row. Selection rules (from phase-4-rev-plan.md §Step 8):

  1. Pre-include any pinned items that survived a reroll (state='surfaced'
     AND pinned=true). They hold their slots across rerolls (§A6).
  2. Fetch all queue_items for user with state='pending', order by priority_score
     desc. Apply any steering constraint (§A5) to re-rank/filter.
  3. F17 fallback: if no pending AND no pinned, insert one concept_review
     pointing to the foundation node closest to the user's interests (or
     calculus-i). Re-query pending.
  4. Pick remaining slots (MAX_SURFACED − pinned_count) with kind variety,
     skipping ref_ids already claimed by pinned items.
  5. Mark only the newly-picked pending items state='surfaced' (pinned items
     are already surfaced).
  6. Write surfaced_picks row for all items (pinned + new picks).

Refreshers are not a content kind here: they are concrete problem /
concept_review / paper_engagement items carrying via_refresher=true (resolved
at creation time, see api/routes/refresher.py). The flag is passed through to
the client so the daily card shows the "Refresher" framing while routing by the
item's real kind.
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

# §A5 "shorter" threshold: items with time_estimate_minutes_high at or below
# this value are considered "short." Adjust here if the target shifts.
_SHORT_MINUTES = 20


def _user_has_no_queue_items(supabase: Client, user_id: str) -> bool:
    """True iff the user has no queue_items rows at all (any state).

    Gate for the F17 starter fallback: it may only seed a concept for a
    genuinely empty account (brand-new, or a cold-start whose planner produced
    nothing). Because inserting one row makes the total non-zero, the fallback
    can fire at most once and can never re-mint the same concept on every empty
    surface (the d16 duplicate-spam root cause). Normal restocking is the
    planner + refill-on-drain path — see curriculum-curator-design §11.4.
    """
    resp = (
        supabase.table("queue_items")
        .select("id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return not (resp.data or [])


def _load_pending(supabase: Client, user_id: str) -> list[dict]:
    resp = (
        supabase.table("queue_items")
        .select(
            "id, kind, ref_id, state, priority_score, "
            "time_estimate_minutes_low, time_estimate_minutes_high, added_reason, "
            "via_refresher, pinned"
        )
        .eq("user_id", user_id)
        .eq("state", "pending")
        .order("priority_score", desc=True)
        .execute()
    )
    return resp.data or []


def _load_pinned_surfaced(supabase: Client, user_id: str) -> list[dict]:
    """Return pinned items that are already surfaced.

    These survive rerolls: the reroll route does NOT reset them to pending.
    surface_daily pre-includes them so they always appear in the pick,
    overriding the variety constraint (§A6).

    The post-execute guard (item.get("pinned")) is belt+suspenders: the DB
    filters correctly, but the test fake doesn't enforce filter predicates, so
    we guard explicitly so old tests that return pending items don't pollute
    the pinned set.
    """
    resp = (
        supabase.table("queue_items")
        .select(
            "id, kind, ref_id, state, priority_score, "
            "time_estimate_minutes_low, time_estimate_minutes_high, added_reason, "
            "via_refresher, pinned"
        )
        .eq("user_id", user_id)
        .eq("state", "surfaced")
        .eq("pinned", True)
        .order("priority_score", desc=True)
        .execute()
    )
    return [item for item in (resp.data or []) if item.get("pinned")]


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


def _apply_steer(
    items: list[dict],
    *,
    steer: str | None,
    steer_excluded_ref_ids: set[str] | None,
    steer_topic_problem_ids: set[str] | None,
) -> list[dict]:
    """Apply a §A5 steering hint to the pending pool.

    All filters are best-effort: if filtering leaves fewer than 1 item we
    fall back to the full pool so the user is never left with nothing.
    """
    if not steer or not items:
        return items

    if steer == "shorter":
        short = [
            i for i in items
            if i.get("time_estimate_minutes_high") is not None
            and i["time_estimate_minutes_high"] <= _SHORT_MINUTES
        ]
        return short if short else items

    if steer == "more_papers":
        # Stable-sort: paper_engagement items first, then original priority order.
        papers = [i for i in items if i["kind"] == "paper_engagement"]
        others = [i for i in items if i["kind"] != "paper_engagement"]
        return papers + others

    if steer == "different":
        excluded = steer_excluded_ref_ids or set()
        filtered = [i for i in items if i.get("ref_id") not in excluded]
        return filtered if filtered else items

    if steer == "less_topic":
        excluded = steer_topic_problem_ids or set()
        filtered = [i for i in items if i.get("ref_id") not in excluded]
        return filtered if filtered else items

    return items


def _pick_varied(
    items: list[dict],
    already_picked_ref_ids: set[str] | None = None,
    max_count: int = MAX_SURFACED,
) -> list[dict]:
    """Choose up to max_count items, preferring kind variety and never
    picking two items with the same ref_id.

    already_picked_ref_ids seeds the dedup set so callers can pre-commit
    ref_ids from pinned items (§A6) without those items being picked again.

    Strategy: greedily take the highest-priority item from each kind in
    round-robin order, skipping any item whose ref_id is already in the
    picked set. Two queue items pointing at the same problem (curator dup
    that slipped through the dedup at /plan-queue time) only contribute
    one slot to the daily three (Phase 10-rev §9a).
    """
    if not items or max_count <= 0:
        return []

    by_kind: dict[str, list[dict]] = {}
    for item in items:
        by_kind.setdefault(item["kind"], []).append(item)

    picked: list[dict] = []
    picked_ref_ids: set[str] = set(already_picked_ref_ids or [])
    kinds = list(by_kind.keys())
    kind_idx = 0
    # Guard against infinite loop if every remaining item duplicates an
    # already-picked ref_id: track whether the last full round made progress.
    rounds_without_progress = 0
    while len(picked) < max_count and any(by_kind.values()):
        kind = kinds[kind_idx % len(kinds)]
        bucket = by_kind.get(kind, [])
        progressed = False
        while bucket:
            candidate = bucket.pop(0)
            ref_id = candidate.get("ref_id")
            if ref_id and ref_id in picked_ref_ids:
                continue
            picked.append(candidate)
            if ref_id:
                picked_ref_ids.add(ref_id)
            progressed = True
            break
        if progressed:
            rounds_without_progress = 0
        else:
            rounds_without_progress += 1
            if rounds_without_progress >= len(kinds):
                break
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

    # 0. Pre-include pinned items that survived the last reroll (§A6).
    #    They stay state='surfaced' through rerolls and claim their slots first,
    #    overriding the variety constraint.
    pinned_items = _load_pinned_surfaced(supabase, user_id)
    pinned_ref_ids: set[str] = {
        p["ref_id"] for p in pinned_items if p.get("ref_id")
    }
    slots_remaining = max(0, MAX_SURFACED - len(pinned_items))

    # 1. Fetch all pending queue items ordered by priority.
    pending = _load_pending(supabase, user_id)

    # 2. F17 fallback: seed ONE starter concept — only for a genuinely empty
    #    account. See _user_has_no_queue_items for why this guard matters
    #    (it's the fix for the d16 duplicate-concept spam).
    if not pending and not pinned_items and _user_has_no_queue_items(supabase, user_id):
        foundation = _closest_foundation(supabase, user_id)
        if foundation and foundation.get("id"):
            logger.info(
                "F17 fallback: no queue items for user=%s; seeding starter "
                "concept_review for node=%s",
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
                    "added_reason": (
                        "A quick read to get you started while we build out "
                        "the rest of your queue."
                    ),
                    "time_estimate_minutes_low": 5,
                    "time_estimate_minutes_high": 15,
                }
            ).execute()
            pending = _load_pending(supabase, user_id)

    if not pending and not pinned_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no pending queue items for user",
        )

    # 3. Apply steering filter if requested (§A5). Best-effort; falls back to
    #    the full pool if filtering drains it.
    steer_topic_problem_ids: set[str] | None = None
    if body.steer == "less_topic" and body.steer_topic_node_id:
        prob_resp = (
            supabase.table("problems")
            .select("id")
            .eq("topic_node_id", str(body.steer_topic_node_id))
            .execute()
        )
        steer_topic_problem_ids = {p["id"] for p in (prob_resp.data or [])}

    steer_excluded_ref_ids: set[str] | None = (
        {str(r) for r in body.steer_excluded_ref_ids}
        if body.steer_excluded_ref_ids
        else None
    )

    steered_pending = _apply_steer(
        pending,
        steer=body.steer,
        steer_excluded_ref_ids=steer_excluded_ref_ids,
        steer_topic_problem_ids=steer_topic_problem_ids,
    )

    # 4. Pick remaining slots from the (possibly steered) pending pool.
    new_picks = _pick_varied(
        steered_pending,
        already_picked_ref_ids=pinned_ref_ids,
        max_count=slots_remaining,
    )

    # 5. Mark only newly-picked items as 'surfaced' (pinned items are already
    #    surfaced and must not be touched — they belong to the previous pick row).
    new_pick_ids = [item["id"] for item in new_picks]
    for item_id in new_pick_ids:
        supabase.table("queue_items").update({"state": "surfaced"}).eq("id", item_id).execute()

    # 6. Write surfaced_picks row for all items (pinned first for clarity).
    all_picked = pinned_items + new_picks
    all_picked_ids = [item["id"] for item in all_picked]
    pick_resp = (
        supabase.table("surfaced_picks")
        .insert({"user_id": user_id, "queue_item_ids": all_picked_ids})
        .execute()
    )
    pick_id = pick_resp.data[0]["id"]

    items = [
        SurfacedItem(
            queue_item_id=UUID(item["id"]),
            kind=item["kind"],
            ref_id=UUID(item["ref_id"]) if item.get("ref_id") else None,
            added_reason=item.get("added_reason"),
            time_estimate_minutes_low=item.get("time_estimate_minutes_low"),
            time_estimate_minutes_high=item.get("time_estimate_minutes_high"),
            via_refresher=bool(item.get("via_refresher")),
            pinned=bool(item.get("pinned")),
        )
        for item in all_picked
    ]

    # Pending items left after this pick (everything in `pending` minus the new
    # picks we just flipped to 'surfaced'). Drives refill-on-drain in the web
    # layer. Pinned items are already surfaced so they don't count against pending.
    pending_remaining = max(0, len(pending) - len(new_picks))

    return SurfaceDailyResponse(
        pick_id=UUID(pick_id), items=items, pending_remaining=pending_remaining
    )
