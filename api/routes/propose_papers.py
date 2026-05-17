"""POST /propose-papers — propose papers from Sonnet's training knowledge.

Flow:
  1. Auth check.
  2. Load user_interests → node_ids → node titles.
  3. Load last 3 notebook_entries for user (recency context).
  4. Sonnet call → ProposePapersLLMOutput (3–5 candidates).
  5. Validate candidate count in [3, 5]; log warning if out of range but continue.
  6. For each candidate:
     a. ingest_paper(...) → (paper_id, created)
     b. Skip if paper_engagements already exists for (user_id, paper_id).
     c. generate_engagement_for_paper(...)
     d. Insert queue_items row.
  7. Return ProposePapersResponse.
"""

from __future__ import annotations

import logging

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from anthropic_client import call_json, get_anthropic_client
from auth import require_internal_token
from config import SONNET_MODEL
from paper_ingest_shared import ingest_paper
from prompts.propose_papers import build_system_prompt, build_user_prompt
from routes.generate_paper_engagement import generate_engagement_for_paper
from schemas import ProposePapersLLMOutput, ProposePapersRequest, ProposePapersResponse
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/propose-papers",
    response_model=ProposePapersResponse,
    dependencies=[Depends(require_internal_token)],
)
def propose_papers(
    body: ProposePapersRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> ProposePapersResponse:
    user_id = str(body.user_id)

    # 2. Load user interests → node titles
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

    # 3. Load last 3 notebook_entries for user
    entries_resp = (
        supabase.table("notebook_entries")
        .select("title")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(3)
        .execute()
    )
    recent_entry_titles = [e["title"] for e in (entries_resp.data or [])]

    # 4. Sonnet call
    llm_output = call_json(
        client=anthropic,
        supabase=supabase,
        model=SONNET_MODEL,
        system_prompt=build_system_prompt(),
        user_prompt=build_user_prompt(
            interest_titles=interest_titles,
            recent_entry_titles=recent_entry_titles,
        ),
        schema=ProposePapersLLMOutput,
        route="/propose-papers",
        user_id=user_id,
        max_tokens=2048,
        request_summary={
            "interest_count": len(interest_titles),
            "recent_entry_count": len(recent_entry_titles),
        },
    )

    # 5. Validate candidate count (3–5); log warning but don't raise 500
    candidate_count = len(llm_output.candidates)
    if candidate_count < 3 or candidate_count > 5:
        logger.warning(
            "/propose-papers returned %d candidates (expected 3–5); continuing with what was returned",
            candidate_count,
        )

    papers_added = 0
    papers_reused = 0
    queue_items_added = 0

    # 6. Process each candidate
    for candidate in llm_output.candidates:
        # a. Ingest (dedup via shared helper)
        try:
            paper_id, created = ingest_paper(
                supabase,
                title=candidate.title,
                authors_json=candidate.authors,
                year=candidate.year,
                abstract_md="",
                arxiv_id=candidate.arxiv_id,
                doi=candidate.doi,
            )
        except Exception:
            logger.warning(
                "/propose-papers: ingest_paper failed for title=%r; skipping",
                candidate.title,
                exc_info=True,
            )
            continue

        if created:
            papers_added += 1
        else:
            papers_reused += 1

        # b. Skip if engagement already exists for this user + paper
        existing_resp = (
            supabase.table("paper_engagements")
            .select("id")
            .eq("user_id", user_id)
            .eq("paper_id", paper_id)
            .limit(1)
            .execute()
        )
        if existing_resp.data:
            logger.debug(
                "/propose-papers: engagement already exists for user=%s paper=%s; skipping",
                user_id,
                paper_id,
            )
            continue

        # c. Generate engagement
        try:
            engagement_id = generate_engagement_for_paper(
                supabase=supabase,
                anthropic=anthropic,
                user_id=user_id,
                paper_id=paper_id,
            )
        except HTTPException:
            logger.warning(
                "/propose-papers: generate_engagement_for_paper failed for paper_id=%s; skipping",
                paper_id,
            )
            continue

        # d. Insert queue item
        supabase.table("queue_items").insert(
            {
                "user_id": user_id,
                "kind": "paper_engagement",
                "ref_id": engagement_id,
                "state": "pending",
                "priority_score": 0.4,
                "added_reason": candidate.rationale,
                "time_estimate_minutes_low": 20,
                "time_estimate_minutes_high": 45,
            }
        ).execute()
        queue_items_added += 1

    return ProposePapersResponse(
        papers_added=papers_added,
        papers_reused=papers_reused,
        queue_items_added=queue_items_added,
    )
