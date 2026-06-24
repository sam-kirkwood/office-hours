"""Dev harness for walking the orientation tutor prompt against the personas.

Phase 13 Step 4b evaluation tool. NOT part of the service. It drives the REAL
system/user prompt builders + the REAL call_json + the REAL signal-merge helpers
(apply_extraction / compute_gaps / is_ready_to_build) in-memory — no DB, no route.
A second LLM plays each persona so a whole walk runs unattended; we inspect the
tutor's turns AND the extracted A/B/C/D signals at the end.

Run from api/:  uv run python -m scripts.walk_orientation [persona_number ...]
e.g.            uv run python -m scripts.walk_orientation 4
                uv run python -m scripts.walk_orientation        # all four
"""

from __future__ import annotations

import sys

from anthropic import Anthropic

from anthropic_client import call_json, get_anthropic_client
from config import HAIKU_MODEL, SONNET_MODEL
from prompts import orientation_tutor as prompts
from routes.orientation_tutor import (
    apply_extraction,
    compute_gaps,
    is_ready_to_build,
)
from schemas import OrientationSignals, OrientationTurnLLMOutput

# The tutor's replies (and our glyphs) are full of em-dashes; the Windows console
# defaults to cp1252 and chokes. Force UTF-8 so walks are readable.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# A no-op stand-in for the Supabase client call_json uses only for llm_calls
# logging (which swallows its own exceptions). Keeps the walk DB-free.
class _NoLogSupabase:
    def table(self, *_a, **_k):
        return self

    def insert(self, *_a, **_k):
        return self

    def execute(self):
        class _R:
            data = [{"id": "walk"}]

        return _R()


# Persona simulators — distilled from docs/personas.md. Each is instructed to
# answer naturally, briefly, like a real person typing into a chat. The notes
# encode the behaviours the prompt must handle (esp. Persona 4's over-claim).
PERSONAS: dict[int, str] = {
    1: """\
You are roleplaying a new Office Hours user being onboarded by a tutor in chat.

YOU ARE: a working scientist, physics undergrad 5-10 years ago. Got pulled into
superconductors and semiconductors after watching science-fraud videos. You can no
longer follow the maths in a Wikipedia bandgap article and want to rebuild solid-state
intuition methodically.

HOW YOU ANSWER:
- Crisp and specific. Your opener: you want to relearn solid-state physics; calc and
  EM feel rusty; you're interested in semiconductors and superconductors specifically.
- Semiconductors, if asked which angle: the deep physics of WHY they work (band
  structure side), not the circuit-design side.
- Altitude: coming back to solid-state / the physics; your maths (calculus, EM) is
  rusty, not gone.
- Foundations: calculus and E&M rusty; classical mechanics fine.
- Mode: a bit more problems than papers — you want to grind some maths back into shape,
  not just read. "Mostly problems, some papers" is right.
- When the tutor offers to build your queue, say yes happily.""",
    2: """\
You are roleplaying a new Office Hours user being onboarded by a tutor in chat.

YOU ARE: a working scientist, physics undergrad 5-10 years ago. The LIGO announcement
hooked you; you want to actually follow gravitational-wave physics rather than read
pop-sci. You do NOT want many problems — you want papers.

HOW YOU ANSWER:
- Crisp and specific. Opener: you want to follow gravitational-wave physics —
  specifically LIGO, the detection papers, and where the field is going.
- Altitude: coming back / following an active field — you're not a GW expert but you
  have the undergrad background.
- Foundations: comfortable with most undergrad maths; special relativity you'd like to
  refresh; QM is rusty but you don't much care.
- Mode: heavily papers, maybe a little problems. "Mostly papers" is right.
- When the tutor offers to build your queue, say yes.""",
    3: """\
You are roleplaying a new Office Hours user being onboarded by a tutor in chat.

YOU ARE: a numerical engineer whose maths has gone rusty. You want your ODEs and
complex analysis back. No physics at all. You like pure maths problems.

HOW YOU ANSWER:
- Crisp and specific. Opener: you want your ODEs and complex analysis back; no physics;
  pure maths problems are great.
- Altitude: coming back / refresh — you knew this once.
- Foundations: comfortable with calc I and II; ODEs and complex analysis are what you
  want to refresh.
- Mode: 100% problems, no papers.
- If asked for work flavour, you can mention you're a numerical engineer.
- When the tutor offers to build your queue, say yes.""",
    4: """\
You are roleplaying a new Office Hours user being onboarded by a tutor in chat. This is
the HARD case — play it honestly, do not be more articulate than this person would be.

YOU ARE: a physics undergrad ~10 years ago, now a software dev. No driving mission —
just "I used to be able to do this, and I miss it." A pop-science series reminded you
that you can't follow the real content anymore. You want the basics back and, vaguely,
to "finally get" some things that went over your head at uni.

HOW YOU ANSWER:
- VAGUE at first. Your literal opener: "I dunno really - physics, I guess? Did a degree
  years ago but I've forgotten most of the maths. I liked quantum but could never
  follow it." Do not name a clean topic up front — you can't.
- You respond well when the tutor offers concrete directions you can RECOGNISE. You
  warm to: getting the maths back, and quantum "properly this time".
- THE OVER-CLAIM (important): you feel nostalgic about quantum and are tempted to say
  you know it well / want to "go deep". But the TRUTH is you're rusty and never really
  followed it — it went over your head. If the tutor frames "go deep" as "you're solid
  on it NOW", you should honestly back off and pick "new to me" for quantum. If the
  tutor just lets you claim go-deep without that framing, you might over-claim — so
  reward good framing by correcting yourself.
- Calculus / linear algebra: rusty. Quantum's prerequisites: mostly new.
- Mode: you have no idea — happy to leave it balanced / 50-50.
- You're a bit self-deprecating and unsure, not a confident menu-picker.
- When the tutor reflects back a little map and offers to build, you feel pleasantly
  surprised ("oh — it actually got what I meant") and say yes.""",
    5: """\
You are roleplaying a new Office Hours user — the Persona-4 diffuse returner, but
playing the OVER-CLAIM stress case hard. Same background (physics degree ~10 years ago,
now a software dev, loved quantum).

HOW YOU ANSWER:
- Opener: vague but nostalgic — "physics, mainly quantum. I did a lot of it at uni and
  always loved it." Lean into the fondness.
- THE OVER-CLAIM: when altitude/level comes up, INITIALLY reach for the confident
  option — "yeah I know quantum pretty well, I'd want to go deep / skip the basics, I
  don't need the hand-holding." Push for go-deep out of nostalgia.
- BUT you are actually rusty: it's been 10 years, you've forgotten the maths, and truth
  be told you could never follow the harder stuff even back then. So if the tutor gently
  clarifies that "go deep" means you're solid on it RIGHT NOW (not that you liked it
  once), honestly reconsider: "...okay fair, maybe not go-deep — it has been a decade
  and the maths is gone. Coming back is more honest." Let good framing talk you down. If
  the tutor just accepts your go-deep claim with no such framing, STAY over-claiming —
  that's the failure we're testing for.
- Calculus / linear algebra: rusty to new.
- Mode: no strong preference, balanced is fine.
- Say yes when offered a build.""",
}


def _simulate_user(client: Anthropic, persona_spec: str, transcript: list[dict]) -> str:
    """Produce the persona's next chat message given the tutor's turns so far."""
    convo = []
    for turn in transcript:
        who = "ME (user)" if turn["role"] == "user" else "TUTOR"
        convo.append(f"{who}: {turn['content']}")
    convo_text = "\n\n".join(convo) if convo else "(the tutor is about to greet you)"

    system = (
        persona_spec
        + "\n\nReply with ONLY your next chat message as this person — one or two short, "
        "natural sentences, lowercase-casual is fine. No narration, no quotes, no stage "
        "directions. Just what you'd type."
    )
    user = f"The conversation so far:\n\n{convo_text}\n\nYour next message:"
    resp = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=300,
        system=[{"type": "text", "text": system}],
        messages=[{"role": "user", "content": user}],
    )
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            return block.text.strip()
    return "(no reply)"


def _fmt_extraction(output: OrientationTurnLLMOutput) -> str:
    e = output.extracted
    bits = []
    if e.new_interests:
        bits.append(
            "interests=["
            + ", ".join(
                f"{i.raw_text!r}:{i.altitude or '?'}" for i in e.new_interests
            )
            + "]"
        )
    if e.foundation_marks:
        bits.append(f"foundations={dict(e.foundation_marks)}")
    if e.foundation_swept is not None:
        bits.append(f"swept={e.foundation_swept}")
    if e.mode is not None:
        bits.append(f"mode={e.mode}")
    if e.work_context is not None:
        bits.append(f"work_context={e.work_context!r}")
    bits.append(f"proposes_build={output.proposes_build}")
    return "  ·  ".join(bits) if bits else "(nothing extracted)"


def walk(persona_num: int, max_turns: int = 10) -> None:
    client = get_anthropic_client()
    supabase = _NoLogSupabase()
    persona_spec = PERSONAS[persona_num]

    print("\n" + "=" * 78)
    print(f"PERSONA {persona_num} WALK")
    print("=" * 78)

    signals = OrientationSignals()
    transcript: list[dict] = []
    user_message: str | None = None

    for turn_no in range(1, max_turns + 1):
        if user_message is not None:
            transcript.append({"role": "user", "content": user_message})
            print(f"\n[user] {user_message}")

        open_signals = [g.label for g in compute_gaps(signals) if not g.satisfied]
        output: OrientationTurnLLMOutput = call_json(
            client=client,
            supabase=supabase,
            model=SONNET_MODEL,
            system_prompt=prompts.build_system_prompt(),
            user_prompt=prompts.build_user_prompt(
                transcript=transcript,
                user_message=user_message,
                signals_summary=signals.model_dump(mode="json"),
                open_signals=open_signals,
            ),
            schema=OrientationTurnLLMOutput,
            route="/orientation-tutor[walk]",
            temperature=0.6,  # match the production route (Step 4b)
            request_summary={"persona": persona_num, "turn": turn_no},
        )
        signals = apply_extraction(signals, output.extracted)
        transcript.append({"role": "assistant", "content": output.assistant_message_md})

        print(f"\n[tutor] {output.assistant_message_md}")
        print(f"   ⤷ extracted: {_fmt_extraction(output)}")
        gap_line = " ".join(
            f"{g.signal}{'✓' if g.satisfied else '·'}" for g in compute_gaps(signals)
        )
        print(f"   ⤷ gaps: {gap_line}")

        if is_ready_to_build(signals):
            print("\n>>> READY TO BUILD (all four signals satisfied)")
            break
        user_message = _simulate_user(client, persona_spec, transcript)
    else:
        print("\n>>> MAX TURNS REACHED without readiness")

    print("\n--- FINAL SIGNALS ---")
    for i in signals.interests:
        path = f" path={i.path_json}" if i.path_json else ""
        print(f"  A/B  {i.raw_text!r}  altitude={i.altitude}{path}")
    print(
        f"  C    foundation_marks={dict(signals.foundation_marks)} "
        f"swept={signals.foundation_swept}"
    )
    print(f"  D    mode={signals.mode}")
    if signals.work_context:
        print(f"  +    work_context={signals.work_context!r}")
    print(f"  ready_to_build={is_ready_to_build(signals)}  turns={turn_no}")


def main() -> None:
    args = [int(a) for a in sys.argv[1:]] or [1, 2, 3, 4]
    for n in args:
        walk(n)


if __name__ == "__main__":
    main()
