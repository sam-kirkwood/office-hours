"""POST /add-interest — dedup then optionally generate a new interest node.

Flow:
  1. Load all existing nodes as the candidate pool.
  2. Build a title-similarity shortlist (cap 20) to keep the Haiku prompt bounded.
  3. Haiku dedup call. Validate the returned slug is in the candidate set.
  4. 'same' verdict → write user_interests, return immediately.
  5. 'related' or 'new' → Sonnet generates title/slug/description/edges.
  6. INSERT the new node (ON CONFLICT DO NOTHING pattern via exception catch).
     Slug collision → write a curation_proposals merge row; link user to existing node.
  7. Insert prerequisite edges from proposed_prerequisite_slugs (skip unknowns).
     Insert a 'related' edge to the matched node when verdict was 'related'.
  8. Write user_interests row.
  9. Return AddInterestResponse.
"""

from __future__ import annotations

import logging
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from anthropic_client import call_json, get_anthropic_client
from auth import require_internal_token
from config import HAIKU_MODEL, SONNET_MODEL
from prompts import add_interest as prompts
from schemas import (
    AddInterestRequest,
    AddInterestResponse,
    DeduplicationVerdict,
    GeneratedInterestNode,
)
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_DEDUP_CANDIDATES = 20


def _is_unique_violation(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if code in ("23505", 23505):
        return True
    return "23505" in str(exc) or "duplicate key" in str(exc).lower()


def _shortlist(raw_text: str, all_nodes: list[dict]) -> list[dict]:
    """Return up to MAX_DEDUP_CANDIDATES nodes, prioritising those whose title
    or slug share tokens with raw_text. Pads with unmatched nodes so Haiku
    always sees some context even on a completely novel topic."""
    tokens = set(raw_text.lower().split())
    matching, rest = [], []
    for node in all_nodes:
        combined = (node["title"] + " " + node["slug"].replace("-", " ")).lower()
        if any(tok in combined for tok in tokens):
            matching.append(node)
        else:
            rest.append(node)
    return (matching + rest)[:MAX_DEDUP_CANDIDATES]


def _upsert_user_interest(
    supabase: Client, *, user_id: str, node_id: str, added_via: str
) -> UUID:
    """Insert a user_interests row. On unique violation (duplicate add), fetch
    and return the existing row's id."""
    row = {"user_id": user_id, "node_id": node_id, "added_via": added_via}
    try:
        result = supabase.table("user_interests").insert(row).execute()
        return UUID(result.data[0]["id"])
    except Exception as exc:
        if not _is_unique_violation(exc):
            raise
        existing = (
            supabase.table("user_interests")
            .select("id")
            .eq("user_id", user_id)
            .eq("node_id", node_id)
            .limit(1)
            .execute()
        )
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="user_interest unique violation but no row found",
            ) from exc
        return UUID(existing.data[0]["id"])


@router.post(
    "/add-interest",
    response_model=AddInterestResponse,
    dependencies=[Depends(require_internal_token)],
)
def add_interest(
    body: AddInterestRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> AddInterestResponse:
    user_id = str(body.user_id)

    # 1. Load all existing nodes.
    nodes_resp = supabase.table("nodes").select("id, slug, title, description_md").execute()
    all_nodes: list[dict] = nodes_resp.data or []
    existing_slugs = [n["slug"] for n in all_nodes]
    existing_titles = [n["title"] for n in all_nodes]
    slug_to_id = {n["slug"]: n["id"] for n in all_nodes}
    title_to_node = {n["title"].strip().lower(): n for n in all_nodes}

    # 2. Shortlist for dedup prompt.
    candidates = _shortlist(body.raw_text, all_nodes)

    # 3. Haiku dedup call (temperature=0 — classification, not generation).
    verdict: DeduplicationVerdict = call_json(
        client=anthropic,
        supabase=supabase,
        model=HAIKU_MODEL,
        system_prompt=prompts.build_dedup_system_prompt(),
        user_prompt=prompts.build_dedup_user_prompt(body.raw_text, candidates),
        schema=DeduplicationVerdict,
        route="add-interest/dedup",
        user_id=user_id,
        request_summary={"raw_text": body.raw_text[:80], "candidates": len(candidates)},
        temperature=0,
    )

    # Validate matched_node_slug is not hallucinated (must be in the candidate set).
    candidate_slugs = {n["slug"] for n in candidates}
    if verdict.matched_node_slug and verdict.matched_node_slug not in candidate_slugs:
        logger.warning(
            "Haiku dedup returned slug %r not in candidates — treating as 'new'",
            verdict.matched_node_slug,
        )
        verdict = DeduplicationVerdict(
            verdict="new", matched_node_slug=None, reason=verdict.reason
        )

    # 4. 'same' → link user to matched node and return.
    if verdict.verdict == "same" and verdict.matched_node_slug:
        matched = next(
            (n for n in all_nodes if n["slug"] == verdict.matched_node_slug), None
        )
        if matched:
            ui_id = _upsert_user_interest(
                supabase, user_id=user_id, node_id=matched["id"], added_via=body.added_via
            )
            return AddInterestResponse(
                node_id=UUID(matched["id"]),
                node_slug=matched["slug"],
                verdict="same",
                user_interest_id=ui_id,
            )
        # Slug validated but node not found — treat as new (shouldn't happen).
        verdict = DeduplicationVerdict(verdict="new", matched_node_slug=None)

    # 5. 'related' or 'new' → Sonnet generates the new node.
    related_slug = verdict.matched_node_slug if verdict.verdict == "related" else None

    generated: GeneratedInterestNode = call_json(
        client=anthropic,
        supabase=supabase,
        model=SONNET_MODEL,
        system_prompt=prompts.build_generate_system_prompt(),
        user_prompt=prompts.build_generate_user_prompt(
            raw_text=body.raw_text,
            existing_slugs=existing_slugs,
            existing_titles=existing_titles,
            related_slug=related_slug,
        ),
        schema=GeneratedInterestNode,
        route="add-interest/generate",
        user_id=user_id,
        request_summary={"raw_text": body.raw_text[:80], "verdict": verdict.verdict},
    )

    # 6a. Title collision check — Sonnet may ignore the "no duplicate title" instruction.
    # If the generated title matches an existing node (case-insensitive), skip the insert
    # and link the user to the existing node instead.
    title_matched = title_to_node.get(generated.title.strip().lower())
    if title_matched:
        logger.warning(
            "Sonnet generated duplicate title %r (matches slug %r) — linking to existing node",
            generated.title,
            title_matched["slug"],
        )
        try:
            supabase.table("curation_proposals").insert(
                {
                    "kind": "merge",
                    "payload_json": {
                        "slug": generated.slug,
                        "new_title": generated.title,
                        "raw_text": body.raw_text,
                        "user_id": user_id,
                        "reason": "title_collision",
                    },
                }
            ).execute()
        except Exception as exc:
            logger.warning("curation_proposals insert failed: %s", exc)
        ui_id = _upsert_user_interest(
            supabase, user_id=user_id, node_id=title_matched["id"], added_via=body.added_via
        )
        return AddInterestResponse(
            node_id=UUID(title_matched["id"]),
            node_slug=title_matched["slug"],
            verdict=verdict.verdict,
            user_interest_id=ui_id,
        )

    # 6b. Insert node; handle slug collision race.
    node_row = {
        "slug": generated.slug,
        "title": generated.title,
        "description_md": generated.description_md,
        "domain": generated.domain,
        "kind": "interest",
        "difficulty_hint": generated.difficulty_hint,
        "subtopics_json": generated.subtopics,
        "created_by_user_id": user_id,
    }
    node_id: str
    race_collision = False
    try:
        insert_resp = supabase.table("nodes").insert(node_row).execute()
        node_id = insert_resp.data[0]["id"]
    except Exception as exc:
        if not _is_unique_violation(exc):
            raise
        race_collision = True
        existing = (
            supabase.table("nodes")
            .select("id, slug")
            .eq("slug", generated.slug)
            .limit(1)
            .execute()
        )
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="slug collision but existing node not found",
            ) from exc
        node_id = existing.data[0]["id"]
        supabase.table("curation_proposals").insert(
            {
                "kind": "merge",
                "payload_json": {
                    "slug": generated.slug,
                    "new_title": generated.title,
                    "raw_text": body.raw_text,
                    "user_id": user_id,
                },
            }
        ).execute()

    # 7. Insert edges — only when we successfully created the node.
    # In the race-collision path the winning insert already wrote edges; skip.
    if not race_collision:
        edge_rows: list[dict] = []
        for prereq_slug in generated.proposed_prerequisite_slugs:
            prereq_id = slug_to_id.get(prereq_slug)
            if prereq_id:
                edge_rows.append(
                    {
                        "source_node_id": prereq_id,
                        "target_node_id": node_id,
                        "edge_kind": "prerequisite",
                    }
                )
        if related_slug:
            related_id = slug_to_id.get(related_slug)
            if related_id and related_id != node_id:
                edge_rows.append(
                    {
                        "source_node_id": related_id,
                        "target_node_id": node_id,
                        "edge_kind": "related",
                    }
                )
        if edge_rows:
            try:
                supabase.table("edges").insert(edge_rows).execute()
            except Exception as exc:
                if not _is_unique_violation(exc):
                    raise

    # 8. Write user_interests.
    ui_id = _upsert_user_interest(
        supabase, user_id=user_id, node_id=node_id, added_via=body.added_via
    )

    return AddInterestResponse(
        node_id=UUID(node_id),
        node_slug=generated.slug,
        verdict=verdict.verdict,
        user_interest_id=ui_id,
    )
