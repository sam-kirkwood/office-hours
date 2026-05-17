"""POST /compute-cross-pollination — Phase 7-rev step 7.

Daily background job (no LLM call). Gated on the first weekly curation
snapshot having been written. For each active user, walks 1-hop and 2-hop
graph frontiers to find candidate nodes not yet in their engaged set, scores
them by edge proximity and multi-user engagement, and inserts a
`suggested_interest` queue item for the top scorer above the threshold.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from supabase import Client

from auth import require_internal_token
from schemas import ComputeCrossPollinationRequest, ComputeCrossPollinationResponse
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


def _load_1hop_edges(supabase: Client, node_ids: list[str]) -> list[dict]:
    """Load all edges where source OR target is in node_ids (two queries merged)."""
    if not node_ids:
        return []
    src_resp = (
        supabase.table("edges")
        .select("source_node_id, target_node_id, weight")
        .in_("source_node_id", node_ids)
        .execute()
    )
    tgt_resp = (
        supabase.table("edges")
        .select("source_node_id, target_node_id, weight")
        .in_("target_node_id", node_ids)
        .execute()
    )
    return (src_resp.data or []) + (tgt_resp.data or [])


def _frontier_from_edges(
    edges: list[dict],
    anchor_ids: set[str],
    excluded_ids: set[str],
) -> dict[str, float]:
    """Return {node_id: max_edge_weight} for nodes reachable from anchor_ids but not in excluded_ids."""
    candidates: dict[str, float] = {}
    for edge in edges:
        src = edge["source_node_id"]
        tgt = edge["target_node_id"]
        weight = float(edge.get("weight") or 0.0)
        if src in anchor_ids and tgt not in excluded_ids:
            candidates[tgt] = max(candidates.get(tgt, 0.0), weight)
        elif tgt in anchor_ids and src not in excluded_ids:
            candidates[src] = max(candidates.get(src, 0.0), weight)
    return candidates


@router.post(
    "/compute-cross-pollination",
    response_model=ComputeCrossPollinationResponse,
    dependencies=[Depends(require_internal_token)],
)
def compute_cross_pollination(
    body: ComputeCrossPollinationRequest,
    supabase: Client = Depends(get_supabase_client),
) -> ComputeCrossPollinationResponse:
    now = datetime.now(timezone.utc)

    # 1. Curation gate: at least one system-written megagraph snapshot required.
    snap_resp = (
        supabase.table("megagraph_snapshots")
        .select("id")
        .eq("taken_by", "system")
        .limit(1)
        .execute()
    )
    if not snap_resp.data:
        return ComputeCrossPollinationResponse(
            suggestions_created=0, reason="no_curation_yet"
        )

    # 2. Load all active users (distinct user_ids in user_interests).
    users_resp = (
        supabase.table("user_interests")
        .select("user_id")
        .execute()
    )
    user_ids = list({row["user_id"] for row in (users_resp.data or [])})

    suggestions_created = 0

    for user_id in user_ids:
        # a. Load engaged node_ids for this user.
        ns_resp = (
            supabase.table("user_node_states")
            .select("node_id")
            .eq("user_id", user_id)
            .in_("state", ["active", "comfortable", "struggling"])
            .execute()
        )
        engaged_ids: set[str] = {row["node_id"] for row in (ns_resp.data or [])}

        if not engaged_ids:
            continue

        # Load bookmarked node ids to exclude from suggestions.
        bm_resp = (
            supabase.table("bookmarks")
            .select("ref_id_or_text")
            .eq("user_id", user_id)
            .eq("kind", "node")
            .execute()
        )
        bookmarked_ids: set[str] = {
            row["ref_id_or_text"] for row in (bm_resp.data or [])
        }
        excluded_ids = engaged_ids | bookmarked_ids

        # b. 1-hop frontier.
        hop1_edges = _load_1hop_edges(supabase, list(engaged_ids))
        hop1_candidates = _frontier_from_edges(hop1_edges, engaged_ids, excluded_ids)

        # c. 2-hop frontier (from 1-hop set, excluding engaged + 1-hop already found).
        hop2_candidates: dict[str, float] = {}
        if hop1_candidates:
            hop2_excluded = excluded_ids | set(hop1_candidates.keys())
            hop2_edges = _load_1hop_edges(supabase, list(hop1_candidates.keys()))
            hop2_candidates = _frontier_from_edges(
                hop2_edges, set(hop1_candidates.keys()), hop2_excluded
            )

        # Merge: hop1 takes precedence (closer nodes score better).
        all_candidates: dict[str, float] = {**hop2_candidates, **hop1_candidates}

        if not all_candidates:
            continue

        # d. Score each candidate.
        scored: list[tuple[float, str]] = []
        for candidate_id, edge_weight in all_candidates.items():
            ou_resp = (
                supabase.table("user_node_states")
                .select("user_id")
                .eq("node_id", candidate_id)
                .execute()
            )
            other_user_count = len(
                {row["user_id"] for row in (ou_resp.data or [])} - {user_id}
            )
            score = edge_weight * 0.5 + min(other_user_count, 5) * 0.1
            scored.append((score, candidate_id))

        if not scored:
            continue

        # e. Pick top candidate; skip if below threshold.
        scored.sort(key=lambda x: x[0], reverse=True)
        top_score, top_node_id = scored[0]

        if top_score <= 0.3:
            continue

        # f. Cooldown: skip if we already suggested this node within 7 days.
        cutoff = (now - timedelta(days=7)).isoformat()
        cooldown_resp = (
            supabase.table("queue_items")
            .select("id")
            .eq("user_id", user_id)
            .eq("kind", "suggested_interest")
            .eq("ref_id", top_node_id)
            .gte("added_at", cutoff)
            .execute()
        )
        if cooldown_resp.data:
            continue

        # g. Insert suggested_interest queue item.
        (
            supabase.table("queue_items")
            .insert({
                "user_id": user_id,
                "kind": "suggested_interest",
                "ref_id": top_node_id,
                "state": "pending",
                "priority_score": 0.35,
                "added_reason": (
                    "Other users working in adjacent areas have explored this."
                ),
            })
            .execute()
        )
        suggestions_created += 1

    return ComputeCrossPollinationResponse(
        suggestions_created=suggestions_created, reason="ok"
    )
