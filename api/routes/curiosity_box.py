"""POST /curiosity-box — classify-and-route for the daily curiosity box (§A4).

Haiku classifies the user's raw_text into one of 9 kinds, then the lightest
sufficient response fires per kind:

  question       → brief Haiku answer + follow-on offer
  drill          → pool-lookup → queue pinned (§A6); generate on pool miss
  existing_interest → same pool-lookup/generate path
  follow_up      → same pool-lookup/generate path
  mood           → redirect to steering chips (§A5)
  feedback       → redirect to FeedbackDialog (fb1)
  paper          → return paper_ref for client to ingest via existing flow
  probe          → warm, brief in-character reply
  topic_new      → explore by default (§A4): resolve to nearest existing node →
                   queue one pinned item (no user_interests write) →
                   action="topic_new_explored"; "Add it properly →" in the card is
                   the opt-in commit path (existing DialogModal flow). Novel topics
                   with no matching node fall through to action="topic_new_stub"
                   nudging the user to commit. Phase 13 §B5 upgrades
                   _resolve_and_queue_one_off to find-or-create novel nodes.

Low-confidence inputs return action="clarify" without executing anything.

Node resolution uses the overloaded-prefix guard from curator_inputs so that
bare generic tokens ("phase", "field", "state") cannot bridge unrelated nodes
(Phase 10.5-rev §9 false-positive fix, applied to curiosity-box matching).
"""

from __future__ import annotations

import logging
import re as _re
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, Depends
from supabase import Client

from anthropic_client import call_json, get_anthropic_client
from auth import require_internal_token
from config import HAIKU_MODEL
from curator_inputs import (
    derive_assumed_background_summary,
    derive_feedback_biases,
    derive_intent,
    is_entry_point as check_is_entry_point,
    topic_match_tokens,
)
from prompts import curiosity_box as prompts
from schemas import (
    BriefAnswer,
    CuriosityBoxRequest,
    CuriosityBoxResponse,
    CuriosityClassification,
)
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter()

# Default queue priority for curiosity-box-requested items — sits above
# normal curator picks so the item surfaces on the next /surface-daily call.
_PINNED_PRIORITY = 0.88

_SLUG_PUNCT_RE = _re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUG_PUNCT_RE.sub("-", text.lower()).strip("-") or "untitled"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_node_for_topic(
    supabase: Client, user_id: str, normalized_topic: str
) -> dict | None:
    """Find the best-matching graph node for a normalized topic string.

    Uses the same overloaded-prefix guard as the refresher subtopic matcher
    (curator_inputs.topic_match_tokens) so bare generic tokens like "phase",
    "field", or "state" cannot bridge unrelated nodes. An empty needle (all
    tokens overloaded) never matches anything.

    Search order:
      1. User's own interests (token overlap) — "more GR" finds the user's own
         general-relativity node before searching the full graph.
      2. All nodes via ilike on the longest distinctive token, refined by token
         overlap in Python — for drill requests on nodes the user hasn't added.
    """
    needle = topic_match_tokens(normalized_topic)
    if not needle:
        # All tokens are stopwords/overloaded — can't safely match anything.
        return None

    # --- Step 1: user's interest nodes ----------------------------------------
    interests_resp = (
        supabase.table("user_interests")
        .select("node_id")
        .eq("user_id", user_id)
        .execute()
    )
    interest_node_ids = [r["node_id"] for r in (interests_resp.data or [])]

    if interest_node_ids:
        nodes_resp = (
            supabase.table("nodes")
            .select("id, slug, title")
            .in_("id", interest_node_ids)
            .execute()
        )
        for node in nodes_resp.data or []:
            node_tokens = topic_match_tokens(node["title"])
            if needle & node_tokens:
                return node

    # --- Step 2: global node search -------------------------------------------
    # Use ilike on the longest distinctive token as a DB-level pre-filter,
    # then pick the best match by token overlap in Python.
    first_token = max(needle, key=len)
    all_resp = (
        supabase.table("nodes")
        .select("id, slug, title")
        .ilike("title", f"%{first_token}%")
        .limit(20)
        .execute()
    )
    best: dict | None = None
    best_overlap = 0
    for node in all_resp.data or []:
        node_tokens = topic_match_tokens(node["title"])
        overlap = len(needle & node_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best = node
    return best


def _pool_lookup_problem(supabase: Client, node_id: str) -> str | None:
    """Return the id of any problem in the pool for the given node, or None."""
    resp = (
        supabase.table("problems")
        .select("id")
        .eq("topic_node_id", node_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0]["id"] if rows else None


def _insert_pinned_queue_item(
    supabase: Client,
    *,
    user_id: str,
    problem_id: str,
    added_reason: str,
) -> str:
    """Insert a pinned queue_item for the given problem and return its id."""
    row = {
        "user_id": user_id,
        "kind": "problem",
        "ref_id": problem_id,
        "state": "pending",
        "priority_score": _PINNED_PRIORITY,
        "added_reason": added_reason,
        "time_estimate_minutes_low": 15,
        "time_estimate_minutes_high": 30,
        "pinned": True,
    }
    resp = supabase.table("queue_items").insert(row).execute()
    return resp.data[0]["id"]


def _generate_problem_for_node(
    supabase: Client,
    anthropic: Anthropic,
    *,
    node_id: str,
    user_id: str,
) -> str | None:
    """Fetch the full node, derive three dials, and call fetch_or_generate_problem.

    Skips hook selection (curiosity-box requests don't need the extra Haiku
    round-trip for a hook match). Returns problem_id, or None if the node row
    cannot be loaded.
    """
    # Import here to avoid module-level circular dependency at parse time.
    from routes.generate_problem import DIFFICULTY_MAP, fetch_or_generate_problem  # noqa: PLC0415

    node_resp = (
        supabase.table("nodes")
        .select("id, slug, title, description_md, difficulty_hint, subtopics_json")
        .eq("id", node_id)
        .limit(1)
        .execute()
    )
    if not node_resp.data:
        return None
    node = node_resp.data[0]

    topic_slug = node.get("slug") or _slugify(node["title"])
    difficulty = DIFFICULTY_MAP.get(node.get("difficulty_hint") or "core", 3)
    intent = derive_intent(supabase, user_id=user_id, node_id=node_id)
    entry_pt = check_is_entry_point(supabase, user_id=user_id, topic_node_id=node_id)
    assumed_bg = derive_assumed_background_summary(
        supabase, user_id=user_id, topic_node_id=node_id, topic_slug=topic_slug
    )
    feedback_biases = derive_feedback_biases(supabase, user_id=user_id)

    # intent_context (soft prose from user_interests) — empty for curiosity-box
    # requests that aren't tied to a formal user_interests row.
    ui_resp = (
        supabase.table("user_interests")
        .select("intent_context")
        .eq("user_id", user_id)
        .eq("node_id", node_id)
        .limit(1)
        .execute()
    )
    intent_context = (ui_resp.data[0].get("intent_context") or "") if ui_resp.data else ""

    return fetch_or_generate_problem(
        supabase,
        anthropic,
        node=node,
        topic_slug=topic_slug,
        topic_node_id=node_id,
        difficulty=difficulty,
        intent=intent,
        assumed_background_summary=assumed_bg,
        is_entry_point=entry_pt,
        intent_context=intent_context,
        feedback_biases=feedback_biases,
        context_hook_id=None,
        context_hook_summary=None,
        user_id=user_id,
    )


def _resolve_and_queue_one_off(
    supabase: Client,
    anthropic: Anthropic,
    *,
    user_id: str,
    normalized_topic: str,
    added_reason: str,
) -> tuple[str | None, str | None]:
    """Resolve an existing node and queue one pinned problem — no user_interests written.

    Returns (queue_item_id, node_title) or (None, None) when no node found.
    Writes only queue_items (+ problems / problem_hints on pool miss).
    Phase 13 §B5 can upgrade to find-or-create by replacing this one function.
    """
    node = _resolve_node_for_topic(supabase, user_id, normalized_topic)
    if not node:
        return None, None
    problem_id = _pool_lookup_problem(supabase, node["id"])
    if not problem_id:
        logger.info(
            "curiosity-box topic_new pool miss for node=%s user=%s — generating inline",
            node["id"],
            user_id,
        )
        try:
            problem_id = _generate_problem_for_node(
                supabase, anthropic, node_id=node["id"], user_id=user_id
            )
        except Exception:
            logger.warning(
                "curiosity-box topic_new generation failed for node=%s user=%s",
                node["id"],
                user_id,
                exc_info=True,
            )
            problem_id = None
    if not problem_id:
        # Return the node title so the caller can distinguish "found but failed"
        # from "no node in megagraph at all".
        return None, node["title"]
    qi_id = _insert_pinned_queue_item(
        supabase,
        user_id=user_id,
        problem_id=problem_id,
        added_reason=added_reason,
    )
    return qi_id, node["title"]


def _handle_queuing_kinds(
    supabase: Client,
    anthropic: Anthropic,
    user_id: str,
    classification: CuriosityClassification,
) -> CuriosityBoxResponse:
    """Shared handler for drill / existing_interest / follow_up.

    Pool-lookup first (fast). On a miss, generate inline via Sonnet (§3.7:
    generate on miss; explicit requests work without bureaucracy).
    """
    normalized_topic = classification.normalized_topic or ""
    if not normalized_topic:
        return CuriosityBoxResponse(
            action="graceful",
            message_md="I couldn't quite make out the topic — try being a bit more specific?",
        )

    node = _resolve_node_for_topic(supabase, user_id, normalized_topic)
    if not node:
        return CuriosityBoxResponse(
            action="graceful",
            message_md=(
                f"I couldn't find **{normalized_topic}** in your interests or the graph — "
                "try being more specific, or add it as a new interest from the box below."
            ),
        )

    # Fast path: pool hit.
    problem_id = _pool_lookup_problem(supabase, node["id"])
    if problem_id:
        queue_item_id = _insert_pinned_queue_item(
            supabase,
            user_id=user_id,
            problem_id=problem_id,
            added_reason=classification.added_reason,
        )
        return CuriosityBoxResponse(
            action="queued_pinned",
            message_md=f"Added a problem on **{node['title']}** to the top of your queue.",
            queue_item_id=UUID(queue_item_id),
        )

    # Pool miss — generate inline (Sonnet; takes a moment).
    logger.info(
        "curiosity-box pool miss for node=%s user=%s — generating inline",
        node["id"],
        user_id,
    )
    generated_id = _generate_problem_for_node(
        supabase, anthropic, node_id=node["id"], user_id=user_id
    )
    if not generated_id:
        return CuriosityBoxResponse(
            action="graceful",
            message_md=(
                f"Something went wrong generating a problem for **{normalized_topic}** — "
                "try again in a moment."
            ),
        )

    queue_item_id = _insert_pinned_queue_item(
        supabase,
        user_id=user_id,
        problem_id=generated_id,
        added_reason=classification.added_reason,
    )
    return CuriosityBoxResponse(
        action="queued_pinned",
        message_md=f"Built a fresh problem on **{node['title']}** — it's up top in your queue.",
        queue_item_id=UUID(queue_item_id),
    )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post(
    "/curiosity-box",
    response_model=CuriosityBoxResponse,
    dependencies=[Depends(require_internal_token)],
)
def handle_curiosity_box(
    body: CuriosityBoxRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> CuriosityBoxResponse:
    user_id = str(body.user_id)

    # 1. Classify with Haiku.
    classification: CuriosityClassification = call_json(
        client=anthropic,
        supabase=supabase,
        model=HAIKU_MODEL,
        system_prompt=prompts.build_classify_system_prompt(),
        user_prompt=prompts.build_classify_user_prompt(body.raw_text),
        schema=CuriosityClassification,
        route="curiosity-box/classify",
        user_id=user_id,
        request_summary={"raw_text": body.raw_text[:80]},
        temperature=0,
    )

    kind = classification.kind

    # 2. Low confidence → clarify without executing.
    if classification.confidence == "low":
        return CuriosityBoxResponse(
            action="clarify",
            message_md="Just checking — want to make sure I route this right.",
            clarification_md=classification.clarification_md,
        )

    # 3. Redirect kinds — hand off to existing surfaces, no machinery here.
    if kind == "mood":
        return CuriosityBoxResponse(
            action="redirect_steer",
            message_md=(
                "Sounds like a mood thing — the chips above let you shape "
                "today's mix without losing what you've already started."
            ),
        )

    if kind == "feedback":
        return CuriosityBoxResponse(
            action="redirect_feedback",
            message_md=(
                "That sounds like feedback — send it through the form so it "
                "doesn't get lost."
            ),
        )

    # 4. Probe / off-topic — warm in-character reply, no machinery.
    if kind == "probe":
        return CuriosityBoxResponse(
            action="graceful",
            message_md=(
                "Just a tutor here, not a general-purpose assistant — but ask me "
                "a real physics or maths question and I'm happy to help."
            ),
        )

    # 5. Question → brief Haiku answer + follow-on offer.
    if kind == "question":
        brief: BriefAnswer = call_json(
            client=anthropic,
            supabase=supabase,
            model=HAIKU_MODEL,
            system_prompt=prompts.build_answer_system_prompt(),
            user_prompt=prompts.build_answer_user_prompt(body.raw_text),
            schema=BriefAnswer,
            route="curiosity-box/answer",
            user_id=user_id,
            request_summary={"question": body.raw_text[:80]},
        )
        return CuriosityBoxResponse(
            action="answer",
            message_md="Here's a quick answer:",
            answer_md=brief.answer_md,
            followon_topic_hint=brief.followon_topic_hint,
        )

    # 6. Paper → return paper_ref for the client to route through the
    #    existing paper-ingestion flow.
    if kind == "paper":
        paper_ref = classification.paper_ref or body.raw_text.strip()
        return CuriosityBoxResponse(
            action="ingest_paper",
            message_md="Found a paper reference — adding it to your papers.",
            paper_ref=paper_ref,
        )

    # 7. Topic-new — explore by default (§A4).
    #    If a node already exists in the megagraph: queue one pinned item with NO
    #    user_interests write (one-off / explore).  The "Add it properly →" button
    #    in the result card is the opt-in commit path, handled entirely in the
    #    frontend via the existing DialogModal / add-interest flow.
    #    If no node exists: fall through to topic_new_stub so the user is nudged to
    #    commit (find-or-create for novel topics lands in Phase 13 §B5).
    if kind == "topic_new":
        topic_hint = classification.normalized_topic or body.raw_text.strip()
        qi_id, node_title = _resolve_and_queue_one_off(
            supabase,
            anthropic,
            user_id=user_id,
            normalized_topic=topic_hint,
            added_reason=classification.added_reason,
        )
        if qi_id and node_title:
            return CuriosityBoxResponse(
                action="topic_new_explored",
                message_md=(
                    f"Here's a one-off problem on **{node_title}** — "
                    "it hasn't been added to your interests."
                ),
                queue_item_id=UUID(qi_id),
                topic_hint=topic_hint,
            )
        if node_title:
            # Node exists but problem generation failed — transient failure.
            return CuriosityBoxResponse(
                action="graceful",
                message_md=(
                    f"Couldn't build a problem for **{node_title}** right now — "
                    "try again in a moment, or add it as an interest for more content."
                ),
            )
        # No matching node in megagraph → nudge to the full add-interest flow.
        return CuriosityBoxResponse(
            action="topic_new_stub",
            message_md=(
                f"**{topic_hint}** isn't in my library yet — "
                "add it as a proper interest and I'll build a queue around it."
            ),
            topic_hint=topic_hint,
        )

    # 8. Queuing kinds: drill / existing_interest / follow_up.
    return _handle_queuing_kinds(supabase, anthropic, user_id, classification)
