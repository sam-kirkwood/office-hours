"""POST /paper-question — free-form Q&A turn about the paper.

Flow:
  1. Auth check.
  2. Load engagement; verify user_id; extract paper_id.
  3. Load paper → abstract_md, title, year.
  4. Count existing paper_qa turns → turn_index.
  5. Load all prior paper_qa rows ordered by turn_index → build message history.
  6. Direct client.messages.create(...) call (multi-turn, not call_json).
  7. log_llm_call.
  8. Insert paper_qa row.
  9. Return PaperQuestionResponse.
"""

from __future__ import annotations

import logging

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from anthropic_client import get_anthropic_client, log_llm_call
from auth import require_internal_token
from config import SONNET_MODEL
from schemas import PaperQuestionRequest, PaperQuestionResponse
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/paper-question",
    response_model=PaperQuestionResponse,
    dependencies=[Depends(require_internal_token)],
)
def paper_question(
    body: PaperQuestionRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> PaperQuestionResponse:
    # 2. Load engagement; verify ownership
    eng_resp = (
        supabase.table("paper_engagements")
        .select("id, user_id, paper_id")
        .eq("id", str(body.engagement_id))
        .limit(1)
        .execute()
    )
    if not eng_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="engagement not found")
    eng = eng_resp.data[0]
    if eng["user_id"] != str(body.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_id mismatch")

    # 3. Load paper
    paper_resp = (
        supabase.table("papers")
        .select("title, abstract_md, year")
        .eq("id", eng["paper_id"])
        .limit(1)
        .execute()
    )
    if not paper_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="paper not found")
    paper = paper_resp.data[0]
    title = paper.get("title") or "this paper"
    year = paper.get("year") or ""
    abstract_md = paper.get("abstract_md") or ""

    # 4. Count existing turns
    turns_resp = (
        supabase.table("paper_qa")
        .select("turn_index, user_message_md, claude_response_md")
        .eq("engagement_id", str(body.engagement_id))
        .order("turn_index")
        .execute()
    )
    prior_turns: list[dict] = turns_resp.data or []
    turn_index = len(prior_turns)

    # 5. Build message history
    history: list[dict] = []
    for turn in prior_turns:
        history.append({"role": "user", "content": turn["user_message_md"]})
        if turn.get("claude_response_md"):
            history.append({"role": "assistant", "content": turn["claude_response_md"]})
    history.append({"role": "user", "content": body.user_message_md})

    # 6. Multi-turn Claude call
    system_prompt = (
        f"You are a reading companion for this paper: {title}"
        + (f" ({year})" if year else "")
        + ".\n\n"
        "Answer the reader's questions about the paper faithfully and concisely.\n"
        "- Draw only on the abstract and the paper's domain knowledge.\n"
        f"- Abstract: {abstract_md}\n"
        "- If you are unsure, say so.\n"
        "- Keep responses to 1–3 paragraphs.\n"
        "Output plain Markdown."
    )

    response = anthropic.messages.create(
        model=SONNET_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=history,
    )

    usage = response.usage
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0

    claude_response_md = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            claude_response_md = block.text
            break

    # 7. Log
    log_llm_call(
        supabase=supabase,
        route="/paper-question",
        model=SONNET_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        user_id=str(body.user_id),
        request_summary={
            "engagement_id": str(body.engagement_id),
            "turn_index": turn_index,
        },
    )

    # 8. Insert paper_qa row
    supabase.table("paper_qa").insert(
        {
            "engagement_id": str(body.engagement_id),
            "turn_index": turn_index,
            "user_message_md": body.user_message_md,
            "claude_response_md": claude_response_md,
        }
    ).execute()

    return PaperQuestionResponse(
        claude_response_md=claude_response_md,
        turn_index=turn_index,
    )
