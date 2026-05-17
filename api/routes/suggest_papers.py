"""POST /suggest-papers — find relevant papers for a user, pre-generate
engagements, and insert queue_items.

Flow:
  1. Auth check.
  2. Load user_interests → node titles.
  3. Load all papers. If none → return empty list (skip Haiku call).
  4. Haiku call: score relevance; return up to 3 relevant paper_ids.
  5. For each shortlisted paper, skip if paper_engagement already exists for
     (user, paper) in any state.
  6. For each new paper: call generate_engagement_for_paper; insert queue_item.
  7. Return list of {paper_id, queue_item_id}.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from anthropic_client import call_json, get_anthropic_client
from auth import require_internal_token
from config import HAIKU_MODEL
from routes.generate_paper_engagement import generate_engagement_for_paper
from schemas import SuggestedPaper, SuggestPapersRequest, SuggestPapersResponse
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_SUGGESTIONS = 3


class _RelevanceResult(BaseModel):
    relevant_paper_ids: list[str]


def _build_relevance_prompt(
    *,
    papers: list[dict],
    interest_titles: list[str],
) -> str:
    interests_str = ", ".join(interest_titles) if interest_titles else "(no interests recorded)"
    papers_block = "\n".join(
        f"- id={p['id']} title={p.get('title', '')} abstract: {(p.get('abstract_md') or '')[:300]}"
        for p in papers
    )
    return (
        f"User interests: {interests_str}\n\n"
        "Papers available:\n"
        f"{papers_block}\n\n"
        f"Return the ids of the most relevant papers (at most {MAX_SUGGESTIONS}). "
        "Only include papers that genuinely relate to at least one of the user's interests. "
        'Respond with JSON: {"relevant_paper_ids": ["<id1>", ...]}'
    )


@router.post(
    "/suggest-papers",
    response_model=SuggestPapersResponse,
    dependencies=[Depends(require_internal_token)],
)
def suggest_papers(
    body: SuggestPapersRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> SuggestPapersResponse:
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

    # 3. Load papers — pre-filter by ILIKE across ALL interest titles (F16: ILIKE ANY).
    # Cap the candidate set at 20 rows before passing to Haiku.
    if interest_titles:
        filter_parts = [f"title.ilike.%{t}%" for t in interest_titles]
        papers_resp = (
            supabase.table("papers")
            .select("id, title, abstract_md")
            .or_(",".join(filter_parts))
            .limit(20)
            .execute()
        )
        if not papers_resp.data:
            # No title match on any interest — load any papers up to the cap
            papers_resp = (
                supabase.table("papers")
                .select("id, title, abstract_md")
                .limit(20)
                .execute()
            )
    else:
        papers_resp = (
            supabase.table("papers")
            .select("id, title, abstract_md")
            .limit(20)
            .execute()
        )
    papers: list[dict] = papers_resp.data or []

    if not papers:
        return SuggestPapersResponse(suggested=[])

    # 4. Haiku relevance call
    relevance = call_json(
        client=anthropic,
        supabase=supabase,
        model=HAIKU_MODEL,
        system_prompt=(
            "You are a relevance classifier. Given a list of papers and a user's interests, "
            "return only the ids of papers that are genuinely relevant. "
            'Output JSON: {"relevant_paper_ids": ["id1", ...]}'
        ),
        user_prompt=_build_relevance_prompt(papers=papers, interest_titles=interest_titles),
        schema=_RelevanceResult,
        route="/suggest-papers",
        user_id=user_id,
        max_tokens=256,
        temperature=0,
        request_summary={"paper_count": len(papers), "interest_count": len(interest_titles)},
    )

    shortlisted_ids = relevance.relevant_paper_ids[:MAX_SUGGESTIONS]

    # 5. Filter papers the user already has an engagement for (any state)
    if shortlisted_ids:
        existing_resp = (
            supabase.table("paper_engagements")
            .select("paper_id")
            .eq("user_id", user_id)
            .in_("paper_id", shortlisted_ids)
            .execute()
        )
        existing_paper_ids = {row["paper_id"] for row in (existing_resp.data or [])}
        shortlisted_ids = [pid for pid in shortlisted_ids if pid not in existing_paper_ids]

    # 6. Generate engagement + queue item for each new paper
    paper_by_id = {p["id"]: p for p in papers}
    suggested: list[SuggestedPaper] = []

    for paper_id in shortlisted_ids:
        paper = paper_by_id.get(paper_id)
        if paper is None:
            logger.warning("Haiku returned paper_id=%s not in loaded papers; skipping", paper_id)
            continue

        try:
            engagement_id = generate_engagement_for_paper(
                supabase=supabase,
                anthropic=anthropic,
                user_id=user_id,
                paper_id=paper_id,
            )
        except HTTPException:
            logger.warning("generate_engagement_for_paper failed for paper_id=%s; skipping", paper_id)
            continue

        # #23: skip if a queue item for this engagement already exists (concurrent dedup)
        existing_qi_resp = (
            supabase.table("queue_items")
            .select("id")
            .eq("user_id", user_id)
            .eq("kind", "paper_engagement")
            .eq("ref_id", engagement_id)
            .in_("state", ["pending", "surfaced", "in_progress"])
            .limit(1)
            .execute()
        )
        if existing_qi_resp.data:
            logger.debug("queue item already exists for engagement_id=%s; skipping", engagement_id)
            queue_item_id = existing_qi_resp.data[0]["id"]
        else:
            interest_label = (
                " and ".join(interest_titles[:2]) if interest_titles else "your interests"
            )
            queue_resp = (
                supabase.table("queue_items")
                .insert(
                    {
                        "user_id": user_id,
                        "kind": "paper_engagement",
                        "ref_id": engagement_id,
                        "state": "pending",
                        "priority_score": 0.4,
                        "added_reason": f"A paper related to your interest in {interest_label}",
                        "time_estimate_minutes_low": 20,
                        "time_estimate_minutes_high": 45,
                    }
                )
                .execute()
            )
            queue_item_id = queue_resp.data[0]["id"]
        suggested.append(
            SuggestedPaper(paper_id=UUID(paper_id), queue_item_id=UUID(queue_item_id))
        )

    return SuggestPapersResponse(suggested=suggested)
