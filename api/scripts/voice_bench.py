"""Fast voice A/B bench for the orientation tutor (Phase 13 Step 4b).

The persona walk (scripts/walk_orientation.py) is for "does the conversation
flow"; this is for "do I like the register". It renders ONE tutor reply for each
of a few frozen scenarios — the spots where voice shows most (the greeting, a
vague opener, the foundations-question beat) — under several candidate REGISTER
profiles, side by side, at temperature 0 (so differences are the prompt, not
sampling). No persona simulator, no multi-turn. ~seconds per full sweep.

Each register is composed with the shared, register-independent `_ANTISLOP` rules,
so we're A/B-ing register alone. Edit REGISTERS, run, read, pick.

Run from api/:  uv run python -m scripts.voice_bench [register ...]
e.g.            uv run python -m scripts.voice_bench            # all registers
                uv run python -m scripts.voice_bench dry blunt  # just these two
"""

from __future__ import annotations

import sys

from anthropic_client import call_json, get_anthropic_client
from config import SONNET_MODEL
from prompts import orientation_tutor as prompts
from prompts.orientation_tutor import _ANTISLOP
from schemas import OrientationInterest, OrientationSignals, OrientationTurnLLMOutput

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class _NoLogSupabase:
    def table(self, *_a, **_k):
        return self

    def insert(self, *_a, **_k):
        return self

    def execute(self):
        class _R:
            data = [{"id": "bench"}]

        return _R()


# Candidate registers — a real spread, none of them cozy. Each is a self-contained
# replacement for the default VOICE intro; the shared _ANTISLOP rules are appended
# automatically. Add/edit freely and re-run.
REGISTERS: dict[str, str] = {
    "brisk": """\
VOICE — a brisk, concrete tutor who drives the conversation.
Efficient and a little brisk: take what they give you, even if it's vague, and move on it
with confidence rather than dwelling — "Undergrad physics coming right up." Friendly, not
gushing; a plain "Hi there, tell me a bit about yourself" is the right amount of warmth,
never flattery.

Be concrete. Name real topics, concepts, and tasks instead of speaking in the abstract:
"electromagnetism, classical, general relativity... none of those?" not "a few areas";
"the uncertainty principle, the double-slit, spin" not "the conceptual side". Specificity
is how you show you know the material and how you give them something to recognise.

Drive with options. Lay out a concrete fork — a short menu of real choices with an easy
out ("...none of the above?", "or both?") — rather than an open "what do you want?". You
may acknowledge that the MATERIAL is hard ("connecting the intuition to the maths is
genuinely tricky"); never that the user is doing well. Name the structure of their
problem when it helps ("those are two distinct halves — which end state do you want?").

For readiness, prefer a concrete anchor to an abstract scale: "if I asked you to
diagonalise a matrix, would you remember, or have to look it up? Find an eigenvector?"
rather than "how's your linear algebra — solid, rusty, or new?". It's a thermometer, not
a test — they place themselves against the example and you still only need the coarse,
node-level read out of it.""",
}


# Frozen scenarios — the beats where register is most visible. Each fixes the
# transcript, the user's latest message, the captured signals, and which signals
# are open, so the only variable across runs is the register.
def _scenarios() -> list[dict]:
    quantum_new = OrientationSignals(
        interests=[OrientationInterest(raw_text="quantum mechanics", altitude="new")]
    )
    return [
        {
            "name": "S1 — opening greeting",
            "transcript": [],
            "user_message": None,
            "signals": OrientationSignals(),
            "open": ["Interests", "Intent & level", "Foundations", "Mode"],
        },
        {
            "name": "S2 — vague opener (the draw-out)",
            "transcript": [],
            "user_message": (
                "i dunno really - physics, i guess? did a degree years ago but i've "
                "forgotten most of the maths. i liked quantum but could never follow it "
                "properly."
            ),
            "signals": OrientationSignals(),
            "open": ["Interests", "Intent & level", "Foundations", "Mode"],
        },
        {
            "name": "S3 — endpoint / altitude clarification",
            "transcript": [
                {"role": "user", "content": "i want to get back into quantum mechanics."},
                {
                    "role": "assistant",
                    "content": (
                        "Quantum mechanics. Coming at it fresh, getting back into it, or "
                        "already solid and wanting to push deeper?"
                    ),
                },
            ],
            "user_message": (
                "new really - i want to actually get it this time, not just nod along to "
                "a podcast."
            ),
            "signals": quantum_new,
            "open": ["Foundations", "Mode"],
        },
        {
            "name": "S5 — crisp opener (specific intent)",
            "transcript": [],
            "user_message": (
                "i want to follow gravitational-wave physics — LIGO, the detection "
                "papers, where the field is going."
            ),
            "signals": OrientationSignals(),
            "open": ["Interests", "Intent & level", "Foundations", "Mode"],
        },
        {
            "name": "S6 — ambiguous topic (forks)",
            "transcript": [],
            "user_message": "i want to learn semiconductors.",
            "signals": OrientationSignals(),
            "open": ["Interests", "Intent & level", "Foundations", "Mode"],
        },
        {
            "name": "S4 — foundations math-probe beat",
            "transcript": [
                {"role": "user", "content": "i want to get back into quantum mechanics."},
                {
                    "role": "assistant",
                    "content": (
                        "New to it, or coming back? And do you want the concepts, the "
                        "maths, or both?"
                    ),
                },
            ],
            "user_message": (
                "both really - i want to actually be able to do the problems, not just "
                "follow the story."
            ),
            "signals": quantum_new,
            "open": ["Foundations"],
        },
    ]


def _reply(client, supabase, system_prompt: str, scenario: dict) -> str:
    out: OrientationTurnLLMOutput = call_json(
        client=client,
        supabase=supabase,
        model=SONNET_MODEL,
        system_prompt=system_prompt,
        user_prompt=prompts.build_user_prompt(
            transcript=scenario["transcript"],
            user_message=scenario["user_message"],
            signals_summary=scenario["signals"].model_dump(mode="json"),
            open_signals=scenario["open"],
        ),
        schema=OrientationTurnLLMOutput,
        route="/orientation-tutor[voicebench]",
        temperature=0,
    )
    return out.assistant_message_md


def main() -> None:
    names = sys.argv[1:] or list(REGISTERS)
    client = get_anthropic_client()
    supabase = _NoLogSupabase()

    for scenario in _scenarios():
        print("\n" + "=" * 78)
        print(scenario["name"])
        if scenario["user_message"]:
            print(f'  user: "{scenario["user_message"]}"')
        print("=" * 78)
        for name in names:
            if name == "default":
                # Test the tuned default _VOICE baked into the prompt (no override).
                system_prompt = prompts.build_system_prompt()
            else:
                register = REGISTERS[name]
                # No two-part closer here — registers vary their own shape.
                voice = f"{register}\n\n{_ANTISLOP}"
                system_prompt = prompts.build_system_prompt(voice=voice)
            reply = _reply(client, supabase, system_prompt, scenario)
            print(f"\n[{name}]\n{reply}")


if __name__ == "__main__":
    main()
