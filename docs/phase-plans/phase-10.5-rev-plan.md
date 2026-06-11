# Phase 10.5-rev — pre-launch remediation plan

> **Status: CLOSED — remediation complete.** This was the **operator-walkthrough
> round**: Steps 1–4 and 7 landed (queue lifecycle, refresher subsystem,
> problem-page template + queue-card topics, survey rendering & concept-tour,
> skill tree & notebook). The remaining items — Step 5 (survey copy), Step 6
> (Stage-4 clarification + the s18 concept-tour redesign), and parts of the
> features bucket — were **not patched in this plan's shape.** A design-review
> round (2026-06-08/09) stepped back and reconceived the survey, add-interest,
> and per-problem-correction surfaces wholesale; those items are **absorbed by
> Phases 12 & 13** (see
> [docs/orientation-and-calibration-design.md](../orientation-and-calibration-design.md)
> and the [phase-12](phase-12-responsive-daily-loop-plan.md) /
> [phase-13](phase-13-conversational-orientation-plan.md) plans). Per-ticket
> disposition is in the Step 5 / Step 6 banners below. Carried-over non-blocking
> work (p1/p2 paper balance, the paper-chip backfill) moves to **Phase 12
> Step 5**. The launch-gating framing (🔴/🟡, soft launch) is retired — the app
> is finished before release. **Operator actions still pending from Step 3:**
> apply migrations 20250032/20250033 and run the reformat backfill.

Forward-looking plan. Source of truth for the product remains
[../SPEC.md](../SPEC.md), [../ARCHITECTURE.md](../ARCHITECTURE.md),
[../graph-design.md](../graph-design.md), and [../personas.md](../personas.md).
This phase fixes roughness in the already-shipped v2 surfaces; it introduces no
new product scope beyond the four explicitly-flagged feature requests in the
final step.

The raw walkthrough evidence — verbatim notes, reproduced UI text, the queue
dumps — lives in `docs/operator-walkthrough-notes.md`, which is gitignored and
local to the operator. **This plan restates every item it covers so it stands
alone** and does not depend on that local file.

---

## Where we are (on entry)

Phase 10-rev is complete: 192 pytest passing; megagraph at 42 nodes
(13 foundation, 29 interest, 0 orphans, every domain ≥ 6); B1 refresher-routing
fix landed. The operator then walked the real Next.js UI end-to-end (seven-stage
onboarding + daily flow + a 375×667 mobile pass) and logged 47 items: bugs,
polish, and four feature requests.

This phase is the remediation. Phase 11-deploy (FastAPI deploy + pg_cron
migration 20250024 + Sentry) follows, gated only by the launch-blocking subset
below.

## Goal

After Phase 10.5-rev:

- The core daily loop (queue → problem / paper / refresher → notebook) is free
  of the correctness bugs that break it for a first-time user: no duplicate
  queue spam, papers honour the mode balance, refreshers route and complete
  correctly, and read/done state clears the card.
- The onboarding survey orients the user — what the site is, what they can ask
  for, and what each stage does — and its cards render without truncation or
  escaping artefacts.
- The problem reading surface has a consistent, legible template.
- The skill tree and notebook are coherent and the bookmark action persists.

## Launch gating

Not all 47 items block launch. The product is deliberately no-guilt / forgiving
(no streaks, comes-when-you-want), so a soft launch to a few trusted friends can
run while polish lands in parallel. The **launch-blocking set (🔴)** is Steps 1,
2, and 4, plus the bookmark-persistence bug (t4) in Step 7. **Phase 11-deploy is
gated only by that set**; the 🟡 steps and the features bucket can overlap the
soft launch.

Suggested order: **1 → 2 → 4** (blockers; 4 is small and high-value) →
**3 → 5 → 6 → 7** (polish, any order) → features.

---

## Open decisions

### Q1 — Queue lifecycle semantics ✅ resolved (Step 1)
Resolved at Step 1 entry and written up in
[curriculum-curator-design.md §11.1, §11.4, §13.4](../curriculum-curator-design.md).
The settled semantics: reroll re-surfaces the next pending items (no regen on
click); the queue is bounded (hard cap 15, refill-on-drain below 6); duplicates
are prevented at every write path; papers are seeded at cold-start to honour the
mode slider; the F17 starter fallback is a guarded last resort that can fire at
most once; removing items / a deferred home is Step 7 (g1).

### Q2 — Does the add-interest tour need per-subtopic prereq calibration? ✅ resolved in principle (orientation redesign, 2026-06-08)
**Resolution:** collapse cold-start calibration to **node-level** (signal C); the
subtopic drill is dropped, subtopic detail accrues from engagement + the
skill-tree node panel. Folded into the larger onboarding reshape in
`docs/orientation-and-calibration-design.md` (§3). Note the data-flow correction
recorded there: the per-subtopic marks *were* consumed — by the assumed-background
paragraph at problem-generation time ([curator_inputs.py](../../api/curator_inputs.py)),
not by the planner — so "the planner never reads it" was true but undersold the
real (narrow) consumer. The original Q2 text is kept below for history.

#### Original Q2 (superseded) ⏳ open (decide in Step 6)
Surfaced in Step 3 while diagnosing s18. Traced the data flow: the curriculum
curator (`build_curator_context`) only ever reads **node-level** prereq state
(`foundation_node_states` ← `user_node_states`); it never reads the concept
tour's per-subtopic `comfort_responses_json` / `user_subtopic_states`. Those
subtopic marks are read back only (a) when a problem is later generated *on that
foundation node* (the assumed-background dial) and (b) to paint skill-tree
node-panel badges — not for planning. So the 10-tile subtopic drill is
over-collection relative to what the planner consumes. **Decision for Step 6:**
keep per-subtopic calibration (sharper generation + UI badges, at the cost of a
test-feeling drill per interest) vs. collapse to a light **node-level** "how
solid are you on the foundations this leans on?" (aligns with "the system
curates; the user trusts"). Bundled with the s18 preview/calibration split in
Step 6's scope note. Also decide there whether to include topical (interest-kind)
prereqs like SR/GR, which the current foundations-only tour drops.

---

## Steps

Each step is one cohesive subsystem or surface, sized to end at a natural review
boundary (a working fix + passing tests). Per-step detail is intentionally light
here — the executing session plans its own approach.

### Step 1 — Queue lifecycle & correctness 🔴 ✅ done

The core daily loop was broken in this cluster. Q1 resolved first (see above).

| ID | Issue | Resolution |
|----|-------|------------|
| g3 | Queue refresh behaviour undefined — reroll vs. fill-gaps, length, dedup, removal, growth. | Written spec ([curriculum-curator-design §11.4](../curriculum-curator-design.md)) + reroll/refill/cap implemented. |
| d16 | Queue contains 6+ duplicate QM concept entries (all priority 0.30); "show me something else" produces nothing. | Root cause was an undeduped F17 fallback re-minting on every empty surface + an under-stocked queue. F17 now fires once for an empty account only; planner enforces a 15-item cap; refill-on-drain keeps it stocked. |
| d17 | No papers appeared despite 50/50 mode balance set in survey. | Papers were orphaned behind a never-run weekly job. Cold-start now seeds papers via `propose-papers` when the slider gives papers a meaningful share. |
| d5 | Concept and first refresher for QM appeared to be the same content. | Refresher pool-miss now generates a refresh-intent problem (distinct active recall) instead of duplicating the node's concept brief; reuses an existing concept on generation failure. |
| d15 | Concept card doesn't disappear after marking it read. | Symptom of the F17 re-mint; fixed by the F17 guard. The client already did `router.refresh()`. |
| d1 | Concept cards in queue unexplained. | Orientation copy added under "Up next" + clearer starter-concept reason. |

Landed in [surface_daily.py](../../api/routes/surface_daily.py),
[curator.py](../../api/routes/curator.py),
[curator_plan.py](../../api/prompts/curator_plan.py),
[refresher.py](../../api/routes/refresher.py), [schemas.py](../../api/schemas.py),
[pythonApi.ts](../../web/lib/pythonApi.ts),
[queueHelpers.ts](../../web/lib/queueHelpers.ts),
[reroll/route.ts](../../web/app/api/queue/reroll/route.ts),
[survey/complete/route.ts](../../web/app/api/survey/complete/route.ts),
[DailyView.tsx](../../web/components/DailyView.tsx). 197 pytest passing (was 192).

**Carried over to Step 2** (surfaced while fixing d17, non-blocking — see the
note under Step 2): ongoing paper-balance replenishment, and proportional
`propose-papers` counts.

### Step 2 — Refresher subsystem end-to-end 🔴 ✅ done

One subsystem broken in several places. **Resolution-model decision
(operator-approved):** a refresher is not a content kind — it is a *framing
flag* (`via_refresher`) on a concrete `problem` / `concept_review` /
`paper_engagement` item, resolved once at **creation** time (the planner, the
post-engagement prerequisite path, or an on-demand request), never by a
navigation side-effect. The click-time `/refresher-resolve` route and the
`web/app/refresher/[id]` resolver page are deleted; resolution lives in
`resolve_refresher_to_content` + `POST /create-refresher`
([api/routes/refresher.py](../../api/routes/refresher.py)). This dissolved the
bug cluster structurally rather than patching each instance. See
[curriculum-curator-design §11.5](../curriculum-curator-design.md).

| ID | Issue | Resolution |
|----|-------|------------|
| d2 | Refresher cards are missing titles. | Items are now concrete kinds, so `resolveTitles` lifts the problem/node/paper title for free. |
| d4 | Hitting "back to queue" inside a refresher marks it done and removes it. | Opening is non-destructive; the card is a normal item, marked done only on completion. |
| d18 | Blank refresher appeared; clicking it redirected to /daily. | Prevent-at-source: the resolver returns `None` when nothing resolves, so a dead row never enters the queue; legacy rows dismissed in migration 20250030. |
| d21 | "Take me to it" from a paper-triggered refresher returns to /daily. | `/api/queue/request` returns the concrete kind; new `queueItemPath` helper routes problem/concept/paper correctly from OrientingConceptsPanel, NodePanel, RequestBox. |
| d20 | In-paper concept-refresher popup is off-style. | Restyled to the forest/paper-mode family with the standard motion tokens. |
| d3 | Refreshers and concepts look structurally identical. | `via_refresher` drives a distinct "Refresher" badge + revisit CTA while routing by the real kind; plain Concept cards keep the neutral badge. |
| g2 | Node → request refresher → navigate-there-and-back unclear. | Parent lineage recorded (`parent_queue_item_id`) for the paper back-link; refreshers now surface as ordinary clearly-badged cards so the round trip is queue-mediated. Deep "back to this node" rides Step 7 (n2). |

Landed in migration 20250030, [refresher.py](../../api/routes/refresher.py)
(rewrite), [curator.py](../../api/routes/curator.py),
[surface_daily.py](../../api/routes/surface_daily.py), [schemas.py](../../api/schemas.py),
[pythonApi.ts](../../web/lib/pythonApi.ts), [queueHelpers.ts](../../web/lib/queueHelpers.ts),
[types.ts](../../web/lib/types.ts), [optimisticQueueRequest.ts](../../web/lib/optimisticQueueRequest.ts),
[DailyView.tsx](../../web/components/DailyView.tsx),
[OrientingConceptsPanel.tsx](../../web/components/OrientingConceptsPanel.tsx),
[NodePanel.tsx](../../web/components/NodePanel.tsx), [RequestBox.tsx](../../web/components/RequestBox.tsx),
[queue/request/route.ts](../../web/app/api/queue/request/route.ts); resolver page deleted.
197 pytest passing; web typecheck clean. **Operator: apply migration 20250030, then reset-walk to a refresher.**

**Carried over from Step 1 (queue/curator follow-ups, non-blocking — fold in
while you're in the curator code, or defer):**

| ID | Issue |
|----|-------|
| p1 | Ongoing paper balance is only partial. Cold-start seeds papers so the slider is honoured on day one, but the refill-on-drain path runs only the planner (problems + refreshers) — papers aren't replenished until the (deferred) weekly job, so the mix drifts problem-heavy over time. Decide whether refill should top up papers proportionally to `mode_balance`, or whether the weekly job is enough. (The planner is deliberately forbidden from emitting paper recs, so this means wiring `propose-papers` into the refill path, not changing the planner.) |
| p2 | `propose-papers` ignores the slider's magnitude — it always returns 3–5 papers whether the user set 0.3 or 1.0. For true proportionality it needs a target-count parameter derived from `mode_balance` and the queue cap. |

### Step 3 — Problem page presentation & template 🟡 ✅ done

Three operator-approved decisions taken at entry: (1) enforce the template in
**both** layers — render now (helps existing rows) + prompt (new rows) — **plus**
a Haiku content-preserving reformat of the ~24 existing problems; (2) **stored**
`part_label` + chip for d10; (3) d12 is a **prompt constraint** (structural), not
a one-off. Diagnosis found two latent renderer bugs behind d6/d8 and confirmed d9
empirically (parts numbered `(a)` / `1.` / "Part" inconsistently across the pool).

| ID | Issue | Resolution |
|----|-------|------------|
| d6 | No title/subheadings; undifferentiated layout. | The page never even selected `problems.title`. Now: topic metadata line + serif title header; `READING_PROSE` styles `##`/`###` headings, `---`, blockquotes. |
| d7 | Context below the statement. | Context rendered **first**, above the statement, always-open (was a collapsed `<details>` below). Prompt + reformat move inline historical framing into `context_md`. |
| d8 | LaTeX cramped. | `.katex-display` gets vertical breathing room + horizontal scroll (mobile overflow guard); prompt mandates display math for standalone equations. |
| d9 | No consistent template. | Canonical skeleton pinned in the generation prompt (context-first, `## Setup`/`## The problem`, bold `**(a)**` parts); render tolerant of old shapes; reformat brings existing rows in line. |
| d10 | Hint→part mapping unclear. | Migration 20250032 `problem_hints.part_label`; `GeneratedProblem.hints` now `[{text, part_label}]`; ProblemView shows a chip per hint (omitted when null). |
| d11 | No topic on problem page. | Metadata line resolves the topic node title (`page.tsx` fetches it). |
| d22 | Queue cards show topic(s). | `resolveTitles` resolves `topics: string[]` for **all** kinds — problem (topic node), concept (the node), suggested_interest (the node), and **paper** via new `papers.topic_node_ids` (migration 20250033, populated by `/propose-papers` mapping each paper to interest titles → node ids; unioned, shared). DailyView renders a chip per topic, suppressing any equal to the title. |
| d13 | No answer-layout guidance. | A short pre-upload tip on Step 2 (label parts, one part per page, number multi-page). |
| d12 | Hints over-assume. | Cited problem was gone (DB reseeded). Root-caused to the prompt: the assumed-background dial governed the statement but not the hint ladder. Added a constraint — hints obey the same dial, never introduce machinery the statement withheld. |

Landed in migrations 20250032 + 20250033, [schemas.py](../../api/schemas.py)
(`GeneratedHint`, `ProposedPaperCandidate.interest_titles`),
[prompts/problem.py](../../api/prompts/problem.py) (template + hint constraint),
[prompts/propose_papers.py](../../api/prompts/propose_papers.py),
[routes/generate_problem.py](../../api/routes/generate_problem.py),
[routes/propose_papers.py](../../api/routes/propose_papers.py),
[markdown.tsx](../../web/lib/markdown.tsx) (remark-gfm),
[ProblemView.tsx](../../web/components/ProblemView.tsx),
[queueHelpers.ts](../../web/lib/queueHelpers.ts) (rewrite → `topics[]`),
[DailyView.tsx](../../web/components/DailyView.tsx), [types.ts](../../web/lib/types.ts),
[problem/[id]/page.tsx](../../web/app/problem/[id]/page.tsx), and a new
[scripts/reformat_problems.py](../../scripts/reformat_problems.py). 201 pytest
passing (was 200); web typecheck + lint clean.

**Operator actions:** (1) apply migrations 20250032 + 20250033
(`npx supabase db push`); (2) restart the web dev server (picks up remark-gfm);
(3) run `scripts/reformat_problems.py --dry-run` → spot-check → `--apply`
(rewrites existing problems + backfills `part_label`, deletes the handful of test
attempts to preserve immutability). Validated on one problem in dry-run.

**Deferred (non-blocking) — captured for later:**
- **User-added papers carry no topic chip.** `topic_node_ids` is populated only
  by `/propose-papers`; papers added via `/ingest-paper-user` (AddPaperForm) have
  none, so those cards show no chip. Graceful (empty → no chip). Cheap follow-up
  if wanted: a Haiku classify-against-interests at ingest time.
- **Existing queued papers won't show a chip** until re-proposed (their
  `topic_node_ids` is empty). Resolves itself on a reset-walk; a one-off backfill
  (same shape as the reformat script) is possible but not worth it pre-launch.
- **s18 concept-tour redesign → Step 6** (see that step's scope note): the
  add-interest tour shows prerequisites, not the interest's own content. An
  interim honesty copy fix landed here; the structural fix (preview own subtopics
  + node-level calibration + the per-subtopic-calibration question) belongs with
  Step 6's same-surface redesign.

### Step 4 — Survey rendering & concept-tour bugs 🔴 ✅ done

Two rendering bugs plus the concept-tour data/logic that surfaced the wrong
prerequisites (t2) and over-skipped tours (s15). Diagnosis was driven by the
verbatim walkthrough output: t2 was reproduced adding **Cosmology & the
Lambda-CDM Model**.

| ID | Issue | Resolution |
|----|-------|------------|
| s5 | Foundation card explainer text is cut off. | `line-clamp-2` on the tile description dropped — it always truncated the foundation nodes' long comma-list descriptions. |
| s9 | Interest-suggestion card text is cut off (same truncation as s5). | Same `line-clamp-2` removed on the suggestion card description. |
| t2a | Double-quotes (`''`) instead of apostrophes in card text. | **Seed-data bug, not a renderer bug.** `01_curriculum.sql` wrote `subtopics` JSONB inside `$$…$$` dollar-quoting but used SQL `''` apostrophe-escaping, which is literal there — so titles stored as "Newton''s", "Coulomb''s", etc. Repaired live data in migration 20250031 and fixed the seed source. |
| t2b | Adding a new interest surfaced the wrong prerequisite topics. | **Bad megagraph edges, not a lookup bug** — the tour correctly read the resolved node's own prereq edges. Cosmology's seeded prereqs wrongly included `electromagnetism-1` (Coulomb/Biot–Savart/RLC) and omitted statistical mechanics. Migration 20250031 drops the EM edge, adds statistical-mechanics + multivariable-calculus prereqs and a general-relativity *related* edge; YAML seed updated to match. **Also** tightened tour granularity: `_concept_tour` now takes tiles round-robin across prereqs (foundations first) so one foundation's long intro list can't monopolise the tour. |
| s15 | Concept tour skipped a node's tour ("covered this earlier") when it shouldn't have. | Cross-tour dedup over-fired: it keyed on subtopic *name* alone and marked every *shown* tile seen. Now node-scoped (`node_id:subtopic_key`) and records only tiles the user actually *answered* (§1.6.5 "unless the state was not captured"). |

Landed in [FoundationsGrid.tsx](../../web/components/survey/FoundationsGrid.tsx),
[InterestSuggestions.tsx](../../web/components/survey/InterestSuggestions.tsx),
[ConceptTour.tsx](../../web/components/addInterest/ConceptTour.tsx),
[DialogOrchestrator.tsx](../../web/components/survey/DialogOrchestrator.tsx),
[add_interest.py](../../api/routes/add_interest.py), migration 20250031, and the
[01_curriculum.sql](../../supabase/seed/01_curriculum.sql) /
[cosmology-lambda-cdm.yaml](../../supabase/seeds/interests/cosmology-lambda-cdm.yaml)
seed sources. 200 pytest passing (was 199); web typecheck clean.
**Operator: apply migration 20250031, then reset-walk the survey through the
concept tour to confirm s5/s9/t2/s15.**

### Step 5 — Survey copy & orientation 🟡

> **Mostly mooted by the orientation redesign (2026-06-08).**
> `docs/orientation-and-calibration-design.md` replaces the seven-stage survey
> with a conversational orientation tutor, so most of these copy questions are
> answered by the conversation rather than by re-writing form labels. Only
> revisit the items that still apply to the *fallback form* (the click-not-talk
> path). Do **not** do a copy pass on the old stages on the assumption they
> survive as-is. See orientation doc §10 for the per-ticket mapping.

One editorial pass. Write the copy in the site's normal voice.

| ID | Issue |
|----|-------|
| s1 | No context about what the site is before the first question (subsumes s2 "which fields?" and s3 "will it block a biology request?"). |
| s4 | Unclear whether to select an adjacent field (e.g. biology) and what "relationship" to it means. |
| s6 | Unclear what marking a foundation for revisit commits to; fear of missing a prerequisite. |
| s7 | Ambiguous whether leaving a foundation unmarked means "comfortable" or "not interested". |
| s8 | Unclear what Stage 3 interest tiles are for and how they differ from Stage 2 foundations. |
| s10 | Unclear how the Stage 3 "anything else" box differs from the Stage 1 free-text field. |
| s16 | No copy explaining what the confirm graph is or how the user interacts with the graph later. |

### Step 6 — Survey Stage 4 clarification 🟡

> **Reconceived by the orientation redesign (2026-06-08).** Do not build these
> tickets in the old shape. `docs/orientation-and-calibration-design.md` absorbs
> and supersedes them: s12/s13/s14 → the conversational orientation tutor (§5) +
> rich per-interest paths (§4); s18/Q2 → node-level calibration + previewing the
> interest's own content (§3); s11 → the tutor's "what I've got so far" map; s17
> → the tutor's end-of-chat graph mirror-back. Read the orientation doc and lock
> its §11 open decisions before writing any code here. The table below is
> retained as the original walkthrough evidence.

| ID | Issue |
|----|-------|
| s12 | First clarifying question is inconsistent — free-text sometimes, multi-select other times. |
| s13 | Multi-select options read as sub-topics, not distinct learning paths / intent signals (the intent axis is lost). |
| s11 | No progress indicator through the per-interest clarification flow. |
| s14 | Preferred flow: free-text "what do you want to learn" → parse → suggest paths. Decide in-session whether to do the full s14 redesign or just s12/s13. |
| s18 | **Concept tour shows prerequisites, not the interest's own content** (found re-walking add-interest with "astrophysics" → resolved to *Stellar Evolution, Compact Objects & Accretion*; the tour surfaced Thermo / Stat Mech / QM subtopics). The screen *promises* a preview ("Here's what will come up for X") but *delivers* prerequisite calibration. An interim honesty copy fix landed in Step 3 ([ConceptTour.tsx](../../web/components/addInterest/ConceptTour.tsx) — reframed to "the groundwork X builds on"); the real fix belongs here because it's the same add-interest surface as s12/s13/s14. |

**Step 6 scope note — add-interest moment, designed once (s18 + ties to s17).**
The Stage-4/5 redesign should split the two things the current tour conflates:
1. **Preview the interest's own subtopics** — "Here's what you'll explore in
   *Stellar Evolution*: stellar structure, nucleosynthesis, compact objects,
   accretion…". Read-only, orienting; data already exists in
   `nodes.subtopics_json`. This is what the user expects to see when adding an
   interest, and it serves the same "the system gets me" goal as s17.
2. **Calibration at the altitude the curator actually consumes — node level.**
   The planner (`build_curator_context`) only reads node-level prereq state
   (`foundation_node_states` ← `user_node_states`); it never reads the tour's
   per-subtopic `comfort_responses_json` / `user_subtopic_states`. Those
   subtopic marks are read back only when a problem is later generated *on that
   foundation node* (assumed-background dial) and to paint skill-tree node-panel
   badges — not for planning. So **decide whether per-subtopic calibration
   survives at all**, or whether a light node-level "how solid are you on the
   foundations this leans on?" is enough (leaning on "the system curates; the
   user trusts" rather than a 10-tile self-assessment per interest).
3. **Include the topical prerequisites.** `_concept_tour`
   ([add_interest.py](../../api/routes/add_interest.py)) tours only
   `kind='foundation'` prereqs and relegates `kind='interest'` prereqs (e.g.
   Special/General Relativity for astrophysics) to a fallback that the 10-tile
   cap means is never reached — so the *most* topic-relevant prerequisites are
   dropped. Fix as part of the calibration redesign.

### Step 7 — Skill tree & notebook ✅ done

| ID | Issue | Resolution |
|----|-------|------------|
| t4 | 🔴 Bookmarking a node doesn't persist — panel updates, node appearance unchanged on return, can be bookmarked again. | Root cause was a disconnect, not RLS: bookmarks live in the `bookmarks` table but the graph coloured nodes purely from `user_node_states.state` (which is never set to `'bookmarked'`). Fixed with an **overlay flag** (operator decision): `/api/graph/me` + `/skill-tree` loader read `kind='node'` bookmarks, attach a `bookmarked` boolean per node, fold bookmarked adjacent nodes into the rendered slice; SkillTreeView draws an amber dot; NodePanel inits from the flag + `router.refresh()`. A per-node `isUserNode` flag (interest OR has-state) keeps "Add/promote to interest" available on bookmark-only nodes. See [[project_node_state_model]]. |
| t1 | Node detail panel has too many buttons/sections; needs reorganisation. | Retiered: contextual promotion banner (nearby nodes) → primary engage pair (problem/paper) → quieter annotation pair (bookmark/comfortable). |
| t3 | Node states too visually similar; "struggling" should not be user-facing. | `struggling` folded into "Active" (amber) across SkillTreeView / SkillTreeListView / ProfileView. Three user-facing colours: neutral / amber / forest. The internal red signal is gone. |
| t5 | "Get a problem" / "bookmark" / "add to interests" actions aren't differentiated — no explainer. | One-line inline explainer under each action (operator chose inline text over tooltip — works in the mobile list view). |
| n2 | "See in skill tree" goes to the default view, not the specific node. | `/skill-tree?node=<slug>` deep-links; the page resolves slug→id and SkillTreeView opens the panel (initial selection state) + `fitView`s to it. Wired from the notebook come-back tab and the ProfileView interest list. |
| n1 | Notebook should have tabs at the top, like a real notebook. | Tab strip: **All** · **Topics ▾** dropdown (by interest — operator chose by-interest; landed on the dropdown styling, "Option C", after a `/design` comparison of four; trigger label truncates, column widened to `max-w-3xl`) · **Come back to this**. |
| g1 | "Come back to this" / deferred items have no clear home (probably a notebook tab — ties to n1). | A unified **Come back to this** tab (operator decision): bookmarked nodes + deferred items (`queue_items.state='deferred'`). Deferred rows show topic badges + an inline read-only **Preview** of the problem and a **Queue it now** manual resume (`POST /api/queue/resume`, inverse of defer). |

### Features / larger asks — schedule or defer

Genuine new capability, not polish. None launch-blocking. Either give each its
own session after the blocking work or push to a post-launch v2.1 phase.

| ID | Request |
|----|---------|
| s17 | Generated "here's what we learned about you" summary at the end of the survey. |
| d14 | Q&A on the feedback page — ask follow-ups, request queue additions. |
| d19 | Pause-and-resume for paper engagements. |
| t6 | Curriculum-path overlay on the skill tree (show the user's planned route). |
| fb1 | **Report-a-problem channel.** A lightweight, always-available way for the friends cohort to tell the operator something is wrong — a persistent "Report a problem / send feedback" affordance (nav or footer link, or a small floating widget) reachable from anywhere in the app. Free-text + optional category (bug / confusing copy / bad problem or paper / other) and it should auto-capture the current URL and user so the operator can reproduce. Stored in a new `feedback_reports` table and surfaced on an operator screen (and/or a notification). Distinct from d14 (which is scoped to a single problem's feedback page) and from the disputed-grade flow (operator review of one grade) — this is the global catch-all so nothing has to find its way into a specific surface to be reported. Low effort, high value for a trusted-friends launch. |
| fb2 | **"I can't find this paper" escape hatch.** A paper engagement assumes the user can obtain the actual paper, but the system only stores metadata (title / arXiv id / DOI / external_url / abstract) — the user has to go find the PDF themselves. When they can't (paywalled, dead link, not freely available), there's currently no way out: the engagement sits in the queue uncompletable. Add an affordance on the paper engagement surface (and/or the daily card) — "I can't find this paper" — that (a) clears it from the user's active queue (a terminal/parked state, optionally backfilling another paper to honour the mode balance — ties to p1), and (b) flags the operator to review whether *they* can source it. Capture an optional reason (paywalled / dead link / can't locate). Suggested data: a `paper_sourcing_reports` table (paper_id, user_id, reason, state, created_at, resolved_at) + an operator surface listing flagged papers. **Decide:** is the flag per-user (only this user's queue clears; the paper stays live for others) with a per-paper operator review, or does N reports auto-deprecate the paper globally? Lean per-user-clear + per-paper operator review — the operator decides global fate, and a successful source (fb3 upload) resolves it. Pairs with fb3 as a "paper sourcing" subsystem. |
| fb3 | **Community PDF store.** When a user *does* find and download a paper, let them upload the PDF so the next user who gets the same paper doesn't have to hunt — and so an fb2 "can't find" report can be resolved by anyone (incl. the operator). Suggested: an "Upload PDF" affordance on the paper engagement view → Supabase Storage bucket (e.g. `paper-pdfs`) keyed by `paper_id`; a `papers.pdf_storage_path` column (or a `paper_files` table if we ever want multiple/versioned files); future users see a "Download PDF" link served from storage alongside the external link. **Copyright caveat (decide before building):** redistributing copyrighted journal PDFs even within a 30-person trusted cohort is legally grey. arXiv / open-access preprints are freely redistributable; paywalled publisher PDFs are not. Recommend scoping the shared store to arXiv/open-access papers (gate on `arxiv_id` present, or an `is_open_access` flag), or making uploads operator-curated rather than auto-shared, and stating the policy in-app. First-upload-wins vs operator-canonical, file-size cap, and virus/lint of uploads are secondary decisions. Pairs with fb2. |

---

## Done when

- Every 🔴 item is fixed and covered by a test where testable; the daily loop
  walks clean on a fresh reset user.
- Every 🟡 step is either landed or explicitly deferred with a note.
- The features bucket is triaged: scheduled as later steps or moved to a v2.1
  deferred list.
- pivot-plan.md status line reflects completion; Phase 11-deploy can begin once
  the 🔴 set is in.
