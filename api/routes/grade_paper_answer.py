"""POST /grade-paper-answer — dialogic response to a user's answer on a guided question.

Flow:
  1. Auth check.
  2. Load paper_engagements by engagement_id; verify user_id.
  3. Load papers by paper_id → abstract_md.
  4. Find question in questions_json by question_id → 404 if missing.
  5. Sonnet call (call_json with GradeResponse schema) — paper answer prompt.
  6. Upsert paper_answers (engagement_id, question_id) — allows re-answering.
  7. Advance current_question_index; if last question → state='completed'.
  8. Return GradePaperAnswerResponse.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from anthropic_client import call_json, get_anthropic_client
from auth import require_internal_token
from config import SONNET_MODEL
from prompts.paper_answer import build_system_prompt, build_user_prompt
from routes.curator import run_assess_engagement
from schemas import GradePaperAnswerRequest, GradePaperAnswerResponse, GradeResponse
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_unique_violation(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if code in ("23505", 23505):
        return True
    return "23505" in str(exc) or "duplicate key" in str(exc).lower()


@router.post(
    "/grade-paper-answer",
    response_model=GradePaperAnswerResponse,
    dependencies=[Depends(require_internal_token)],
)
def grade_paper_answer(
    body: GradePaperAnswerRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> GradePaperAnswerResponse:
    # 2. Load engagement; verify ownership
    eng_resp = (
        supabase.table("paper_engagements")
        .select("id, user_id, paper_id, questions_json, current_question_index, state")
        .eq("id", str(body.engagement_id))
        .limit(1)
        .execute()
    )
    if not eng_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="engagement not found")
    eng = eng_resp.data[0]
    if eng["user_id"] != str(body.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_id mismatch")

    # 3. Load paper for context
    paper_resp = (
        supabase.table("papers")
        .select("abstract_md")
        .eq("id", eng["paper_id"])
        .limit(1)
        .execute()
    )
    if not paper_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="paper not found")
    abstract_md = paper_resp.data[0].get("abstract_md") or ""

    # 4. Find question
    questions: list[dict] = eng["questions_json"] or []
    question = next((q for q in questions if str(q.get("id")) == body.question_id), None)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="question not found")

    # 5. Sonnet call
    result = call_json(
        client=anthropic,
        supabase=supabase,
        model=SONNET_MODEL,
        system_prompt=build_system_prompt(),
        user_prompt=build_user_prompt(
            abstract_md=abstract_md,
            question_kind=question.get("kind", "comprehension"),
            question_prompt_md=question.get("prompt_md", ""),
            user_response_md=body.user_response_md,
        ),
        schema=GradeResponse,
        route="/grade-paper-answer",
        user_id=str(body.user_id),
        max_tokens=2048,
        request_summary={
            "engagement_id": str(body.engagement_id),
            "question_id": body.question_id,
        },
    )

    # 6. Upsert paper_answers
    try:
        supabase.table("paper_answers").upsert(
            {
                "engagement_id": str(body.engagement_id),
                "question_id": body.question_id,
                "user_response_md": body.user_response_md,
                "claude_response_md": result.response_md,
                "submitted_at": _now_iso(),
            },
            on_conflict="engagement_id,question_id",
        ).execute()
    except Exception as exc:  # noqa: BLE001
        if not _is_unique_violation(exc):
            raise
        # Concurrent upsert — safe to ignore; the winner wrote the row
        logger.warning("paper_answers upsert race on engagement=%s question=%s",
                       body.engagement_id, body.question_id)

    # 7. Advance current_question_index
    sorted_questions = sorted(questions, key=lambda q: q.get("order", 0))
    current_orders = [q.get("order", 0) for q in sorted_questions]
    this_order = question.get("order", 0)
    next_orders = [o for o in current_orders if o > this_order]
    is_last = not next_orders

    if is_last:
        supabase.table("paper_engagements").update(
            {
                "state": "completed",
                "current_question_index": len(questions),
                "completed_at": _now_iso(),
                "updated_at": _now_iso(),
            }
        ).eq("id", str(body.engagement_id)).execute()
        next_index = -1
        # Post-engagement assessment runs only on completion. Best-effort.
        try:
            run_assess_engagement(
                supabase=supabase,
                anthropic=anthropic,
                user_id=str(body.user_id),
                engagement_id=str(body.engagement_id),
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "assess-engagement failed for paper engagement=%s",
                body.engagement_id,
            )
    else:
        next_idx = current_orders.index(min(next_orders))
        supabase.table("paper_engagements").update(
            {
                "current_question_index": next_idx,
                "state": "in_progress",
                "updated_at": _now_iso(),
            }
        ).eq("id", str(body.engagement_id)).execute()
        next_index = next_idx

    return GradePaperAnswerResponse(
        claude_response_md=result.response_md,
        next_question_index=next_index,
    )
