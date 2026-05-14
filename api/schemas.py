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
