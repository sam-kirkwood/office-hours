"""POST /generate-concept-brief — Step 5.5.

Produces a short (~250 word) warm orientation to a topic node plus per-
subtopic glosses, caches it on node_concept_briefs by node_id, and returns
it. Reused across users; the first user to land on a node pays for the
Haiku call and every subsequent user on the same node gets the cached row.

Called inline from /concept-review-resolve's reading-surface (miss) path
when no cached brief exists yet — see routes/concept_review.py.
"""

from __future__ import annotations

import logging

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from anthropic_client import call_json, get_anthropic_client
from auth import require_internal_token
from config import HAIKU_MODEL
from prompts.concept_brief import build_system_prompt, build_user_prompt
from schemas import (
    GenerateConceptBriefRequest,
    GenerateConceptBriefResponse,
    GeneratedConceptBrief,
)
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


def _normalize_subtopics_for_prompt(subtopics_json: object) -> list[dict]:
    """Coerce legacy list[str] subtopics to {slug, title} dicts so the prompt
    can reference them by slug. Mirrors concept_review._normalize_subtopics."""
    if not isinstance(subtopics_json, list):
        return []
    out: list[dict] = []
    for item in subtopics_json:
        if isinstance(item, dict):
            slug = item.get("slug") or _slugify(item.get("title") or "")
            title = item.get("title") or slug
            out.append({"slug": slug, "title": title})
        elif isinstance(item, str):
            out.append({"slug": _slugify(item), "title": item})
    return out


def _slugify(text: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "untitled"


def _fetch_cached_brief(supabase: Client, node_id: str) -> dict | None:
    resp = (
        supabase.table("node_concept_briefs")
        .select("brief_md, subtopic_glosses_json")
        .eq("node_id", node_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    return resp.data[0]


def generate_brief_for_node(
    *,
    supabase: Client,
    anthropic: Anthropic,
    user_id: str,
    node_id: str,
) -> GenerateConceptBriefResponse:
    """Shared helper. Used by the HTTP route and by /concept-review-resolve."""
    # 1. Cache check.
    cached = _fetch_cached_brief(supabase, node_id)
    if cached is not None:
        return GenerateConceptBriefResponse(
            brief_md=cached["brief_md"],
            subtopic_glosses_json=cached.get("subtopic_glosses_json") or [],
            cached=True,
        )

    # 2. Load node.
    node_resp = (
        supabase.table("nodes")
        .select("id, title, description_md, subtopics_json")
        .eq("id", node_id)
        .limit(1)
        .execute()
    )
    if not node_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="node not found",
        )
    node = node_resp.data[0]
    subtopics = _normalize_subtopics_for_prompt(node.get("subtopics_json"))

    # 3. Haiku call.
    generated = call_json(
        client=anthropic,
        supabase=supabase,
        model=HAIKU_MODEL,
        system_prompt=build_system_prompt(),
        user_prompt=build_user_prompt(
            node_title=node["title"],
            node_description_md=node.get("description_md") or "",
            subtopics=subtopics,
        ),
        schema=GeneratedConceptBrief,
        route="/generate-concept-brief",
        user_id=user_id,
        request_summary={"node_id": node_id, "subtopic_count": len(subtopics)},
    )

    # 4. Cache. Upsert in case two users race on the same node — the second
    # write is harmless since the brief is reusable.
    glosses_payload = [g.model_dump() for g in generated.subtopic_glosses_json]
    supabase.table("node_concept_briefs").upsert(
        {
            "node_id": node_id,
            "brief_md": generated.brief_md,
            "subtopic_glosses_json": glosses_payload,
            "generated_by_model": HAIKU_MODEL,
        }
    ).execute()

    return GenerateConceptBriefResponse(
        brief_md=generated.brief_md,
        subtopic_glosses_json=generated.subtopic_glosses_json,
        cached=False,
    )


@router.post(
    "/generate-concept-brief",
    response_model=GenerateConceptBriefResponse,
    dependencies=[Depends(require_internal_token)],
)
def generate_concept_brief(
    body: GenerateConceptBriefRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> GenerateConceptBriefResponse:
    return generate_brief_for_node(
        supabase=supabase,
        anthropic=anthropic,
        user_id=str(body.user_id),
        node_id=str(body.node_id),
    )
