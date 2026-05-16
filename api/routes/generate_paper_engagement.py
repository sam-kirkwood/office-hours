"""POST /generate-paper-engagement — pre-generate a structured paper engagement.

Flow:
  1. Auth check.
  2. Load paper by paper_id → title, abstract_md, authors_json, year.
  3. Load user interests → node titles for personalisation.
  4. Sonnet call (call_json) → GeneratedEngagement (why_this_md, concepts, questions).
  5. Validate question count in [3, 5]; raise 500 if not.
  6. Insert paper_engagements row.
  7. Return engagement_id.

The inner function `generate_engagement_for_paper` can be called directly by
suggest_papers to avoid HTTP round-trips.
"""

from __future__ import annotations

import logging
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from anthropic_client import call_json, get_anthropic_client
from auth import require_internal_token
from config import SONNET_MODEL
from prompts.paper_engagement import build_system_prompt, build_user_prompt
from schemas import (
    GeneratedEngagement,
    GeneratePaperEngagementRequest,
    GeneratePaperEngagementResponse,
)
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


def generate_engagement_for_paper(
    *,
    supabase: Client,
    anthropic: Anthropic,
    user_id: str,
    paper_id: str,
) -> str:
    """Core logic: generate an engagement for a paper and insert the DB row.

    Returns the new paper_engagements.id as a string. Raises HTTPException on
    errors so callers get consistent error semantics whether called from the
    route or from suggest_papers.
    """
    # Load paper
    paper_resp = (
        supabase.table("papers")
        .select("id, title, abstract_md, authors_json, year")
        .eq("id", paper_id)
        .limit(1)
        .execute()
    )
    if not paper_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="paper not found")
    paper = paper_resp.data[0]

    # Load user interests → node titles
    interests_resp = (
        supabase.table("user_interests")
        .select("node_id")
        .eq("user_id", user_id)
        .execute()
    )
    node_ids = [ui["node_id"] for ui in (interests_resp.data or [])]
    interest_titles: list[str] = []
    if node_ids:
        nodes_resp = (
            supabase.table("nodes")
            .select("title")
            .in_("id", node_ids)
            .execute()
        )
        interest_titles = [n["title"] for n in (nodes_resp.data or [])]

    # Sonnet generation
    generated = call_json(
        client=anthropic,
        supabase=supabase,
        model=SONNET_MODEL,
        system_prompt=build_system_prompt(),
        user_prompt=build_user_prompt(
            title=paper["title"],
            year=paper.get("year") or 0,
            authors=paper.get("authors_json") or [],
            abstract_md=paper.get("abstract_md") or "",
            interest_titles=interest_titles,
        ),
        schema=GeneratedEngagement,
        route="/generate-paper-engagement",
        user_id=user_id,
        max_tokens=4096,
        request_summary={"paper_id": paper_id},
    )

    # Validate question count
    if len(generated.questions_json) not in range(3, 6):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"question count {len(generated.questions_json)} out of range [3, 5]; "
                "generation failed"
            ),
        )

    # Insert engagement row
    engagement_resp = (
        supabase.table("paper_engagements")
        .insert(
            {
                "user_id": user_id,
                "paper_id": paper_id,
                "why_this_md": generated.why_this_md,
                "orienting_concepts_json": generated.orienting_concepts_json,
                "questions_json": generated.questions_json,
                "state": "pending",
                "current_question_index": 0,
            }
        )
        .execute()
    )
    return engagement_resp.data[0]["id"]


@router.post(
    "/generate-paper-engagement",
    response_model=GeneratePaperEngagementResponse,
    dependencies=[Depends(require_internal_token)],
)
def generate_paper_engagement(
    body: GeneratePaperEngagementRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> GeneratePaperEngagementResponse:
    engagement_id = generate_engagement_for_paper(
        supabase=supabase,
        anthropic=anthropic,
        user_id=str(body.user_id),
        paper_id=str(body.paper_id),
    )
    return GeneratePaperEngagementResponse(engagement_id=UUID(engagement_id))
