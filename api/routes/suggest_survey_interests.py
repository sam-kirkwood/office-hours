"""POST /survey/suggest-interests — Stage 3 of the onboarding survey.

Returns 6–10 interest-node suggestion tiles based on the user's Stage 1
per-domain background (chips, sub-areas, relationship cards) and Stage 2
foundation marks. Heuristic shortlist + Haiku rerank (see
survey-and-difficulty-design.md §1.4 and docs/phase-plans/phase-10-rev-plan.md
Step 2c).
"""

from __future__ import annotations

import logging
import re
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

# Stage 1 domain chip → database `nodes.domain` value. Engineering /
# computation feed into "applied"; biology / chemistry have no foundation
# tiles yet but their sub-areas still flow into the Haiku prompt.
_CHIP_TO_DB_DOMAIN: dict[str, str] = {
    "mathematics": "math",
    "physics": "physics",
    "engineering": "applied",
    "computation": "applied",
}


def _tokenise(text: str) -> set[str]:
    """Lowercase word tokens of length >= 3 — used for cheap text overlap."""
    return {t for t in re.findall(r"[a-z]+", text.lower()) if len(t) >= 3}


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

    # ---- Project the per-domain input into the signals we use ---------------
    chip_keys = [d.key for d in body.domains]
    db_domains = {
        _CHIP_TO_DB_DOMAIN[k] for k in chip_keys if k in _CHIP_TO_DB_DOMAIN
    }
    # Flat sub-area label list across all picked domains. Used both for the
    # text-overlap heuristic and to render the Haiku prompt's per-domain block.
    all_subarea_labels: list[str] = []
    for d in body.domains:
        all_subarea_labels.extend(d.subarea_labels or [])
    subarea_tokens: set[str] = set()
    for label in all_subarea_labels:
        subarea_tokens |= _tokenise(label)

    # Existing user_interests — never suggest something the user already has.
    existing_resp = (
        supabase.table("user_interests")
        .select("node_id")
        .eq("user_id", user_id)
        .execute()
    )
    existing_interest_ids = {ui["node_id"] for ui in (existing_resp.data or [])}

    # ---- Heuristic shortlist ------------------------------------------------
    nodes_resp = (
        supabase.table("nodes")
        .select("id, slug, title, description_md, domain, kind")
        .eq("kind", "interest")
        .eq("pool_status", "active")
        .execute()
    )
    interest_nodes: list[dict] = nodes_resp.data or []
    if db_domains:
        # Defensive fallback: if no chips map to a db domain (e.g. user picked
        # only bio + chem), keep the whole pool — the Haiku prompt still has
        # the bio/chem signal to rank with.
        scoped = [n for n in interest_nodes if n["domain"] in db_domains]
        if scoped:
            interest_nodes = scoped
    interest_nodes = [n for n in interest_nodes if n["id"] not in existing_interest_ids]

    candidate_ids = [n["id"] for n in interest_nodes]

    prereq_overlap: dict[str, int] = {nid: 0 for nid in candidate_ids}
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
                prereq_overlap[edge["target_node_id"]] += 1

    # Sub-area text overlap: count how many sub-area tokens appear in the
    # node's title or description. Cheap signal but does meaningful work —
    # "condensed-matter" picks up nodes mentioning condensed in their text.
    for n in interest_nodes:
        n["prereq_overlap_count"] = prereq_overlap.get(n["id"], 0)
        if subarea_tokens:
            text = ((n.get("title") or "") + " " + (n.get("description_md") or "")).lower()
            n["subarea_overlap_count"] = sum(
                1 for tok in subarea_tokens if tok in text
            )
        else:
            n["subarea_overlap_count"] = 0

    # Order: combined overlap, prereq weighted slightly higher than sub-area
    # text-match (prereq is structural, sub-area is keyword-y). Then title for
    # a stable secondary sort.
    interest_nodes.sort(
        key=lambda n: (
            -(2 * n["prereq_overlap_count"] + n["subarea_overlap_count"]),
            n["title"].lower(),
        )
    )
    shortlist = interest_nodes[:SHORTLIST_MAX]

    if not shortlist:
        return SuggestSurveyInterestsResponse(suggestions=[])

    # ---- Haiku rerank -------------------------------------------------------
    survey_resp = (
        supabase.table("surveys")
        .select("free_text_intent")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    short_text = (survey_resp.data or [{}])[0].get("free_text_intent") or ""

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
            domains=[d.model_dump() for d in body.domains],
            short_text=short_text,
            marked_foundation_titles=marked_titles,
            shortlist=shortlist,
        ),
        schema=SurveyInterestSuggestionLLMOutput,
        route="survey/suggest-interests",
        user_id=user_id,
        request_summary={
            "shortlist_size": len(shortlist),
            "chips": chip_keys,
            "subarea_count": len(all_subarea_labels),
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

    # No padding fallback. If Haiku ranks fewer than SUGGESTION_MIN, we return
    # the short honest list rather than padding from the unfiltered shortlist
    # with a rationale ("Adjacent to the foundations you flagged.") that is
    # provably false when the in-domain pool was thin. A small in-domain list
    # is better than a padded misleading one; the free-text "Curious about
    # something specific?" input is the safety net for users whose interests
    # the megagraph doesn't yet cover. See Step 9c-ii.
    return SuggestSurveyInterestsResponse(suggestions=suggestions)
