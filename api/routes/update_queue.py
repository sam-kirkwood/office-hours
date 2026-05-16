"""POST /update-queue — stub for Phase 4-rev.

Real implementation lands in Phase 7-rev step 1. The stub exists so the
Next.js survey handler has a callable endpoint after onboarding completes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from auth import require_internal_token
from schemas import UpdateQueueRequest, UpdateQueueResponse

router = APIRouter()


@router.post(
    "/update-queue",
    response_model=UpdateQueueResponse,
    dependencies=[Depends(require_internal_token)],
)
def update_queue(body: UpdateQueueRequest) -> UpdateQueueResponse:  # noqa: ARG001
    return UpdateQueueResponse(ok=True)
