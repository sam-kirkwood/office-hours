"""Prompts for POST /orientation-tutor (Phase 13 §B4).

⚠️ FIRST-DRAFT / PLACEHOLDER PROMPT — Step 4b deliverable.

Step 4a wires the orchestrator (signal state, gap tracking, resumability, the
chat/form envelopes). The conversational *quality* of the tutor — eliciting all
four signals, presenting paths with honest detail, reading clear-vs-ambiguous
intent and branching commit-vs-explore, staying peer-to-peer, knowing when it
has enough — is Step 4b's own iteration cycle, walked against the three personas
(docs/personas.md). This draft is just enough to make the orchestrator round-trip
end to end; treat the wording here as provisional and replace it in 4b.

The model returns OrientationTurnLLMOutput (see api/schemas.py): a conversational
reply, the signals it extracted from the user's latest turn, and an advisory
`proposes_build` flag. The orchestrator — not the model — owns the canonical
readiness decision.
"""

from __future__ import annotations

import json


# The four signals, restated for the model. Kept in one place so 4b can iterate
# the framing without it drifting between the system and user prompts.
_FOUR_SIGNALS = """\
You are gathering exactly four things, conversationally — never as a quiz:

  A — Interests: what they want to work on or get back to, in their words.
  B — Intent / altitude (per interest): are they NEW to it, COMING BACK to it
      after a while, or do they already KNOW it and want to GO DEEP? Where an
      interest spans genuinely different shapes (e.g. "semiconductors"), offer
      the distinct paths with honest detail so they can choose — or start broad.
  C — Foundation readiness: a coarse, node-level read (solid / rusty / new) on
      the scaffolding their interests lean on. Node-level, never subtopic drill.
  D — Mode: do they lean toward working problems, reading papers, or both?
"""


def build_system_prompt() -> str:
    """System prompt for one tutor turn. PLACEHOLDER — see module docstring."""
    return f"""\
You are a warm, peer-level science tutor running a new user's orientation. The
person is a competent working professional who studied maths/physics years ago.
This is a conversation between equals, not a placement test. No condescension,
no gatekeeping, never ask how much time they have.

{_FOUR_SIGNALS}

Move naturally. Reflect back what you heard, ask one good question at a time,
and close the open signals before suggesting you're done. When an interest is
ambiguous, lay out the real paths with what each actually involves — don't
flatten it to a label.

Return ONLY a JSON object with this shape:
{{
  "assistant_message_md": "<your next conversational reply, Markdown>",
  "extracted": {{
    "new_interests": [
      {{"raw_text": "<an interest the user expressed>",
        "altitude": "new|coming_back|go_deep" or null,
        "path_key": null, "path_json": null}}
    ],
    "foundation_marks": {{"<foundation-area>": "solid|rusty|new"}},
    "foundation_swept": true or false or null,
    "mode": "problems|papers|balanced" or null,
    "work_context": "<optional one-line work-context-as-flavour>" or null
  }},
  "proposes_build": false
}}

Only populate `extracted` fields the user actually gave you this turn — leave the
rest empty/null. Set `proposes_build` true only when you believe all four signals
are covered; the system makes the final call.
"""


def build_user_prompt(
    *,
    transcript: list[dict],
    user_message: str | None,
    signals_summary: dict,
    open_signals: list[str],
) -> str:
    """User-turn prompt: the running transcript, the signals captured so far,
    which signals are still open, and the user's latest message (if any)."""
    lines: list[str] = []
    lines.append("Conversation so far:")
    if transcript:
        for turn in transcript:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            speaker = "User" if role == "user" else "You"
            lines.append(f"{speaker}: {content}")
    else:
        lines.append("(none yet — this is the opening turn)")

    lines.append("")
    lines.append("Signals captured so far (JSON):")
    lines.append(json.dumps(signals_summary, ensure_ascii=False))
    lines.append("")
    if open_signals:
        lines.append(
            "Signals still open: " + ", ".join(open_signals) + ". Work toward these."
        )
    else:
        lines.append(
            "All four signals look covered. You may reflect back and offer to build "
            "their queue."
        )

    lines.append("")
    if user_message is not None:
        lines.append(f"The user just said: {user_message}")
        lines.append("Reply, and extract any signals they gave you.")
    else:
        lines.append("Open the conversation warmly and start drawing out their interests.")

    return "\n".join(lines)
