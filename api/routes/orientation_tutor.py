"""POST /orientation-tutor — the conversational orientation orchestrator.

Phase 13 Step 4a (orientation-and-calibration-design.md §B4). This is the
*machinery* under the tutor: the A/B/C/D signal state, gap tracking, session
persistence + resumability, and the two envelopes over one signal model —
mode="chat" (LLM turns) and mode="form" (a structured gaps payload, resolved
decision 3). The conversational quality lives in the system prompt (Step 4b);
the chat UI + tap-to-answer chips live in Step 4c.

The orchestrator — not the model — owns the readiness decision. The model's
`proposes_build` is advisory; `is_ready_to_build` here is canonical.

Signals are tracked in the same structured shape generation reads (altitude,
path_json). When interests resolve (4c), they land on user_interests via the
add-interest core — never re-parsed from the transcript.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from anthropic_client import call_json, get_anthropic_client
from auth import require_internal_token
from config import SONNET_MODEL
from prompts import orientation_tutor as prompts
from schemas import (
    OrientationExtraction,
    OrientationFormField,
    OrientationGap,
    OrientationInterest,
    OrientationSignals,
    OrientationSignalUpdate,
    OrientationTurnLLMOutput,
    OrientationTutorRequest,
    OrientationTutorResponse,
)
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter()

# Signal labels, shared by gap detection and the form fallback.
_SIGNAL_LABELS = {
    "A": "Interests",
    "B": "Intent & level",
    "C": "Foundations",
    "D": "Mode",
}


# ---------------------------------------------------------------------------
# Pure signal-state helpers (importable; no DB / LLM)
# ---------------------------------------------------------------------------


def _norm(text: str) -> str:
    return text.strip().lower()


def apply_signal_update(
    signals: OrientationSignals, update: OrientationSignalUpdate
) -> OrientationSignals:
    """Merge a structured (chip/form) update into the signal state. Deterministic
    — this is the spine 4c's chips call and the contract form mode submits."""
    by_text = {_norm(i.raw_text): i for i in signals.interests}

    # A (+ optional B): add or update interests, deduped by raw_text.
    for inp in update.add_interests:
        key = _norm(inp.raw_text)
        existing = by_text.get(key)
        if existing is None:
            interest = OrientationInterest(**inp.model_dump())
            signals.interests.append(interest)
            by_text[key] = interest
        else:
            # Update only the fields the input actually carried.
            data = inp.model_dump(exclude_unset=True)
            for field, value in data.items():
                if field == "raw_text":
                    continue
                setattr(existing, field, value)

    # B: set altitude (and optional path) on a tracked interest by index.
    for alt in update.set_altitude:
        if 0 <= alt.interest_index < len(signals.interests):
            interest = signals.interests[alt.interest_index]
            interest.altitude = alt.altitude
            if alt.path_key is not None:
                interest.path_key = alt.path_key
            if alt.path_json is not None:
                interest.path_json = alt.path_json
        else:
            logger.warning(
                "orientation: set_altitude index %d out of range (%d interests)",
                alt.interest_index,
                len(signals.interests),
            )

    # C: foundation readiness marks + the sweep flag.
    if update.foundation_marks:
        signals.foundation_marks.update(update.foundation_marks)
    if update.foundation_swept is not None:
        signals.foundation_swept = update.foundation_swept

    # D + flavour.
    if update.mode is not None:
        signals.mode = update.mode
    if update.work_context is not None:
        signals.work_context = update.work_context

    return signals


def apply_extraction(
    signals: OrientationSignals, extraction: OrientationExtraction
) -> OrientationSignals:
    """Merge the model's per-turn extraction into the signal state — same merge
    rules as a structured update, narrower surface."""
    update = OrientationSignalUpdate(
        add_interests=extraction.new_interests,
        foundation_marks=extraction.foundation_marks or None,
        foundation_swept=extraction.foundation_swept,
        mode=extraction.mode,
        work_context=extraction.work_context,
    )
    return apply_signal_update(signals, update)


def compute_gaps(signals: OrientationSignals) -> list[OrientationGap]:
    """Which of A/B/C/D are still open. The orchestrator nudges the model to
    close these before offering to build the queue."""
    gaps: list[OrientationGap] = []

    # A — at least one interest.
    has_interests = len(signals.interests) > 0
    gaps.append(
        OrientationGap(
            signal="A",
            label=_SIGNAL_LABELS["A"],
            satisfied=has_interests,
            detail=None if has_interests else "No interests captured yet.",
        )
    )

    # B — every interest has an altitude (new / coming-back / go-deep).
    missing_alt = [i.raw_text for i in signals.interests if not i.altitude]
    b_satisfied = has_interests and not missing_alt
    if not has_interests:
        b_detail = "Need an interest first."
    elif missing_alt:
        b_detail = f"{len(missing_alt)} interest(s) still need new / coming-back / go-deep."
    else:
        b_detail = None
    gaps.append(
        OrientationGap(signal="B", label=_SIGNAL_LABELS["B"], satisfied=b_satisfied, detail=b_detail)
    )

    # C — the coarse node-level readiness sweep happened (marks may be empty if
    # everything is new; the sweep being done is the signal).
    gaps.append(
        OrientationGap(
            signal="C",
            label=_SIGNAL_LABELS["C"],
            satisfied=signals.foundation_swept,
            detail=None if signals.foundation_swept else "Foundation readiness not checked yet.",
        )
    )

    # D — mode chosen.
    d_satisfied = signals.mode is not None
    gaps.append(
        OrientationGap(
            signal="D",
            label=_SIGNAL_LABELS["D"],
            satisfied=d_satisfied,
            detail=None if d_satisfied else "Problems, papers, or both — not set yet.",
        )
    )

    return gaps


def is_ready_to_build(signals: OrientationSignals) -> bool:
    """All four signals satisfied — the tutor may offer 'build my queue'."""
    return all(g.satisfied for g in compute_gaps(signals))


def build_form_fields(signals: OrientationSignals) -> list[OrientationFormField]:
    """Form-mode (resolved decision 3) structured inputs for the still-open
    signals — the same A/B/C/D collection as the chat, without conversation."""
    fields: list[OrientationFormField] = []
    for gap in compute_gaps(signals):
        if gap.satisfied:
            continue
        if gap.signal == "A":
            fields.append(
                OrientationFormField(
                    signal="A",
                    kind="text",
                    prompt="What would you like to work on or get back to?",
                )
            )
        elif gap.signal == "B":
            fields.append(
                OrientationFormField(
                    signal="B",
                    kind="altitude",
                    prompt="For each interest — are you new to it, coming back, or going deep?",
                    chips=["New to me", "Coming back", "I know this — go deep"],
                )
            )
        elif gap.signal == "C":
            fields.append(
                OrientationFormField(
                    signal="C",
                    kind="node_readiness",
                    prompt="How solid are the foundations these lean on?",
                    chips=["Solid", "Rusty", "New"],
                )
            )
        elif gap.signal == "D":
            fields.append(
                OrientationFormField(
                    signal="D",
                    kind="mode",
                    prompt="Do you lean toward working problems, reading papers, or both?",
                    chips=["Problems", "Papers", "Both"],
                )
            )
    return fields


# ---------------------------------------------------------------------------
# Session persistence
# ---------------------------------------------------------------------------


def _load_or_create_session(
    supabase: Client, *, user_id: str, session_id: str | None
) -> dict:
    """Resolve the working session row. Resume by id, else the user's single
    in-progress session (the partial unique index guarantees ≤1), else create."""
    if session_id:
        resp = (
            supabase.table("orientation_sessions")
            .select("id, user_id, status, transcript_json, signals_json")
            .eq("id", session_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
        row = rows[0]
        if row["user_id"] != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_id mismatch")
        return row

    resp = (
        supabase.table("orientation_sessions")
        .select("id, user_id, status, transcript_json, signals_json")
        .eq("user_id", user_id)
        .eq("status", "in_progress")
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if rows:
        return rows[0]

    insert = (
        supabase.table("orientation_sessions")
        .insert(
            {
                "user_id": user_id,
                "status": "in_progress",
                "transcript_json": [],
                "signals_json": {},
            }
        )
        .execute()
    )
    new_id = insert.data[0]["id"]
    return {
        "id": new_id,
        "user_id": user_id,
        "status": "in_progress",
        "transcript_json": [],
        "signals_json": {},
    }


def _persist_session(
    supabase: Client,
    *,
    session_id: str,
    transcript: list[dict],
    signals: OrientationSignals,
    status_value: str,
) -> None:
    supabase.table("orientation_sessions").update(
        {
            "transcript_json": transcript,
            "signals_json": signals.model_dump(mode="json"),
            "status": status_value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", session_id).execute()


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post(
    "/orientation-tutor",
    response_model=OrientationTutorResponse,
    dependencies=[Depends(require_internal_token)],
)
def orientation_tutor(
    body: OrientationTutorRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> OrientationTutorResponse:
    user_id = str(body.user_id)
    row = _load_or_create_session(
        supabase,
        user_id=user_id,
        session_id=str(body.session_id) if body.session_id else None,
    )
    session_id = row["id"]
    transcript: list[dict] = list(row.get("transcript_json") or [])
    signals = OrientationSignals.model_validate(row.get("signals_json") or {})

    # 1. Apply any structured chip/form input first (deterministic, no LLM).
    if body.signal_update is not None:
        signals = apply_signal_update(signals, body.signal_update)

    assistant_message_md: str | None = None

    if body.mode == "chat":
        # Call the model on a real user turn or the opening greeting (empty
        # transcript). A pure state fetch on an existing conversation does not.
        should_call_llm = body.user_message is not None or len(transcript) == 0
        if should_call_llm:
            if body.user_message is not None:
                transcript.append({"role": "user", "content": body.user_message})

            open_signals = [g.label for g in compute_gaps(signals) if not g.satisfied]
            output: OrientationTurnLLMOutput = call_json(
                client=anthropic,
                supabase=supabase,
                model=SONNET_MODEL,
                system_prompt=prompts.build_system_prompt(),
                user_prompt=prompts.build_user_prompt(
                    transcript=transcript,
                    user_message=body.user_message,
                    signals_summary=signals.model_dump(mode="json"),
                    open_signals=open_signals,
                ),
                schema=OrientationTurnLLMOutput,
                route="/orientation-tutor",
                user_id=user_id,
                request_summary={
                    "turns": len(transcript),
                    "mode": "chat",
                },
            )
            signals = apply_extraction(signals, output.extracted)
            assistant_message_md = output.assistant_message_md
            transcript.append({"role": "assistant", "content": assistant_message_md})

    gaps = compute_gaps(signals)
    ready = is_ready_to_build(signals)

    # 2. Honour an explicit "build my queue" only when the signals are ready.
    status_value = row.get("status", "in_progress")
    if body.finalize and ready:
        status_value = "completed"

    _persist_session(
        supabase,
        session_id=session_id,
        transcript=transcript,
        signals=signals,
        status_value=status_value,
    )

    form_fields = build_form_fields(signals) if body.mode == "form" else []

    return OrientationTutorResponse(
        session_id=session_id,
        mode=body.mode,
        status=status_value,
        assistant_message_md=assistant_message_md,
        signals=signals,
        gaps=gaps,
        ready_to_build=ready,
        form_fields=form_fields,
    )
