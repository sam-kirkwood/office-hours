"""POST /refresher-resolve — click-time resolver for kind='refresher' queue cards.

Two refresher shapes exist (see schemas.RefresherResolveRequest header):

  (a) Legacy/deterministic — ref_id is a refresher_schedule.id whose subject is
      a prior attempt or paper engagement. Resolution returns the subject's
      original queue_item_id so the client redirects back to /problem or
      /paper.

  (b) Curator-style — ref_id is a nodes.id. The curator emits these for
      ad-hoc refreshers (see api/routes/curator.py _execute_add_refresher).
      Resolution does a pool lookup at (topic_node_id, intent='refresh',
      difficulty=1). On hit, enqueues a kind='problem' row pointing at the
      cached problem. On miss, enqueues a kind='concept_review' row pointing
      at the same node so the user lands on the brief.

In both cases the original refresher queue_items row is marked 'done'.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from auth import require_internal_token
from routes.curator import _pool_lookup_for_recommendation
from schemas import RefresherResolveRequest, RefresherResolveResponse
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mark_done(supabase: Client, queue_item_id: str) -> None:
    supabase.table("queue_items").update(
        {"state": "done", "updated_at": _now_iso()}
    ).eq("id", queue_item_id).execute()


def _resolve_schedule(
    supabase: Client, *, user_id: str, ref_id: str
) -> RefresherResolveResponse | None:
    """Try the legacy refresher_schedule path. Returns None if ref_id doesn't
    match a refresher_schedule row.

    Both subject shapes (attempt → problem, engagement → paper) get a fresh
    queue_items row pointing at the same content — the original queue items
    are in state='done' so /problem and /paper would bounce back to /daily
    if we returned those ids directly.
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
            problem_id = att_resp.data[0]["problem_id"]
            insert_resp = (
                supabase.table("queue_items")
                .insert(
                    {
                        "user_id": user_id,
                        "kind": "problem",
                        "ref_id": problem_id,
                        "state": "pending",
                        "priority_score": 0.55,
                        "added_reason": "Revisiting this to reinforce it.",
                    }
                )
                .execute()
            )
            if insert_resp.data:
                return RefresherResolveResponse(
                    kind="problem",
                    queue_item_id=insert_resp.data[0]["id"],
                )

    elif subject_kind == "engagement":
        insert_resp = (
            supabase.table("queue_items")
            .insert(
                {
                    "user_id": user_id,
                    "kind": "paper_engagement",
                    "ref_id": subject_ref_id,
                    "state": "pending",
                    "priority_score": 0.55,
                    "added_reason": "Revisiting this paper to reinforce it.",
                }
            )
            .execute()
        )
        if insert_resp.data:
            return RefresherResolveResponse(
                kind="paper_engagement",
                queue_item_id=insert_resp.data[0]["id"],
            )

    return None


def _resolve_curator_node(
    supabase: Client, *, user_id: str, node_id: str
) -> RefresherResolveResponse:
    """Curator-style refresher: ref_id is a node. Pool-lookup a refresh-intent
    problem; on miss, fall back to a concept_review on the same node.
    """
    node_resp = (
        supabase.table("nodes")
        .select("id, title")
        .eq("id", node_id)
        .limit(1)
        .execute()
    )
    if not node_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="refresher ref_id resolves to neither refresher_schedule nor a node",
        )

    cached_problem_id = _pool_lookup_for_recommendation(
        supabase,
        topic_node_id=node_id,
        difficulty=1,
        intent="refresh",
        subtopic_slug=None,
    )

    if cached_problem_id is not None:
        insert_resp = (
            supabase.table("queue_items")
            .insert(
                {
                    "user_id": user_id,
                    "kind": "problem",
                    "ref_id": cached_problem_id,
                    "state": "pending",
                    "priority_score": 0.55,
                    "added_reason": "A refresher problem picked from the pool.",
                }
            )
            .execute()
        )
        if not insert_resp.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="failed to enqueue refresher problem row",
            )
        return RefresherResolveResponse(
            kind="problem",
            queue_item_id=insert_resp.data[0]["id"],
        )

    # Pool miss → concept_review on the same node so the user lands on the brief.
    insert_resp = (
        supabase.table("queue_items")
        .insert(
            {
                "user_id": user_id,
                "kind": "concept_review",
                "ref_id": node_id,
                "state": "pending",
                "priority_score": 0.55,
                "added_reason": "A short read to refresh this topic.",
            }
        )
        .execute()
    )
    if not insert_resp.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to enqueue refresher concept_review row",
        )
    return RefresherResolveResponse(
        kind="concept_review",
        queue_item_id=insert_resp.data[0]["id"],
    )


@router.post(
    "/refresher-resolve",
    response_model=RefresherResolveResponse,
    dependencies=[Depends(require_internal_token)],
)
def refresher_resolve(
    body: RefresherResolveRequest,
    supabase: Client = Depends(get_supabase_client),
) -> RefresherResolveResponse:
    user_id = str(body.user_id)
    queue_item_id = str(body.queue_item_id)

    qi_resp = (
        supabase.table("queue_items")
        .select("id, user_id, kind, ref_id, state")
        .eq("id", queue_item_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not qi_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="queue_item not found",
        )
    qi = qi_resp.data[0]
    if qi["kind"] != "refresher":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"queue_item is kind={qi['kind']!r}, expected 'refresher'",
        )
    if qi.get("state") in ("done", "dismissed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"queue_item already in terminal state {qi.get('state')!r}",
        )

    ref_id = qi.get("ref_id")
    if not ref_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresher queue_item has no ref_id",
        )

    resolved = _resolve_schedule(supabase, user_id=user_id, ref_id=ref_id)
    if resolved is None:
        resolved = _resolve_curator_node(
            supabase, user_id=user_id, node_id=ref_id
        )

    _mark_done(supabase, queue_item_id)
    return resolved
