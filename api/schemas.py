from uuid import UUID

from pydantic import BaseModel, Field


class GenerateProblemRequest(BaseModel):
    user_id: UUID
    plan_node_id: UUID


class GeneratedProblem(BaseModel):
    """Strict shape the Sonnet generation call must return as JSON."""

    statement_md: str
    solution_md: str
    rubric_md: str
    hints: list[str] = Field(..., min_length=5, max_length=5)
    generated_context_md: str | None = None


class GenerateProblemResponse(BaseModel):
    problem_id: UUID


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
