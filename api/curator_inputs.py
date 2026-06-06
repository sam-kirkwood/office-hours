"""Shared input-derivation helpers used by the curriculum curator and the
problem generator.

The four `derive_*` helpers were originally written for `generate_problem.py`
in Phase 10-rev Step 2f. They are now load-bearing across three routes
(`/generate-problem`, `/assess-engagement`, `/plan-queue`) so they live here.

The `load_engagement_signals_*` helpers are new for Step 3a: they pull the
post-engagement signals that `/assess-engagement` feeds to Haiku.

The `build_curator_context` block at the bottom is new for Step 3b: it
composes the full §4.2 input JSON the daily Sonnet `/plan-queue` call
receives.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import Client

# ---------------------------------------------------------------------------
# Constants (shared with generate_problem)
# ---------------------------------------------------------------------------

# Feedback-bias keys understood by the prompts. Mirror of the allowlist in
# web/app/api/profile/feedback/route.ts.
FEEDBACK_KEYS: set[str] = {
    "feedback_too_hard",
    "feedback_assume_less",
    "feedback_more_papers",
    "feedback_harder_problems",
}


# ---------------------------------------------------------------------------
# Three-dial derivation (extracted from generate_problem.py)
# ---------------------------------------------------------------------------


def derive_intent(supabase: Client, *, user_id: str, node_id: str) -> str:
    """Infer intent for this (user, topic). intent_context is source of truth
    (Step 2f decision); engagement state does not override it.

    Falls back to 'teach' when there is no user_interests row (concept_review
    on a foundation node the user hasn't claimed as an interest).
    """
    resp = (
        supabase.table("user_interests")
        .select("intent_context")
        .eq("user_id", user_id)
        .eq("node_id", node_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return "teach"

    raw = (resp.data[0].get("intent_context") or "").lower()
    if not raw:
        return "teach"

    if "consolidat" in raw or "harder" in raw or "deeper" in raw:
        return "consolidate"
    if "refresh" in raw or "remember" in raw or "rusty" in raw or "reconnect" in raw:
        return "refresh"
    return "teach"


def is_entry_point(supabase: Client, *, user_id: str, topic_node_id: str) -> bool:
    """True iff the user has no prior attempts on a problem whose
    topic_node_id matches.
    """
    attempts_resp = (
        supabase.table("attempts")
        .select("problem_id")
        .eq("user_id", user_id)
        .execute()
    )
    attempt_problem_ids = list(
        {r["problem_id"] for r in (attempts_resp.data or []) if r.get("problem_id")}
    )
    if not attempt_problem_ids:
        return True
    problems_resp = (
        supabase.table("problems")
        .select("id")
        .eq("topic_node_id", topic_node_id)
        .in_("id", attempt_problem_ids)
        .limit(1)
        .execute()
    )
    return not (problems_resp.data or [])


def derive_assumed_background_summary(
    supabase: Client,
    *,
    user_id: str,
    topic_node_id: str,
    topic_slug: str,
) -> str:
    """Build a short paragraph describing what the system has confirmed for
    this user, scoped to the topic + its direct prerequisites.
    """
    edges_resp = (
        supabase.table("edges")
        .select("source_node_id")
        .eq("target_node_id", topic_node_id)
        .eq("edge_kind", "prerequisite")
        .execute()
    )
    prereq_ids = [r["source_node_id"] for r in (edges_resp.data or [])]

    relevant_ids = [topic_node_id] + prereq_ids
    nodes_resp = (
        supabase.table("nodes")
        .select("id, slug, title")
        .in_("id", relevant_ids)
        .execute()
    )
    nodes_by_id = {n["id"]: n for n in (nodes_resp.data or [])}

    states_resp = (
        supabase.table("user_node_states")
        .select("node_id, state, engagement_count")
        .eq("user_id", user_id)
        .in_("node_id", relevant_ids)
        .execute()
    )
    state_by_id = {r["node_id"]: r for r in (states_resp.data or [])}

    survey_resp = (
        supabase.table("surveys")
        .select("comfort_responses_json")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    comfort_raw: dict[str, Any] = {}
    if survey_resp.data:
        comfort_raw = (survey_resp.data[0].get("comfort_responses_json") or {}).get(
            "subtopics", {}
        )

    confirmed_comfortable: list[str] = []
    refreshing: list[str] = []
    struggling: list[str] = []
    for nid in relevant_ids:
        node = nodes_by_id.get(nid)
        if not node:
            continue
        s = state_by_id.get(nid)
        if not s:
            continue
        title = node["title"]
        engagement = s.get("engagement_count") or 0
        if s["state"] == "comfortable":
            confirmed_comfortable.append(f"{title} (comfortable, {engagement} engagements)")
        elif s["state"] == "active":
            refreshing.append(f"{title} (actively working through)")
        elif s["state"] == "struggling":
            struggling.append(f"{title} (struggling)")

    topic_subtopic_keys = [k for k in comfort_raw if k.startswith(f"{topic_slug}:")]
    sub_familiar: list[str] = []
    sub_refresh: list[str] = []
    sub_new: list[str] = []
    for key in topic_subtopic_keys:
        subname = key.split(":", 1)[1].replace("-", " ")
        st = comfort_raw[key]
        if st == "familiar":
            sub_familiar.append(subname)
        elif st == "refresh":
            sub_refresh.append(subname)
        elif st == "new":
            sub_new.append(subname)

    parts: list[str] = []
    if confirmed_comfortable:
        parts.append("Confirmed comfortable: " + "; ".join(confirmed_comfortable) + ".")
    if refreshing:
        parts.append("Actively refreshing: " + "; ".join(refreshing) + ".")
    if struggling:
        parts.append("Struggling with: " + "; ".join(struggling) + ".")
    if sub_familiar:
        parts.append(
            f"On this topic specifically, the user marked these subtopics as familiar: {', '.join(sub_familiar)}."
        )
    if sub_refresh:
        parts.append(f"Subtopics they want refreshed: {', '.join(sub_refresh)}.")
    if sub_new:
        parts.append(
            f"Subtopics that are new to them — introduce these before using: {', '.join(sub_new)}."
        )

    if not parts:
        return ""
    return " ".join(parts)


def derive_feedback_biases(supabase: Client, *, user_id: str) -> dict[str, bool]:
    """Read user_preferences rows in the feedback_* allowlist."""
    resp = (
        supabase.table("user_preferences")
        .select("key, value")
        .eq("user_id", user_id)
        .execute()
    )
    out: dict[str, bool] = {}
    for row in resp.data or []:
        key = row.get("key")
        if key in FEEDBACK_KEYS and row.get("value") == "true":
            out[key] = True
    return out


# ---------------------------------------------------------------------------
# Engagement-context loaders (new for Step 3a)
# ---------------------------------------------------------------------------


def load_node_state(
    supabase: Client, *, user_id: str, node_id: str
) -> dict[str, Any]:
    """Return the user_node_states row for (user, node), or sensible defaults
    if no row exists yet.
    """
    resp = (
        supabase.table("user_node_states")
        .select("state, struggle_score, engagement_count, last_engaged_at")
        .eq("user_id", user_id)
        .eq("node_id", node_id)
        .limit(1)
        .execute()
    )
    if resp.data:
        row = resp.data[0]
        return {
            "state": row.get("state") or "unseen",
            "struggle_score": float(row.get("struggle_score") or 0.0),
            "engagement_count": int(row.get("engagement_count") or 0),
            "last_engaged_at": row.get("last_engaged_at"),
        }
    return {
        "state": "unseen",
        "struggle_score": 0.0,
        "engagement_count": 0,
        "last_engaged_at": None,
    }


def load_engagement_signals_for_attempt(
    supabase: Client, *, attempt_id: str
) -> dict[str, Any]:
    """Pull the signals Haiku needs to assess a graded problem attempt.

    Returns a dict shaped for AssessEngagementRequest.engagement, with
    `node_id`, `node_title`, `topic_slug`, `subtopic` and the per-attempt
    flags. The grading text is summarised by length only (the prompt does
    not see the full Sonnet feedback — keeps the Haiku call cheap and the
    signal source unambiguous).
    """
    attempt_resp = (
        supabase.table("attempts")
        .select(
            "id, user_id, problem_id, hint_levels_used, "
            "marked_refreshed, requested_easier, requested_harder, "
            "requested_assume_less, grade_response_md"
        )
        .eq("id", attempt_id)
        .limit(1)
        .execute()
    )
    if not attempt_resp.data:
        raise ValueError(f"attempt not found: {attempt_id}")
    attempt = attempt_resp.data[0]

    problem_resp = (
        supabase.table("problems")
        .select("topic_node_id, tags, intent, difficulty")
        .eq("id", attempt["problem_id"])
        .limit(1)
        .execute()
    )
    if not problem_resp.data:
        raise ValueError(f"problem not found: {attempt['problem_id']}")
    problem = problem_resp.data[0]

    node_resp = (
        supabase.table("nodes")
        .select("title, slug")
        .eq("id", problem["topic_node_id"])
        .limit(1)
        .execute()
    )
    node = (node_resp.data or [{}])[0]

    # Subtopic = first tag that isn't the topic slug. Tags are validated at
    # generation time (Step 2f); the topic slug is always present.
    tags: list[str] = list(problem.get("tags") or [])
    topic_slug: str = node.get("slug") or ""
    subtopic: str | None = next((t for t in tags if t != topic_slug), None)

    hint_levels = list(attempt.get("hint_levels_used") or [])

    return {
        "kind": "problem",
        "node_id": problem["topic_node_id"],
        "node_title": node.get("title") or "",
        "topic_slug": topic_slug,
        "subtopic": subtopic,
        "intent": problem.get("intent") or "teach",
        "difficulty": int(problem.get("difficulty") or 3),
        "hints_used": len(hint_levels),
        "requested_easier": bool(attempt.get("requested_easier")),
        "requested_harder": bool(attempt.get("requested_harder")),
        "requested_assume_less": bool(attempt.get("requested_assume_less")),
        "marked_refreshed": bool(attempt.get("marked_refreshed")),
        "not_ready_deferred": False,
        "grade_summary_md": attempt.get("grade_response_md") or "",
    }


def load_engagement_signals_for_paper(
    supabase: Client, *, engagement_id: str
) -> dict[str, Any]:
    """Pull the signals Haiku needs to assess a completed paper engagement.

    Note: `paper_engagements` does not carry a topic_node_id in v2's schema,
    so paper-engagement assessment is a lighter pulse-check than the problem
    path. node_id is None, and the route caller will skip node-state writes
    when it sees that. The Haiku call still runs so engagement-pattern
    signals (questions answered, paper title) flow into `llm_calls` for the
    daily curator's recent_engagement context.
    """
    eng_resp = (
        supabase.table("paper_engagements")
        .select("id, user_id, paper_id, questions_json, current_question_index")
        .eq("id", engagement_id)
        .limit(1)
        .execute()
    )
    if not eng_resp.data:
        raise ValueError(f"paper engagement not found: {engagement_id}")
    eng = eng_resp.data[0]

    paper_resp = (
        supabase.table("papers")
        .select("title")
        .eq("id", eng["paper_id"])
        .limit(1)
        .execute()
    )
    paper = (paper_resp.data or [{}])[0]

    questions = eng.get("questions_json") or []

    return {
        "kind": "paper_engagement",
        "node_id": None,
        "node_title": "",
        "topic_slug": "",
        "subtopic": None,
        "intent": "teach",
        "difficulty": 3,
        "hints_used": 0,
        "requested_easier": False,
        "requested_harder": False,
        "requested_assume_less": False,
        "marked_refreshed": False,
        "not_ready_deferred": False,
        "paper_title": paper.get("title") or "",
        "questions_answered": len(questions),
    }


# ---------------------------------------------------------------------------
# Curator context (Step 3b) — the full §4.2 input shape for /plan-queue
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def load_mode_balance(supabase: Client, *, user_id: str) -> float:
    """Read the user's mode_balance from surveys (0.0 = all problems, 1.0 =
    all papers). Default 0.5 when no row exists."""
    resp = (
        supabase.table("surveys")
        .select("mode_balance")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return 0.5
    val = resp.data[0].get("mode_balance")
    if val is None:
        return 0.5
    return float(val)


def load_active_interests(supabase: Client, *, user_id: str) -> list[dict[str, Any]]:
    """Return the user's interests with node info and current state.

    Active means the row exists in user_interests — the curator decides
    based on engagement/state whether to keep including each one."""
    ui_resp = (
        supabase.table("user_interests")
        .select("node_id, intent_context")
        .eq("user_id", user_id)
        .execute()
    )
    interest_node_ids = [r["node_id"] for r in (ui_resp.data or [])]
    if not interest_node_ids:
        return []
    intent_by_node = {
        r["node_id"]: (r.get("intent_context") or "")
        for r in ui_resp.data or []
    }

    nodes_resp = (
        supabase.table("nodes")
        .select("id, slug, title")
        .in_("id", interest_node_ids)
        .execute()
    )
    nodes_by_id = {n["id"]: n for n in (nodes_resp.data or [])}

    states_resp = (
        supabase.table("user_node_states")
        .select("node_id, state, engagement_count, last_engaged_at, struggle_score")
        .eq("user_id", user_id)
        .in_("node_id", interest_node_ids)
        .execute()
    )
    states_by_id = {r["node_id"]: r for r in (states_resp.data or [])}

    out: list[dict[str, Any]] = []
    for nid in interest_node_ids:
        node = nodes_by_id.get(nid)
        if not node:
            continue
        st = states_by_id.get(nid, {})
        out.append(
            {
                "node_id": nid,
                "node_slug": node["slug"],
                "node_title": node["title"],
                "intent_context": intent_by_node.get(nid, ""),
                "engagement_count": int(st.get("engagement_count") or 0),
                "last_engaged_at": st.get("last_engaged_at"),
                "node_state": st.get("state") or "unseen",
                "struggle_score": float(st.get("struggle_score") or 0.0),
            }
        )
    return out


def load_foundation_node_states(
    supabase: Client, *, user_id: str, interest_node_ids: list[str]
) -> list[dict[str, Any]]:
    """Return the user's foundation-node states, scoped to the prerequisite
    closure of the active interests. Keeps the input cheap on Persona-1-scale
    profiles (only the math/foundation nodes that actually matter for the
    interests they're working through).
    """
    if not interest_node_ids:
        return []

    # Step 1: walk prerequisite edges out from each interest. We do a single
    # query for direct prereqs (depth=1). Indirect prereqs are picked up via
    # the foundation states already in user_node_states from prior generation
    # runs. This keeps the query bounded.
    edges_resp = (
        supabase.table("edges")
        .select("source_node_id, target_node_id")
        .in_("target_node_id", interest_node_ids)
        .eq("edge_kind", "prerequisite")
        .execute()
    )
    prereq_node_ids = list(
        {e["source_node_id"] for e in (edges_resp.data or [])}
    )
    if not prereq_node_ids:
        return []

    nodes_resp = (
        supabase.table("nodes")
        .select("id, slug, title, kind")
        .in_("id", prereq_node_ids)
        .execute()
    )
    foundation_nodes = [
        n for n in (nodes_resp.data or []) if n.get("kind") == "foundation"
    ]
    foundation_ids = [n["id"] for n in foundation_nodes]
    if not foundation_ids:
        return []

    states_resp = (
        supabase.table("user_node_states")
        .select("node_id, state, struggle_score, engagement_count, last_engaged_at")
        .eq("user_id", user_id)
        .in_("node_id", foundation_ids)
        .execute()
    )
    states_by_id = {r["node_id"]: r for r in (states_resp.data or [])}

    out: list[dict[str, Any]] = []
    for node in foundation_nodes:
        st = states_by_id.get(node["id"], {})
        out.append(
            {
                "node_id": node["id"],
                "node_slug": node["slug"],
                "node_title": node["title"],
                "state": st.get("state") or "unseen",
                "struggle_score": float(st.get("struggle_score") or 0.0),
                "engagement_count": int(st.get("engagement_count") or 0),
                "last_engaged_at": st.get("last_engaged_at"),
            }
        )
    return out


def load_prerequisite_edges(
    supabase: Client, *, node_ids: list[str]
) -> list[dict[str, Any]]:
    """Return prerequisite edges where both endpoints are in `node_ids`.
    Edge endpoints are reported as node titles (not ids) so Sonnet can
    reason about them in plain English."""
    if len(node_ids) < 2:
        return []
    edges_resp = (
        supabase.table("edges")
        .select("source_node_id, target_node_id, edge_kind, weight")
        .in_("target_node_id", node_ids)
        .eq("edge_kind", "prerequisite")
        .execute()
    )
    relevant = [
        e for e in (edges_resp.data or []) if e["source_node_id"] in node_ids
    ]
    if not relevant:
        return []

    nodes_resp = (
        supabase.table("nodes")
        .select("id, title")
        .in_("id", node_ids)
        .execute()
    )
    title_by_id = {n["id"]: n["title"] for n in (nodes_resp.data or [])}

    out: list[dict[str, Any]] = []
    for e in relevant:
        out.append(
            {
                "from": title_by_id.get(e["source_node_id"], ""),
                "to": title_by_id.get(e["target_node_id"], ""),
                "edge_kind": e["edge_kind"],
                "weight": float(e.get("weight") or 0),
            }
        )
    return out


def load_recent_engagement(
    supabase: Client, *, user_id: str, window_days: int = 14
) -> dict[str, Any]:
    """Pull the curator's recent_engagement block: graded attempts, completed
    paper engagements, rerolls, deferred items. Window is the past N days
    (default 14).
    """
    cutoff = (_now() - timedelta(days=window_days)).isoformat()

    attempts_resp = (
        supabase.table("attempts")
        .select(
            "id, problem_id, hint_levels_used, marked_refreshed, "
            "requested_easier, requested_harder, requested_assume_less, "
            "submitted_at"
        )
        .eq("user_id", user_id)
        .gte("submitted_at", cutoff)
        .execute()
    )
    attempts = list(attempts_resp.data or [])

    problem_ids = list({a["problem_id"] for a in attempts if a.get("problem_id")})
    problems_by_id: dict[str, dict[str, Any]] = {}
    nodes_by_id: dict[str, dict[str, Any]] = {}
    if problem_ids:
        p_resp = (
            supabase.table("problems")
            .select("id, topic_node_id, tags, intent, difficulty")
            .in_("id", problem_ids)
            .execute()
        )
        problems_by_id = {p["id"]: p for p in (p_resp.data or [])}
        node_ids = list({p["topic_node_id"] for p in problems_by_id.values()})
        if node_ids:
            n_resp = (
                supabase.table("nodes")
                .select("id, slug, title")
                .in_("id", node_ids)
                .execute()
            )
            nodes_by_id = {n["id"]: n for n in (n_resp.data or [])}

    attempt_records: list[dict[str, Any]] = []
    for a in attempts:
        p = problems_by_id.get(a.get("problem_id") or "", {})
        node = nodes_by_id.get(p.get("topic_node_id") or "", {})
        tags = list(p.get("tags") or [])
        topic_slug = node.get("slug") or ""
        subtopic = next((t for t in tags if t != topic_slug), None)
        attempt_records.append(
            {
                "kind": "problem",
                "node": node.get("title") or "",
                "subtopic": subtopic,
                "intent": p.get("intent") or "teach",
                "hints_used": len(list(a.get("hint_levels_used") or [])),
                "requested_easier": bool(a.get("requested_easier")),
                "requested_harder": bool(a.get("requested_harder")),
                "requested_assume_less": bool(a.get("requested_assume_less")),
                "marked_refreshed": bool(a.get("marked_refreshed")),
                "submitted_at": a.get("submitted_at"),
            }
        )

    # Completed paper engagements in the window.
    paper_resp = (
        supabase.table("paper_engagements")
        .select("id, paper_id, completed_at")
        .eq("user_id", user_id)
        .eq("state", "completed")
        .gte("completed_at", cutoff)
        .execute()
    )
    paper_records: list[dict[str, Any]] = []
    paper_ids = list({pe["paper_id"] for pe in (paper_resp.data or [])})
    paper_title_by_id: dict[str, str] = {}
    if paper_ids:
        papers_resp = (
            supabase.table("papers")
            .select("id, title")
            .in_("id", paper_ids)
            .execute()
        )
        paper_title_by_id = {
            p["id"]: p.get("title") or "" for p in (papers_resp.data or [])
        }
    for pe in paper_resp.data or []:
        paper_records.append(
            {
                "kind": "paper_engagement",
                "paper_title": paper_title_by_id.get(pe["paper_id"], ""),
                "completed_at": pe.get("completed_at"),
            }
        )

    # Reroll patterns: surfaced_picks with chosen_item_id=null in the window.
    # Each such row represents one passed-over item. Group by node title.
    rerolls_resp = (
        supabase.table("surfaced_picks")
        .select("queue_item_ids, surfaced_at, chosen_item_id")
        .eq("user_id", user_id)
        .is_("chosen_item_id", "null")
        .gte("surfaced_at", cutoff)
        .execute()
    )
    passed_over_queue_ids: list[str] = []
    for row in rerolls_resp.data or []:
        ids = row.get("queue_item_ids") or []
        passed_over_queue_ids.extend(ids)

    reroll_pattern_counts: dict[str, int] = {}
    if passed_over_queue_ids:
        qi_resp = (
            supabase.table("queue_items")
            .select("id, kind, ref_id")
            .in_("id", passed_over_queue_ids)
            .execute()
        )
        ref_problem_ids = [
            r["ref_id"] for r in (qi_resp.data or [])
            if r.get("kind") == "problem" and r.get("ref_id")
        ]
        ref_problems_by_id: dict[str, dict[str, Any]] = {}
        if ref_problem_ids:
            rp_resp = (
                supabase.table("problems")
                .select("id, topic_node_id")
                .in_("id", ref_problem_ids)
                .execute()
            )
            ref_problems_by_id = {p["id"]: p for p in (rp_resp.data or [])}
            extra_node_ids = list(
                {p["topic_node_id"] for p in ref_problems_by_id.values()}
                - nodes_by_id.keys()
            )
            if extra_node_ids:
                en_resp = (
                    supabase.table("nodes")
                    .select("id, slug, title")
                    .in_("id", extra_node_ids)
                    .execute()
                )
                for n in en_resp.data or []:
                    nodes_by_id[n["id"]] = n

        for q in qi_resp.data or []:
            kind = q.get("kind") or "unknown"
            label = kind
            if kind == "problem":
                p = ref_problems_by_id.get(q.get("ref_id") or "", {})
                node = nodes_by_id.get(p.get("topic_node_id") or "", {})
                if node.get("title"):
                    label = node["title"]
            reroll_pattern_counts[label] = reroll_pattern_counts.get(label, 0) + 1

    reroll_patterns = [
        {"label": k, "count": v} for k, v in reroll_pattern_counts.items()
    ]

    # Deferred items currently sitting in the queue.
    deferred_resp = (
        supabase.table("queue_items")
        .select("id, kind, ref_id, deferred_at, added_reason")
        .eq("user_id", user_id)
        .eq("state", "deferred")
        .execute()
    )
    deferred_items: list[dict[str, Any]] = []
    deferred_problem_ids = [
        r["ref_id"] for r in (deferred_resp.data or [])
        if r.get("kind") == "problem" and r.get("ref_id")
    ]
    deferred_problems_by_id: dict[str, dict[str, Any]] = {}
    if deferred_problem_ids:
        dp_resp = (
            supabase.table("problems")
            .select("id, topic_node_id, tags")
            .in_("id", deferred_problem_ids)
            .execute()
        )
        deferred_problems_by_id = {p["id"]: p for p in (dp_resp.data or [])}
        extra_node_ids = list(
            {p["topic_node_id"] for p in deferred_problems_by_id.values()}
            - nodes_by_id.keys()
        )
        if extra_node_ids:
            dn_resp = (
                supabase.table("nodes")
                .select("id, slug, title")
                .in_("id", extra_node_ids)
                .execute()
            )
            for n in dn_resp.data or []:
                nodes_by_id[n["id"]] = n

    for r in deferred_resp.data or []:
        p = deferred_problems_by_id.get(r.get("ref_id") or "", {})
        node = nodes_by_id.get(p.get("topic_node_id") or "", {})
        tags = list(p.get("tags") or [])
        topic_slug = node.get("slug") or ""
        subtopic = next((t for t in tags if t != topic_slug), None)
        deferred_items.append(
            {
                "queue_item_id": r["id"],
                "node": node.get("title") or "",
                "subtopic": subtopic,
                "deferred_at": r.get("deferred_at"),
                "reason": r.get("added_reason") or "",
            }
        )

    return {
        "last_14_days": attempt_records + paper_records,
        "reroll_patterns": reroll_patterns,
        "deferred_items": deferred_items,
    }


def load_current_queue_summary(
    supabase: Client, *, user_id: str
) -> dict[str, Any]:
    """Return pending_count, pending_by_interest, pending_by_kind. Surfaced
    items count as pending for this purpose (they're still 'on deck')."""
    resp = (
        supabase.table("queue_items")
        .select("id, kind, ref_id, state")
        .eq("user_id", user_id)
        .in_("state", ["pending", "surfaced"])
        .execute()
    )
    rows = list(resp.data or [])
    by_kind: Counter[str] = Counter(r.get("kind") or "unknown" for r in rows)

    # Map problem ref_ids → topic_node_id → node title for the by_interest count.
    problem_ref_ids = [
        r["ref_id"] for r in rows
        if r.get("kind") == "problem" and r.get("ref_id")
    ]
    by_interest_counter: Counter[str] = Counter()
    if problem_ref_ids:
        problems_resp = (
            supabase.table("problems")
            .select("id, topic_node_id")
            .in_("id", problem_ref_ids)
            .execute()
        )
        node_ids = list(
            {p["topic_node_id"] for p in (problems_resp.data or [])}
        )
        problem_node_by_id = {
            p["id"]: p.get("topic_node_id") for p in (problems_resp.data or [])
        }
        title_by_node_id: dict[str, str] = {}
        if node_ids:
            nodes_resp = (
                supabase.table("nodes")
                .select("id, title")
                .in_("id", node_ids)
                .execute()
            )
            title_by_node_id = {
                n["id"]: n["title"] for n in (nodes_resp.data or [])
            }
        for r in rows:
            if r.get("kind") == "problem" and r.get("ref_id"):
                node_id = problem_node_by_id.get(r["ref_id"])
                title = title_by_node_id.get(node_id or "", "Unknown")
                by_interest_counter[title] += 1

    return {
        "pending_count": len(rows),
        "pending_by_kind": dict(by_kind),
        "pending_by_interest": dict(by_interest_counter),
    }


def load_feedback_signals(
    supabase: Client, *, user_id: str, window_days: int = 14
) -> dict[str, Any]:
    """Return the profile-level feedback biases plus counts of recent
    attempt-level signal requests in the window."""
    profile_feedback = derive_feedback_biases(supabase, user_id=user_id)

    cutoff = (_now() - timedelta(days=window_days)).isoformat()
    attempts_resp = (
        supabase.table("attempts")
        .select(
            "requested_easier, requested_assume_less, requested_harder, "
            "marked_refreshed, submitted_at"
        )
        .eq("user_id", user_id)
        .gte("submitted_at", cutoff)
        .execute()
    )
    rows = list(attempts_resp.data or [])
    return {
        "profile_feedback": sorted(profile_feedback.keys()),
        "recent_easier_requests": sum(
            1 for r in rows if r.get("requested_easier")
        ),
        "recent_assume_less_requests": sum(
            1 for r in rows if r.get("requested_assume_less")
        ),
        "recent_harder_requests": sum(
            1 for r in rows if r.get("requested_harder")
        ),
        "recent_marked_refreshed_count": sum(
            1 for r in rows if r.get("marked_refreshed")
        ),
    }


def build_curator_context(
    supabase: Client, *, user_id: str, window_days: int = 14
) -> dict[str, Any]:
    """Compose the full §4.2 input JSON for the /plan-queue Sonnet call."""
    mode_balance = load_mode_balance(supabase, user_id=user_id)
    active_interests = load_active_interests(supabase, user_id=user_id)
    interest_node_ids = [i["node_id"] for i in active_interests]
    foundation_states = load_foundation_node_states(
        supabase, user_id=user_id, interest_node_ids=interest_node_ids
    )
    foundation_node_ids = [f["node_id"] for f in foundation_states]
    prerequisite_edges = load_prerequisite_edges(
        supabase, node_ids=interest_node_ids + foundation_node_ids
    )
    recent_engagement = load_recent_engagement(
        supabase, user_id=user_id, window_days=window_days
    )
    current_queue = load_current_queue_summary(supabase, user_id=user_id)
    feedback_signals = load_feedback_signals(
        supabase, user_id=user_id, window_days=window_days
    )

    return {
        "user_context": {
            "mode_balance": mode_balance,
            "active_interests": active_interests,
            "foundation_node_states": foundation_states,
            "prerequisite_edges": prerequisite_edges,
        },
        "recent_engagement": recent_engagement,
        "current_queue": current_queue,
        "feedback_signals": feedback_signals,
    }


# ---------------------------------------------------------------------------
# Queue-item dedup (Phase 10-rev Step 9a)
# ---------------------------------------------------------------------------


def find_pending_queue_item(
    supabase: Client, *, user_id: str, kind: str, ref_id: str
) -> str | None:
    """Return the id of an existing pending/surfaced queue_items row for this
    (user, kind, ref_id), or None.

    Used by dedup checks in both `/generate-problem` (before unconditionally
    writing a queue row) and `/plan-queue` (before inserting a pool-hit
    recommendation). Without this check, the curator-pool-miss →
    generate-problem-cache-hit path can produce multiple queue rows pointing
    at the same problem under different recommendation rationales
    (Phase 10-rev Step 9a, surfaced by the persona walkthroughs).
    """
    resp = (
        supabase.table("queue_items")
        .select("id")
        .eq("user_id", user_id)
        .eq("kind", kind)
        .eq("ref_id", ref_id)
        .in_("state", ["pending", "surfaced"])
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0]["id"] if rows else None


# Stop-words excluded from token-overlap matching so common conjunctions /
# articles don't produce spurious matches.
_SUBTOPIC_STOPWORDS = {
    "and", "the", "for", "with", "from", "into", "in", "of", "to",
    "on", "or", "an", "a", "by",
}

# 5-char prefixes of words so overloaded across physics/math that a match on
# them alone is meaningless. Without this guard the matcher false-positives:
# "phase relationships" → ODEs ("phase plane analysis"); a "...distribution"
# subtopic → Probability ("random variables & distributions"). Foundation
# refreshers should match on a *distinctive* token (e.g. "partition",
# "helmholtz"), not a generic one. Deliberately excludes prefixes that collide
# with distinctive canonical tokens — e.g. "parti" (partition), "trans"
# (transfer/transform/transition) — so true matches survive. See Phase 10-rev
# §9 (B1, persona walkthrough).
_OVERLOADED_PREFIXES = {
    "phase", "distr", "field", "wave", "state", "funct", "energ", "syste",
    "equat", "analy", "metho", "model", "theor", "gener", "basic", "probl",
    "dynam",
}


def _subtopic_tokens(text: str) -> set[str]:
    """Tokenise a subtopic name into substantive 4+ char tokens, lowercased
    and prefix-truncated so 'energy' and 'energies' both match 'energ'.
    Overloaded prefixes (see _OVERLOADED_PREFIXES) are dropped so a lone
    generic word can't bridge two unrelated foundations."""
    import re

    words = re.findall(r"[a-z]+", text.lower())
    out: set[str] = set()
    for w in words:
        if len(w) < 4 or w in _SUBTOPIC_STOPWORDS:
            continue
        prefix = w[:5]
        if prefix in _OVERLOADED_PREFIXES:
            continue
        out.add(prefix)
    return out


def find_foundation_owning_subtopic(
    supabase: Client, *, subtopic_slug: str
) -> dict | None:
    """Find a foundation node whose subtopics_json contains this concept.

    Used by the curator's refresher dispatch: when Sonnet emits a refresher
    rec with a subtopic that's owned by a foundation (e.g. "partition
    function manipulations" → statistical-mechanics, or "Helmholtz and
    Gibbs free energies" → thermodynamics), route the queue row's ref_id
    to that foundation rather than to the interest_node it was emitted
    under. Falls back to None if no foundation owns the subtopic — caller
    should fall back to interest_node behaviour.

    Matcher tokenises the needle into substantive 4+ char tokens (after
    truncation to 5-char prefixes — so 'energy'/'energies' both reduce to
    'energ'). A foundation subtopic matches when it shares at least one
    such token with the needle. This tolerates pluralisation, conjunctions,
    and word order differences across the curator's phrasings vs the
    foundation's canonical subtopic labels.
    """
    if not subtopic_slug:
        return None
    needle_tokens = _subtopic_tokens(subtopic_slug.replace("-", " "))
    if not needle_tokens:
        return None

    # Pull foundation rows and check their subtopics_json client-side.
    # The seed has ~13 foundations so this is cheap.
    resp = (
        supabase.table("nodes")
        .select("id, slug, title, subtopics_json")
        .eq("kind", "foundation")
        .execute()
    )
    for n in resp.data or []:
        for entry in n.get("subtopics_json") or []:
            if isinstance(entry, dict):
                label = (entry.get("title") or entry.get("slug") or "")
            elif isinstance(entry, str):
                label = entry
            else:
                continue
            entry_tokens = _subtopic_tokens(label.replace("-", " "))
            if needle_tokens & entry_tokens:
                return n
    return None
