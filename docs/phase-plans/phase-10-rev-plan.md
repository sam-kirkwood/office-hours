# Phase 10-rev — execution plan

> **Status: Step 1 complete.** Step 1 produced three design documents that
> significantly reshape the rest of the phase. Step 2 onwards is rewritten
> below to reflect them.

Forward-looking plan for Phase 10-rev. Source of truth for the product is
[../SPEC.md](../SPEC.md), [../ARCHITECTURE.md](../ARCHITECTURE.md),
[../graph-design.md](../graph-design.md), [../personas.md](../personas.md),
and the three Step 1 design documents:

- [survey-and-difficulty-design.md](../survey-and-difficulty-design.md) — the
  redesigned survey, add-interest flow, difficulty/intent/assumed-background
  model, and schema additions.
- [curriculum-curator-design.md](../curriculum-curator-design.md) — the
  LLM-driven queue intelligence (Sonnet daily planner + Haiku post-engagement
  assessor). Replaces the minimal `/update-queue` design.
- [persona-1-walkthrough.md](../persona-1-walkthrough.md) — illustrative
  four-week walkthrough demonstrating the design in practice.

This file captures *execution* decisions and step ordering.

---

## Where we are (expected on entry)

Phase 9-rev is complete:
- All `contradicts`-severity drift items resolved.
- All API bugs fixed (#18–23).
- Queue cards show titles and dynamic reasons.
- Skill tree uses correct auth client; NodePanel has full action set.
- Admin surfaces complete.
- Pre-step fixes applied: reroll route now calls `resolveTitles`;
  `problems.title` column added.

Step 1 of Phase 10-rev produced the three design docs listed above. The
design diverges substantially from the original Step 2 scope in the previous
version of this plan; the new Step 2 reflects the actual design.

---

## Phase 10-rev goal

After Phase 10-rev:

- The survey is the seven-stage flow specified in
  [survey-and-difficulty-design.md §1](../survey-and-difficulty-design.md):
  background page → foundation tiles → interest suggestions → add-interest
  dialog → concept tour → mode balance → confirmation. The original three
  missing drift items (#7 comfort calibration, #8 skill-tree exploration,
  #9 post-submission confirmation) are subsumed by this redesign — see
  Section "Drift report reconciliation" below.
- The add-interest flow specified in
  [survey-and-difficulty-design.md §2](../survey-and-difficulty-design.md) is
  the single mechanism used at onboarding and from the "Curious about
  something specific?" input box on the daily tab.
- The curriculum curator from
  [curriculum-curator-design.md](../curriculum-curator-design.md) replaces
  `/update-queue`. The queue is planned daily by a Sonnet call per active
  user; engagements are assessed by a Haiku call; deferred items are
  re-queued deterministically when prerequisites are addressed.
- The three-dial problem character model (difficulty / assumed background /
  intent) is enforced at generation time, with subtopic tagging treated as
  load-bearing.
- The queue UX is spec-correct: `concept_review` items work, reroll events
  are recorded for the curator, paper requests trigger paper discovery on
  empty pools, and the queue surfaces are fire-and-forget rather than
  blocking.
- The spirit/persona gaps are addressed: paper resume shows progress,
  orienting concepts are interactive, cross-pollination has social framing,
  bookmarks have a forward path, the notebook is prominent.
- The skill tree has edge interaction, "what's nearby?" expansion, and a
  per-subtopic refresh action in the node panel (per
  [survey-and-difficulty-design.md §7](../survey-and-difficulty-design.md)).
- The product works well on mobile for the key flows.
- Error monitoring is in place.
- **Acceptance:** a live site walkthrough passes all three persona journeys
  without friction; v2 is ready for the first friends cohort.

---

## Out of scope

- **Live arXiv search, D3 megagraph visualisation, notebook export, BYO API
  key, hand-authored problems, calendar view, return-after-absence prompts.**
  All deferred to v2.1+.
- **Adjacent surfacing** (papers mentioned in other papers' engagements).
  v2.1 at earliest.
- **User-controlled interest prioritisation.** The curriculum curator
  consumes engagement signals (rerolls, deferrals, marked-refreshed) as the
  prioritisation channel in v2; explicit priority controls are v2.1.

---

## Open decisions

The Step 1 design docs resolved D1, D2, and D4 from the previous version of
this plan. Two decisions remain open and must be locked in before the
relevant steps begin.

### D3 — Concept review content source (still open)

`queue_items.kind = 'concept_review'` points to `nodes(id)` and is intended
to surface concept-level material on a node without generating a full
problem. The design docs partially constrain this: the add-interest flow's
"Case 3" (concept-level request from the input box, see
[survey-and-difficulty-design.md §2.7](../survey-and-difficulty-design.md))
queries the problem pool for a subtopic-tagged problem; the skill-tree node
panel's per-subtopic "request a refresher" action does the same.

But what does the `concept_review` *card* itself render when clicked? The
options remain:

a) **Node description + subtopics** as a structured reading surface — a
   "what this is and what it covers" page rather than a problem.
b) **A pool-drawn problem** at conceptual depth (intent = teach, assumed
   background minimal) for the node's primary subtopic.
c) **A Claude-generated concept brief** (new LLM call) — discouraged unless
   (a) and (b) are insufficient.

Default recommendation pending decision: (b) — reuse the problem pool, since
the curriculum curator and subtopic tagging already make this cheap. (a)
remains a fallback for nodes with no eligible pool content.

**Decide before Step 4.**

### D5 — Bookmark → interest promotion trigger (still open)

Drift S8 asks for a forward path from bookmarked nodes to active interests.
The add-interest flow specified in Section 2 of the survey design doc is the
mechanism, but the *trigger* — what user action invokes it for a bookmarked
node — is not specified. Options:

a) **Explicit "Add to my interests" button** on the bookmark, which invokes
   the add-interest flow with the node pre-filled.
b) **Automatic promotion** after N engagements with the bookmarked node.
c) **A "Ready to explore?" prompt** surfaced in the queue after a week.

Default recommendation pending decision: (a) — explicit, consistent with
"the system curates, but the user trusts" (the user remains in charge of
what becomes a permanent interest). (c) is a possible enhancement once (a)
exists.

**Decide before Step 5.**

---

## Steps

### Step 1 — Survey redesign scoping ✅ DONE

*No code.* User produced three design docs:

- [survey-and-difficulty-design.md](../survey-and-difficulty-design.md)
- [curriculum-curator-design.md](../curriculum-curator-design.md)
- [persona-1-walkthrough.md](../persona-1-walkthrough.md)

D1 (survey step order), D2 (skill-tree exploration step placement), and D4
(mode balance post-survey location → profile page, per Section 6) are
resolved by these docs.

---

### Step 2 — Survey + add-interest flow + schema additions

Implement the seven-stage survey
([survey-and-difficulty-design.md §1](../survey-and-difficulty-design.md)),
the add-interest flow
([survey-and-difficulty-design.md §2](../survey-and-difficulty-design.md)),
the difficulty/intent/assumed-background generation discipline
([survey-and-difficulty-design.md §3](../survey-and-difficulty-design.md)),
and the schema additions
([survey-and-difficulty-design.md §8](../survey-and-difficulty-design.md)).
Also stand up the profile page surface for mode balance and high-level
feedback (Section 6).

This step is substantial — likely 3–5 sub-sessions. Sub-steps:

#### 2a — Schema migration

A single migration adding:

- `user_interests.intent_context TEXT NOT NULL` (with backfill default
  `''` for existing rows; the column is required going forward).
- `queue_items.state` enum: add `'deferred'`.
- `attempts.requested_assume_less BOOLEAN DEFAULT FALSE`.

No structural changes to `surveys`, `user_node_states`, or `problems` —
existing fields (`comfort_responses_json`, `tags`) are now populated where
they weren't before but the columns are already present.

Files: new migration in `supabase/migrations/`.

#### 2b — Add-interest flow on the API side

Rewrite `api/routes/add_interest.py` (and supporting prompts) to implement
the dialog specified in Section 2:

- Step 2 — Haiku parse: topic(s) + specificity + implicit intent dial.
  Multi-interest splitting per the megagraph reference. Returns either a
  specific or ambiguous branch and a proposed `intent_context` string.
- Step 3 — branch on specificity: specific → mirror-back + optional
  follow-up; ambiguous → mirror-back + path options.
- Step 4 — resolve and preview: name a concrete starter item.
- Per-interest `user_interests` row written with `intent_context` populated.
- Concept tour data: surface 6–10 subtopic-level tiles drawn from prereq
  edges; each tile carries a node/subtopic key the client can post back as
  state.

This API powers both the onboarding survey (Stage 4–5) and the
post-onboarding panel/modal triggered from the daily-tab input box or the
skill tree.

Files: `api/routes/add_interest.py`, new prompts in `api/prompts/`,
`api/schemas.py`.

#### 2c — Onboarding survey UI (the seven stages)

Rewrite the survey flow under `web/app/survey/` and `web/components/`:

- **Stage 1 (Background page):** domain chips + relationship cards +
  optional short text. Single page.
- **Stage 2 (Foundation tiles):** tappable grid grouped by domain. Two-state
  toggle (unmarked / refresh). Tile label framing adapts to the relationship
  card from Stage 1.
- **Stage 3 (Interest suggestions):** 6–10 megagraph-sourced suggestion
  tiles + "anything else?" free-text input.
- **Stage 4 (Add-interest dialog):** invokes the add-interest API for each
  selected interest in sequence (or batched where the parse returns
  related-but-distinct).
- **Stage 5 (Concept tour):** per-interest three-state self-report
  (Familiar / Refresh / New to me). Deduplicated across sequential tours.
- **Stage 6 (Mode balance):** single slider, optional, pre-set on strong
  signals.
- **Stage 7 (Confirmation):** rendered megagraph slice with tappable nodes.
  Interest nodes have Delete and Edit actions; foundation nodes are
  read-only.

`/api/survey/route.ts` now writes:
- `surveys` row with `comfort_responses_json` populated from Stage 5
- `user_interests` rows (via Stage 4 add-interest API) with `intent_context`
- `user_node_states` rows from Stage 2 tile marks and Stage 5 concept tour
- `surveys.mode_balance` from Stage 6

Files: `web/app/survey/page.tsx`, `web/components/SurveyForm.tsx` (likely
broken up into stage components), `web/app/api/survey/route.ts`.

#### 2d — Post-onboarding add-interest UI

Wire the same add-interest flow as a panel/modal triggered from:

- The "Curious about something specific?" input box on the daily tab
  (Section 2.7 — three cases: new topic, existing topic one-off, concept
  request).
- The skill-tree node panel's "add to interests" action (existing affordance,
  now routed through the dialog rather than direct insertion).

Files: `web/components/DailyView.tsx`, `web/components/NodePanel.tsx`, new
add-interest panel component.

#### 2e — Profile page (initial surface)

Implement the profile page per Section 6. Initial scope:

- Mode balance slider (writes to the appropriate field — see implementation
  decision below).
- High-level feedback prompts: "too hard", "assume less", "more papers",
  "harder problems". These write to a new `user_preferences` table or to
  text columns on `user_interests` — pick the simpler option at implementation
  time. The mechanic is: feedback adjusts generator instructions for the
  relevant interests next time content is generated.
- Interest list with delete (mirrors the Stage 7 confirmation panel).
- Foundation node state list (read-only view).

Files: new `web/app/profile/page.tsx`, supporting components.

#### 2f — Problem generation: three-dial discipline + subtopic tagging

Update `api/prompts/problem.py` and `api/routes/generate_problem.py` to:

- Accept and act on `intent` (teach / refresh / consolidate) as a separate
  parameter from difficulty.
- Pass `intent_context` from `user_interests` and current `user_node_states`
  for the relevant nodes into the prompt as the assumed-background frame.
- Apply the entry-point default (Section 3.4): first problem on a new
  interest is conceptual entrance, regardless of stated background.
- Enforce the practical generation test (Section 3.6) in the prompt.
- Require subtopic-level tags in addition to topic tags (Section 3.7 + 8.4).
  Update the schema/return shape to enforce non-empty `tags` containing both
  the primary topic and at least one subtopic.

Files: `api/prompts/problem.py`, `api/routes/generate_problem.py`,
`api/schemas.py`.

#### 2g — "Not ready yet" action

Add the per-problem "not ready yet — come back later" action on the problem
page. On submission:

- `queue_items.state` for the linked queue item transitions to `'deferred'`.
- A signal is sent to `/assess-engagement` (see Step 3) with
  `not_ready_deferred: true`.
- The deferred item is held back; the curator will re-queue it via
  `/check-deferred` (Step 3) once prerequisites are addressed.

Files: `web/app/problem/[id]/page.tsx`, `web/app/api/...` (likely a new
route or extension of an existing one).

---

**Step 2 acceptance:**

- A new user completes the seven-stage survey end-to-end and lands on the
  daily view with a populated queue.
- The "Curious about something specific?" input on the daily tab invokes the
  dialog and adds an interest (or queues a one-off) correctly.
- Every new `user_interests` row has `intent_context` populated.
- Every new problem has subtopic tags in `problems.tags`.
- The profile page exists and the mode balance slider persists.

**Drift report reconciliation:** #7, #8, #9 → `done`. Note that the
resolution is far more comprehensive than the original drift descriptions
implied (the original entries described adding a textarea step, a
skill-tree-style step 2, and a confirmation screen — the actual
implementation rewrites the survey entirely as a seven-stage flow). The
drift items remain valid signals of the gap; the fix is the new design.

---

### Step 3 — Curriculum curator

Implement the LLM-driven queue intelligence per
[curriculum-curator-design.md](../curriculum-curator-design.md). This step
replaces the previous `/update-queue` design with the two-call architecture:
Sonnet for daily planning, Haiku for post-engagement assessment, plus a
deterministic `/check-deferred` for conditional re-queue.

#### 3a — `/assess-engagement` (Haiku)

New endpoint in `api/routes/assess_engagement.py`. Called after every
graded attempt or completed paper engagement.

Input/output shapes as specified in
[curriculum-curator-design.md §5.2](../curriculum-curator-design.md).
Updates `user_node_states` (struggle_score, state, last_engaged_at,
engagement_count) and executes the recommended `immediate_action`
(`queue_reinforcement`, `accelerate`, `surface_prerequisite`, or `null`).
Logs the call to `llm_calls`.

Wire calls to this endpoint from:
- `api/routes/grade_solution.py` (after grading an attempt)
- The paper engagement completion path (probably in `api/routes/` — confirm
  during implementation)

#### 3b — `/plan-queue` (Sonnet)

New endpoint in `api/routes/plan_queue.py`. Called once per active user per
day from a background job.

Input/output shapes as specified in
[curriculum-curator-design.md §4.2](../curriculum-curator-design.md).
Receives full user context (interests, foundation states, prerequisite
edges, recent engagement, queue state, feedback signals). Returns
recommendations (`add`, `reprioritise`). Executes recommendations:

- For `add`: queries the problem pool for a match on
  `(interest_node, subtopic, intent)`; if a match exists, creates a
  `queue_items` row pointing to it; otherwise triggers
  `/generate-problem` with the recommendation as the generation brief.
- For `reprioritise`: updates `priority_score` on the existing row.

Populates `queue_items.added_reason` from the recommendation `reason` field
(the curator's "why this" string is the source for daily-card copy).

#### 3c — `/check-deferred` (deterministic)

New endpoint in `api/routes/check_deferred.py`. Runs daily after
`/plan-queue`. No LLM call.

For each `queue_items` row with `state = 'deferred'`, checks the megagraph's
prerequisite edges from the problem's `topic_node_id`: are the blocking
prerequisites addressed? A prerequisite is "addressed" when its
`user_node_states.state = 'comfortable'` or `struggle_score < 0.3` with
`engagement_count >= 2`
([curriculum-curator-design.md §8](../curriculum-curator-design.md)). If so,
the deferred item transitions back to `state = 'pending'` with a refreshed
priority.

#### 3d — Daily background job

A scheduled job that, for each active user (any user with engagement in the
past 14 days), calls `/plan-queue` followed by `/check-deferred`. Cold-start
case: a brand-new user from Step 2's survey gets an immediate `/plan-queue`
call rather than waiting for the next scheduled run.

Implementation: simplest mechanism that fits the deployment — Vercel cron,
Railway/Fly cron, or a `pg_cron` job invoking the FastAPI endpoint. Pick
during implementation.

#### 3e — Reroll signal capture

`POST /api/queue/reroll/route.ts` must persist the reroll event (which item
was passed over, which mode, which interest) so that future `/plan-queue`
calls can observe reroll patterns via `surfaced_picks`. Ensure
`surfaced_picks` rows are written on every reroll with `chosen_item_id =
null` for passed-over items
([curriculum-curator-design.md §16](../curriculum-curator-design.md)).

This subsumes drift #4: the data side of reroll feedback is implemented
here; the curator consumes it on the next daily plan.

#### 3f — Deprecate `/update-queue`

Once `/plan-queue`, `/assess-engagement`, and `/check-deferred` are
implemented and wired:

- Remove call sites of `/update-queue` from the Next.js app and FastAPI.
- Mark `api/routes/update_queue.py` as deprecated (delete after a session of
  verification that nothing still references it).
- Update `ARCHITECTURE.md` if it still names `/update-queue` as authoritative.

---

**Step 3 acceptance:**

- A new attempt grading triggers `/assess-engagement` and updates
  `user_node_states`.
- The daily job runs end-to-end and produces queue changes visible on the
  daily tab.
- A deferred item is re-queued automatically once its prerequisites meet the
  threshold.
- `surfaced_picks` rows record both chosen and passed-over items.
- `/update-queue` has no remaining callers.

**Drift report reconciliation:** #4 (reroll feedback) → `done`; new entries
may be added for any gaps surfaced during curator implementation.

---

### Step 4 — Queue UX + behavior

Spec-correct fixes that complement the curator but don't depend on it being
fully wired. Decide D3 before implementing concept_review.

- **#3** Implement `concept_review` queue items per D3 (see Open
  Decisions). The queue card links to a page (or modal) that renders the
  node's content. Update `web/app/daily/page.tsx` and add the concept review
  route/component. Reuse the problem pool by default (D3 option b); fall
  back to node description + subtopics (D3 option a) when no pool match
  exists.
- **#5** Paper request flow: when `POST /api/queue/request` receives
  `kind_hint='paper'` and `/suggest-papers` returns nothing, automatically
  call `/propose-papers` to expand the pool, then re-run `/suggest-papers`.
  The user should never see "check back soon" for a paper request on a
  topic the system knows about.
- **#39** Non-blocking queue requests: "Get a problem" and "Request a
  paper" currently block the UI for the duration of the LLM call. Change to
  fire-and-forget: kick off the API call, immediately return a confirmation
  ("Added to your queue — it'll be ready soon."), and let the item appear on
  next page load or queue refresh. If the item is already available (fast
  cache hit / paper already in pool), offer a "Go to it now →" link in the
  confirmation. Applies to `NodePanel` and the daily-tab input.
- Copy/tone: tighten queue card text and empty-state messages per the tone
  guidelines in
  [survey-and-difficulty-design.md §5](../survey-and-difficulty-design.md).

Files: `web/components/DailyView.tsx`, `web/components/NodePanel.tsx`,
`web/app/api/queue/request/route.ts`, `api/routes/propose_papers.py`, new
concept-review route/component.

**Drift report reconciliation:** #3, #5, #39 → `done`. (S10 mode balance
post-survey is resolved in Step 2e — the profile page is its home.)

---

### Step 5 — Spirit gaps: engagement quality

Resolve D5 before implementing S8.

- **S1** `web/app/paper/[id]/page.tsx`: when a user returns to an in-progress
  engagement, show progress state prominently — "Question 2 of 4" with a
  visual indicator of which questions are answered and which remain. Source
  from `paper_engagements.current_question_index` and `paper_answers` count.
- **S2/S3** Orienting concepts: render `context_hooks` /
  `orienting_concepts_json` as interactive named terms rather than flat
  text. Clicking a term expands a brief definition and offers "get a
  refresher on this" — which queues a `refresher` or `concept_review` item
  for that foundation node before the user starts the paper. This is the
  same mechanic as Section 2.7 Case 3 and Section 7 of the survey design
  doc.
- **S4** Cross-pollination suggestions in the queue must include anonymous
  social framing: "Someone studying adjacent topics recently explored this."
  The card copy for `kind='suggested_interest'` items should convey this
  without identifying anyone.
- **S8** Bookmarks: implement the forward path per D5. The default
  recommendation is an explicit "Add to my interests" action that invokes
  the add-interest flow (the same one used everywhere else) with the node
  pre-filled.
- **S9** Audit the notebook's place in the navigation hierarchy. The
  notebook is described in personas as "the lasting treasured artefact"; it
  should be reachable within one tap from the daily view. Promote it if it
  is currently secondary. Consider a subtle notebook entry count or recent
  activity indicator in the nav link.

Files: `web/app/paper/[id]/page.tsx`, `web/components/PaperView.tsx`,
`web/app/notebook/page.tsx`, `web/components/DailyView.tsx`,
`web/app/layout.tsx`.

**Drift report reconciliation:** S1, S2, S3, S4, S8, S9 → `done`.

---

### Step 6 — Skill tree: interaction completeness

- **#12** Edge click: clicking an edge in `SkillTreeView` should open a
  small tooltip or side panel showing the relationship type (prerequisite vs
  related) and a one-line description. Source from `edges.edge_kind` and the
  node titles.
- **#13** "What's nearby?" affordance: add a control that expands the
  visible region to show nodes two hops away from the user's active
  interests. The `/api/graph/me` route may need a `depth` parameter.
- **Survey-design §7** Per-subtopic refresh action in the node panel. For
  each subtopic listed in a foundation node's panel:
  - Show the subtopic name and one-line description.
  - Show the current state (familiar / refresh / unseen), if known.
  - Offer a "request a refresher" action. Tapping it triggers the Case 3
    mechanic from Section 2.7: queries the problem pool for a
    subtopic-tagged problem and queues it. Reuses the queue request /
    fire-and-forget plumbing from Step 4 (#39).

Files: `web/components/SkillTreeView.tsx`, `web/app/api/graph/me/route.ts`,
`web/components/NodePanel.tsx`.

**Drift report reconciliation:** #12, #13 → `done`. (Survey design §7 is
not a separate drift item but is satisfied here.)

---

### Step 7 — Mobile polish

- Audit queue (`/daily`), notebook, problem, and profile views on a narrow
  (375px) viewport. Fix touch targets, overflow, and spacing.
- Skill tree (`/skill-tree`) is desktop-only. Add a friendly fallback for
  narrow screens.
- Test the problem submission flow (camera → upload → parse → review →
  submit) on mobile.
- Test the new seven-stage survey on mobile end-to-end. The Stage 7
  confirmation (megagraph render) may need a simplified mobile rendering.

Files: `web/components/DailyView.tsx`, `web/app/notebook/page.tsx`,
`web/app/problem/[id]/page.tsx`, `web/app/skill-tree/page.tsx`, survey
components.

---

### Step 8 — Error monitoring + final hardening

- Add Sentry (or equivalent) to the Next.js app (`@sentry/nextjs`) and the
  FastAPI service (`sentry-sdk`). Instrument uncaught exceptions and API
  errors. Set up a project in Sentry; store the DSN in env vars.
- Final walkthrough against the Persona 1 four-week walkthrough document.
  Read for anything obviously broken or missing; defer cosmetic items.
- Update `docs/pivot-plan.md` status line:
  `Phase 10-rev complete. v2 ready for friends.`

---

## Drift report reconciliation summary

| # | Status after Phase 10-rev | Resolved by |
|---|---|---|
| #3 concept_review | done | Step 4 |
| #4 reroll feedback | done | Step 3e |
| #5 paper request flow | done | Step 4 |
| #7 comfort calibration | done | Step 2 (subsumed by concept tour, Stage 5) |
| #8 skill-tree exploration step | done | Step 2 (subsumed by foundation tiles + interest suggestions + Stage 7 megagraph confirmation) |
| #9 post-submission confirmation | done | Step 2 (Stage 7 confirmation) |
| #12 edge click | done | Step 6 |
| #13 what's nearby | done | Step 6 |
| #39 non-blocking queue requests | done | Step 4 |
| S1 paper resume progress | done | Step 5 |
| S2/S3 interactive orienting concepts | done | Step 5 |
| S4 cross-pollination social framing | done | Step 5 |
| S8 bookmark forward path | done | Step 5 (pending D5) |
| S9 notebook prominence | done | Step 5 |
| S10 mode balance post-survey | done | Step 2e (profile page) |

Drift items #24–#38 and S11/S12 remain `deferred` from Phase 9-rev triage
and are not in this phase's scope; the Step 8 final walkthrough may
elect to address specific ones inline if cheap.
