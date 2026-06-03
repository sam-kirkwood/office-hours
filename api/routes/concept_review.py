"""POST /concept-review-resolve — pool-hit-or-reading resolver for
kind='concept_review' queue cards (phase-10-rev-plan §Step 4, D3).

Pool lookup at conceptual depth: intent='teach', difficulty=1, optional tag
filter on the node's primary subtopic. On hit, atomically enqueue a
kind='problem' row and mark the original concept_review row done. On miss,
return the node's description + subtopics for the client to render as a
reading surface.

Reuses `_pool_lookup_for_recommendation` from routes.curator since the
signature is exactly what the concept_review surface needs (cross-route
helper is fine; both routes are owned in the same module).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from anthropic_client import get_anthropic_client
from auth import require_internal_token
from routes.curator import _pool_lookup_for_recommendation, _slugify_phrase
from routes.generate_concept_brief import generate_brief_for_node
from schemas import (
    ConceptReviewNodeReading,
    ConceptReviewResolveRequest,
    ConceptReviewResolveResponse,
)
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_subtopics(subtopics_json: list | None) -> list[dict]:
    """Coerce legacy `list[str]` subtopics to the `[{slug, title}, ...]` shape
    the reading-surface UI expects. New rows already write dicts; older nodes
    (pre-shape-migration) may store plain strings."""
    if not subtopics_json:
        return []
    out: list[dict] = []
    for item in subtopics_json:
        if isinstance(item, dict):
            slug = item.get("slug") or _slugify_phrase(item.get("title") or "")
            title = item.get("title") or slug
            out.append({"slug": slug, "title": title})
        elif isinstance(item, str):
            out.append({"slug": _slugify_phrase(item), "title": item})
    return out


def _primary_subtopic_slug(subtopics_json: list | None) -> str | None:
    normalized = _normalize_subtopics(subtopics_json)
    if not normalized:
        return None
    return normalized[0]["slug"] or None


@router.post(
    "/concept-review-resolve",
    response_model=ConceptReviewResolveResponse,
    dependencies=[Depends(require_internal_token)],
)
def concept_review_resolve(
    body: ConceptReviewResolveRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> ConceptReviewResolveResponse:
    user_id = str(body.user_id)
    queue_item_id = str(body.queue_item_id)

    # 1. Load the queue_item, verify kind + ownership.
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
    if qi["kind"] != "concept_review":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"queue_item is kind={qi['kind']!r}, expected 'concept_review'",
        )
    if qi.get("state") in ("done", "dismissed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"queue_item already in terminal state {qi.get('state')!r}",
        )

    node_id = qi.get("ref_id")
    if not node_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="concept_review queue_item has no ref_id (node)",
        )

    # 2. Load the node.
    node_resp = (
        supabase.table("nodes")
        .select("id, slug, title, description_md, subtopics_json")
        .eq("id", node_id)
        .limit(1)
        .execute()
    )
    if not node_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="node referenced by queue_item not found",
        )
    node = node_resp.data[0]

    # 3. Pool lookup at conceptual depth.
    subtopic_slug = _primary_subtopic_slug(node.get("subtopics_json"))
    cached_problem_id = _pool_lookup_for_recommendation(
        supabase,
        topic_node_id=node["id"],
        difficulty=1,
        intent="teach",
        subtopic_slug=subtopic_slug,
    )

    # 4a. Pool hit: enqueue a kind='problem' row, mark concept_review done.
    if cached_problem_id is not None:
        insert_resp = (
            supabase.table("queue_items")
            .insert(
                {
                    "user_id": user_id,
                    "kind": "problem",
                    "ref_id": cached_problem_id,
                    "state": "pending",
                    "priority_score": 0.5,
                    "added_reason": (
                        "Picked from the practice pool to ground this concept."
                    ),
                }
            )
            .execute()
        )
        if not insert_resp.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="failed to enqueue problem row",
            )
        new_queue_item_id = insert_resp.data[0]["id"]

        supabase.table("queue_items").update(
            {"state": "done", "updated_at": _now_iso()}
        ).eq("id", queue_item_id).execute()

        return ConceptReviewResolveResponse(
            kind="problem",
            queue_item_id=new_queue_item_id,
        )

    # 4b. Miss: return the node reading surface.
    #
    # Step 5.5 — generate or fetch a cached concept brief (Haiku) and use its
    # per-subtopic glosses to enrich the subtopic list. The brief is cached
    # on node_concept_briefs by node_id and reused across users. If brief
    # generation fails (e.g. Anthropic outage), fall back to the bare reading
    # surface so the user still gets *something*.
    normalized_subtopics = _normalize_subtopics(node.get("subtopics_json"))
    brief_md: str | None = None
    try:
        brief = generate_brief_for_node(
            supabase=supabase,
            anthropic=anthropic,
            user_id=user_id,
            node_id=node["id"],
        )
        brief_md = brief.brief_md
        gloss_by_slug = {g.slug: g.gloss_md for g in brief.subtopic_glosses_json}
        for s in normalized_subtopics:
            gloss = gloss_by_slug.get(s["slug"])
            if gloss:
                s["gloss_md"] = gloss
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "concept-review-resolve: brief generation failed for node=%s — "
            "falling back to bare reading surface: %s",
            node["id"],
            exc,
        )

    return ConceptReviewResolveResponse(
        kind="reading",
        node=ConceptReviewNodeReading(
            id=node["id"],
            slug=node["slug"],
            title=node["title"],
            description_md=node.get("description_md") or "",
            subtopics_json=normalized_subtopics,
            brief_md=brief_md,
        ),
    )
