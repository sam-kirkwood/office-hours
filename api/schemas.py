from uuid import UUID

from pydantic import BaseModel, Field


class GenerateProblemRequest(BaseModel):
    user_id: UUID
    node_id: UUID  # replaces plan_node_id


class GeneratedProblem(BaseModel):
    """Strict shape the Sonnet generation call must return as JSON."""

    title: str  # plain English, no LaTeX, 4-8 words
    statement_md: str
    solution_md: str
    rubric_md: str
    hints: list[str] = Field(..., min_length=5, max_length=5)
    context_md: str | None = None  # matches DB column name


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
    # Populated for kind='refresher' so the client can link back to original content
    subject_kind: str | None = None            # 'attempt' | 'engagement'
    subject_queue_item_id: UUID | None = None  # original queue item for the link


class SurfaceDailyResponse(BaseModel):
    pick_id: UUID
    items: list[SurfacedItem]


# ---------------------------------------------------------------------------
# /update-queue
# ---------------------------------------------------------------------------


class UpdateQueueRequest(BaseModel):
    user_id: UUID
    trigger: str  # 'attempt_submit' | 'engagement_complete' | 'interest_add'
    ref_id: UUID | None = None  # the attempt_id or engagement_id that triggered this


class UpdateQueueResponse(BaseModel):
    items_reweighted: int
    refreshers_scheduled: int
    items_pruned: int


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
    orienting_concepts_json: list[str]
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


class SuggestSurveyInterestsRequest(BaseModel):
    user_id: UUID
    domain_chips: list[str]  # 'math' | 'physics' | 'applied'
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
