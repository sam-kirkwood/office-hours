from uuid import UUID

from pydantic import BaseModel, Field


class GenerateProblemRequest(BaseModel):
    user_id: UUID
    node_id: UUID  # replaces plan_node_id


class GeneratedProblem(BaseModel):
    """Strict shape the Sonnet generation call must return as JSON."""

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
# /add-interest
# ---------------------------------------------------------------------------


class AddInterestRequest(BaseModel):
    user_id: UUID
    raw_text: str
    added_via: str  # 'survey' | 'explicit_request'


class DeduplicationVerdict(BaseModel):
    """Haiku dedup call output."""

    verdict: str  # 'same' | 'related' | 'new' | 'split' | 'vague'
    matched_node_slug: str | None = None
    reason: str | None = None


class GeneratedInterestNode(BaseModel):
    """Sonnet node-generation call output."""

    title: str
    slug: str  # kebab-case, lowercase, ASCII
    description_md: str
    domain: str  # 'math' | 'physics' | 'applied'
    difficulty_hint: str  # 'intro' | 'core' | 'advanced'
    subtopics: list[str]  # display names, not slugs
    proposed_prerequisite_slugs: list[str]


class AddInterestResponse(BaseModel):
    node_id: UUID | None = None
    node_slug: str | None = None
    verdict: str  # 'same' | 'related' | 'new' | 'split' | 'vague'
    user_interest_id: UUID | None = None
    clarification_prompt: str | None = None  # for 'split' and 'vague' verdicts


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
