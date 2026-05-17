"""Anthropic client wrapper.

Every Claude call MUST flow through `call_json` (or, in future, a streaming
equivalent) so that `log_llm_call` is invoked on every attempt — including
retries and parse failures. The `llm_calls` row is what powers the Phase 6
cost dashboard, so a missed write is a hole in the observability story.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError
from supabase import Client

from config import HAIKU_MODEL, SONNET_MODEL, get_settings

logger = logging.getLogger(__name__)


# Per-million-token pricing in USD. Confirmed with the operator on 2026-05-14.
# Update when Anthropic changes published prices.
PRICING: dict[str, dict[str, float]] = {
    SONNET_MODEL: {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write": 3.75,
    },
    HAIKU_MODEL: {
        "input": 1.00,
        "output": 5.00,
        "cache_read": 0.10,
        "cache_write": 1.25,
    },
}


@lru_cache
def get_anthropic_client() -> Anthropic:
    return Anthropic(api_key=get_settings().anthropic_api_key)


def estimate_cost_usd(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
) -> float:
    rates = PRICING.get(model)
    if rates is None:
        logger.warning("no pricing for model=%s; recording cost as 0", model)
        return 0.0
    return (
        input_tokens * rates["input"]
        + output_tokens * rates["output"]
        + cache_read_tokens * rates["cache_read"]
        + cache_write_tokens * rates["cache_write"]
    ) / 1_000_000


def log_llm_call(
    *,
    supabase: Client,
    route: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    request_summary: dict | None = None,
    response_summary: dict | None = None,
    user_id: str | None = None,
) -> str | None:
    """Insert a row into `llm_calls`. Returns the new row id, or None if the
    insert failed (we never want logging to block a user-facing call)."""
    cost = estimate_cost_usd(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )
    payload = {
        "route": route,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "estimated_cost_usd": cost,
        "request_summary": request_summary,
        "response_summary": response_summary,
        "user_id": user_id,
    }
    try:
        result = supabase.table("llm_calls").insert(payload).execute()
        return result.data[0]["id"] if result.data else None
    except Exception:
        logger.exception("failed to log llm_call (route=%s model=%s)", route, model)
        return None


def _extract_json(text: str) -> str:
    """Strip optional ```json fences and extract the JSON object.

    Handles three cases Claude produces in practice:
      1. Clean JSON with no fences.
      2. JSON wrapped in ```...``` fences.
      3. JSON followed by trailing prose (e.g. "Note: …") — extract by
         walking matched braces so trailing text is silently dropped.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[: -len("```")]
    stripped = stripped.strip()

    # Find the JSON object boundaries so trailing prose is ignored.
    start = stripped.find("{")
    if start == -1:
        return stripped
    depth = 0
    for i, ch in enumerate(stripped[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : i + 1]
    return stripped


def _extract_usage(response) -> tuple[int, int, int, int]:
    usage = response.usage
    return (
        getattr(usage, "input_tokens", 0) or 0,
        getattr(usage, "output_tokens", 0) or 0,
        getattr(usage, "cache_read_input_tokens", 0) or 0,
        getattr(usage, "cache_creation_input_tokens", 0) or 0,
    )


def _text_from_response(response) -> str:
    for block in response.content:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


def call_json[T: BaseModel](
    *,
    client: Anthropic,
    supabase: Client,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema: type[T],
    route: str,
    user_id: str | None = None,
    request_summary: dict | None = None,
    max_tokens: int = 4096,
    temperature: float | None = None,
) -> T:
    """Call Claude expecting a single JSON object, parse into `schema`, retry
    once on parse/validation failure. Every API call is logged to `llm_calls`
    — including the failed first attempt on a retry.

    `temperature=None` (the default) omits the field and uses Anthropic's
    default (1.0). Pass `temperature=0` for classification tasks where
    determinism matters — e.g., hook matching, where non-determinism breaks
    the (topic, difficulty, hook) cache key by flipping the chosen hook
    between otherwise-identical requests.
    """
    system = [
        {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
    ]
    messages: list[dict] = [{"role": "user", "content": user_prompt}]

    extra: dict = {}
    if temperature is not None:
        extra["temperature"] = temperature

    last_error: Exception | None = None
    last_text = ""

    for attempt in range(2):
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            **extra,
        )
        input_t, output_t, cache_read_t, cache_write_t = _extract_usage(response)
        text = _text_from_response(response)
        log_llm_call(
            supabase=supabase,
            route=route,
            model=model,
            input_tokens=input_t,
            output_tokens=output_t,
            cache_read_tokens=cache_read_t,
            cache_write_tokens=cache_write_t,
            request_summary={**(request_summary or {}), "attempt": attempt + 1},
            response_summary={"output_chars": len(text)},
            user_id=user_id,
        )

        try:
            return schema.model_validate_json(_extract_json(text))
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            last_text = text
            logger.warning(
                "call_json parse failure on attempt %d (route=%s): %s",
                attempt + 1,
                route,
                exc,
            )
            # Add the bad reply + a tightening correction and retry.
            messages = [
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": text},
                {
                    "role": "user",
                    "content": (
                        "Your previous response could not be parsed against the "
                        f"required schema. Error: {exc}. Reply with ONLY the JSON "
                        "object — no prose, no markdown fences, nothing else."
                    ),
                },
            ]

    raise ValueError(
        f"call_json failed to produce valid JSON for route={route} after 2 attempts: "
        f"{last_error}; last_text_head={last_text[:200]!r}"
    )
