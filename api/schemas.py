from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class GenerateProblemRequest(BaseModel):
    user_id: UUID
    node_id: UUID  # replaces plan_node_id
    # Three-dial overrides (survey-and-difficulty-design.md §3). When omitted,
    # the route derives them from the user's interest + state. Tests and
    # future curator calls (Step 3 /plan-queue) supply them explicitly.
    intent: str | None = None  # 'teach' | 'refresh' | 'consolidate'
    feedback_bias: dict[str, bool] | None = None


class GeneratedHint(BaseModel):
    """One rung of the depth hint ladder.

    `part_label` (d10) names the part(s) the hint addresses — "Parts (a)-(b)",
    "Part (c)", or "Whole problem" for ladder rungs that apply throughout. It
    is rendered as a chip so the user can see which part a hint speaks to
    before opening it. Nullable for tolerance; the render layer omits the chip
    when absent.
    """

    text: str
    part_label: str | None = None


class GeneratedProblem(BaseModel):
    """Strict shape the Sonnet generation call must return as JSON."""

    title: str  # plain English, no LaTeX, 4-8 words
    statement_md: str
    solution_md: str
    rubric_md: str
    hints: list[GeneratedHint] = Field(..., min_length=5, max_length=5)
    context_md: str | None = None  # matches DB column name
    # Required: at least the topic slug + one subtopic slug. Concept-refresher
    # surfaces (§2.7 Case 3, §7) query by tags @> ARRAY['<subtopic>'] so
    # subtopic tagging is load-bearing (§3.7 + §8.4).
    tags: list[str] = Field(..., min_length=2)


class GenerateProblemResponse(BaseModel):
    problem_id: UUID
    queue_item_id: UUID  # the queue item written for this user


class HookMatch(BaseModel):
    """Strict shape the Haiku hook-matcher must return as JSON."""

    hook_slug: str | None
    reason: str | None = None


# ---------------------------------------------------------------------------
# /add-interest/parse and /add-interest/resolve
# ---------------------------------------------------------------------------
# The add-interest flow is a dialog (survey-and-difficulty-design.md §2):
#
#   1. /parse — Haiku reads the user's raw text, splits it into one or more
#      distinct interest segments, runs dedup against the megagraph, and
#      reports specificity + implicit intent. Returns mirror-back text and
#      (for ambiguous segments) path options. NO database writes.
#
#   2. /resolve — the client passes back the final intent text for ONE
#      segment together with the matched node slug from /parse (when there
#      was a dedup hit). The server writes the user_interests row, runs
#      Sonnet generation if a new node is required, and returns the concept
#      tour tiles for stage 5 of the onboarding survey.
#
# Multi-interest input → the client calls /resolve once per segment.


# --- /add-interest/parse ----------------------------------------------------


class DedupVerdict(BaseModel):
    """The dedup outcome for one segment of the user's raw text."""

    verdict: str  # 'same' | 'related' | 'new'
    matched_node_slug: str | None = None  # populated for 'same' and 'related'


class PathOption(BaseModel):
    """One clarifying path offered for an ambiguous segment."""

    key: str               # stable identifier, e.g. 'transistors-and-circuits'
    label_md: str          # short display label (≤ 80 chars)
    draft_intent_context: str  # intent_context prose if the user picks this path
    # Rich fields (Phase 13 Step 2) — presented in the path-pick UI so the user
    # has enough detail to choose; stored as path_json on user_interests.
    what_you_learn: str    # 1-2 sentences: concrete deliverables of this path
    endpoint: str          # first-person capability statement ("I can …")
    math_intensity: str    # 'algebra'|'calculus'|'linear_algebra'|'heavy_math'|'qualitative'
    mode_lean: str         # 'problems'|'papers'|'balanced'
    leans_on_prereq_slugs: list[str]  # validated against real node slugs before storage


class ParsedInterestSegment(BaseModel):
    """One distinct interest extracted from the user's raw text."""

    raw_text_segment: str       # the portion of raw_text this segment came from
    kind: str = "interest"      # 'interest' | 'concept' — see §2.7 Case 3
    specificity: str            # 'specific' | 'ambiguous'
    implicit_intent: str        # 'teach' | 'refresh' | 'consolidate'
    mirror_back_md: str         # natural-language echo of the user's intent
    optional_followup_md: str | None = None  # present for 'specific'
    path_options: list[PathOption] = Field(default_factory=list)  # for 'ambiguous'
    dedup: DedupVerdict
    draft_intent_context: str   # intent_context if user accepts without clarifying


class ParsedInterestPayload(BaseModel):
    """Haiku's structured output for one /parse call. Internal only — wrapped
    by the route into ParseAddInterestResponse with dedup info attached."""

    segments: list[ParsedInterestSegment]


class ParseAddInterestRequest(BaseModel):
    user_id: UUID
    raw_text: str
    added_via: str  # 'survey' | 'explicit_request' | 'cross_pollination'


class ParseAddInterestResponse(BaseModel):
    segments: list[ParsedInterestSegment]


# --- /add-interest/resolve --------------------------------------------------


class ResolveAddInterestRequest(BaseModel):
    user_id: UUID
    added_via: str  # 'survey' | 'explicit_request' | 'cross_pollination'
    raw_text: str                       # original text the user typed (for audit)
    final_intent_text: str              # synthesized: original + chosen path + extra context
    intent_context: str                 # the prose narrative stored on user_interests

    # Echoed back from /parse. Server validates each slug exists in the
    # megagraph before acting on it. Mutually exclusive — at most one is set.
    # - existing_node_slug: link the user to this node, no Sonnet call.
    #   Use when /parse dedup returned 'same'.
    # - related_node_slug: generate a new node and write a 'related' edge to
    #   this existing one. Use when /parse dedup returned 'related'.
    # - Both null: generate a new standalone node. Use when /parse dedup
    #   returned 'new'.
    existing_node_slug: str | None = None
    related_node_slug: str | None = None

    # Structured path facts (Phase 13 Step 2). Present when the user chose a
    # path from an ambiguous interest; null when the interest was specific or
    # the user skipped. Stored as path_json on user_interests. The curator
    # reads mode_lean and leans_on as field reads from this column; they are
    # NOT duplicated in intent_context prose.
    path_json: dict | None = None

    # Per-interest altitude signal (Phase 13 Step 3). Drives intent and the
    # §3.4 entry-lane at generation time. Read as a structured field — never
    # re-parsed from intent_context prose. Values: 'new' | 'coming_back' |
    # 'go_deep'. Null when the user did not set one (falls back to prose).
    altitude: str | None = None


class GeneratedInterestNode(BaseModel):
    """Sonnet node-generation call output. Only used when /resolve must create
    a brand-new interest node (no megagraph hit on the resolved intent)."""

    title: str
    slug: str  # kebab-case, lowercase, ASCII
    description_md: str
    domain: str  # 'math' | 'physics' | 'applied'
    difficulty_hint: str  # 'intro' | 'core' | 'advanced'
    subtopics: list[str]  # display names, not slugs
    proposed_prerequisite_slugs: list[str]
    entry_point_preview_md: str  # one sentence; powers starter_preview_md


class ConceptTourTile(BaseModel):
    """One subtopic tile for the Stage 5 concept tour.

    Tiles live at the SUBTOPIC level of foundation nodes (see
    survey-and-difficulty-design.md §1.6.2). subtopic_key is derived from
    the subtopic name (lowercase kebab-case) and is stable across calls so
    the client can post tile-level state back.

    Retained for backward-compat with existing survey code; replaced in the
    resolve response by NodeReadinessTile (Phase 13 Step 3).
    """

    node_id: UUID         # foundation node owning the subtopic
    node_slug: str
    subtopic_key: str
    name: str
    gloss: str | None = None


class NodeReadinessTile(BaseModel):
    """One node-level tile for the coarse readiness pass (Phase 13 Step 3).

    Replaces the subtopic ConceptTour. Lives at the PREREQUISITE NODE level —
    solid / rusty / new over the whole node, not per subtopic. The user marks
    each node's overall readiness; detail accrues from engagement + the node
    panel per §B1.
    """

    node_id: UUID
    node_slug: str
    node_title: str
    node_description_preview: str | None = None  # first ~120 chars of description_md


class NodeReadinessStateItem(BaseModel):
    """One user readiness mark for a prereq node."""
    node_id: UUID
    state: str  # 'solid' | 'rusty' | 'new' — mapped to comfortable/active/unseen


class NodeReadinessSubmitRequest(BaseModel):
    """POST /add-interest/node-readiness — write node-level user_node_states."""
    user_id: UUID
    user_interest_id: UUID
    node_states: list[NodeReadinessStateItem]


class ResolveAddInterestResponse(BaseModel):
    user_interest_id: UUID
    node_id: UUID
    node_slug: str
    verdict: str  # 'same' | 'related' | 'new'
    intent_context: str
    starter_preview_md: str
    node_readiness: list[NodeReadinessTile]  # replaces concept_tour (Phase 13 Step 3)


# --- /add-interest/rewrite-summaries -----------------------------------------
# Backfills user-facing prose for existing user_interests.intent_context rows
# that were produced by the older tag-soup prompt. One batch Haiku call per
# user. See web/app/api/profile/regenerate-summaries/route.ts.


class IntentSummaryItem(BaseModel):
    user_interest_id: UUID
    node_title: str
    node_description_md: str | None = None
    subtopics: list[str] = []
    current_context: str


class RewriteIntentSummariesRequest(BaseModel):
    user_id: UUID
    items: list[IntentSummaryItem]


class RewrittenIntentSummary(BaseModel):
    user_interest_id: UUID
    summary: str


class RewriteIntentSummariesLLMOutput(BaseModel):
    """Internal — Haiku's raw return shape."""

    summaries: list[RewrittenIntentSummary]


class RewriteIntentSummariesResponse(BaseModel):
    summaries: list[RewrittenIntentSummary]


# ---------------------------------------------------------------------------
# /surface-daily
# ---------------------------------------------------------------------------


class SurfaceDailyRequest(BaseModel):
    user_id: UUID
    # §A5 steering (optional). Applied before _pick_varied as a best-effort
    # filter; each hint falls back to the full pool if filtering leaves fewer
    # than 1 item so the user is never left with nothing.
    #   shorter      — prefer items with time_estimate_minutes_high ≤ 20
    #   more_papers  — bring paper_engagement items to the front
    #   different    — exclude ref_ids listed in steer_excluded_ref_ids
    #   less_topic   — exclude problems from the given topic node
    steer: Literal["shorter", "more_papers", "different", "less_topic"] | None = None
    steer_excluded_ref_ids: list[UUID] | None = None  # for "different"
    steer_topic_node_id: UUID | None = None           # for "less_topic"


class SurfacedItem(BaseModel):
    queue_item_id: UUID
    kind: str
    ref_id: UUID | None = None
    added_reason: str | None = None
    time_estimate_minutes_low: int | None = None
    time_estimate_minutes_high: int | None = None
    # True when this item was created as a refresher (spaced revisiting). The
    # row's own `kind` drives routing/title; this flag drives the "Refresher"
    # badge + revisit copy in the daily queue. See refresher.py.
    via_refresher: bool = False
    # True for user-requested items (siblings, curiosity-box requests). These
    # survive rerolls and are shown with a "Requested" badge (§A6).
    pinned: bool = False


class SurfaceDailyResponse(BaseModel):
    pick_id: UUID
    items: list[SurfacedItem]
    # Non-surfaced pending items left after this pick. The web layer uses this
    # to fire a background refill when stock runs low (curriculum-curator-design
    # §11.4 refill-on-drain).
    pending_remaining: int = 0


# ---------------------------------------------------------------------------
# /curiosity-box (orientation-and-calibration-design.md §A4)
# ---------------------------------------------------------------------------
# Single-endpoint classify-and-route. Haiku classifies the raw_text into one
# of 9 kinds, then the route dispatches to the lightest sufficient response.
# Low-confidence inputs return a clarifying question instead of guessing.


class CuriosityClassification(BaseModel):
    """Haiku's internal classification output — not exposed to the client."""

    kind: Literal[
        "question",
        "drill",
        "existing_interest",
        "mood",
        "follow_up",
        "paper",
        "feedback",
        "probe",
        "topic_new",
    ]
    confidence: Literal["high", "low"]
    normalized_topic: str | None = None  # for drill/existing_interest/follow_up/topic_new
    paper_ref: str | None = None         # for paper kind — verbatim from input
    added_reason: str                    # first-person: "You asked for a problem on X."
    clarification_md: str                # shown when confidence="low"


class BriefAnswer(BaseModel):
    """Haiku's brief answer for question-kind inputs."""

    answer_md: str          # 2–3 paragraphs of plain markdown prose
    followon_topic_hint: str  # plain English topic name for the follow-on offer


class CuriosityBoxRequest(BaseModel):
    user_id: UUID
    raw_text: str


class CuriosityBoxResponse(BaseModel):
    action: Literal[
        "redirect_steer",
        "redirect_feedback",
        "graceful",
        "topic_new_stub",
        "topic_new_explored",
        "answer",
        "ingest_paper",
        "queued_pinned",
        "clarify",
    ]
    message_md: str
    # action-specific optional fields:
    answer_md: str | None = None              # "answer"
    followon_topic_hint: str | None = None    # "answer"
    queue_item_id: UUID | None = None         # "queued_pinned" / "topic_new_explored"
    paper_ref: str | None = None              # "ingest_paper"
    topic_hint: str | None = None             # "topic_new_stub" / "topic_new_explored"
    clarification_md: str | None = None       # "clarify"


# ---------------------------------------------------------------------------
# /assess-engagement (curriculum-curator-design.md §5)
# ---------------------------------------------------------------------------
# Called after a graded problem attempt or a completed paper engagement.
# Runs a small Haiku call that updates user_node_states (struggle_score,
# state, last_engaged_at, engagement_count) and may execute an
# immediate_action (queue a reinforcement, accelerate, or surface a
# prerequisite refresher).


class AssessEngagementRequest(BaseModel):
    """The Next.js side never calls this directly — it's invoked from
    /grade-solution and /grade-paper-answer. The caller passes either
    attempt_id (problem) or engagement_id (paper); the route loads the rest.
    """

    user_id: UUID
    attempt_id: UUID | None = None
    engagement_id: UUID | None = None


class AssessEngagementResult(BaseModel):
    """Strict shape the Haiku /assess-engagement call must return as JSON."""

    updated_struggle_score: float = Field(..., ge=0.0, le=1.0)
    state_transition: Literal["active", "struggling", "comfortable"] | None = None
    immediate_action: (
        Literal["queue_reinforcement", "accelerate", "surface_prerequisite"] | None
    ) = None
    reinforcement_target: str | None = None
    reasoning: str


class AssessEngagementResponse(BaseModel):
    """Returned to the caller (typically the grade route). Fields mirror the
    Haiku output plus the action_executed flag so the caller can tell whether
    the curator wrote anything new to the queue."""

    updated_struggle_score: float
    state_transition: str | None
    immediate_action: str | None
    action_executed: bool
    reasoning: str


# ---------------------------------------------------------------------------
# /plan-queue (curriculum-curator-design.md §4)
# ---------------------------------------------------------------------------
# Daily Sonnet call, per active user. Reads full user context, returns
# add/reprioritise recommendations, executes them.


class PlanQueueRequest(BaseModel):
    user_id: UUID


class CuratorRecommendation(BaseModel):
    """One add or reprioritise recommendation from the Sonnet planner. Both
    shapes share the model; required fields differ by action."""

    action: Literal["add", "reprioritise"]
    # Add fields
    interest_node: str | None = None      # node title (server resolves)
    kind: Literal["problem", "refresher", "paper_engagement"] | None = None
    intent: Literal["teach", "refresh", "consolidate"] | None = None
    subtopic: str | None = None           # short phrase
    depth: (
        Literal["conceptual", "foundational", "intermediate", "advanced"] | None
    ) = None
    assumed_background: list[str] = Field(default_factory=list)
    # Shared by both actions
    priority: Literal["low", "medium", "high"] | None = None
    reason: str
    # Reprioritise fields
    queue_item_id: UUID | None = None
    new_priority: Literal["low", "medium", "high"] | None = None


class CuratorPlanLLMOutput(BaseModel):
    """Strict shape the Sonnet /plan-queue call must return."""

    recommendations: list[CuratorRecommendation]
    observations: str = ""


class PlanQueueResponse(BaseModel):
    """Per-recommendation outcome of executing the planner output."""

    recommendations_received: int
    items_added: int
    items_reprioritised: int
    items_skipped: int
    observations: str


# ---------------------------------------------------------------------------
# /check-deferred (curriculum-curator-design.md §8)
# ---------------------------------------------------------------------------
# Deterministic, no LLM. Run daily after /plan-queue. For each deferred queue
# item, check whether its blocking prerequisites are now addressed. When yes,
# transition state back to 'pending'.


class CheckDeferredRequest(BaseModel):
    user_id: UUID


class CheckDeferredResponse(BaseModel):
    requeued_count: int
    kept_deferred_count: int


# ---------------------------------------------------------------------------
# /run-daily-planner (curriculum-curator-design.md §15, Phase 10-rev §3d)
# ---------------------------------------------------------------------------
# Per-user wrapper that calls /plan-queue then /check-deferred and records the
# outcome to `curator_job_runs`. Invoked by:
#  - pg_cron daily job (triggered_by='cron'), one HTTP POST per active user
#  - Stage 7 survey completion (triggered_by='cold_start')
#  - Manual operator runs (triggered_by='manual')


class RunDailyPlannerRequest(BaseModel):
    user_id: UUID
    triggered_by: Literal["cron", "cold_start", "manual"] = "manual"


class RunDailyPlannerResponse(BaseModel):
    job_run_id: UUID
    plan_queue_status: Literal["ok", "error", "skipped"]
    plan_queue_items_added: int
    plan_queue_items_reprioritised: int
    plan_queue_items_skipped: int
    check_deferred_requeued: int
    check_deferred_kept: int
    error_message: str | None = None


# ---------------------------------------------------------------------------
# /parse-solution
# ---------------------------------------------------------------------------


class ParseSolutionRequest(BaseModel):
    user_id: UUID
    attempt_id: UUID
    image_urls: list[str]  # pre-signed Supabase Storage URLs (signed by Next.js)


class ParseSolutionResponse(BaseModel):
    attempt_id: UUID
    parsed_markdown: str
    parse_status: str  # 'parsed' | 'failed'


# ---------------------------------------------------------------------------
# /grade-solution
# ---------------------------------------------------------------------------


class GradeResponse(BaseModel):
    """Sonnet grade call output — wrapped in JSON for call_json compatibility."""

    response_md: str


class GradeSolutionRequest(BaseModel):
    user_id: UUID
    attempt_id: UUID
    user_edited_markdown: str  # the user's (possibly-edited) parsed solution


class GradeSolutionResponse(BaseModel):
    grade_response_md: str
    notebook_entry_id: UUID


# ---------------------------------------------------------------------------
# /admin/ingest-paper
# ---------------------------------------------------------------------------


class IngestPaperRequest(BaseModel):
    title: str
    authors_json: list[str]
    year: int
    abstract_md: str
    arxiv_id: str | None = None
    doi: str | None = None
    external_url: str | None = None


class IngestPaperResponse(BaseModel):
    paper_id: UUID
    created: bool


# ---------------------------------------------------------------------------
# /generate-paper-engagement
# ---------------------------------------------------------------------------


class GeneratePaperEngagementRequest(BaseModel):
    user_id: UUID
    paper_id: UUID


class GeneratedEngagement(BaseModel):
    """Strict shape the Sonnet engagement-generation call must return as JSON."""

    why_this_md: str
    orienting_concepts_json: list[dict]  # [{term, definition_md}]
    questions_json: list[dict]  # [{id, kind, prompt_md, order}]


class GeneratePaperEngagementResponse(BaseModel):
    engagement_id: UUID


# ---------------------------------------------------------------------------
# /grade-paper-answer
# ---------------------------------------------------------------------------


class GradePaperAnswerRequest(BaseModel):
    user_id: UUID
    engagement_id: UUID
    question_id: str  # uuid string from questions_json[*].id
    user_response_md: str


class GradePaperAnswerResponse(BaseModel):
    claude_response_md: str
    next_question_index: int  # updated current_question_index; -1 = all done


# ---------------------------------------------------------------------------
# /paper-question
# ---------------------------------------------------------------------------


class PaperQuestionRequest(BaseModel):
    user_id: UUID
    engagement_id: UUID
    user_message_md: str


class PaperQuestionResponse(BaseModel):
    claude_response_md: str
    turn_index: int


# ---------------------------------------------------------------------------
# /suggest-papers
# ---------------------------------------------------------------------------


class SuggestPapersRequest(BaseModel):
    user_id: UUID


class SuggestedPaper(BaseModel):
    paper_id: UUID
    queue_item_id: UUID


class SuggestPapersResponse(BaseModel):
    suggested: list[SuggestedPaper]


# ---------------------------------------------------------------------------
# /ingest-paper-user
# ---------------------------------------------------------------------------


class IngestPaperUserRequest(BaseModel):
    user_id: UUID
    raw_input: str  # arXiv URL, arXiv ID, DOI, or bare title


class IngestPaperUserResponse(BaseModel):
    paper_id: UUID
    queue_item_id: UUID
    created: bool  # False if paper already existed
    engagement_id: UUID


# ---------------------------------------------------------------------------
# /propose-papers
# ---------------------------------------------------------------------------


class ProposePapersRequest(BaseModel):
    user_id: UUID
    # 0.0 = all problems, 1.0 = all papers. Used to compute the paper target
    # count proportional to the queue cap (15). Defaults to 0.5 (50/50 mix).
    mode_balance: float = 0.5


class ProposedPaperCandidate(BaseModel):
    title: str
    authors: list[str]
    year: int
    arxiv_id: str | None = None
    doi: str | None = None
    rationale: str  # one sentence; stored in queue_items.added_reason
    # Which of the user's stated interests this paper maps to — a subset of the
    # interest titles supplied in the prompt, echoed verbatim. Resolved back to
    # node ids and stored in papers.topic_node_ids so the queue card can show
    # the topic(s) the paper is drawn from (d22). Defaults to [] for tolerance.
    interest_titles: list[str] = []


class ProposePapersLLMOutput(BaseModel):
    candidates: list[ProposedPaperCandidate]  # 3–5 items


class ProposePapersResponse(BaseModel):
    papers_added: int        # count of new papers inserted
    papers_reused: int       # count of proposals that matched existing rows
    queue_items_added: int   # may be < papers_added if engagement already exists


class PaperInterestClassification(BaseModel):
    """Haiku response: which of the user's interest titles does a paper map to."""
    interest_titles: list[str] = []


# ---------------------------------------------------------------------------
# /compute-cross-pollination
# ---------------------------------------------------------------------------


class ComputeCrossPollinationRequest(BaseModel):
    pass  # runs for all active users; no per-user scoping


class ComputeCrossPollinationResponse(BaseModel):
    suggestions_created: int
    reason: str  # 'no_curation_yet' | 'ok'


# ---------------------------------------------------------------------------
# /survey/suggest-interests
# ---------------------------------------------------------------------------
# Stage 3 of the onboarding survey (survey-and-difficulty-design.md §1.4):
# 6–10 interest-node suggestion tiles surfaced from the megagraph, ranked by
# overlap with the user's Stage 1 domain chips and prerequisite edges into the
# nodes they marked in Stage 2. Heuristic shortlist + Haiku rerank.


class SurveyDomainInput(BaseModel):
    """One Stage 1 domain entry: the chip key, plus optional sub-area labels
    and a relationship-card label. Labels (not raw keys) so the Haiku prompt
    can name signals verbatim without Python re-deriving display strings."""

    key: str  # 'physics' | 'mathematics' | 'engineering' | 'computation' | 'biology' | 'chemistry'
    label: str
    subarea_labels: list[str] = Field(default_factory=list)
    relationship_label: str | None = None


class SuggestSurveyInterestsRequest(BaseModel):
    user_id: UUID
    domains: list[SurveyDomainInput]
    marked_foundation_node_ids: list[UUID]  # nodes the user marked 'refresh'


class SurveyInterestSuggestion(BaseModel):
    node_id: UUID
    slug: str
    title: str
    description_md: str
    why_suggested_md: str  # one-line rationale, generated by Haiku


class SurveyInterestSuggestionLLMOutput(BaseModel):
    """Internal — Haiku's reranking output. Server resolves slugs back to ids."""

    suggestions: list[dict]  # [{slug, why_suggested_md}]


class SuggestSurveyInterestsResponse(BaseModel):
    suggestions: list[SurveyInterestSuggestion]


# ---------------------------------------------------------------------------
# /concept-review-resolve (phase-10-rev-plan §Step 4, D3)
# ---------------------------------------------------------------------------
# Called when the user taps a kind='concept_review' queue card. Tries the
# problem pool at conceptual depth (intent='teach', difficulty=1, tag = node's
# primary subtopic). On a hit, atomically enqueues a kind='problem' row
# pointing at the pool problem and marks the original concept_review row done.
# On a miss, returns the node's reading-surface content for the client to
# render in serif prose. See survey-and-difficulty-design.md §2.7 Case 3.


class ConceptReviewResolveRequest(BaseModel):
    user_id: UUID
    queue_item_id: UUID


class ConceptReviewNodeReading(BaseModel):
    id: UUID
    slug: str
    title: str
    description_md: str
    subtopics_json: list[dict]  # [{slug, title, gloss_md?}, ...] — may be empty
    brief_md: str | None = None  # generated concept brief (Step 5.5)


class ConceptReviewResolveResponse(BaseModel):
    # kind='problem' → client redirects to /problem/<new_queue_item_id>.
    # kind='reading' → client renders ConceptReadingView with `node`.
    kind: Literal["problem", "reading"]
    queue_item_id: UUID | None = None      # set when kind='problem'
    node: ConceptReviewNodeReading | None = None  # set when kind='reading'


# ---------------------------------------------------------------------------
# /create-refresher (phase-10.5-rev Step 2)
# ---------------------------------------------------------------------------
# Resolves a refresher reference to a concrete, directly-routable queue item
# with via_refresher=true. ref_id is either a refresher_schedule.id (legacy:
# revisit a prior attempt/paper) or a nodes.id (curator-style: pool-first
# refresh-intent problem, generate on miss, concept_review on generation
# failure). The in-process callers (the curator planner + post-engagement
# prerequisite path) call resolve_refresher_to_content directly; this HTTP
# wrapper serves the Next.js on-demand request route.


class CreateRefresherRequest(BaseModel):
    user_id: UUID
    ref_id: UUID  # a refresher_schedule.id or a nodes.id
    reason: str | None = None
    priority_score: float | None = None
    parent_queue_item_id: UUID | None = None


class RefresherResolveResponse(BaseModel):
    # The resolved item's content kind — drives client routing:
    # problem → /problem, paper_engagement → /paper, concept_review →
    # /concept-review. The new queue item carries via_refresher=true.
    kind: Literal["problem", "paper_engagement", "concept_review"]
    queue_item_id: UUID


# ---------------------------------------------------------------------------
# /generate-concept-brief — Step 5.5. One-shot generation of a warm
# concept-orientation brief + per-subtopic glosses, cached on
# node_concept_briefs by node_id. Called inline from /concept-review-resolve's
# miss path when no brief exists yet for the node.
# ---------------------------------------------------------------------------


class GenerateConceptBriefRequest(BaseModel):
    user_id: UUID  # logged on llm_calls; brief itself is not user-specific
    node_id: UUID


class ConceptBriefSubtopicGloss(BaseModel):
    slug: str
    title: str
    gloss_md: str


class GeneratedConceptBrief(BaseModel):
    """Strict shape Haiku must return as JSON."""
    brief_md: str
    subtopic_glosses_json: list[ConceptBriefSubtopicGloss]


class GenerateConceptBriefResponse(BaseModel):
    brief_md: str
    subtopic_glosses_json: list[ConceptBriefSubtopicGloss]
    cached: bool  # true if returned from existing node_concept_briefs row


# ---------------------------------------------------------------------------
# /generate-edge-description — Step 6 follow-up. One-shot generation of a
# short paragraph explaining why two nodes are connected (what specific
# concepts bridge from source to target), cached on edge_descriptions by
# edge_id. Called inline from the EdgePanel surface on first click.
# ---------------------------------------------------------------------------


class GenerateEdgeDescriptionRequest(BaseModel):
    user_id: UUID  # logged on llm_calls; description itself is not user-specific
    edge_id: UUID


class GeneratedEdgeDescription(BaseModel):
    """Strict shape Haiku must return as JSON."""
    description_md: str


class GenerateEdgeDescriptionResponse(BaseModel):
    description_md: str
    cached: bool  # true if returned from existing edge_descriptions row


# ---------------------------------------------------------------------------
# /generate-curation-report
# ---------------------------------------------------------------------------


class GenerateCurationReportRequest(BaseModel):
    pass  # system-level; no user_id — called by the operator UI


class CurationProposalOutput(BaseModel):
    kind: str  # merge|split|rename|promote|demote|add_edge|deprecate
    payload_json: dict  # shape per D2 in phase-8-rev-plan.md


class CurationReportLLMOutput(BaseModel):
    proposals: list[CurationProposalOutput]


class GenerateCurationReportResponse(BaseModel):
    proposals_created: int
    since: str  # ISO timestamp of the input window start


# ---------------------------------------------------------------------------
# /generate-sibling (Phase 12 Step 3 — §A3 correction loop)
# ---------------------------------------------------------------------------
# Pre-start correction loop. The user requests a sibling problem at a
# different difficulty ('easier'/'harder') or with lower assumed background
# ('assume_less'). The original queue_item is superseded and the sibling
# takes its slot in the queue.


class GenerateSiblingRequest(BaseModel):
    user_id: UUID
    queue_item_id: UUID   # the original problem's queue_item
    kind: Literal["easier", "harder", "assume_less"]


class GenerateSiblingResponse(BaseModel):
    sibling_problem_id: UUID | None = None      # None when at max/min difficulty
    sibling_queue_item_id: UUID | None = None
    is_max_difficulty: bool = False
    is_min_difficulty: bool = False


# ---------------------------------------------------------------------------
# /orientation-tutor (Phase 13 Step 4a — §B4 the orientation tutor)
# ---------------------------------------------------------------------------
# The conversational orientation tutor: a guided chat that elicits the four
# signals (A interests, B intent/altitude + path, C foundation readiness, D
# mode), structured underneath. This module is the *orchestrator* — the signal
# state model, gap tracking, resumability, and the chat/form envelopes. The
# system prompt that drives the conversation is a separate first-class
# deliverable (Step 4b); the chat UI + tap-to-answer chips are Step 4c.
#
# Design contract:
#   - The orchestrator tracks which of A/B/C/D are still open and decides when
#     it has enough to offer "build my queue" (ready_to_build). The model is
#     advisory (`proposes_build`); readiness is computed here, not trusted to
#     the model.
#   - Two envelopes over one signal model: mode="chat" (LLM turns) and
#     mode="form" (a structured gaps payload — chips + fields — for the
#     click-not-talk fallback, resolved decision 3). Form mode never calls the
#     LLM.
#   - Signals are written to the SAME structured shape that generation reads
#     (altitude, path_json). The tutor is a new collection surface, not a new
#     storage model — when interests resolve (4c), they land on user_interests
#     via the add-interest core, never re-parsed from the transcript.


class OrientationInterest(BaseModel):
    """Signal A (one interest) carrying its B (altitude + path).

    `resolved` marks whether the add-interest core (/parse → /resolve) has run
    for this interest yet — 4a only *tracks* interests; 4c wires resolution.
    """

    raw_text: str
    node_slug: str | None = None         # resolved megagraph node, once resolved
    altitude: str | None = None          # B: 'new' | 'coming_back' | 'go_deep'
    path_key: str | None = None          # B: chosen path option key (ambiguous only)
    path_json: dict | None = None        # B: the chosen rich path object
    resolved: bool = False


class OrientationSignals(BaseModel):
    """The A/B/C/D tracking struct, persisted as orientation_sessions.signals_json.

    This is the canonical 'what I've got so far' state and the source of truth
    for gap detection. It is the same shape the growing-map UI (4c) renders.
    """

    interests: list[OrientationInterest] = Field(default_factory=list)  # A + B
    foundation_marks: dict[str, str] = Field(default_factory=dict)       # C: slug→solid/rusty/new
    foundation_swept: bool = False                                       # C: the sweep happened
    mode: str | None = None                                              # D: problems/papers/balanced
    work_context: str | None = None                                      # optional flavour escape valve


class OrientationInterestInput(BaseModel):
    """A new interest submitted via a chip/form (deterministic) or extracted by
    the model from free text."""

    raw_text: str
    node_slug: str | None = None
    altitude: str | None = None
    path_key: str | None = None
    path_json: dict | None = None
    resolved: bool = False


class OrientationAltitudeSet(BaseModel):
    """Set altitude (and optionally path) on an already-tracked interest by
    index into signals.interests."""

    interest_index: int
    altitude: str
    path_key: str | None = None
    path_json: dict | None = None


class OrientationSignalUpdate(BaseModel):
    """Structured (non-LLM) signal input from tap-to-answer chips or form
    fields. Applied to the session state deterministically — this is the spine
    4c's chips call and the contract form mode submits against."""

    add_interests: list[OrientationInterestInput] = Field(default_factory=list)  # A (+ optional B)
    set_altitude: list[OrientationAltitudeSet] = Field(default_factory=list)     # B
    foundation_marks: dict[str, str] | None = None                               # C: merge
    foundation_swept: bool | None = None                                         # C: mark swept
    mode: str | None = None                                                      # D
    work_context: str | None = None                                              # flavour


class OrientationExtraction(BaseModel):
    """What the model parsed from the user's latest free-text turn (chat mode).
    Merged into the signal state the same way a structured update is. Kept
    deliberately simple for 4a; the prompt that fills it is Step 4b's work."""

    new_interests: list[OrientationInterestInput] = Field(default_factory=list)
    foundation_marks: dict[str, str] = Field(default_factory=dict)
    foundation_swept: bool | None = None
    mode: str | None = None
    work_context: str | None = None


class OrientationTurnLLMOutput(BaseModel):
    """The model's structured return for one chat turn: the conversational
    reply plus the signals it extracted plus whether it thinks it's done."""

    assistant_message_md: str
    extracted: OrientationExtraction = Field(default_factory=OrientationExtraction)
    proposes_build: bool = False


class OrientationGap(BaseModel):
    """One of the four signals and whether it is satisfied yet."""

    signal: str          # 'A' | 'B' | 'C' | 'D'
    label: str           # human label, e.g. 'Interests'
    satisfied: bool
    detail: str | None = None  # what's still needed when unsatisfied


class OrientationFormField(BaseModel):
    """A structured field/chip-set for form mode (resolved decision 3). Renders
    the same A/B/C/D collection as the chat, without conversation."""

    signal: str          # 'A' | 'B' | 'C' | 'D'
    kind: str            # 'text' | 'altitude' | 'node_readiness' | 'mode'
    prompt: str
    chips: list[str] = Field(default_factory=list)  # chip labels where applicable


class OrientationTutorRequest(BaseModel):
    user_id: UUID
    # Resume an existing session; if null the route loads the user's in-progress
    # session or creates a fresh one.
    session_id: UUID | None = None
    mode: Literal["chat", "form"] = "chat"
    # Free-text turn (chat mode). None = opening greeting (fresh session) or a
    # pure state fetch (existing session, no new input).
    user_message: str | None = None
    # Structured chip/form input, applied deterministically before any LLM call.
    signal_update: OrientationSignalUpdate | None = None
    # The explicit "I'm happy — build my queue" action. Honoured only when the
    # signals are ready_to_build; otherwise the session stays in_progress and
    # the gaps are returned.
    finalize: bool = False


class OrientationTutorResponse(BaseModel):
    session_id: UUID
    mode: str
    status: str                          # 'in_progress' | 'completed'
    assistant_message_md: str | None = None      # chat mode turn
    signals: OrientationSignals                  # the growing 'what I've got so far' map
    gaps: list[OrientationGap]                   # A/B/C/D, satisfied or not
    ready_to_build: bool
    form_fields: list[OrientationFormField] = Field(default_factory=list)  # form mode only
