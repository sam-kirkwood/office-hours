"""POST /parse-solution — vision-parse a photographed handwritten solution.

Flow:
  1. Auth check.
  2. Load the attempts row; verify user_id matches the request.
  3. Build a multi-block user message: one text block + one image block per URL.
  4. Call client.messages.create directly (vision requires content blocks, not a
     plain string, so call_json cannot be used here).
  5. Log manually with log_llm_call.
  6. Determine parse_status: 'parsed' if extraction produced >= 10 chars, else 'failed'.
  7. Update the attempts row with parsed_markdown, parse_status, and llm_call_id.
  8. Return ParseSolutionResponse.
"""

from __future__ import annotations

import logging
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from anthropic_client import (
    _extract_usage,
    _text_from_response,
    get_anthropic_client,
    log_llm_call,
)
from auth import require_internal_token
from config import SONNET_MODEL
from prompts.parse_solution import SYSTEM_PROMPT, USER_TEXT
from schemas import ParseSolutionRequest, ParseSolutionResponse
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/parse-solution",
    response_model=ParseSolutionResponse,
    dependencies=[Depends(require_internal_token)],
)
def parse_solution(
    body: ParseSolutionRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> ParseSolutionResponse:
    # 1. Load attempt; verify it belongs to the requesting user.
    attempt_resp = (
        supabase.table("attempts")
        .select("id, user_id")
        .eq("id", str(body.attempt_id))
        .limit(1)
        .execute()
    )
    if not attempt_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attempt not found")
    if attempt_resp.data[0]["user_id"] != str(body.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_id mismatch")

    # 2. Build the message content: text preamble + one image block per URL.
    content: list[dict] = [{"type": "text", "text": USER_TEXT}]
    for url in body.image_urls:
        content.append({"type": "image", "source": {"type": "url", "url": url}})

    system = [
        {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
    ]
    messages = [{"role": "user", "content": content}]

    # 3. Call Anthropic directly — vision requires content blocks, not a plain string.
    response = anthropic.messages.create(
        model=SONNET_MODEL,
        max_tokens=4096,
        system=system,
        messages=messages,
    )
    input_t, output_t, cache_read_t, cache_write_t = _extract_usage(response)
    text = _text_from_response(response)

    # 4. Log the LLM call (required for every Claude call per project rules).
    llm_call_id = log_llm_call(
        supabase=supabase,
        route="/parse-solution",
        model=SONNET_MODEL,
        input_tokens=input_t,
        output_tokens=output_t,
        cache_read_tokens=cache_read_t,
        cache_write_tokens=cache_write_t,
        request_summary={
            "attempt_id": str(body.attempt_id),
            "image_count": len(body.image_urls),
        },
        response_summary={"output_chars": len(text)},
        user_id=str(body.user_id),
    )

    # 5. Classify success vs failure by content length.
    parse_status = "parsed" if len(text) >= 10 else "failed"

    # 6. Persist the parse result back onto the attempt.
    supabase.table("attempts").update(
        {
            "parsed_markdown": text,
            "parse_status": parse_status,
            "parsed_by_llm_call_id": llm_call_id,
        }
    ).eq("id", str(body.attempt_id)).execute()

    return ParseSolutionResponse(
        attempt_id=body.attempt_id,
        parsed_markdown=text,
        parse_status=parse_status,
    )
