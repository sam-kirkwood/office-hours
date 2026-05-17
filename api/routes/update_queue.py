"""POST /update-queue — Phase 7-rev steps 3 & 4.

Recomputes priority scores for all pending/surfaced queue items, schedules
refreshers for notebook entries older than 10 days, inserts queue items for
due refresher_schedule rows, prunes old done/dismissed items, and recomputes
user_node_states for the node touched by the triggering engagement.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from supabase import Client

from auth import require_internal_token
from schemas import UpdateQueueRequest, UpdateQueueResponse
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()

_THRESHOLDS = {
    "to_active": {"min_engagements": 1},
    "to_struggling": {"min_engagements": 2, "min_struggle": 0.6},
    "to_comfortable": {"min_engagements": 3, "max_struggle": 0.2},
    "struggling_to_comfortable": {"min_engagements": 5, "max_struggle": 0.2},
}


def _recompute_node_state(supabase: Client, user_id: str, node_id: str) -> None:
    """Recompute struggle_score and state for one user/node after a problem attempt.

    Two-step join: problems for node → attempts for those problems (last 5).
    """
    now_str = datetime.now(timezone.utc).isoformat()

    # 1. Load problem IDs for this node
    prob_ids_resp = (
        supabase.table("problems")
        .select("id")
        .eq("topic_node_id", node_id)
        .execute()
    )
    problem_ids = [p["id"] for p in (prob_ids_resp.data or [])]

    # 2. Load last 5 attempts for this user/node
    attempts: list[dict] = []
    if problem_ids:
        att_resp = (
            supabase.table("attempts")
            .select("hint_levels_used")
            .eq("user_id", user_id)
            .in_("problem_id", problem_ids)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        attempts = att_resp.data or []

    # 3. Compute struggle_score: fraction of attempts where hints were used
    if attempts:
        struggle_score = sum(
            1 for a in attempts if a.get("hint_levels_used")
        ) / len(attempts)
    else:
        struggle_score = 0.0

    # 4. Load current state
    ns_resp = (
        supabase.table("user_node_states")
        .select("state, engagement_count")
        .eq("user_id", user_id)
        .eq("node_id", node_id)
        .execute()
    )
    current = (ns_resp.data or [{}])[0]
    current_state: str = current.get("state") or "unseen"
    engagement_count: int = (current.get("engagement_count") or 0) + 1

    # 5. Apply transition table
    new_state = current_state
    if current_state in ("bookmarked", "comfortable"):
        pass  # bookmarked is never auto-cleared; comfortable never auto-regresses
    elif current_state == "unseen":
        if engagement_count >= _THRESHOLDS["to_active"]["min_engagements"]:
            new_state = "active"
    elif current_state == "active":
        t_str = _THRESHOLDS["to_struggling"]
        t_com = _THRESHOLDS["to_comfortable"]
        if struggle_score >= t_str["min_struggle"] and engagement_count >= t_str["min_engagements"]:
            new_state = "struggling"
        elif struggle_score <= t_com["max_struggle"] and engagement_count >= t_com["min_engagements"]:
            new_state = "comfortable"
    elif current_state == "struggling":
        t = _THRESHOLDS["struggling_to_comfortable"]
        if struggle_score <= t["max_struggle"] and engagement_count >= t["min_engagements"]:
            new_state = "comfortable"

    # 6. Upsert user_node_states
    (
        supabase.table("user_node_states")
        .upsert(
            {
                "user_id": user_id,
                "node_id": node_id,
                "struggle_score": struggle_score,
                "state": new_state,
                "engagement_count": engagement_count,
                "last_engaged_at": now_str,
            },
            on_conflict="user_id,node_id",
        )
        .execute()
    )

_BASE_SCORES: dict[str, float] = {
    "problem": 0.5,
    "paper_engagement": 0.4,
    "refresher": 0.9,
    "concept_review": 0.3,
    "suggested_interest": 0.2,
}


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _user_tz(supabase: Client, user_id: str) -> timezone:
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # noqa: PLC0415
    except ImportError:
        return timezone.utc

    resp = (
        supabase.table("profiles")
        .select("timezone")
        .eq("id", user_id)
        .execute()
    )
    tz_str = (resp.data or [{}])[0].get("timezone") if resp.data else None
    if not tz_str:
        return timezone.utc
    try:
        return ZoneInfo(tz_str)  # type: ignore[return-value]
    except (ZoneInfoNotFoundError, KeyError):
        return timezone.utc


@router.post(
    "/update-queue",
    response_model=UpdateQueueResponse,
    dependencies=[Depends(require_internal_token)],
)
def update_queue(
    body: UpdateQueueRequest,
    supabase: Client = Depends(get_supabase_client),
) -> UpdateQueueResponse:
    user_id = str(body.user_id)
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()

    # ------------------------------------------------------------------
    # 2. Load active queue items
    # ------------------------------------------------------------------
    items_resp = (
        supabase.table("queue_items")
        .select("id, kind, ref_id, priority_score, state, updated_at")
        .eq("user_id", user_id)
        .in_("state", ["pending", "surfaced"])
        .execute()
    )
    active_items: list[dict] = items_resp.data or []

    # ------------------------------------------------------------------
    # 3. Priority reweight
    # ------------------------------------------------------------------
    items_reweighted = 0

    for item in active_items:
        kind = item["kind"]
        base = _BASE_SCORES.get(kind, 0.5)
        boost = 0.0
        node_state: str | None = None

        if kind == "problem" and item.get("ref_id"):
            prob_resp = (
                supabase.table("problems")
                .select("topic_node_id")
                .eq("id", item["ref_id"])
                .execute()
            )
            if prob_resp.data:
                node_id = prob_resp.data[0]["topic_node_id"]
                ns_resp = (
                    supabase.table("user_node_states")
                    .select("state")
                    .eq("user_id", user_id)
                    .eq("node_id", node_id)
                    .execute()
                )
                if ns_resp.data:
                    node_state = ns_resp.data[0]["state"]

        elif kind in ("concept_review", "suggested_interest") and item.get("ref_id"):
            ns_resp = (
                supabase.table("user_node_states")
                .select("state")
                .eq("user_id", user_id)
                .eq("node_id", item["ref_id"])
                .execute()
            )
            if ns_resp.data:
                node_state = ns_resp.data[0]["state"]

        elif kind == "refresher" and item.get("ref_id"):
            rs_resp = (
                supabase.table("refresher_schedule")
                .select("due_at")
                .eq("id", item["ref_id"])
                .execute()
            )
            if rs_resp.data:
                due_at = _parse_ts(rs_resp.data[0]["due_at"])
                days_overdue = max(0, (now - due_at).days)
                boost += min(days_overdue * 0.05, 0.4)

        if node_state == "struggling" and kind == "problem":
            boost += 0.2
        elif node_state == "comfortable" and kind != "refresher":
            boost -= 0.1

        new_score = round(base + boost, 4)
        (
            supabase.table("queue_items")
            .update({"priority_score": new_score, "updated_at": now_str})
            .eq("id", item["id"])
            .execute()
        )
        items_reweighted += 1

    # ------------------------------------------------------------------
    # 4. Schedule refreshers
    # ------------------------------------------------------------------
    refreshers_scheduled = 0

    entries_resp = (
        supabase.table("notebook_entries")
        .select("id, entry_kind, ref_id, created_at")
        .eq("user_id", user_id)
        .execute()
    )
    entries: list[dict] = entries_resp.data or []

    schedule_resp = (
        supabase.table("refresher_schedule")
        .select("subject_ref_id")
        .eq("user_id", user_id)
        .execute()
    )
    scheduled_ref_ids: set[str] = {row["subject_ref_id"] for row in (schedule_resp.data or [])}

    tz = _user_tz(supabase, user_id)
    ten_days_ago = now - timedelta(days=10)

    for entry in entries:
        ref_id = entry.get("ref_id")
        if not ref_id:
            continue

        created_at_str = entry.get("created_at", "")
        try:
            created_at = _parse_ts(created_at_str)
        except (ValueError, AttributeError):
            continue

        if created_at > ten_days_ago:
            continue

        if ref_id in scheduled_ref_ids:
            continue

        entry_kind = entry.get("entry_kind", "problem_attempt")
        if entry_kind == "problem_attempt":
            subject_kind = "attempt"
            days_until_due = 14
        else:
            subject_kind = "engagement"
            days_until_due = 21

        due_dt = created_at + timedelta(days=days_until_due)
        due_at = due_dt.astimezone(tz).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).astimezone(timezone.utc)

        (
            supabase.table("refresher_schedule")
            .insert({
                "user_id": user_id,
                "subject_kind": subject_kind,
                "subject_ref_id": ref_id,
                "due_at": due_at.isoformat(),
            })
            .execute()
        )
        refreshers_scheduled += 1
        scheduled_ref_ids.add(ref_id)

    # ------------------------------------------------------------------
    # 5. Insert queue items for due refresher_schedule rows
    # ------------------------------------------------------------------
    due_schedules_resp = (
        supabase.table("refresher_schedule")
        .select("id, subject_kind, due_at")
        .eq("user_id", user_id)
        .is_("surfaced_at", None)
        .execute()
    )
    due_schedules = [
        s for s in (due_schedules_resp.data or [])
        if _parse_ts(s["due_at"]) <= now
    ]

    if due_schedules:
        existing_resp = (
            supabase.table("queue_items")
            .select("ref_id")
            .eq("user_id", user_id)
            .eq("kind", "refresher")
            .in_("state", ["pending", "surfaced"])
            .execute()
        )
        existing_refresher_ref_ids: set[str] = {
            row["ref_id"] for row in (existing_resp.data or [])
        }

        for sched in due_schedules:
            sched_id = sched["id"]
            if sched_id in existing_refresher_ref_ids:
                continue

            subject_kind = sched["subject_kind"]
            (
                supabase.table("queue_items")
                .insert({
                    "user_id": user_id,
                    "kind": "refresher",
                    "ref_id": sched_id,
                    "state": "pending",
                    "priority_score": 0.9,
                    "added_reason": f"Run through this again to reinforce it.",
                    "time_estimate_minutes_low": 10,
                    "time_estimate_minutes_high": 30,
                })
                .execute()
            )
            (
                supabase.table("refresher_schedule")
                .update({"surfaced_at": now_str})
                .eq("id", sched_id)
                .execute()
            )

    # ------------------------------------------------------------------
    # 6. Prune done/dismissed items older than 30 days
    # ------------------------------------------------------------------
    items_pruned = 0
    cutoff = (now - timedelta(days=30)).isoformat()

    prune_resp = (
        supabase.table("queue_items")
        .delete()
        .eq("user_id", user_id)
        .in_("state", ["done", "dismissed"])
        .lt("updated_at", cutoff)
        .execute()
    )
    items_pruned += len(prune_resp.data or [])

    # Dedup pending items: same (kind, ref_id), keep highest priority_score
    pending_resp = (
        supabase.table("queue_items")
        .select("id, kind, ref_id, priority_score")
        .eq("user_id", user_id)
        .eq("state", "pending")
        .execute()
    )
    pending_items: list[dict] = pending_resp.data or []

    seen: dict[tuple, dict] = {}
    dupes: list[str] = []
    for item in pending_items:
        key = (item["kind"], item.get("ref_id"))
        if key not in seen:
            seen[key] = item
        else:
            existing = seen[key]
            if (item.get("priority_score") or 0) > (existing.get("priority_score") or 0):
                dupes.append(existing["id"])
                seen[key] = item
            else:
                dupes.append(item["id"])

    for dupe_id in dupes:
        (
            supabase.table("queue_items")
            .delete()
            .eq("id", dupe_id)
            .execute()
        )
        items_pruned += 1

    # ------------------------------------------------------------------
    # 7. Recompute user_node_states for the triggering engagement
    # ------------------------------------------------------------------
    if body.trigger == "attempt_submit" and body.ref_id:
        try:
            att_resp = (
                supabase.table("attempts")
                .select("problem_id")
                .eq("id", str(body.ref_id))
                .execute()
            )
            if att_resp.data:
                problem_id = att_resp.data[0].get("problem_id")
                if problem_id:
                    prob_resp = (
                        supabase.table("problems")
                        .select("topic_node_id")
                        .eq("id", problem_id)
                        .execute()
                    )
                    if prob_resp.data:
                        node_id = prob_resp.data[0].get("topic_node_id")
                        if node_id:
                            _recompute_node_state(supabase, user_id, node_id)
        except Exception:
            logger.exception("_recompute_node_state failed; continuing")

    elif body.trigger == "engagement_complete" and body.ref_id:
        # Paper engagements have no single topic_node_id. Update engagement_count
        # for all of the user's interested nodes — paper completion is a general
        # reinforcement signal across the user's interest graph.
        try:
            ui_resp = (
                supabase.table("user_interests")
                .select("node_id")
                .eq("user_id", user_id)
                .execute()
            )
            for ui in (ui_resp.data or []):
                ni = ui["node_id"]
                ns_resp = (
                    supabase.table("user_node_states")
                    .select("state, engagement_count")
                    .eq("user_id", user_id)
                    .eq("node_id", ni)
                    .execute()
                )
                current = (ns_resp.data or [{}])[0]
                current_state: str = current.get("state") or "unseen"
                engagement_count: int = (current.get("engagement_count") or 0) + 1
                new_state = current_state
                if current_state in ("bookmarked", "comfortable"):
                    pass
                elif current_state == "unseen":
                    new_state = "active"
                (
                    supabase.table("user_node_states")
                    .upsert(
                        {
                            "user_id": user_id,
                            "node_id": ni,
                            "state": new_state,
                            "engagement_count": engagement_count,
                            "last_engaged_at": now_str,
                        },
                        on_conflict="user_id,node_id",
                    )
                    .execute()
                )
        except Exception:
            logger.exception("engagement_complete node state update failed; continuing")

    return UpdateQueueResponse(
        items_reweighted=items_reweighted,
        refreshers_scheduled=refreshers_scheduled,
        items_pruned=items_pruned,
    )
