"""Tests for POST /orientation-tutor (Phase 13 Step 4a).

Three required surfaces (the 4a end boundary):
  1. signal-tracking — the A/B/C/D gap detection + merge helpers.
  2. resumability    — transcript + signals persist and reload across calls.
  3. form-mode gaps  — mode="form" returns a structured gaps payload, no LLM.

Plus auth and the chat-turn LLM path. The *conversational quality* of the
tutor (the system prompt) is Step 4b's deliverable and is not asserted here.
"""

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from anthropic_client import get_anthropic_client
from main import app
from routes.orientation_tutor import (
    apply_extraction,
    apply_signal_update,
    build_form_fields,
    compute_gaps,
    is_ready_to_build,
)
from schemas import (
    OrientationExtraction,
    OrientationInterest,
    OrientationInterestInput,
    OrientationSignals,
    OrientationSignalUpdate,
)
from supabase_client import get_supabase_client
from tests.fake_anthropic import FakeAnthropic
from tests.fake_supabase import FakeSupabase

INTERNAL_TOKEN = "test-internal-token"
AUTH_HEADERS = {"Authorization": f"Bearer {INTERNAL_TOKEN}"}


@pytest.fixture
def fakes() -> tuple[FakeSupabase, FakeAnthropic]:
    fake_supabase = FakeSupabase()
    fake_anthropic = FakeAnthropic()
    app.dependency_overrides[get_supabase_client] = lambda: fake_supabase
    app.dependency_overrides[get_anthropic_client] = lambda: fake_anthropic
    try:
        yield fake_supabase, fake_anthropic
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(fakes) -> TestClient:  # noqa: ARG001
    return TestClient(app)


def _prime_llm_calls(supabase: FakeSupabase) -> None:
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])


def _wire_session_store(supabase: FakeSupabase, initial: dict | None = None) -> dict:
    """A stateful in-memory orientation_sessions row so select/insert/update
    round-trip within and across requests (resumability)."""
    store: dict = {"row": initial}

    def select(_call):
        return [store["row"]] if store["row"] else []

    def insert(call):
        new = {
            "id": str(uuid4()),
            "user_id": call.payload["user_id"],
            "status": call.payload["status"],
            "transcript_json": call.payload["transcript_json"],
            "signals_json": call.payload["signals_json"],
        }
        store["row"] = new
        return [{"id": new["id"]}]

    def update(call):
        if store["row"]:
            store["row"].update(call.payload)
        return [{}]

    supabase.respond("orientation_sessions", "select", select)
    supabase.respond("orientation_sessions", "insert", insert)
    supabase.respond("orientation_sessions", "update", update)
    return store


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post("/orientation-tutor", json={"user_id": str(uuid4()), "mode": "form"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 1. Signal-tracking (pure helpers — no DB / LLM)
# ---------------------------------------------------------------------------


def test_gaps_empty_state_all_open() -> None:
    gaps = compute_gaps(OrientationSignals())
    by_sig = {g.signal: g for g in gaps}
    assert set(by_sig) == {"A", "B", "C", "D"}
    assert all(not g.satisfied for g in gaps)
    assert not is_ready_to_build(OrientationSignals())


def test_gaps_close_as_signals_arrive() -> None:
    s = OrientationSignals()

    # A: add an interest, no altitude yet → A satisfied, B still open.
    s = apply_signal_update(s, OrientationSignalUpdate(
        add_interests=[OrientationInterestInput(raw_text="general relativity")]
    ))
    by_sig = {g.signal: g.satisfied for g in compute_gaps(s)}
    assert by_sig["A"] is True
    assert by_sig["B"] is False  # interest lacks altitude
    assert not is_ready_to_build(s)

    # B: set altitude on interest 0 → B satisfied.
    from schemas import OrientationAltitudeSet
    s = apply_signal_update(s, OrientationSignalUpdate(
        set_altitude=[OrientationAltitudeSet(interest_index=0, altitude="coming_back")]
    ))
    assert {g.signal: g.satisfied for g in compute_gaps(s)}["B"] is True

    # C: mark the readiness sweep done → C satisfied (marks may be empty).
    s = apply_signal_update(s, OrientationSignalUpdate(foundation_swept=True))
    assert {g.signal: g.satisfied for g in compute_gaps(s)}["C"] is True
    assert not is_ready_to_build(s)  # D still open

    # D: choose mode → ready.
    s = apply_signal_update(s, OrientationSignalUpdate(mode="balanced"))
    assert {g.signal: g.satisfied for g in compute_gaps(s)}["D"] is True
    assert is_ready_to_build(s)


def test_add_interests_dedupes_by_raw_text() -> None:
    s = OrientationSignals()
    s = apply_signal_update(s, OrientationSignalUpdate(
        add_interests=[OrientationInterestInput(raw_text="Quantum")]
    ))
    # Re-adding the same text (different case/space) updates in place, not append.
    s = apply_signal_update(s, OrientationSignalUpdate(
        add_interests=[OrientationInterestInput(raw_text=" quantum ", altitude="go_deep")]
    ))
    assert len(s.interests) == 1
    assert s.interests[0].altitude == "go_deep"


def test_apply_extraction_merges_like_an_update() -> None:
    s = OrientationSignals()
    s = apply_extraction(s, OrientationExtraction(
        new_interests=[OrientationInterestInput(raw_text="fluids", altitude="new")],
        mode="problems",
        foundation_swept=True,
    ))
    assert s.interests[0].raw_text == "fluids"
    assert s.interests[0].altitude == "new"
    assert s.mode == "problems"
    assert s.foundation_swept is True


def test_set_altitude_out_of_range_is_ignored() -> None:
    from schemas import OrientationAltitudeSet
    s = OrientationSignals(interests=[OrientationInterest(raw_text="x")])
    s = apply_signal_update(s, OrientationSignalUpdate(
        set_altitude=[OrientationAltitudeSet(interest_index=5, altitude="new")]
    ))
    assert s.interests[0].altitude is None  # untouched, no crash


# ---------------------------------------------------------------------------
# 3. Form-mode gaps payload (no LLM)
# ---------------------------------------------------------------------------


def test_form_mode_fresh_returns_all_four_fields_no_llm(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    _wire_session_store(supabase)
    _prime_llm_calls(supabase)

    resp = client.post(
        "/orientation-tutor",
        json={"user_id": str(uuid4()), "mode": "form"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mode"] == "form"
    assert body["assistant_message_md"] is None
    assert body["ready_to_build"] is False
    signals = {f["signal"] for f in body["form_fields"]}
    assert signals == {"A", "B", "C", "D"}
    # Form mode never calls the model.
    assert anthropic.messages.calls == []


def test_build_form_fields_only_open_signals() -> None:
    s = OrientationSignals(
        interests=[OrientationInterest(raw_text="GR", altitude="new")],
        foundation_swept=True,
        mode="papers",
    )
    # All satisfied → no fields.
    assert build_form_fields(s) == []


def test_form_mode_with_full_update_is_ready(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    _wire_session_store(supabase)
    _prime_llm_calls(supabase)

    resp = client.post(
        "/orientation-tutor",
        json={
            "user_id": str(uuid4()),
            "mode": "form",
            "signal_update": {
                "add_interests": [{"raw_text": "thermodynamics", "altitude": "coming_back"}],
                "foundation_swept": True,
                "mode": "balanced",
            },
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ready_to_build"] is True
    assert body["form_fields"] == []
    assert all(g["satisfied"] for g in body["gaps"])


# ---------------------------------------------------------------------------
# 2. Resumability — state persists and reloads across calls
# ---------------------------------------------------------------------------


def test_resume_preserves_signals_across_calls(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    store = _wire_session_store(supabase)
    _prime_llm_calls(supabase)
    user_id = str(uuid4())

    # Call 1: open a session, capture interest A. Form mode → no LLM.
    resp1 = client.post(
        "/orientation-tutor",
        json={
            "user_id": user_id,
            "mode": "form",
            "signal_update": {"add_interests": [{"raw_text": "general relativity"}]},
        },
        headers=AUTH_HEADERS,
    )
    assert resp1.status_code == 200, resp1.text
    session_id = resp1.json()["session_id"]
    assert resp1.json()["ready_to_build"] is False
    # Persisted to the store.
    assert store["row"]["signals_json"]["interests"][0]["raw_text"] == "general relativity"

    # Call 2: resume by session_id, finish the remaining signals.
    resp2 = client.post(
        "/orientation-tutor",
        json={
            "user_id": user_id,
            "session_id": session_id,
            "mode": "form",
            "signal_update": {
                "set_altitude": [{"interest_index": 0, "altitude": "coming_back"}],
                "foundation_swept": True,
                "mode": "papers",
            },
        },
        headers=AUTH_HEADERS,
    )
    assert resp2.status_code == 200, resp2.text
    body2 = resp2.json()
    # The interest from call 1 survived the reload (resumability), now with B set.
    assert body2["session_id"] == session_id
    assert len(body2["signals"]["interests"]) == 1
    assert body2["signals"]["interests"][0]["raw_text"] == "general relativity"
    assert body2["signals"]["interests"][0]["altitude"] == "coming_back"
    assert body2["ready_to_build"] is True


def test_session_id_user_mismatch_returns_403(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    other_user = str(uuid4())
    _wire_session_store(
        supabase,
        initial={
            "id": str(uuid4()),
            "user_id": other_user,
            "status": "in_progress",
            "transcript_json": [],
            "signals_json": {},
        },
    )
    _prime_llm_calls(supabase)

    resp = client.post(
        "/orientation-tutor",
        json={"user_id": str(uuid4()), "session_id": str(uuid4()), "mode": "form"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 403


def test_finalize_completes_only_when_ready(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    _wire_session_store(supabase)
    _prime_llm_calls(supabase)
    user_id = str(uuid4())

    # finalize with everything provided → completed.
    resp = client.post(
        "/orientation-tutor",
        json={
            "user_id": user_id,
            "mode": "form",
            "finalize": True,
            "signal_update": {
                "add_interests": [{"raw_text": "QFT", "altitude": "go_deep"}],
                "foundation_swept": True,
                "mode": "problems",
            },
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "completed"


def test_finalize_ignored_when_not_ready(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    _wire_session_store(supabase)
    _prime_llm_calls(supabase)

    resp = client.post(
        "/orientation-tutor",
        json={
            "user_id": str(uuid4()),
            "mode": "form",
            "finalize": True,
            "signal_update": {"add_interests": [{"raw_text": "QFT"}]},
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "in_progress"  # not ready → stays open


# ---------------------------------------------------------------------------
# Chat-turn LLM path
# ---------------------------------------------------------------------------


def test_chat_turn_extracts_signals_and_persists_transcript(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    store = _wire_session_store(supabase)
    _prime_llm_calls(supabase)

    anthropic.queue(
        json.dumps(
            {
                "assistant_message_md": "Welcome back to GR — coming back to it, or going deep?",
                "extracted": {
                    "new_interests": [
                        {"raw_text": "general relativity", "altitude": "coming_back"}
                    ],
                    "mode": "papers",
                },
                "proposes_build": False,
            }
        )
    )

    resp = client.post(
        "/orientation-tutor",
        json={
            "user_id": str(uuid4()),
            "mode": "chat",
            "user_message": "I'd love to get back into general relativity",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["assistant_message_md"].startswith("Welcome back")
    # The model's extraction was merged into the signal state.
    assert body["signals"]["interests"][0]["raw_text"] == "general relativity"
    assert body["signals"]["interests"][0]["altitude"] == "coming_back"
    assert body["signals"]["mode"] == "papers"

    # Transcript persisted: user turn + assistant turn.
    transcript = store["row"]["transcript_json"]
    assert len(transcript) == 2
    assert transcript[0]["role"] == "user"
    assert transcript[1]["role"] == "assistant"

    # Exactly one model call.
    assert len(anthropic.messages.calls) == 1
