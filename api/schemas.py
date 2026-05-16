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

    verdict: str  # 'same' | 'related' | 'new'
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
    node_id: UUID
    node_slug: str
    verdict: str  # 'same' | 'related' | 'new'
    user_interest_id: UUID


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
# /update-queue
# ---------------------------------------------------------------------------


class UpdateQueueRequest(BaseModel):
    user_id: UUID


class UpdateQueueResponse(BaseModel):
    ok: bool


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
