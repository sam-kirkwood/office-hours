# Phase 12 — The responsive daily loop

> **Status: planned, not started.** Opened from the design-review round
> (2026-06-08/09) that followed the Phase 10.5-rev operator walkthrough. The
> design and rationale live in
> [docs/orientation-and-calibration-design.md](../orientation-and-calibration-design.md)
> **Part A** — read it first; this plan is the build breakdown, not the argument.

## Theme

*The system listens and adapts to every interaction.* This phase builds **leg 2**
of the learning loop (cheap, explicit, in-flight correction) and the daily surfaces
around the queue. It is self-contained, independently valuable, and is what makes a
lighter intake (Phase 13) safe — so it lands first. The design doc's decisions are
all resolved (decisions 5 and 6 below are Phase 12 work).

## Goal

After Phase 12, a user can express the genuinely different things they mean about a
card — *do it · I know this · save it for later · not ready · not for me · make
this harder/easier · shape today's mix* — each routed to a distinct curator signal,
and explicit requests surface immediately and unmistakably rather than waiting in
priority order.

## Steps

Each step ends at a natural review boundary (a working change + passing tests).
Commit after each; update the pivot-plan status line.

### Step 1 — The card action set (§A1)
Calm card (primary CTA stays the hero) + an unobtrusive "···" overflow carrying the
from-the-card judgments. **Split the conflated "Skip — I've got this"** into **I
know this** (+comfort → node toward comfortable) and **Not for me** (−preference →
down-weight the topic) — they currently send the same `marked_refreshed` signal,
which mis-reads a bored skip as comfort. Each action maps to a distinct curator
signal (see the §A1 table). Fix the **dismiss→`/api/queue/bookmark`** smell on the
suggested-interest "Not for me" handler (resolved decision 6 — it's a bug: "Not for
me" must write a dismiss/negative-preference, not a bookmark).

### Step 2 — Bookmark as a polymorphic save (§A2)
Make `bookmarks.kind` polymorphic (`node | problem | paper`). Bookmark means *save
this, find it later, **I** manage the return* — references durable content, leaves
the active rotation, lands in "Come back to this," gets "Queue it now," sends a
soft positive signal. Define against **Not ready** (system-managed return) and **I
know this** (comfort, opposite knowledge state).

### Step 3 — The correction loop (§A3)
Wire the missing **easier / harder / assume-less** controls (columns + assessor
already exist; UI + sibling generation do not). Implement the lifecycle:
supersede-not-destroy, sibling-not-version, fetch-when-pooled / generate-on-miss,
in-place swap, max-difficulty + generating states, and the "too hard — back to the
original?" fallback. Two entry points (pre-start swap; post-attempt flag). Add
**direct foundation-state editing** on the profile (today read-only) — resolved
decision 5: framed as "tell us" (the user re-states node-level readiness, refined by
engagement), not exposing raw `struggle_score`.

### Step 4 — The curiosity box, steering, and requested items (§A4–§A6)
Extend the parse into a **classifier-and-router** (question / drill / topic /
existing-interest / mood / follow-up / paper / feedback / probe), defaulting to the
lightest sufficient response and **explore-by-default** (ambiguous topics →
"just this once," commit on opt-in). **Redirect** mood → steering and feedback →
fb1 rather than absorbing them. Build **steering chips** (selection-satisfiable:
Shorter · More papers · Something different · Less [topic]; difficulty stays
item-level) with transient→durable graduation and post-reroll honesty. Make
**requested items pinned + badged** ("Requested" + first-person reason), surfaced
immediately, exempt from reroll demotion, overriding the variety constraint.

**Dependency: fb1.** The feedback redirect needs a landing place, so build the
**fb1 report-a-problem / feedback catch-all** channel (from the closed 10.5-rev
features bucket) with / just before this step — otherwise "feedback → fb1" is a
dead end.

### Step 5 — Carry-in housekeeping (opportunistic)
Fold in while in the curator/paper code: **p1** (paper-balance replenishment on
refill, not just cold-start), **p2** (proportional `propose-papers` count from
`mode_balance`), and the **paper-chip backfill** (user-added papers carry no
`topic_node_ids`). Non-narrative; don't let it grow its own phase.

## Out of scope (→ Phase 13)

The conversational orientation tutor, rich paths, altitude/§3.4, node-level
calibration, and the daily add-interest reshape. Note that the curiosity box's
*commit* path (Step 4) is the seam where Phase 13's shared add-interest core
plugs in — build Step 4 so that seam is clean.

## Done when

- The §A1 action set is live with each action mapped to its distinct signal; no
  action conflates two intents.
- Bookmark saves problems/papers/nodes to "Come back to this" and survives queue
  churn.
- A user can make a surfaced problem easier/harder/assume-less and gets a sibling,
  with the original superseded-not-destroyed.
- The curiosity box routes the realistic input shapes correctly and redirects
  mood/feedback to their own surfaces; requested items are unmistakable and never
  require a reroll to find.
- Tests green; the daily loop walks clean on a fresh reset user.
- The orientation doc's Part A items are checked off and folded toward the
  canonical specs (defer the full fold-back to the §-reconciliation step if it
  reads better after Phase 13).
