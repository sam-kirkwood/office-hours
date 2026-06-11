# Phase 13 — Conversational orientation

> **Status: planned, not started. Build after Phase 12.** Design and rationale in
> [docs/orientation-and-calibration-design.md](../orientation-and-calibration-design.md)
> **Part B** — read it first. The design doc's decisions are **resolved** (see its
> "Resolved decisions" section: path persistence on `user_interests`, soft prereq
> emphasis, the form-mode fallback, the §3.4 edit) — build to them.

## Theme

*Onboarding as a tutor that gets you, not a form.* This phase builds **leg 1** of
the learning loop (an accurate breadth *prior*) delivered as a guided conversation,
and the rich per-interest **paths** that make a topic choice the densest signal in
onboarding. It builds on the shared add-interest core that Phase 12's curiosity box
already plugs into.

## Goal

After Phase 13, a new user is oriented by a conversational tutor that elicits four
signals — interests (A), per-interest intent/altitude including path (B), coarse
node-level foundation readiness (C), and mode (D) — without feeling quizzed, ending
on a graph mirror-back that shows the system got them; and the daily add-interest
flow is the same core in a lighter envelope.

## Prerequisites

- Phase 12 complete (the correction loop / leg 2 makes this lighter intake safe;
  the curiosity-box commit path is the seam this plugs into).
- The design doc's decisions are resolved (✅ 2026-06-10 — see its "Resolved
  decisions" section).

## Steps

### Step 1 — The §3.4 amendment
Write the entry-point amendment (entry-point keyed on
*new-to-the-user*, overridable by a go-deep signal; §B3) into
`survey-and-difficulty-design.md`, reconciled with §3.1/§3.5, so generation code
can rely on the altitude signal. Small; unblocks the rest.

### Step 2 — Rich paths (§B2)
Extend the path object (`what_you_learn`, `endpoint`, `math_intensity`/`mode_lean`,
`leans_on_prereq_slugs`); generate them; wire path → `intent_context` + altitude +
mode lean. Keep prereqs node-level but **path-aware** (no path-nodes — graph-design
§2.2). Surfaces in both the tutor and the curiosity box (shared core).

### Step 3 — Altitude + node-level calibration (§B1, §B3)
Per-interest altitude (new / coming-back / go-deep) feeding intent + entry-point +
difficulty default. Replace the subtopic drill with a coarse **node-level**
readiness pass (solid / rusty / new) over the prereqs the interests lean on,
including topical prereqs (SR/GR). Subtopic detail keeps accruing from engagement +
the node panel.

### Step 4 — The orientation tutor (§B4)
The conversational onboarding: orchestrator with A/B/C/D **signal tracking**,
**tap-to-answer chips**, a growing **"what I've got so far" map** (also the s17
mirror-back and s11 progress), an explicit **"build my queue,"** the structured
**fallback form**, and **resumability**. The **system prompt is a first-class
deliverable** — budget real iteration.

### Step 5 — The daily add-interest reshape (§B5)
Fold the shared core into the curiosity box's commit path: core × 1, no foundation
sweep (read existing engagement state), no mode question, no wrapper; preserve
"just this once." Drop the subtopic drill here too. Re-point `RequestBox` /
`NodePanel` off the old `ConceptTour`. Guardrail: keep daily-add light.

### Step 6 — Doc reconciliation
Fold the redesign into the canonical specs (`survey-and-difficulty-design.md` §1/
§2.3/§2.7/§3.4/§3.5), update the **personas' onboarding beats**, note the new
curator priors in `curriculum-curator-design.md`, remove the superseded banner, and
demote the orientation doc to an archived design exploration. Then **deploy + write
the reader-facing README** (the end-of-project artifacts).

## Out of scope

Per-problem correction and the daily surfaces (Phase 12). Live arXiv search,
bespoke megagraph viz, notebook export, etc. remain v2.1+ deferred.

## Done when

- A fresh user completes onboarding via the tutor, collecting A/B/C/D, ending on a
  graph mirror-back; the structured fallback works for click-not-talk.
- An ambiguous interest surfaces rich, detailed paths; the chosen path shapes the
  first item's topic/altitude/mode.
- Entry-point honours the altitude signal (go-deep friends aren't sent to the
  conceptual entrance).
- Daily add-interest is the same core, lighter, with the subtopic drill gone and
  `RequestBox`/`NodePanel` re-pointed.
- The canonical specs and personas are reconciled; the orientation doc is archived.
- Tests green; the three persona journeys still hold under the new onboarding.
