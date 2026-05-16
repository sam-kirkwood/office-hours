"""POST /grade-solution — dialogic feedback on a user's submitted solution.

Flow:
  1. Auth check.
  2. Load attempt → verify user_id; extract problem_id.
  3. Load problem → statement_md, rubric_md, topic_node_id.
     solution_md is the answer key and is deliberately excluded from the select
     so it cannot accidentally appear in the Claude prompt.
  4. Load node → title, slug.
  5. call_json with GradeResponse schema (Sonnet, cached system prompt).
  6. Update attempt: user_edited_markdown, grade_response_md, submitted_at.
  7. Insert notebook_entries row (fts_vector is generated — omit from insert).
  8. Return GradeSolutionResponse.
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
from prompts.grade_solution import build_system_prompt, build_user_prompt
from schemas import GradeResponse, GradeSolutionRequest, GradeSolutionResponse
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/grade-solution",
    response_model=GradeSolutionResponse,
    dependencies=[Depends(require_internal_token)],
)
def grade_solution(
    body: GradeSolutionRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> GradeSolutionResponse:
    # 1. Load attempt; verify ownership.
    attempt_resp = (
        supabase.table("attempts")
        .select("id, user_id, problem_id")
        .eq("id", str(body.attempt_id))
        .limit(1)
        .execute()
    )
    if not attempt_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attempt not found")
    attempt = attempt_resp.data[0]
    if attempt["user_id"] != str(body.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_id mismatch")
    problem_id = attempt["problem_id"]

    # 2. Load problem — statement and rubric only.
    #    solution_md is intentionally excluded: it's the answer key and must
    #    never appear in the grading prompt where it could be echoed to the user.
    problem_resp = (
        supabase.table("problems")
        .select("statement_md, rubric_md, topic_node_id")
        .eq("id", str(problem_id))
        .limit(1)
        .execute()
    )
    if not problem_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="problem not found")
    problem = problem_resp.data[0]

    # 3. Load node for notebook entry metadata.
    node_resp = (
        supabase.table("nodes")
        .select("title, slug")
        .eq("id", str(problem["topic_node_id"]))
        .limit(1)
        .execute()
    )
    if not node_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="node not found")
    node = node_resp.data[0]

    # 4. Sonnet grade call.
    result = call_json(
        client=anthropic,
        supabase=supabase,
        model=SONNET_MODEL,
        system_prompt=build_system_prompt(),
        user_prompt=build_user_prompt(
            statement_md=problem["statement_md"],
            rubric_md=problem["rubric_md"],
            user_edited_markdown=body.user_edited_markdown,
        ),
        schema=GradeResponse,
        route="/grade-solution",
        user_id=str(body.user_id),
        request_summary={
            "attempt_id": str(body.attempt_id),
            "problem_id": str(problem_id),
        },
    )

    # 5. Persist grade result onto the attempt.
    supabase.table("attempts").update(
        {
            "user_edited_markdown": body.user_edited_markdown,
            "grade_response_md": result.response_md,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", str(body.attempt_id)).execute()

    # 6. Create notebook entry (fts_vector is a generated column — excluded).
    nb_resp = (
        supabase.table("notebook_entries")
        .insert(
            {
                "user_id": str(body.user_id),
                "entry_kind": "problem_attempt",
                "ref_id": str(body.attempt_id),
                "title": f"{node['title']} — Problem",
                "topic_node_slugs": [node["slug"]],
            }
        )
        .execute()
    )
    notebook_entry_id = nb_resp.data[0]["id"]

    return GradeSolutionResponse(
        grade_response_md=result.response_md,
        notebook_entry_id=UUID(notebook_entry_id),
    )
