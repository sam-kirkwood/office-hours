"""POST /generate-curation-report — Phase 8-rev step 1.

Weekly operator-triggered route. Reads the megagraph's recent additions and
engagement signals, calls Sonnet, and writes curation_proposals rows for the
operator to approve or reject in the admin UI.
"""

from __future__ import annotations

import logging
from datetime import timezone, datetime

from anthropic import Anthropic
from fastapi import APIRouter, Depends
from supabase import Client

from anthropic_client import call_json, get_anthropic_client
from auth import require_internal_token
from config import SONNET_MODEL
from prompts import curation_report as prompts
from schemas import (
    CurationReportLLMOutput,
    GenerateCurationReportRequest,
    GenerateCurationReportResponse,
)
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_PROPOSALS = 20
ROUTE = "/generate-curation-report"


def _resolve_node_titles(
    node_ids: list[str], node_map: dict[str, str]
) -> list[dict]:
    """Return list of {node_id, title} for the given IDs, skipping unknowns."""
    return [{"node_id": nid, "title": node_map.get(nid, nid)} for nid in node_ids]


def _epoch() -> str:
    return "1970-01-01T00:00:00+00:00"


@router.post(
    "/generate-curation-report",
    response_model=GenerateCurationReportResponse,
    dependencies=[Depends(require_internal_token)],
)
def generate_curation_report(
    _body: GenerateCurationReportRequest,
    supabase: Client = Depends(get_supabase_client),
    client: Anthropic = Depends(get_anthropic_client),
) -> GenerateCurationReportResponse:
    # 1. Compute input window since last snapshot (D5).
    snap_resp = (
        supabase.table("megagraph_snapshots")
        .select("taken_at")
        .order("taken_at", desc=True)
        .limit(1)
        .execute()
    )
    since = snap_resp.data[0]["taken_at"] if snap_resp.data else _epoch()

    # 2. Load all active nodes (for context + title resolution).
    all_nodes_resp = (
        supabase.table("nodes")
        .select("id, slug, title, kind, domain")
        .eq("pool_status", "active")
        .execute()
    )
    all_nodes: list[dict] = all_nodes_resp.data or []
    node_map: dict[str, str] = {n["id"]: n["title"] for n in all_nodes}

    # 3. Load all edges with titles resolved.
    all_edges_resp = (
        supabase.table("edges")
        .select("source_node_id, target_node_id, edge_kind, weight")
        .execute()
    )
    raw_edges: list[dict] = all_edges_resp.data or []
    all_edges = [
        {
            **e,
            "source_title": node_map.get(e["source_node_id"], e["source_node_id"]),
            "target_title": node_map.get(e["target_node_id"], e["target_node_id"]),
        }
        for e in raw_edges
    ]

    # 4. Load recent additions since last snapshot.
    new_nodes_resp = (
        supabase.table("nodes")
        .select("id, slug, title, kind, domain, subtopics_json")
        .gt("created_at", since)
        .eq("pool_status", "active")
        .execute()
    )
    new_nodes: list[dict] = new_nodes_resp.data or []

    new_edges_resp = (
        supabase.table("edges")
        .select("source_node_id, target_node_id, edge_kind, weight")
        .gt("created_at", since)
        .execute()
    )
    new_edges_raw: list[dict] = new_edges_resp.data or []
    new_edges = [
        {
            **e,
            "source_title": node_map.get(e["source_node_id"], e["source_node_id"]),
            "target_title": node_map.get(e["target_node_id"], e["target_node_id"]),
        }
        for e in new_edges_raw
    ]

    # 5. Load recent autonomous dedup decisions (applied curation_proposals since since).
    dedup_resp = (
        supabase.table("curation_proposals")
        .select("kind, payload_json")
        .gt("proposed_at", since)
        .eq("status", "applied")
        .execute()
    )
    recent_dedup: list[dict] = dedup_resp.data or []

    # 6. Load engagement signals, resolve IDs to titles.
    high_eng_resp = (
        supabase.table("user_node_states")
        .select("node_id, engagement_count")
        .gte("engagement_count", 5)
        .order("engagement_count", desc=True)
        .limit(20)
        .execute()
    )
    high_engagement = [
        {**row, "title": node_map.get(row["node_id"], row["node_id"])}
        for row in (high_eng_resp.data or [])
    ]

    struggling_resp = (
        supabase.table("user_node_states")
        .select("node_id, struggle_score")
        .gte("struggle_score", 0.6)
        .order("struggle_score", desc=True)
        .limit(20)
        .execute()
    )
    struggling = [
        {**row, "title": node_map.get(row["node_id"], row["node_id"])}
        for row in (struggling_resp.data or [])
    ]

    # Neglected: active nodes not in user_node_states at all (simple proxy).
    engaged_node_ids_resp = (
        supabase.table("user_node_states")
        .select("node_id")
        .execute()
    )
    engaged_ids = {row["node_id"] for row in (engaged_node_ids_resp.data or [])}
    neglected = [n for n in all_nodes if n["id"] not in engaged_ids][:20]

    # 7. Call Sonnet.
    megagraph_data = {
        "since": since,
        "all_nodes": all_nodes,
        "all_edges": all_edges,
        "new_nodes": new_nodes,
        "new_edges": new_edges,
        "recent_dedup_decisions": recent_dedup,
        "high_engagement": high_engagement,
        "struggling": struggling,
        "neglected": neglected,
    }

    result: CurationReportLLMOutput = call_json(
        client=client,
        supabase=supabase,
        model=SONNET_MODEL,
        system_prompt=prompts.SYSTEM_PROMPT,
        user_prompt=prompts.build_user_prompt(megagraph_data),
        schema=CurationReportLLMOutput,
        route=ROUTE,
        max_tokens=4096,
        request_summary={"node_count": len(all_nodes), "since": since},
    )

    proposals = result.proposals
    if len(proposals) > MAX_PROPOSALS:
        logger.warning(
            "Sonnet returned %d proposals (limit %d); truncating.",
            len(proposals),
            MAX_PROPOSALS,
        )
        proposals = proposals[:MAX_PROPOSALS]

    # 8. Insert proposals.
    now_iso = datetime.now(timezone.utc).isoformat()
    for proposal in proposals:
        supabase.table("curation_proposals").insert({
            "kind": proposal.kind,
            "payload_json": proposal.payload_json,
            "status": "pending",
            "proposed_at": now_iso,
        }).execute()

    return GenerateCurationReportResponse(
        proposals_created=len(proposals),
        since=since,
    )
