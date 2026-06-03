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


class GeneratedProblem(BaseModel):
    """Strict shape the Sonnet generation call must return as JSON."""

    title: str  # plain English, no LaTeX, 4-8 words
    statement_md: str
    solution_md: str
    rubric_md: str
    hints: list[str] = Field(..., min_length=5, max_length=5)
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
    draft_intent_context: str  # intent_context if the user picks this path


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
    intent_context: str                 # the soft text stored on user_interests

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
    """

    node_id: UUID         # foundation node owning the subtopic
    node_slug: str
    subtopic_key: str
    name: str
    gloss: str | None = None


class ResolveAddInterestResponse(BaseModel):
    user_interest_id: UUID
    node_id: UUID
    node_slug: str
    verdict: str  # 'same' | 'related' | 'new'
    intent_context: str
    starter_preview_md: str
    concept_tour: list[ConceptTourTile]


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


class SurfacedItem(BaseModel):
    queue_item_id: UUID
    kind: str
    ref_id: UUID | None = None
    added_reason: str | None = None
    time_estimate_minutes_low: int | None = None
    time_estimate_minutes_high: int | None = None


class SurfaceDailyResponse(BaseModel):
    pick_id: UUID
    items: list[SurfacedItem]


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


class ProposedPaperCandidate(BaseModel):
    title: str
    authors: list[str]
    year: int
    arxiv_id: str | None = None
    doi: str | None = None
    rationale: str  # one sentence; stored in queue_items.added_reason


class ProposePapersLLMOutput(BaseModel):
    candidates: list[ProposedPaperCandidate]  # 3–5 items


class ProposePapersResponse(BaseModel):
    papers_added: int        # count of new papers inserted
    papers_reused: int       # count of proposals that matched existing rows
    queue_items_added: int   # may be < papers_added if engagement already exists


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
# /refresher-resolve (phase-10-rev Step 8 fix)
# ---------------------------------------------------------------------------
# Called when the user taps a kind='refresher' queue card. Two shapes of
# refresher exist:
#   (a) Legacy/deterministic — ref_id points to a refresher_schedule row whose
#       subject is a prior attempt or paper engagement. Resolution redirects
#       back to the original problem/paper queue item.
#   (b) Curator-style — ref_id points directly to a node (the curator emits
#       this for ad-hoc refreshers; see api/routes/curator.py). Resolution
#       pool-looks-up at intent='refresh', difficulty=1 on that node. On hit,
#       enqueues a kind='problem' row; on miss, enqueues a kind='concept_review'
#       row pointing at the same node so the user still has somewhere to land.
# In both cases the original refresher queue_items row is marked 'done'.


class RefresherResolveRequest(BaseModel):
    user_id: UUID
    queue_item_id: UUID


class RefresherResolveResponse(BaseModel):
    # kind='problem' → client redirects to /problem/<queue_item_id>.
    # kind='paper_engagement' → client redirects to /paper/<queue_item_id>.
    # kind='concept_review' → client redirects to /concept-review/<queue_item_id>.
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
