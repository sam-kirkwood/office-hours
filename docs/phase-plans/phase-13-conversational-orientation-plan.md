# Phase 13 — Conversational orientation

> **Status: Steps 1–3 done (Step 3 2026-06-17).** Design and rationale in
> [docs/orientation-and-calibration-design.md](../orientation-and-calibration-design.md)
> **Part B** — read it first. The design doc's decisions are **resolved** (see its
> "Resolved decisions" section: path persistence on `user_interests` as `path_json`
> JSONB, soft prereq emphasis, the form-mode fallback, the §3.4 edit) — build to them.

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

### Step 1 — The §3.4 amendment ✅ done (2026-06-16)
Three-lane entry-point written into `survey-and-difficulty-design.md` §3.4
(Lane 1 default / Lane 2 coming-back / Lane 3 go-deep), §3.1 consolidate updated
(two entry paths: engagement comfort OR go-deep intake signal), §3.5 difficulty
default updated (go-deep → one step above moderate). Behavior is inert until
Phase 13 Steps 3/4 collect the altitude signal.

### Step 2 — Rich paths (§B2) ✅ done (2026-06-16)
Extend the path object (`what_you_learn`, `endpoint`, `math_intensity`/`mode_lean`,
`leans_on_prereq_slugs`); generate them; wire path → `intent_context` + altitude +
mode lean. Keep prereqs node-level but **path-aware** (no path-nodes — graph-design
§2.2). Surfaces in both the tutor and the curiosity box (shared core).

**Schema:** add `path_json JSONB` to `user_interests` (confirmed pre-code decision).
Shape: `{"label": "...", "endpoint": "...", "math_intensity": "...",
"mode_lean": "problems|papers|balanced", "leans_on": ["calculus", ...]}`.
Steps 2 and 3 are sequentially dependent — path sets altitude, so Step 2 must land first.

### Step 3 — Altitude + node-level calibration (§B1, §B3) ✅ done (2026-06-17)
Per-interest altitude (new / coming-back / go-deep) feeding intent + entry-point +
difficulty default. Replace the subtopic drill with a coarse **node-level**
readiness pass (solid / rusty / new) over the prereqs the interests lean on,
including topical prereqs (SR/GR). Subtopic detail keeps accruing from engagement +
the node panel.

**Built:** `altitude` TEXT column on `user_interests` (migration `20250039`,
CHECK new/coming_back/go_deep); collected via three chips in `Dialog.tsx`
(pre-set from the parser's `implicit_intent`), stored through `/resolve`.
Generation reads it as a **structured field**: `derive_intent` maps
altitude→intent (go_deep→consolidate / coming_back→refresh / new→teach) ahead of
the prose fallback, and a new `derive_entry_lane` returns the §3.4 lane (3 skip
entrance / 2 light recall / 1 new-entry-point / 0 has-history) — `generate_problem`
shows the entrance only for lanes 1–2, so a go-deep interest's first problem skips
it (Lane 3 live) and a new interest gets it (Lane 1). The subtopic `ConceptTour` is
replaced by node-level `NodeReadiness.tsx` + `POST /add-interest/node-readiness`
(solid/rusty/new → comfortable/active/unseen on `user_node_states`); prereq scope
comes from `path_json.leans_on_prereq_slugs` when a path was picked, else the node's
prereq edges — **all prereq kinds included** (the old foundations-only filter that
dropped SR/GR is fixed). Old `ConceptTour.tsx` + `/api/add-interest/concept-tour`
route deleted. Tests: altitude→lane/intent, leans_on-scoped + topical-prereq
selection, node-level state writes.

### Step 4 — The orientation tutor (§B4) — split into three sub-sessions

**Step 4a — Orchestrator + signal state + resumability (Python + DB)**
New `POST /orientation-tutor` route. Signal state model (A/B/C/D tracking struct)
persisted as JSONB on `surveys` or a new `orientation_sessions` table. Resumability:
persist transcript + extracted-signals-so-far. Form-mode flag: orchestrator accepts
`mode: "chat" | "form"`; in form mode it returns a structured gaps payload (chips +
fields) instead of chat turns. The seven-stage survey stays live until 4c ships.

**Step 4b — The system prompt (first-class deliverable, own iteration cycle)**
Draft → walk against all three persona inputs → tune → walk again. Must: elicit
four signals, present paths with honest detail, read clear-vs-ambiguous intent and
branch commit-vs-explore, stay peer-to-peer (never quiz-like), know when it has
enough. Budget at minimum one full session here, not a sub-bullet of 4a.

**Step 4c — Chat UI + chips + growing map + "Build my queue" + form-mode toggle**
`/survey` page replaced with the tutor UI. Tap-to-answer chips for paths, altitude
(new / coming-back / go-deep), solid/rusty/new. Growing "what I've got so far" map
(interests added, paths chosen, foundations calibrated). "Show me the questions"
toggle → form mode. Explicit "I'm happy — build my queue" CTA.

**Fallback form (resolved decision 3):** same orchestrator, `mode="form"` — renders
A/B/C/D gaps as structured fields + chips. NOT the retired seven-stage. The seven-
stage is deleted when 4c ships.

### Step 5 — The daily add-interest reshape (§B5)
Fold the shared core into the curiosity box's commit path: core × 1, no foundation
sweep (read existing engagement state), no mode question, no wrapper; preserve
"just this once." Drop the subtopic drill here too. Guardrail: keep daily-add light.

**Concrete seam (Phase 12 built):** "Add it properly →" in `RequestBox.tsx:387`
calls `handleTopicNewAddIt` → re-parses via `/api/add-interest/parse` → opens
`web/components/addInterest/DialogModal`. Step 5 replaces or reshapes `DialogModal`
with the new shared-core component (path-pick if ambiguous → preview → go; no
foundation sweep / mode question / wrapper). Re-point `NodePanel` and the survey
page off the old `ConceptTour` at the same time.

**`topic_new_stub` upgrade:** `_resolve_and_queue_one_off` in
`api/routes/curiosity_box.py:243` already has the Phase 13 §B5 upgrade note.
For novel topics, replace the stub nudge with a find-or-create call into the
existing add-interest parse/resolve path.

### Step 6 — Doc reconciliation
Fold the redesign into the canonical specs (`survey-and-difficulty-design.md` §1/
§2.3/§2.7/§3.4/§3.5), update the **personas' onboarding beats**, note the new
curator priors in `curriculum-curator-design.md`, remove the superseded banner, and
demote the orientation doc to an archived design exploration. Then **deploy + write
the reader-facing README** (the end-of-project artifacts).

**§2.3 reconciliation note (from Step 2):** Step 2 changed the path pick from
multi-select to **single-select** (one path = one coherent `mode_lean`/`leans_on`
set; the free-text escape still covers "a bit of both"). §2.3 still says "multi-
select is allowed" — reconcile it to single-select here. Operator-confirmed as
intentional.

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
