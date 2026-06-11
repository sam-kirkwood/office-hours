# Orientation & Calibration Redesign — Office Hours

## About this document

> **Status: design proposal, not yet built.** Produced in a design-review
> session (2026-06-08/09) that stepped back from the operator-walkthrough
> remediation (Phase 10.5-rev) and asked how onboarding and the daily loop
> *should* work for the median friend — someone who studied physics/maths years
> ago, remembers some of it, wants to rebuild intuition (recall how to integrate,
> get a 1D potential well to click again) and learn a few new things.
>
> It reframes the work around one question — *what signal does the system
> actually need, and when?* — and splits the build into two phases:
> **Part A → Phase 12 (the responsive daily loop)** and **Part B → Phase 13
> (conversational orientation)**. §2's principle is the shared spine.

This document **amends** the existing source-of-truth specs; when the work lands,
fold the changes back into them (see "Docs to update when this lands") and demote
this file to an archived design exploration:

- `docs/survey-and-difficulty-design.md` — §1 (seven-stage survey → conversational
  tutor + four signals), §2.3 (path options → rich paths), §2.7 (the input box →
  a universal intent router), §3.4 (entry-point default → keyed on *new-to-the-
  user*), §3.5 (per-problem controls → the correction loop, built).
- `docs/curriculum-curator-design.md` — mechanism unchanged; the priors it starts
  from change (path-aware `intent_context`, node-level calibration, altitude).
- `docs/personas.md` — the three personas still hold; their *onboarding beats*
  will need updating to the conversational flow.

### For the session that builds this — read first

1. Read this doc, then `survey-and-difficulty-design.md` §1–§3 and §5 — but treat
   its §1/§2.3/§2.7/§3.4/§3.5 as superseded here. It still accurately describes
   what is **currently built**; this describes where it goes.
2. **The design decisions are resolved** (see "Resolved decisions"). Build to them;
   re-open with the operator only if something forces it.
3. Re-verify the "what's wired vs not" audit (§A3) against current code — it was
   taken 2026-06-09 and the gap may have been closed since.
4. The orientation-tutor system prompt (§B4) is a first-class deliverable, not an
   afterthought.

---

## 1. Why redesign — the diagnosis

The seven-stage survey is over-engineered relative to what the rest of the system
already does, and it taxes the user where it reads as a placement test — the one
thing SPEC/§5 forbid. Walking it as the median friend:

1. **Free-text intent is buried.** The personas say "free-text interest
   expression drives everything," yet it's split between a Stage-1 box labelled
   *background* and a Stage-3 box labelled *anything else*. The densest signal is
   an afterthought.
2. **The user is calibrated twice.** Stage 2 (node-level foundation tiles) and
   Stage 5 (per-interest subtopic drill) both write `user_node_states`; the second
   is the most test-feeling part and the part the curator consumes least (it
   collapses to node-level before the planner reads it).
3. **Over-collection of taxonomy.** Sub-area chips + per-domain relationship cards
   feed only Stage-3 suggestion ranking, which the parsed free-text does as well.
   Empirically, heaviness hasn't bought calibration accuracy — the same survey
   collected all this and the walkthrough still surfaced mis-pitched problems.
4. **Paths are flattened** to an 80-char chip + a soft string (Part B §B2).
5. **The entry-point default condescends the strong user** (§B3).

The unifying error: the survey tries to *model the user precisely* up front, when
the content model is built to *figure the user out as they go* (entry-point
defaults, dynamic assumed-background, engagement-driven adaptation). A heavy
survey is the system distrusting its own adaptation.

---

## 2. The principle — signal half-life and the three-legged loop

For every candidate signal: *can the system learn it cheaply from engagement, and
how costly is getting it wrong on day 1?* Collect the high-day-1-value signals
engagement can't cheaply learn; let the fast-self-correcting ones default.

But "survey vs engagement" is a false dichotomy. The learning loop has three legs,
and engagement is the weakest:

1. **A breadth *prior* from a light intake** — initializes across the graph at the
   altitude the curator consumes, accurately enough that the first item on each
   topic is pitched well enough to be *useful* and to generate *clean* signal.
   Breaks the bootstrap; doesn't model the user.
2. **Cheap explicit in-flight correction** — easier/harder/assume-less,
   not-ready, the card actions, the curiosity box, profile feedback. One-tap,
   honest, at the point of friction. Faster and cleaner than inference.
3. **Passive engagement refinement** — struggle/ease/reroll. Good *locally*, slow
   and blind *globally*.

**Why this app can't lean on engagement alone.** The cadence is sparse and slow by
design (pen-and-paper, no streaks, ≤ ~1 attempt/day) — week 1 yields a handful of
data points against a large space. And no-guilt removes the retention pressure
that rescues a bad first week elsewhere: a friend who gets three condescending or
examining problems just stops opening the app. So the cold start is **costly** (no
retention floor) and **signal-polluting** (a mis-pitched problem makes the user
look like they're struggling). The priors (leg 1) must be reasonably *accurate*,
and the correction channel (leg 2) must be *real and frictionless* — that's what
lets the intake stay light. **Phase 12 builds leg 2; Phase 13 builds leg 1.**

Calibration is necessary but not sufficient for usefulness: usefulness = right
topics × right calibration × good problems. This doc touches the first two; problem
quality is the generator's job.

---

# Part A — The responsive daily loop (Phase 12)

The legs-2 correction channel, plus the daily surfaces around the queue. This is
what makes "the system curates and adapts" *real* rather than spec'd, and it's
what makes a lighter intake (Part B) safe. Independently valuable; build first.

## A1. The card action set — every action is a curator signal

The right set of card actions isn't a UX nicety; it's whatever lets the user
express the genuinely different things they mean, **each mapping to a distinct
adaptation.** Collapsing two intents into one button (as the current build does —
§A3) destroys signal, which is worse than collecting none.

| User means… | Action | Where | Signal to curator |
|---|---|---|---|
| Do it now | Open / Start | card (primary CTA) | engagement |
| I finished it | (terminal) → done | — | engagement outcome |
| I already know this | **I know this** | card overflow | +comfort, advance |
| Interesting — later, I'll manage it | **Bookmark** (§A2) | card overflow | save (user-return) + soft positive |
| I want it but need prereqs first | **Not ready yet** | problem page | +struggle, accelerate prereqs (system-return) |
| I don't want this / less of it | **Not for me** | card overflow | −preference, down-weight topic |
| *This* problem is mis-pitched | Easier / Harder / Assume-less (§A3) | problem page | sibling + dial |
| Shake up the mix | Steering chips / reroll (§A5) | queue | re-pick / drift |

**Calm card, actions in an overflow.** The daily view must stay calm (not a button
dashboard — design principle). Keep the primary CTA as the hero; tuck the
from-the-card judgments (*I know this · Bookmark · Not for me*) behind an
unobtrusive "···". This fixes the current friction where the *only* card action is
"Open," so every "no" costs an open-then-reject or a blind reroll.

**Split "Skip — I've got this" into two opposite signals.** The current single
button writes `marked_refreshed` (a comfort signal) but is labelled like a skip —
so a user skipping out of *boredom* gets read as *"I know this,"* telling the
curator to advance them. Separate them: **I know this** (+comfort) vs **Not for
me** (−preference). The `/design` dropdown already had these as distinct items;
the build merged them.

## A2. Bookmark — save any object, you manage the return

Bookmark means: *"I like this, no time/mood right now, set it aside so I can find
it easily later."* One consistent verb across the app — you bookmark **topics
(nodes), problems, and papers** alike, all landing in the notebook's "Come back to
this" tab.

The clean axis that separates the two "keep it" actions is **who manages the
return:**

- **Bookmark = user-managed return.** No system action; you pull it back when you
  want. Positive/neutral valence.
- **Not ready = system-managed return.** Triggers prerequisite acceleration and
  auto-returns the item when the path is ready.

Mechanics:
- **References the durable content** (problem/paper/node), not the queue slot, so
  queue churn never loses it.
- **Leaves the active rotation** — stops being surfaced daily, lands in "Come back
  to this," gets a **"Queue it now"** to bring it back (the affordance deferred
  items already have, g1).
- **Soft positive signal** on the thread (mirror image of "Not for me," but light
   — the point is the save).
- Distinct from **I know this** (comfort — I *don't* want it): bookmark is "I *do*
  want it, later." Opposite knowledge states, no overlap.
- **Data:** the `bookmarks` table is node-only today (from the t4 overlay fix);
  make it polymorphic — `kind ∈ {node, problem, paper}`.

## A3. The correction loop — per-problem dials

§3.5's three per-problem controls, finally built. The audit (2026-06-09):

**Wired:** profile feedback toggles (too hard / assume less / more papers /
harder) → `user_preferences` → generator biases; mode balance (editable);
interest edit/delete; **Not ready yet** (defer → `state='deferred'` →
`/check-deferred` + Come-back tab + resume); **Skip — I've got this** (writes
`marked_refreshed`); hints; the request input box.

**The hole:** **easier / harder / assume-less do not exist as user actions.** The
`requested_easier/harder/assume_less` columns are on `attempts`, the assessor
reads them into the struggle score, and §3.5 specs them with sibling generation —
but no button sets them and no route regenerates a sibling. The column is there;
the tap is not. This is the *fastest, most honest* correction leg, missing the
control for the assumed-background dial ("the most important and most frequently
miscalibrated," §3.1).

**The easier/harder lifecycle** (answers "harder what, and do I see the original
again?"):

- **Per-item, not per-queue.** Difficulty is a property of a *problem*, generated,
  not selected — so it lives on the problem (the `/design` "Request harder version"
  dropdown), not as a queue-level chip. "Harder what" = harder *this*.
- **Supersede, don't destroy.** The sibling takes the original's slot; the original
  problem row stays in the shared pool (immutability + reuse) — only *this user's*
  queue item goes terminal (superseded), so the rejected-as-too-easy problem
  doesn't re-surface as if new.
- **Sibling, not version.** A *version* (`previous_version_id`) is an edit of the
  same problem; a *sibling* is a different problem — same node/subtopic/intent,
  different difficulty. Difficulty is part of the pool cache key
  `(topic_node_id, difficulty, intent)`, so easy/hard are distinct pooled
  entries — **fetch if it exists, generate only on a miss.**
- **Two entry points:** pre-start ("this looks too easy" → swap in place, supersede)
  and post-attempt (`requested_harder` on the attempt → curator queues a harder
  follow-up).
- **Edge cases:** at max difficulty, say so gracefully; on a generate (not fetch),
  show the work briefly ("making a tougher one…"); offer a **"too hard — back to
  the original?"** fallback if the sibling overshoots.

**Direct foundation-state editing.** The profile Foundations list is read-only
today. A friend who knows ODEs are now solid should be able to say so without
waiting for inference — C-style correction after onboarding.

## A4. The curiosity box — a universal intent router

The box under the queue ("Curious about something else?") is **not an add-interest
box.** Realistic input is short, lazy, and rarely a clean interest statement —
bare nouns ("entropy"), questions ("why is the sky blue?"), drills ("more
integration by parts"), moods ("something harder"), follow-ups, feedback dumped
wherever there's a text field, papers, and week-one probes ("are you smart?"). The
clean persona statement is ~10% of traffic.

So the box's job is **classify-and-route, defaulting to the lightest sufficient
response, escalating to commitment only on signal.** The classifier (extending the
existing parse) is the new core piece.

| Input shape | Lightest right response | Commit only if… |
|---|---|---|
| Question ("why is the sky blue") | Answer it, then offer "a problem on this?" / "follow it?" | they take the offer |
| Bare topic ("entropy") | One starter item (read/problem) | they say "add this" |
| Drill ("more IBP") | Pool-lookup → queue a problem; no node created | — |
| Existing interest ("more GR") | Queue an item directly, no dialog | — |
| Mood ("something harder") | **Redirect** → steering chips (§A5) | — |
| Follow-up ("finite well now") | Queue the related problem | — |
| Feedback ("too hard", "no more thermo") | **Redirect** → correction/feedback (fb1) | — |
| Paper / link | Ingest the link/DOI; graceful "can't fetch arbitrary papers yet" | — |
| Out-of-scope / probe | Warm, brief, in-character; no machinery | — |

Principles:
- **Explore by default; don't clutter the graph.** Ambiguous topic input defaults
  to **"just this once"** (one item, no permanent node, à la §2.7 Case 3), with
  "follow this properly?" as the *opt-in* upgrade. Otherwise a week of "entropy"
  at 9pm fills the graph (and the megagraph) with transient curiosities.
- **Redirect, don't silently absorb.** For off-target input the box hands off with
  one tap ("Sounds like that's about how your problems feel — just today, or
  always?" → steering / profile), so the user always sees where it goes. This is
  where the *graceful, fast, slightly delightful* handling of low-effort/probing
  input lives.
- The heavy add-interest machinery (paths/altitude/calibration — Part B) fires
  **only** on the commit case, and even then it's offered. The box is the daily
  embodiment of "explore until intent is clear."

## A5. Steering — directed reroll

The mood route gets a dedicated, legible home next to the blind reroll: a small set
of **chips**, not a box (the vocabulary is bounded; a box would just be parsed back
into these). Crucially, the chips split by whether they're **selection-** or
**generation-**satisfiable:

- **Selection chips (instant re-pick):** **Shorter · More papers · Something
  different · Less [active topic]** — these items plausibly already exist in the
  pending queue. ("Less [topic]" is populated dynamically from what's queued.)
- **Difficulty is *not* a selection chip.** Harder/Easier require generation (the
  pending queue rarely holds a harder version), so they live item-level (§A3),
  with an optional queue-level "Harder" that means *"make one of these in-view
  problems meatier"* + a forward bias — not a magic queue mutation.

**Transient by default; graduates to durable.** "Shorter today" is a mood. But if
a user taps "Harder" four sessions running, the curator notices (it already reads
reroll patterns) and *offers* to bump the durable profile preference — keeping the
promotion in the user's hands.

**Post-reroll honesty.** After heavy rerolling the pending pool is depleted, so the
selection chips are scraping a thin barrel; say so ("That's about all that's
queued — want me to make a fresh one?") rather than re-surfacing the same set.

## A6. Requested items — pinned and badged, never priority-ordered

An explicitly-requested item must never make the user reroll to *find* it
(Pattern 7: requests work without bureaucracy). So requested items don't obey
normal priority ordering:

- **Surfaces immediately**, not eventually — the request flow *shows* the item
  ("Here's a problem on IBP — start now, or it's up top when you're ready").
- **A distinct "Requested" badge + a first-person reason** on the card ("You asked
  for this") — the `added_reason` line already exists; for requests it's explicit
  and in the user's framing, so it's the obvious card among the three.
- **Confirmation at the moment of asking** (toast / inline) with a direct "open it."
- **Pinned against reroll** — reroll cycles the *other* slots around it; the thing
  you asked for can't be buried by the next reroll. It stays until engaged or
  dismissed, and persists if you wander off and return.
- **Overrides the variety constraint** (the surfaced three may skew) and, for
  harder/easier, swaps in place (§A3) so there's no traversal at all.

The rule: **requested ≠ queued-and-prioritised; requested = surfaced-now, pinned,
labelled as yours.** The priority queue is for what the *curator* chose.

---

# Part B — Conversational orientation (Phase 13)

The legs-1 breadth prior, delivered as a tutor rather than a form. Builds on the
shared add-interest core that Part A's curiosity box also uses.

## B1. The four signals

The intake collects exactly four things; everything else is redundant or has a
short enough half-life that engagement learns it for free.

| Signal | What it is | Why it can't be cheaply learned | Form |
|---|---|---|---|
| **A — Interests** | What they want to work on / get back | Irreducible seed | Their words |
| **B — Intent / altitude** (per interest) | New / coming-back / already-strong — and, where ambiguous, **which path** (§B2) | Self-corrects in ~1–2 attempts, but wrong-on-day-1 is costly both ways | One choice per interest |
| **C — Foundation readiness** | Coarse node-level read on the scaffolding the interests lean on: solid / rusty / new | Needed as a prior to pitch the first items + weave proactive refreshers | Node-level, *not* subtopic |
| **D — Mode** | Problems vs papers | Cheap to ask; partly inferable | One slider, pre-set from language |

Deliberately **not** collected: difficulty (fastest self-correct), sub-area chips
/ relationship-card matrix (proxies for B/C asked directly), and **biography** — a
noisy proxy for B and C. *The app doesn't want your CV; it wants your intent and a
rough readiness read.* The one slice worth keeping is *work context as problem
flavour* ("I'm a numerical engineer"), in an explicitly-optional escape valve.

**Coarse C is more accurate, not just lighter:** people know whether *calculus* is
rusty; they're unreliable about *integration-by-parts specifically*. Subtopic
detail still accrues — from engagement and the skill-tree node panel (§7) — so
`user_subtopic_states` and its badges survive; we stop cold-collecting them via a
quiz.

How each shapes the arc — Day 1 / Week 1 / Month 1:
- **A** — topics of the queue → the spine → skill-tree terrain.
- **B** — the biggest lever on "does my first problem feel right" → a prior the
  curator quietly refines against real attempts → superseded by engagement state.
- **C** — which refreshers weave in + seeds assumed-background → feeds prerequisite
  look-ahead → fully engagement-driven.
- **D** — first-queue mix → soft balance target → drifts toward revealed
  preference.

## B2. Topics are a fan of paths — the densest signal

A topic is **not a linear curriculum; it's a fan of paths** with different prereq
profiles, math intensity, and endpoints. "Semiconductors" is ≥5 genuinely
different shapes:

| Path | Character | Math | Endpoint |
|---|---|---|---|
| Devices / circuits | Components; design with them | Algebra, empirical | "I can analyse a circuit with devices" |
| Quantum / band structure | *Why* they work | Lin-alg + QM, heavy | Band structures; direct vs indirect gaps |
| Optoelectronics | LEDs / lasers / solar | Some QM, goal-pulled | How a solar cell / LED works |
| Following research | 2D materials / spintronics / TIs | Opportunistic | Keeping up with a live field |
| Conceptual / industry | Moore's law, CMOS, scaling | Qualitative | The modern chip industry, physically |

**The path pick is the densest signal in onboarding:** one choice sets which shape
of the topic, the prereq emphasis, the math intensity/altitude (B), the mode lean
(D), and the endpoint. That's why it deserves *detail* (the user needs to
understand each path to choose) and why the current 80-char chip wastes it
(walkthrough ticket s13).

What's in the app today (thin): a `PathOption` is `key` + `label_md` (≤80 chars) +
`draft_intent_context` (soft string); picked, it collapses into `intent_context`
free text. It does **not** branch the curriculum — the node keeps one prereq edge
set, so all paths get the same tour and prereqs.

**Build it rich as *content*, not *structure*:**
1. **Rich path object** — `what_you_learn`, `endpoint`, `math_intensity` /
   `mode_lean`, `leans_on_prereq_slugs`. LLM-generated; presented *with detail* by
   the tutor and the curiosity box.
2. **Prereqs stay node-level but path-*aware*** — one (union) prereq set;
   readiness (C) and prereq timing *emphasize* the path-relevant ones via the path
   text. Soft, not structural — keep the megagraph coarse (graph-design §2.2; no
   path-nodes).
3. **The path sets B/D/altitude**, not just flavour.

**Commit vs explore is a false binary — decide it per-user.** Intent clear ("I want
to understand FETs") → commit (rich path `intent_context`, weighted prereqs,
pitch at that altitude). Ambiguous ("learn semiconductors") → present paths with
detail; pick, or say "not sure" → stay non-committal (start at the cross-path
conceptual entrance, let reactions reveal the path, firm up later).

## B3. Entry-point amendment (§3.4)

Current §3.4 keys the conceptual entrance off *new node in the user's graph* and
applies it "regardless of background." That conflates *new node* with *new to the
user*: a physicist who never studied superconductors → new → entrance is right; one
who *did* and wants depth → entrance condescends (and §5 forbids condescension).

**Fix:** key the entry-point on **new-to-the-user**, a *default* overridable by a
go-deep signal — which signal B captures:
- **New to me** → teach, entrance, assume little.
- **Coming back** → refresh, light recall, assume residual.
- **I know this — go deep** → consolidate/advanced, assume the apparatus, pitch up
  (the existing `consolidate` intent, now *enterable* at onboarding rather than
  only after the system decides you're comfortable).

§3.4's intent survives for the first two lanes; we carve out the third for the
go-deep friends. Reconcile with §3.1 (consolidate) and §3.5 (difficulty default).

## B4. The orientation tutor

Replace the seven-stage form with a **guided conversation** that elicits the four
signals the way a good tutor would — every question reframed as *interest in the
person*, not data extraction. A worked beat (the path interaction):

> "When you say semiconductors — the device-and-circuit side (designing with
> diodes and transistors, mostly algebra), the deep physics of *why* they work
> (band structure, more QM and linear algebra), applications like solar cells and
> LEDs, or following current research? Or not sure yet — we can start broad."

**Structure under the chat (this is what de-risks it):**
- **Signal tracking underneath** — an orchestrator tracks which of A/B/C/D it still
  needs and nudges the model to close gaps before offering "done." Open on the
  surface, structured underneath.
- **Tap-to-answer chips inline** — paths, the altitude choice, solid/rusty/new —
  so it's not all typing; free text always welcome alongside.
- **A growing "here's what I've got so far" map** — interests, paths/altitude, the
  foundations being calibrated — so the user sees the system hearing them and the
  graph forming. (This is also where s17 "what we learned about you" lives, and
  it subsumes s11's progress indicator.)
- **Explicit "I'm happy — build my queue"** — the user controls when it ends.
- **A "show me the questions" form mode** is the fallback for click-not-talk users
  and the resume surface — rendered by the *same orchestrator* (same four-signal
  collection, same chips), not the retired seven-stage survey (resolved decision 3).
- **Resumability:** persist the transcript + extracted-signals-so-far. At 30 users,
  latency/cost are irrelevant.

**The prompt is load-bearing.** The system prompt has to elicit four signals,
present paths with honest detail, read clear-vs-ambiguous intent and branch
commit-vs-explore, stay peer-to-peer (never quiz-like), and know when it has
enough. First-class deliverable with its own iteration.

## B5. The daily add-interest reshape — shared core, two envelopes

The survey and "add an interest in daily use" are the **same flow** today (one
`Dialog` + `ConceptTour`, driven by the survey page, `RequestBox`, and
`NodePanel`). The redesign preserves that, via a **shared core and two envelopes:**

- **Core (per-interest resolution):** parse → (path pick if ambiguous, §B2) →
  altitude/intent (§B3) → preview the first item → calibrate only the prereqs we
  don't already know.
- **Orientation tutor** = core × N interests **+** a foundation-readiness sweep
  (C — there's no engagement history yet) **+** mode (D) **+** the conversational
  wrapper.
- **Daily add** (the curiosity box's *commit* path, §A4) = core × 1, **no**
  foundation sweep (read existing `user_node_states` from weeks of engagement),
  **no** mode question, **no** wrapper. Light: parse → path-only-if-ambiguous →
  preview → go. Preserves §2.7 "just this once."

Because paths (§B2) and altitude (§B3) live in the *shared core*, **daily-add
inherits them for free**; its only specific change is *subtractive* — drop the
subtopic drill there too, read engagement state instead of calibrating cold. The
three personas' week-3 adds all survive and improve under this (path richness in,
redundant drill out). The guardrail: keep daily-add light; don't let the tutor's
conversational wrapper leak into "add GR."

---

## What we deliberately do *not* build

- **Path nodes / path-specific prereq edges** — keep the graph coarse
  (graph-design §2.2). Paths are rich content + soft path-awareness.
- **Subtopic-level cold-start calibration** — replaced by node-level C; subtopic
  detail accrues from engagement + the node panel.
- **Precise upfront user modelling** — the intake is a prior, not a model.
- **Biography collection** — only optional work-context-as-flavour.
- **A magic omni-box** — the curiosity box redirects rather than silently absorbing
  mood/feedback; those have their own legible surfaces.

## Build plan — Phases 12 and 13

**Phase 12 — The responsive daily loop** (Part A). *The system listens and adapts
to every interaction.* Self-contained; all decisions resolved.
1. Card action set (§A1) — calm card + overflow; split I-know-this / Not-for-me.
2. Bookmark as polymorphic save (§A2) — node/problem/paper; user-vs-system return.
3. Correction loop (§A3) — easier/harder/assume-less UI + sibling lifecycle;
   direct foundation-state edit.
4. Curiosity box as router (§A4) + steering chips (§A5) + requested-item pinning &
   badge (§A6).
5. Carry-in housekeeping (opportunistic): p1 (paper replenishment), p2
   (proportional `propose-papers`), the paper-chip backfill.

**Phase 13 — Conversational orientation** (Part B). *Onboarding as a tutor that
gets you, not a form.* Builds on the shared core Phase 12 touches.
1. Write the §3.4 amendment into `survey-and-difficulty-design.md` (resolved
   decision 4).
2. Rich paths (§B2) — object + generation + wire to `intent_context`/altitude/mode.
3. Altitude + node-level C calibration (§B1, §B3).
4. The orientation tutor (§B4) — orchestrator + signal tracking + chips + growing
   map + fallback + resumability + s17 mirror-back; the system prompt.
5. The daily add-interest reshape (§B5) — fold into the curiosity box's commit path.
6. Doc reconciliation (below).

**Deploy + a reader-facing README** land at the end, once the operator is happy
(localhost is the dev/test loop until then).

## Resolved decisions (2026-06-10)

All six are closed; build with these as settled.

1. **Path persistence → persist on `user_interests`, not a new table.** ✅ The path
   is the densest signal collected; storing it structured (a `path_json`, or a few
   columns: label / endpoint / mode_lean / leans_on) keeps it visible, editable,
   and curator-readable without re-parsing prose. It's per-(user, interest), so it
   lives on that row — no `interest_paths` table (paths aren't shared canonical
   objects; the megagraph stays coarse). Feeds a future path-overlay (t6) for free.
   *Phase 13 Step 2.*
2. **Foundation prereq emphasis → soft.** ✅ The prereq set stays node-level
   (union); the curator weights the path-relevant ones by reading the structured
   `path.leans_on` (decision 1 makes this a field read, not prose-parsing). No
   path-tagged edges — that pushes path-specificity into the graph structure
   (over-fine; graph-design §2.2). *Phase 13 Step 2.*
3. **Fallback form → a "show me the questions" *mode of the tutor's orchestrator*,
   not the seven-stage.** ✅ Preserving the seven-stage would ship and maintain the
   design we're retiring as a second divergent flow. Instead the tutor's
   orchestrator (which already tracks A/B/C/D and offers chips) renders the same
   collection as a plain form for click-not-talk users — one signal-model, two
   presentations. The existing seven-stage stays until Phase 13 ships, then it's
   replaced. *Phase 13 Step 4.*
4. **§3.4 amendment → yes, write it first.** ✅ Entrance stays the *default*; only
   an explicit go-deep signal (altitude B) bypasses it, entering at the existing
   `consolidate` altitude. Must land before the generator reads altitude, or the
   signal is inert. *Phase 13 Step 1.*
5. **Direct foundation-state editing → yes, framed as "tell us."** ✅ It's just
   making signal C editable post-onboarding: the user re-states node-level
   readiness ("solid on ODEs now" / "still rusty"), writing the same kind of prior
   a survey mark does, refined by engagement as usual. Don't expose raw
   `struggle_score`; keep the "system curates" surface. *Phase 12 Step 3.*
6. **dismiss→bookmark smell → it's a bug; fix in Phase 12 Step 1.** ✅ "Not for me"
   must write a negative-preference/dismiss, not a bookmark. Verify the current
   behaviour, then replace when the real card-action set lands — not a feature to
   preserve.

## Docs to update when this lands

Pointers are already in place so a fresh session isn't caught out (CLAUDE.md
source-of-truth list + build-phase list; banner atop `survey-and-difficulty-
design.md`; notes on the now-closed Phase 10.5-rev plan). When built, fold the
changes into the canonical specs and drop the "proposal" framing:

- **`survey-and-difficulty-design.md`** — rewrite §1 (tutor + four signals), §2.3
  (rich paths), §2.7 (curiosity-box router), §3.4 (entry-point new-to-user), §3.5
  (correction loop built). Remove the superseded banner once reconciled.
- **`personas.md`** — update each persona's *onboarding beat* to the conversational
  tutor + path pick + altitude (week-1/month-1 arcs are unaffected). Don't let the
  personas drift silently.
- **`curriculum-curator-design.md`** — note the new cold-start priors (path-aware
  `intent_context`, node-level C, altitude) and path-aware prereq emphasis.
- **`pivot-plan.md` / phase plans** — mark Phases 12/13 done as they land.
- **CLAUDE.md** — soften the "not yet built" caution to a plain source-of-truth
  entry once built.
