"""POST /generate-edge-description — Step 6 follow-up.

Produces a short (~3-5 sentence) paragraph explaining why two nodes are
connected — what specific concepts/skills from the source load-bear into
the target. Caches on edge_descriptions by edge_id and returns it. Shared
across users: the first viewer of a given edge pays for the Haiku call,
every subsequent click reads the cached row.

Called from the web's /api/edge/[id]/description proxy on first EdgePanel
open.
"""

from __future__ import annotations

import logging

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from anthropic_client import call_json, get_anthropic_client
from auth import require_internal_token
from config import HAIKU_MODEL
from prompts.edge_description import build_system_prompt, build_user_prompt
from schemas import (
    GenerateEdgeDescriptionRequest,
    GenerateEdgeDescriptionResponse,
    GeneratedEdgeDescription,
)
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


def _subtopic_titles(subtopics_json: object) -> list[str]:
    """Flatten a node's subtopics_json (mixed shape) into a list of titles
    suitable for prompt context. Tolerates legacy string[] interest-node
    subtopics; foundation nodes are [{slug, title}]."""
    if not isinstance(subtopics_json, list):
        return []
    titles: list[str] = []
    for item in subtopics_json:
        if isinstance(item, dict):
            t = item.get("title")
            if isinstance(t, str) and t:
                titles.append(t)
        elif isinstance(item, str) and item:
            titles.append(item)
    return titles


def _fetch_cached(supabase: Client, edge_id: str) -> dict | None:
    resp = (
        supabase.table("edge_descriptions")
        .select("description_md")
        .eq("edge_id", edge_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    return resp.data[0]


def generate_description_for_edge(
    *,
    supabase: Client,
    anthropic: Anthropic,
    user_id: str,
    edge_id: str,
) -> GenerateEdgeDescriptionResponse:
    # 1. Cache check.
    cached = _fetch_cached(supabase, edge_id)
    if cached is not None:
        return GenerateEdgeDescriptionResponse(
            description_md=cached["description_md"],
            cached=True,
        )

    # 2. Load edge + both nodes.
    edge_resp = (
        supabase.table("edges")
        .select("id, source_node_id, target_node_id, edge_kind")
        .eq("id", edge_id)
        .limit(1)
        .execute()
    )
    if not edge_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="edge not found",
        )
    edge = edge_resp.data[0]

    nodes_resp = (
        supabase.table("nodes")
        .select("id, title, description_md, subtopics_json")
        .in_("id", [edge["source_node_id"], edge["target_node_id"]])
        .execute()
    )
    nodes_by_id = {n["id"]: n for n in (nodes_resp.data or [])}
    source = nodes_by_id.get(edge["source_node_id"])
    target = nodes_by_id.get(edge["target_node_id"])
    if source is None or target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="edge endpoint nodes not found",
        )

    # 3. Haiku call.
    generated = call_json(
        client=anthropic,
        supabase=supabase,
        model=HAIKU_MODEL,
        system_prompt=build_system_prompt(),
        user_prompt=build_user_prompt(
            edge_kind=edge["edge_kind"],
            source_title=source["title"],
            source_description_md=source.get("description_md") or "",
            source_subtopics=_subtopic_titles(source.get("subtopics_json")),
            target_title=target["title"],
            target_description_md=target.get("description_md") or "",
            target_subtopics=_subtopic_titles(target.get("subtopics_json")),
        ),
        schema=GeneratedEdgeDescription,
        route="/generate-edge-description",
        user_id=user_id,
        request_summary={
            "edge_id": edge_id,
            "edge_kind": edge["edge_kind"],
        },
    )

    # 4. Cache. Upsert tolerates two viewers racing on the same edge.
    supabase.table("edge_descriptions").upsert(
        {
            "edge_id": edge_id,
            "description_md": generated.description_md,
            "generated_by_model": HAIKU_MODEL,
        }
    ).execute()

    return GenerateEdgeDescriptionResponse(
        description_md=generated.description_md,
        cached=False,
    )


@router.post(
    "/generate-edge-description",
    response_model=GenerateEdgeDescriptionResponse,
    dependencies=[Depends(require_internal_token)],
)
def generate_edge_description(
    body: GenerateEdgeDescriptionRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> GenerateEdgeDescriptionResponse:
    return generate_description_for_edge(
        supabase=supabase,
        anthropic=anthropic,
        user_id=str(body.user_id),
        edge_id=str(body.edge_id),
    )
