"""Add-interest dialog routes.

Two endpoints implement the dialog specified in
docs/survey-and-difficulty-design.md §2:

  POST /add-interest/parse
    Read-only. Haiku splits the raw text into one or more interest segments,
    classifies each as specific|ambiguous, infers implicit intent, and
    deduplicates each segment against a candidate slice of the megagraph.
    Returns mirror-back text and (for ambiguous segments) path options.
    No database writes.

  POST /add-interest/resolve
    Commits one resolved interest segment. The client passes the final
    intent text, the soft intent_context, and at most one of:
      - existing_node_slug → link to that node, no Sonnet call.
      - related_node_slug  → generate a new node + 'related' edge.
      - neither            → generate a new standalone node.
    Writes the user_interests row with intent_context populated. Returns a
    starter preview string and a 6–10 tile concept tour for stage 5 of the
    onboarding survey.

Multi-interest input from /parse → the client calls /resolve once per
segment so the concept tours can be deduplicated across the sequence
(survey-and-difficulty-design.md §1.6.5).
"""

from __future__ import annotations

import logging
import re
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from anthropic_client import call_json, get_anthropic_client
from auth import require_internal_token
from config import HAIKU_MODEL, SONNET_MODEL
from prompts import add_interest as prompts
from schemas import (
    ConceptTourTile,  # retained for backward-compat; not used in resolve response
    DedupVerdict,
    GeneratedInterestNode,
    NodeReadinessTile,
    NodeReadinessSubmitRequest,
    ParseAddInterestRequest,
    ParseAddInterestResponse,
    ParsedInterestPayload,
    ParsedInterestSegment,
    PathOption,
    ResolveAddInterestRequest,
    ResolveAddInterestResponse,
    RewriteIntentSummariesLLMOutput,
    RewriteIntentSummariesRequest,
    RewriteIntentSummariesResponse,
)
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_DEDUP_CANDIDATES = 20
CONCEPT_TOUR_MIN = 6
CONCEPT_TOUR_MAX = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_unique_violation(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if code in ("23505", 23505):
        return True
    return "23505" in str(exc) or "duplicate key" in str(exc).lower()


def _shortlist(raw_text: str, all_nodes: list[dict]) -> list[dict]:
    """Up to MAX_DEDUP_CANDIDATES nodes ranked by token overlap with raw_text.
    Always padded with unmatched nodes so Haiku sees some breadth even on a
    completely novel topic."""
    tokens = {t for t in raw_text.lower().split() if len(t) > 2}
    matching, rest = [], []
    for node in all_nodes:
        combined = (node["title"] + " " + node["slug"].replace("-", " ")).lower()
        if any(tok in combined for tok in tokens):
            matching.append(node)
        else:
            rest.append(node)
    return (matching + rest)[:MAX_DEDUP_CANDIDATES]


_SLUG_PUNCT_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    s = _SLUG_PUNCT_RE.sub("-", text.lower()).strip("-")
    return s or "untitled"


def _subtopic_entries(subtopics_json: object) -> list[dict[str, str]]:
    """nodes.subtopics_json contains either bare strings (newer interest nodes)
    or {slug, title} dicts (seeded foundation nodes). Normalise to a list of
    {name, gloss} dicts where gloss may be empty."""
    if not isinstance(subtopics_json, list):
        return []
    entries: list[dict[str, str]] = []
    for raw in subtopics_json:
        if isinstance(raw, str):
            entries.append({"name": raw, "gloss": ""})
        elif isinstance(raw, dict):
            name = raw.get("title") or raw.get("name") or raw.get("slug") or ""
            if not name:
                continue
            entries.append({"name": str(name), "gloss": str(raw.get("gloss", ""))})
    return entries


def _validate_dedup_slugs(
    segments: list[ParsedInterestSegment], candidate_slugs: set[str]
) -> list[ParsedInterestSegment]:
    """Drop hallucinated slugs from segment.dedup so the client never sees a
    slug we don't actually have."""
    cleaned: list[ParsedInterestSegment] = []
    for seg in segments:
        if seg.dedup.matched_node_slug and seg.dedup.matched_node_slug not in candidate_slugs:
            logger.warning(
                "Haiku parse returned unknown slug %r for segment %r — dropping to 'new'",
                seg.dedup.matched_node_slug,
                seg.raw_text_segment[:60],
            )
            seg = seg.model_copy(
                update={"dedup": DedupVerdict(verdict="new", matched_node_slug=None)}
            )
        cleaned.append(seg)
    return cleaned


def _validate_path_leans_on(
    segments: list[ParsedInterestSegment], all_slug_set: set[str]
) -> list[ParsedInterestSegment]:
    """Drop hallucinated leans_on_prereq_slugs from each path option.

    Validated against ALL nodes (not just the shortlist candidates) because
    foundation prerequisite slugs — e.g. 'calculus', 'linear-algebra' — may
    not appear in the 20-node shortlist selected for the typed topic."""
    cleaned: list[ParsedInterestSegment] = []
    for seg in segments:
        cleaned_opts = []
        for opt in seg.path_options:
            bad = [s for s in opt.leans_on_prereq_slugs if s not in all_slug_set]
            if bad:
                logger.warning(
                    "Haiku path %r for segment %r has unknown leans_on slugs %r — dropping them",
                    opt.key,
                    seg.raw_text_segment[:60],
                    bad,
                )
                opt = opt.model_copy(
                    update={
                        "leans_on_prereq_slugs": [
                            s for s in opt.leans_on_prereq_slugs if s in all_slug_set
                        ]
                    }
                )
            cleaned_opts.append(opt)
        cleaned.append(seg.model_copy(update={"path_options": cleaned_opts}))
    return cleaned


def _fetch_node_by_slug(supabase: Client, slug: str) -> dict | None:
    resp = (
        supabase.table("nodes")
        .select("id, slug, title, kind, subtopics_json")
        .eq("slug", slug)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def _upsert_user_interest(
    supabase: Client,
    *,
    user_id: str,
    node_id: str,
    added_via: str,
    intent_context: str,
    path_json: dict | None = None,
    altitude: str | None = None,
) -> UUID:
    """Insert a user_interests row with intent_context, path_json (Phase 13
    Step 2), and altitude (Phase 13 Step 3). On unique violation (duplicate
    add), refresh all three columns and return the existing row's id."""
    row: dict = {
        "user_id": user_id,
        "node_id": node_id,
        "added_via": added_via,
        "intent_context": intent_context,
        "path_json": path_json,
        "altitude": altitude,
    }
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
        ui_id = existing.data[0]["id"]
        # Refresh intent_context, path_json, and altitude — the user just
        # resolved this interest again and may have updated any of these.
        supabase.table("user_interests").update(
            {"intent_context": intent_context, "path_json": path_json, "altitude": altitude}
        ).eq("id", ui_id).execute()
        return UUID(ui_id)


# ---------------------------------------------------------------------------
# /add-interest/parse
# ---------------------------------------------------------------------------


@router.post(
    "/add-interest/parse",
    response_model=ParseAddInterestResponse,
    dependencies=[Depends(require_internal_token)],
)
def parse_add_interest(
    body: ParseAddInterestRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> ParseAddInterestResponse:
    user_id = str(body.user_id)

    nodes_resp = (
        supabase.table("nodes").select("id, slug, title, kind, description_md").execute()
    )
    all_nodes: list[dict] = nodes_resp.data or []
    candidates = _shortlist(body.raw_text, all_nodes)
    candidate_slugs = {n["slug"] for n in candidates}

    payload: ParsedInterestPayload = call_json(
        client=anthropic,
        supabase=supabase,
        model=HAIKU_MODEL,
        system_prompt=prompts.build_parse_system_prompt(),
        user_prompt=prompts.build_parse_user_prompt(body.raw_text, candidates),
        schema=ParsedInterestPayload,
        route="add-interest/parse",
        user_id=user_id,
        request_summary={
            "raw_text": body.raw_text[:80],
            "candidates": len(candidates),
        },
        temperature=0,
    )

    all_slug_set = {n["slug"] for n in all_nodes}
    segments = _validate_dedup_slugs(payload.segments, candidate_slugs)
    segments = _validate_path_leans_on(segments, all_slug_set)

    # Belt-and-braces: clamp specificity-shaped fields. Haiku occasionally puts
    # path_options on a 'specific' segment or leaves them empty on 'ambiguous'.
    cleaned: list[ParsedInterestSegment] = []
    for seg in segments:
        update: dict = {}
        if seg.specificity == "specific":
            update["path_options"] = []
            if not seg.optional_followup_md:
                update["optional_followup_md"] = (
                    "Want to tell me more about what draws you to this?"
                )
        elif seg.specificity == "ambiguous":
            update["optional_followup_md"] = None
        cleaned.append(seg.model_copy(update=update) if update else seg)

    return ParseAddInterestResponse(segments=cleaned)


# ---------------------------------------------------------------------------
# /add-interest/resolve
# ---------------------------------------------------------------------------


@router.post(
    "/add-interest/resolve",
    response_model=ResolveAddInterestResponse,
    dependencies=[Depends(require_internal_token)],
)
def resolve_add_interest(
    body: ResolveAddInterestRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> ResolveAddInterestResponse:
    user_id = str(body.user_id)

    if body.existing_node_slug and body.related_node_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="existing_node_slug and related_node_slug are mutually exclusive",
        )

    nodes_resp = (
        supabase.table("nodes")
        .select("id, slug, title, kind, subtopics_json")
        .execute()
    )
    all_nodes: list[dict] = nodes_resp.data or []
    slug_to_node = {n["slug"]: n for n in all_nodes}
    title_to_node = {n["title"].strip().lower(): n for n in all_nodes}
    all_slug_set = {n["slug"] for n in all_nodes}

    # Validate and clean path_json.leans_on_prereq_slugs against the real
    # megagraph. The client validated at parse time, but the resolve call is
    # the authority — a stale client or a crafted request could send bad slugs.
    path_json = body.path_json
    if path_json is not None:
        raw_leans_on = path_json.get("leans_on_prereq_slugs") or []
        cleaned_leans_on = [s for s in raw_leans_on if s in all_slug_set]
        bad = [s for s in raw_leans_on if s not in all_slug_set]
        if bad:
            logger.warning(
                "resolve: path_json.leans_on_prereq_slugs contains unknown slugs %r — dropping",
                bad,
            )
        path_json = {**path_json, "leans_on_prereq_slugs": cleaned_leans_on}

    # --- Case 1: link to an existing node (verdict='same' from /parse) ------
    if body.existing_node_slug:
        existing = slug_to_node.get(body.existing_node_slug)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"existing_node_slug {body.existing_node_slug!r} not found",
            )
        ui_id = _upsert_user_interest(
            supabase,
            user_id=user_id,
            node_id=existing["id"],
            added_via=body.added_via,
            intent_context=body.intent_context,
            path_json=path_json,
            altitude=body.altitude,
        )
        starter = _starter_preview_for_existing(existing)
        readiness = _node_readiness_tiles(
            supabase, node_id=existing["id"], path_json=path_json, all_nodes=all_nodes
        )
        return ResolveAddInterestResponse(
            user_interest_id=ui_id,
            node_id=UUID(existing["id"]),
            node_slug=existing["slug"],
            verdict="same",
            intent_context=body.intent_context,
            starter_preview_md=starter,
            node_readiness=readiness,
        )

    # --- Case 2 + 3: generate a new node ------------------------------------
    related_slug = body.related_node_slug
    if related_slug and related_slug not in slug_to_node:
        logger.warning(
            "related_node_slug %r not in megagraph — dropping the 'related' edge hint",
            related_slug,
        )
        related_slug = None

    existing_slugs = [n["slug"] for n in all_nodes]
    existing_titles = [n["title"] for n in all_nodes]

    generated: GeneratedInterestNode = call_json(
        client=anthropic,
        supabase=supabase,
        model=SONNET_MODEL,
        system_prompt=prompts.build_generate_system_prompt(),
        user_prompt=prompts.build_generate_user_prompt(
            final_intent_text=body.final_intent_text,
            intent_context=body.intent_context,
            existing_slugs=existing_slugs,
            existing_titles=existing_titles,
            related_slug=related_slug,
        ),
        schema=GeneratedInterestNode,
        route="add-interest/resolve",
        user_id=user_id,
        request_summary={
            "final_intent_text": body.final_intent_text[:80],
            "verdict": "related" if related_slug else "new",
        },
    )

    # Title collision — Sonnet ignored "must be case-insensitively distinct".
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
                        "final_intent_text": body.final_intent_text,
                        "user_id": user_id,
                        "reason": "title_collision",
                    },
                }
            ).execute()
        except Exception as exc:
            logger.warning("curation_proposals insert failed: %s", exc)
        ui_id = _upsert_user_interest(
            supabase,
            user_id=user_id,
            node_id=title_matched["id"],
            added_via=body.added_via,
            intent_context=body.intent_context,
            path_json=path_json,
            altitude=body.altitude,
        )
        readiness = _node_readiness_tiles(
            supabase, node_id=title_matched["id"], path_json=path_json, all_nodes=all_nodes
        )
        return ResolveAddInterestResponse(
            user_interest_id=ui_id,
            node_id=UUID(title_matched["id"]),
            node_slug=title_matched["slug"],
            verdict="same",  # we collapsed into the existing node
            intent_context=body.intent_context,
            starter_preview_md=_starter_preview_for_existing(title_matched),
            node_readiness=readiness,
        )

    # Insert the new node, handling slug collision races.
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
    race_collision = False
    try:
        insert_resp = supabase.table("nodes").insert(node_row).execute()
        node_id = insert_resp.data[0]["id"]
    except Exception as exc:
        if not _is_unique_violation(exc):
            raise
        race_collision = True
        existing = _fetch_node_by_slug(supabase, generated.slug)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="slug collision but existing node not found",
            ) from exc
        node_id = existing["id"]
        supabase.table("curation_proposals").insert(
            {
                "kind": "merge",
                "payload_json": {
                    "slug": generated.slug,
                    "new_title": generated.title,
                    "raw_text": body.raw_text,
                    "final_intent_text": body.final_intent_text,
                    "user_id": user_id,
                },
            }
        ).execute()

    if not race_collision:
        edge_rows: list[dict] = []
        for prereq_slug in generated.proposed_prerequisite_slugs:
            prereq = slug_to_node.get(prereq_slug)
            if prereq:
                edge_rows.append(
                    {
                        "source_node_id": prereq["id"],
                        "target_node_id": node_id,
                        "edge_kind": "prerequisite",
                    }
                )
        if related_slug:
            related = slug_to_node.get(related_slug)
            if related and related["id"] != node_id:
                edge_rows.append(
                    {
                        "source_node_id": related["id"],
                        "target_node_id": node_id,
                        "edge_kind": "related",
                    }
                )
        # Insert edges one at a time. A batched insert rolls the whole
        # batch back if any single row collides with an existing edge —
        # which silently orphaned new interest nodes whenever the resolved
        # related_slug also appeared in proposed_prerequisite_slugs (the
        # second row 23505'd and took the first row down with it). Per-row
        # inserts isolate the collision and leave a breadcrumb.
        for edge_row in edge_rows:
            try:
                supabase.table("edges").insert(edge_row).execute()
            except Exception as exc:
                if not _is_unique_violation(exc):
                    raise
                logger.warning(
                    "edge insert skipped (unique violation): %s -> %s (%s)",
                    edge_row["source_node_id"],
                    edge_row["target_node_id"],
                    edge_row["edge_kind"],
                )

    ui_id = _upsert_user_interest(
        supabase,
        user_id=user_id,
        node_id=node_id,
        added_via=body.added_via,
        intent_context=body.intent_context,
        path_json=path_json,
        altitude=body.altitude,
    )

    verdict = "related" if related_slug else "new"
    starter = (
        f"Your first item will be: {generated.entry_point_preview_md}".rstrip(".") + "."
    )
    readiness = _node_readiness_tiles(
        supabase, node_id=node_id, path_json=path_json, all_nodes=all_nodes
    )
    return ResolveAddInterestResponse(
        user_interest_id=ui_id,
        node_id=UUID(node_id),
        node_slug=generated.slug,
        verdict=verdict,
        intent_context=body.intent_context,
        starter_preview_md=starter,
        node_readiness=readiness,
    )


# ---------------------------------------------------------------------------
# Node-readiness + starter preview helpers (Phase 13 Step 3)
# ---------------------------------------------------------------------------

NODE_READINESS_MAX = 8  # max prereq nodes shown in the readiness pass
NODE_DESCRIPTION_PREVIEW_LEN = 120  # chars to show as the node preview


def _starter_preview_for_existing(node: dict) -> str:
    """When the resolved interest links to an existing node, we don't have
    a Sonnet-generated entry-point preview. Compose a generic one that the
    next UI session can live with until the curriculum curator (Step 3)
    surfaces real queue items."""
    title = node.get("title", "this topic")
    return f"Your first item will be: a conceptual entrance to {title}."


def _node_readiness_tiles(
    supabase: Client,
    *,
    node_id: str,
    path_json: dict | None,
    all_nodes: list[dict],
) -> list[NodeReadinessTile]:
    """Build up to NODE_READINESS_MAX node-level tiles for the coarse
    readiness pass (Phase 13 Step 3 §B1/§B3).

    Replaces the subtopic-level ConceptTour. Two paths for prereq scope:

    1. path_json.leans_on_prereq_slugs is set (user picked a path in Step 2):
       use those slugs — they include both foundation and interest-kind nodes
       (e.g. SR/GR for an astrophysics path). This is the explicit fix for
       the foundations-only blind spot in the old _concept_tour: interest-kind
       prereqs like Special Relativity MUST appear here.

    2. Fallback (leans_on absent/empty): walk the node's prerequisite edges and
       include ALL prereq kinds (foundation + interest). The old _concept_tour
       only used foundations as primary; this pass includes everything.
    """
    nodes_by_id = {n["id"]: n for n in all_nodes}
    slug_to_node = {n["slug"]: n for n in all_nodes}

    # --- Scope prereqs via path_json.leans_on_prereq_slugs if available -----
    leans_on: list[str] = (path_json or {}).get("leans_on_prereq_slugs") or []
    if leans_on:
        prereqs = [slug_to_node[s] for s in leans_on if s in slug_to_node]
    else:
        # Fallback: walk the node's actual prereq edges — ALL kinds
        edges_resp = (
            supabase.table("edges")
            .select("source_node_id")
            .eq("target_node_id", node_id)
            .eq("edge_kind", "prerequisite")
            .execute()
        )
        prereq_ids = [e["source_node_id"] for e in (edges_resp.data or [])]
        prereqs = [nodes_by_id[i] for i in prereq_ids if i in nodes_by_id]

    tiles: list[NodeReadinessTile] = []
    for prereq in prereqs[:NODE_READINESS_MAX]:
        desc = prereq.get("description_md") or ""
        preview = desc[:NODE_DESCRIPTION_PREVIEW_LEN] if desc else None
        tiles.append(
            NodeReadinessTile(
                node_id=UUID(prereq["id"]),
                node_slug=prereq["slug"],
                node_title=prereq["title"],
                node_description_preview=preview,
            )
        )
    return tiles


# Retained for backward-compat with older survey code that may still call
# the round-robin subtopic helper directly in tests. Not used in the resolve
# response after Phase 13 Step 3.
def _round_robin_tiles(
    nodes: list[dict],
    *,
    limit: int,
    seen: set[tuple[str, str]],
) -> list[ConceptTourTile]:
    tiles: list[ConceptTourTile] = []
    if limit <= 0:
        return tiles
    per_node = [(n, _subtopic_entries(n.get("subtopics_json"))) for n in nodes]
    max_len = max((len(entries) for _, entries in per_node), default=0)
    for idx in range(max_len):
        for node, entries in per_node:
            if idx >= len(entries):
                continue
            entry = entries[idx]
            subtopic_key = _slugify(entry["name"])
            dedup_key = (node["id"], subtopic_key)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            tiles.append(
                ConceptTourTile(
                    node_id=UUID(node["id"]),
                    node_slug=node["slug"],
                    subtopic_key=subtopic_key,
                    name=entry["name"],
                    gloss=entry["gloss"] or None,
                )
            )
            if len(tiles) >= limit:
                return tiles
    return tiles


# ---------------------------------------------------------------------------
# /add-interest/node-readiness  (Phase 13 Step 3)
# ---------------------------------------------------------------------------

_NODE_READINESS_STATE_MAP = {
    "solid": "comfortable",
    "rusty": "active",
    "new": "unseen",
}


@router.post(
    "/add-interest/node-readiness",
    status_code=204,
    dependencies=[Depends(require_internal_token)],
)
def submit_node_readiness(
    body: NodeReadinessSubmitRequest,
    supabase: Client = Depends(get_supabase_client),
) -> None:
    """Write node-level user_node_states from the coarse readiness pass.

    Maps user-facing labels (solid/rusty/new) to DB states
    (comfortable/active/unseen) and upserts one row per answered node.
    The upsert key is (user_id, node_id) — existing rows from Stage 2
    foundation tiles or engagement are updated in place rather than
    duplicated.
    """
    user_id = str(body.user_id)
    for item in body.node_states:
        db_state = _NODE_READINESS_STATE_MAP.get(item.state)
        if db_state is None:
            logger.warning(
                "node-readiness: unknown state %r for node %s — skipping",
                item.state,
                item.node_id,
            )
            continue
        try:
            supabase.table("user_node_states").upsert(
                {
                    "user_id": user_id,
                    "node_id": str(item.node_id),
                    "state": db_state,
                },
                on_conflict="user_id,node_id",
            ).execute()
        except Exception as exc:
            logger.warning(
                "node-readiness: upsert failed for node %s: %s",
                item.node_id,
                exc,
            )


# ---------------------------------------------------------------------------
# /add-interest/rewrite-summaries
# ---------------------------------------------------------------------------
# Backfill endpoint for cleaning up tag-soup intent_context values produced
# by the older parse prompt. Single batch Haiku call → list of rewritten
# user-facing prose summaries. The web orchestrator at
# /api/profile/regenerate-summaries fetches the user's interests, calls this,
# and writes the results back.


@router.post(
    "/add-interest/rewrite-summaries",
    response_model=RewriteIntentSummariesResponse,
    dependencies=[Depends(require_internal_token)],
)
def rewrite_intent_summaries(
    body: RewriteIntentSummariesRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> RewriteIntentSummariesResponse:
    if not body.items:
        return RewriteIntentSummariesResponse(summaries=[])

    items_payload = [
        {
            "user_interest_id": str(it.user_interest_id),
            "node_title": it.node_title,
            "node_description_md": it.node_description_md or "",
            "subtopics": it.subtopics,
            "current_context": it.current_context,
        }
        for it in body.items
    ]

    output: RewriteIntentSummariesLLMOutput = call_json(
        client=anthropic,
        supabase=supabase,
        model=HAIKU_MODEL,
        system_prompt=prompts.build_rewrite_summary_system_prompt(),
        user_prompt=prompts.build_rewrite_summary_user_prompt(items_payload),
        schema=RewriteIntentSummariesLLMOutput,
        route="add-interest/rewrite-summaries",
        user_id=str(body.user_id),
        request_summary={"count": len(items_payload)},
        temperature=0,
    )

    # Belt-and-braces: if Haiku skipped or duplicated entries, align by id and
    # fill in the missing ones from the originals so the caller can write back
    # without surprises.
    by_id = {str(s.user_interest_id): s.summary for s in output.summaries}
    aligned: list = []
    for it in body.items:
        sid = str(it.user_interest_id)
        if sid in by_id:
            aligned.append(
                {"user_interest_id": it.user_interest_id, "summary": by_id[sid]}
            )
        else:
            logger.warning(
                "rewrite-summaries: Haiku omitted %s; keeping original context",
                sid,
            )
            aligned.append(
                {"user_interest_id": it.user_interest_id, "summary": it.current_context}
            )

    return RewriteIntentSummariesResponse(summaries=aligned)
