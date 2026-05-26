"""POST /survey/suggest-interests — Stage 3 of the onboarding survey.

Returns 6–10 interest-node suggestion tiles based on the user's Stage 1
domain chips, Stage 2 foundation marks, and the megagraph's prerequisite
edges. Heuristic shortlist + Haiku rerank (see
survey-and-difficulty-design.md §1.4 and docs/phase-plans/phase-10-rev-plan.md
Step 2c).
"""

from __future__ import annotations

import logging
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, Depends
from supabase import Client

from anthropic_client import call_json, get_anthropic_client
from auth import require_internal_token
from config import HAIKU_MODEL
from prompts.suggest_survey_interests import build_system_prompt, build_user_prompt
from schemas import (
    SuggestSurveyInterestsRequest,
    SuggestSurveyInterestsResponse,
    SurveyInterestSuggestion,
    SurveyInterestSuggestionLLMOutput,
)
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter()

SHORTLIST_MAX = 20
SUGGESTION_MIN = 6
SUGGESTION_MAX = 10


@router.post(
    "/survey/suggest-interests",
    response_model=SuggestSurveyInterestsResponse,
    dependencies=[Depends(require_internal_token)],
)
def suggest_survey_interests(
    body: SuggestSurveyInterestsRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> SuggestSurveyInterestsResponse:
    user_id = str(body.user_id)
    marked_ids = {str(nid) for nid in body.marked_foundation_node_ids}
    domain_chips = [d.strip() for d in body.domain_chips if d and d.strip()]

    # Load the user's existing interests so we don't re-suggest something
    # they've already accepted in an earlier add-interest segment.
    existing_resp = (
        supabase.table("user_interests")
        .select("node_id")
        .eq("user_id", user_id)
        .execute()
    )
    existing_interest_ids = {ui["node_id"] for ui in (existing_resp.data or [])}

    # ---- Heuristic shortlist ------------------------------------------------
    # All interest-kind nodes; filter to ones whose domain matches the chips
    # (or all of them if no chips were selected — defensive fallback).
    nodes_resp = (
        supabase.table("nodes")
        .select("id, slug, title, description_md, domain, kind")
        .eq("kind", "interest")
        .eq("pool_status", "active")
        .execute()
    )
    interest_nodes: list[dict] = nodes_resp.data or []
    if domain_chips:
        interest_nodes = [n for n in interest_nodes if n["domain"] in domain_chips]
    interest_nodes = [n for n in interest_nodes if n["id"] not in existing_interest_ids]

    candidate_ids = [n["id"] for n in interest_nodes]

    # Score each candidate by the count of prerequisite edges from a
    # marked-foundation node into it.
    overlap_count: dict[str, int] = {nid: 0 for nid in candidate_ids}
    if candidate_ids and marked_ids:
        edges_resp = (
            supabase.table("edges")
            .select("source_node_id, target_node_id, edge_kind")
            .eq("edge_kind", "prerequisite")
            .in_("target_node_id", candidate_ids)
            .execute()
        )
        for edge in edges_resp.data or []:
            if edge["source_node_id"] in marked_ids:
                overlap_count[edge["target_node_id"]] += 1

    for n in interest_nodes:
        n["prereq_overlap_count"] = overlap_count.get(n["id"], 0)

    # Order: prereq overlap first, then title for stable secondary sort.
    interest_nodes.sort(
        key=lambda n: (-n["prereq_overlap_count"], n["title"].lower())
    )
    shortlist = interest_nodes[:SHORTLIST_MAX]

    if not shortlist:
        return SuggestSurveyInterestsResponse(suggestions=[])

    # ---- Haiku rerank -------------------------------------------------------
    # Load the user's surveys row for background context (relationship cards,
    # short text). The route is called from the Stage 3 page, which has
    # already persisted Stage 1 + 2.
    survey_resp = (
        supabase.table("surveys")
        .select("background_json, free_text_intent")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    survey_row = (survey_resp.data or [{}])[0]
    background = survey_row.get("background_json") or {}
    relationship_cards = list(background.get("relationship_cards") or [])
    short_text = survey_row.get("free_text_intent") or ""

    marked_titles: list[str] = []
    if marked_ids:
        marked_resp = (
            supabase.table("nodes")
            .select("title")
            .in_("id", list(marked_ids))
            .execute()
        )
        marked_titles = [n["title"] for n in (marked_resp.data or [])]

    llm_output: SurveyInterestSuggestionLLMOutput = call_json(
        client=anthropic,
        supabase=supabase,
        model=HAIKU_MODEL,
        system_prompt=build_system_prompt(),
        user_prompt=build_user_prompt(
            domain_chips=domain_chips,
            relationship_cards=relationship_cards,
            short_text=short_text,
            marked_foundation_titles=marked_titles,
            shortlist=shortlist,
        ),
        schema=SurveyInterestSuggestionLLMOutput,
        route="survey/suggest-interests",
        user_id=user_id,
        request_summary={
            "shortlist_size": len(shortlist),
            "domain_chips": domain_chips,
            "marked_foundations": len(marked_ids),
        },
        temperature=0,
    )

    # Validate Haiku's slugs against the shortlist; drop hallucinations.
    slug_to_node = {n["slug"]: n for n in shortlist}
    suggestions: list[SurveyInterestSuggestion] = []
    seen: set[str] = set()
    for entry in llm_output.suggestions:
        slug = entry.get("slug")
        why = (entry.get("why_suggested_md") or "").strip()
        if not slug or slug in seen or slug not in slug_to_node:
            if slug and slug not in slug_to_node:
                logger.warning("Haiku returned unknown slug %r — dropping", slug)
            continue
        seen.add(slug)
        node = slug_to_node[slug]
        suggestions.append(
            SurveyInterestSuggestion(
                node_id=UUID(node["id"]),
                slug=node["slug"],
                title=node["title"],
                description_md=node.get("description_md") or "",
                why_suggested_md=why,
            )
        )
        if len(suggestions) >= SUGGESTION_MAX:
            break

    # Belt-and-braces: if Haiku came up short, pad from the heuristic
    # shortlist in score order, with a neutral fallback rationale.
    if len(suggestions) < SUGGESTION_MIN:
        for node in shortlist:
            if node["slug"] in seen:
                continue
            suggestions.append(
                SurveyInterestSuggestion(
                    node_id=UUID(node["id"]),
                    slug=node["slug"],
                    title=node["title"],
                    description_md=node.get("description_md") or "",
                    why_suggested_md="Adjacent to the foundations you flagged.",
                )
            )
            seen.add(node["slug"])
            if len(suggestions) >= SUGGESTION_MIN:
                break

    return SuggestSurveyInterestsResponse(suggestions=suggestions)
