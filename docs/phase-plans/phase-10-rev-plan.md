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

#### 2c — Onboarding survey UI (Stages 1, 2, 3, 6, 7) ✅ DONE

The seven-stage survey was wired as five route-segmented pages under
`/survey/<stage>` plus per-stage POST routes under `/api/survey/<stage>`.
Stages 4 and 5 (add-interest dialog + concept tour) were intentionally
stubbed server-side — that work landed under Step 2d below.

Shape:
- Stage 1 went through a mid-session redesign after testing surfaced that
  global domain chips + a single global relationship card was too coarse
  (users came out with similar-feeling queues). Stage 1 now carries
  per-domain detail: each picked domain gets its own sub-area chip block
  and its own relationship card. See
  [survey-and-difficulty-design.md §1.2](../survey-and-difficulty-design.md)
  for the spec and [web/lib/surveyDomains.ts](../../web/lib/surveyDomains.ts)
  for the canonical chip vocabulary.
- Stage 2 tile label framing is now keyed per-db-domain off the Stage 1
  relationship card (math tiles can read one way while physics tiles read
  another).
- Stage 3 suggestions use a heuristic shortlist (domain filter + prereq
  overlap with marked foundations + sub-area token overlap, scoring
  `2 × prereq + subarea`) then Haiku rerank with the full per-domain
  context surfaced verbatim in the prompt.
- Stage 7 confirmation reuses `SkillTreeView` with an injected legend and
  a survey-specific node panel (Delete on interests works; Edit is stubbed
  with a 2d marker).
- Route-per-stage shell gates the user back to the earliest incomplete
  stage on reload via `surveys.completed_stages`.

Schema: one additive migration ([`20250019_phase10_survey_v2_shape.sql`](../../supabase/migrations/20250019_phase10_survey_v2_shape.sql))
added `surveys.background_json`, `surveys.completed_stages`,
`surveys.pending_interests_json`. JSONB shape for background:
`{domains: [{key, subareas, relationship}]}`.

Stage 4 + 5 stub: [/api/survey/interests](../../web/app/api/survey/interests/route.ts)
runs `parseAddInterest` + `resolveAddInterest` server-side, best-guess
per segment, ignoring the concept tour data. Marked `TODO(2d)`.

Admin reset: `POST /api/survey/reset` (admin-gated via
`ADMIN_EMAIL`) wipes the user's survey + interests + node states + queue
items so the seven-stage flow can be re-walked from scratch. A small
"Restart (admin)" button is rendered in the survey layout and on the
`/survey` redirector when the user is signed in as the admin.

UX details polished mid-session:
- Stage 1 sub-area copy clarified ("anything you've studied, encounter at
  work, or are curious about").
- Stage 2 copy clarified what "unmarked" means ("not a judgement, not a
  commitment").
- Stage 6 slider redesigned: radix track + thumb (no `Range` fill) so the
  position reads as a single dot; label shows the majority side
  ("60% problems" / "Even split" / "60% papers") rather than always
  reporting papers %.
- Stage 7 legend simplified from six categories to two ("Your interests &
  foundations to refresh" / "Nearby"); interest user_nodes are
  synthetically given `state: "active"` so they visually unify with
  marked foundations.

Cross-pollination path (`/api/interest` POST with
`added_via=cross_pollination`) was updated to write `intent_context`
(canned: "Surfaced via cross-pollination from adjacent interests") so the
NOT NULL constraint added in 20250018 stops biting that path.

Known gap (intentionally deferred): no problem queue items are generated
post-survey — the deleted v1 `/api/survey/route.ts` used to seed 2
problems via `generateProblem` but the route was removed in this step.
Paper engagement queue items still populate via `suggestPapers` +
`proposePapers`. Problem seeding belongs to the curriculum curator in
Step 3; not worth restoring a placeholder.

Files shipped: 1 migration, 1 Python route + prompt + schema additions,
9 web pages/components under `web/app/survey/` and `web/components/survey/`,
6 web API routes under `web/app/api/survey/`, a `surveyDomains.ts` /
`surveyState.ts` helper pair, and a small `SkillTreeView` change adding an
optional `legend` prop.

#### 2d — Add-interest dialog UI (Stage 4 + Stage 5 + post-onboarding) ✅ DONE

The real add-interest dialog UI (parse → mirror-back / path picks → resolve)
and concept-tour UI shipped and were wired to every surface that needed them.

Shape:
- Reusable suite at [web/components/addInterest/](../../web/components/addInterest/):
  `Dialog.tsx` (one segment, state machine `gathering → resolving → resolved`),
  `ConceptTour.tsx` (3-state self-report + skip-tour + skip-remaining-tours
  affordances), `DialogModal.tsx` (shadcn Dialog wrapper for post-onboarding
  use), `types.ts`. Dialog supports two input modes: `source="segment"` from
  /parse, or `source="preNode"` for callers that already know the node and
  want to skip /parse (NodePanel Add, SurveyNodePanel Edit).
- Parse schema gained `kind: "interest" | "concept"` so §2.7 Case 3
  (concept-level requests like "remind me what eigenvectors are") can be
  routed without creating a new node. Haiku prompt updated to set it.
- `STAGE_ORDER` in [web/lib/surveyState.ts](../../web/lib/surveyState.ts)
  now includes `dialog` between `interests` and `balance` (label "Explore"
  in the progress chip).
- Stage 4 + 5 host: new `/survey/dialog` route with a `DialogOrchestrator`
  client component that walks each pending interest through Dialog → ConceptTour
  interleaved, with cross-tour subtopic-key dedup per §1.6.5. The "Skip
  remaining tours" button surfaces after the second tour completes.
- Stage 3 page now redirects to `/survey/dialog` (was `/survey/balance`); the
  old `/api/survey/interests` stub is trimmed to "save pending + advance gate".
- Three new thin API routes:
  - [/api/add-interest/parse](../../web/app/api/add-interest/parse/route.ts)
  - [/api/add-interest/resolve](../../web/app/api/add-interest/resolve/route.ts)
  - [/api/add-interest/concept-tour](../../web/app/api/add-interest/concept-tour/route.ts) —
    writes `user_node_states` (precedence-bumped, never downgrades comfort)
    and merges into `surveys.comfort_responses_json` keyed by
    `<node_slug>:<subtopic_key>`.
- Plus [/api/survey/dialog/complete](../../web/app/api/survey/dialog/complete/route.ts)
  (clears `pending_interests_json` + marks `dialog` stage done) and
  [/api/interest/me](../../web/app/api/interest/me/route.ts) (slug-or-id lookup
  used by SurveyNodePanel Edit pre-fill and RequestBox Case 1/2 detection).

Post-onboarding integrations:
- [RequestBox](../../web/components/RequestBox.tsx) on the daily tab now runs
  the §2.7 three-case router: `kind="concept"` queues a focused problem on
  the matched node without persisting interest; matched-and-already-an-interest
  queues one-off; otherwise surfaces a Case 1 panel with "Add it" (opens the
  full dialog modal + concept tour) or "Just this once" (queues without
  persisting). The latter required a new `skip_interest_add` flag on
  `/api/queue/request`.
- [NodePanel "Add to my interests"](../../web/components/NodePanel.tsx) opens
  the modal pre-filled with the node title and a "What draws you to this?"
  followup; resolves with `existing_node_slug` set.
- [SurveyNodePanel Edit](../../web/components/survey/SurveyNodePanel.tsx)
  opens the modal pre-filled with the current intent_context and a "What's
  off, or what would you change?" followup.

Cleanup:
- The `addInterest` shim is gone from [web/lib/pythonApi.ts](../../web/lib/pythonApi.ts).
  Headless callers now go through a small inline `headlessResolveToNode`
  helper in `/api/queue/request/route.ts` that calls /parse + /resolve with
  auto-confirm on `draft_intent_context`.
- [/api/interest](../../web/app/api/interest/route.ts) POST is now
  cross-pollination-only. The standard raw-text path is explicitly rejected
  with a 400 directing callers to /parse + /resolve.

Known gaps (deferred):
- Case 3 (`kind="concept"`) currently queues a regular problem on the matched
  node; the spec calls for a "brief orienting explanation + focused problem"
  and concept-level pool tagging will need its own pass (Step 2f handles
  subtopic tagging; the orienting explanation is a follow-on).
- `user_node_states` updates only the parent foundation node from the concept
  tour (we have no subtopic-level state column). Strongest signal across
  subtopics wins.

Files shipped:
- Python: `api/schemas.py` (kind field), `api/prompts/add_interest.py` (Haiku
  prompt update).
- Web: 4 new components under `web/components/addInterest/`; new
  `web/components/survey/DialogOrchestrator.tsx`; updates to RequestBox,
  NodePanel, SurveyNodePanel, ConfirmGraph (onEdited callback), InterestSuggestions
  (Stage 3 redirect), SurveyProgress (6-stage). 5 new API routes + 3 modified
  (`/api/survey/interests` shrunk, `/api/interest` cross-pollination only,
  `/api/queue/request` uses inline headless resolve).

#### 2e — Profile page ✅ DONE

A new `/profile` route surfaces the four sections in Section 6: mode balance,
high-level feedback, interest management, foundation state.

Shape:
- Mode balance section uses a new shared
  [`ModeBalanceControl`](../../web/components/ModeBalanceControl.tsx)
  (the visual core extracted from `ModeBalanceSlider`) wrapped in a
  debounced auto-save section — drag the slider, value persists after a
  short delay via the existing `POST /api/survey/balance` route. The survey
  Stage 6 still uses `ModeBalanceSlider` with its Back/Continue chrome.
- High-level feedback section: four toggle chips (`feedback_too_hard`,
  `feedback_assume_less`, `feedback_more_papers`, `feedback_harder_problems`)
  hitting `POST /api/profile/feedback`. Storage uses a new `user_preferences`
  table (`user_id`, `key`, `value`, `updated_at` PK on `(user_id, key)`,
  RLS-gated) so Step 3's curator can extend without further migrations.
  Migration: [`20250020_user_preferences.sql`](../../supabase/migrations/20250020_user_preferences.sql).
- Interest section: each row expands to show the user's engagement count,
  a link to the skill tree, and the active queue items currently linked to
  that interest's node (problems only — `queue_items` JOIN `problems` on
  `topic_node_id`). Edit opens the same `DialogModal` SurveyNodePanel uses,
  in `preNode` mode pre-filled with current intent_context. Delete posts to
  the existing `DELETE /api/interest/[node_id]`.
- "Rewrite summaries" button: the older /parse prompt produced tag-soup
  `intent_context` values ("teach intent, X foundations") that read poorly
  on the profile. A new `POST /add-interest/rewrite-summaries` (Haiku batch)
  rewrites them into descriptive "Topic Name: what it covers" prose,
  grounded in `node.description_md` + `subtopics_json` and tilted by the
  user's existing intent_context when it carries a real angle. The parse
  prompt itself was also updated to emit prose-form draft_intent_context
  for new interests going forward (forbidden openings: "Wants to learn",
  "The user wants", etc.).
- Foundation state section: read-only list of all foundation nodes with
  their `user_node_states.state` (defaulting to `unseen`). State badge
  colors follow the design tokens (forest = comfortable, amber = active,
  destructive-subtle = struggling).
- Nav: fourth top-level link `Daily / Notebook / Skill Tree / Profile` in
  `web/app/layout.tsx`.

Files shipped: 1 migration, 1 Python prompt builder + schema additions +
endpoint, 1 web Python proxy + new orchestration route, 1 new web feedback
route, 1 new profile page + ProfileView component, 1 shared
ModeBalanceControl, edits to ModeBalanceSlider + layout.

Known gap (deferred): paper engagement queue items don't currently carry a
`topic_node_id` (papers tie to nodes only via orienting_concepts text), so
they aren't grouped under interests in the expand view. The current scope
shows problems only.

#### 2f — Problem generation: three-dial discipline + subtopic tagging ✅ DONE

`api/prompts/problem.py` rewritten end-to-end. The system prompt now spells
out difficulty / assumed background / intent as INDEPENDENT dials, with
the entry-point default (§3.4 — conceptual entrance regardless of stated
background on the user's first problem on a topic) and the practical
generation test (§3.6 — "could a user with only the confirmed background
work through this?") encoded as load-bearing instructions. Subtopic tagging
(§3.7) is required with example slugs in the prompt.

`api/routes/generate_problem.py` refactored with four new helpers:
- `derive_intent(supabase, user_id, node_id)` — string-matches
  `user_interests.intent_context` (consolidate > refresh > teach). Per the
  locked decision, engagement state does NOT override intent_context;
  adaptive intent lives in Step 3's /plan-queue.
- `is_entry_point(supabase, user_id, topic_node_id)` — queries `attempts`
  first (most users with no engagement short-circuit), then narrows to
  topic-matching problems via `in_("id", attempt_problem_ids)`.
- `derive_assumed_background_summary(supabase, user_id, topic_node_id,
  topic_slug)` — builds a narrative paragraph from `user_node_states` for
  the topic + its direct prerequisites (via `edges` table) plus
  subtopic-level signals from `surveys.comfort_responses_json`.
- `derive_feedback_biases(supabase, user_id)` — reads `user_preferences`
  for the four `feedback_*` keys.

Pipeline: cache lookup extended to include `intent` in the key — new
migration [`20250021_problems_intent.sql`](../../supabase/migrations/20250021_problems_intent.sql)
adds `problems.intent text` with a CHECK constraint and rewrites the two
partial unique indexes to include intent (`(topic, difficulty, hook, intent)`
WHERE-clause keeps the legacy null-intent rows distinct from non-null
intent rows).

Schema: `GenerateProblemRequest.intent` and `feedback_bias` are now
optional fields; when omitted the route derives them. `GeneratedProblem.tags`
is now required with `min_length=2` (pydantic) and additionally validated
in-route to contain the topic slug.

Tests: 8 new cases in `api/tests/test_generate_problem.py` covering tag
persistence, invalid tags, entry-point default, prior-attempts means no
entry-point, intent derived from intent_context, body intent overrides
context, invalid intent → 400, feedback biases in prompt, intent in cache
key. Existing tests updated for required `slug` + `tags`. Full suite:
134/134 passing.

Files shipped: 1 migration, `api/prompts/problem.py` (rewrite),
`api/routes/generate_problem.py` (helpers + pipeline), `api/schemas.py`,
`api/tests/test_generate_problem.py` (+ cache_lookup tests).

Nothing in `web/` changed for 2f.

#### 2g — "Not ready yet" action ✅ DONE

A per-problem deferral action available on Step 1 (before the user starts
working). One tap, silent transition, back to `/daily`.

Migration: [`20250022_queue_items_deferred_at.sql`](../../supabase/migrations/20250022_queue_items_deferred_at.sql)
adds `queue_items.deferred_at timestamptz` as the authoritative timestamp
Step 3's /check-deferred will read (separate from `updated_at` which gets
overwritten on every state change). The `'deferred'` enum value was added
back in `20250018`.

New endpoint: [`web/app/api/problem/[id]/defer/route.ts`](../../web/app/api/problem/[id]/defer/route.ts).
Modeled on the skip route but distinct: no `attempts` row is written, no
`user_node_states` mutation. Only accepts transitions from `pending` or
`surfaced` (returns 409 otherwise — defer is only valid before starting).
Updates state → `deferred`, stamps `deferred_at` and `updated_at`.

UI: `web/components/ProblemView.tsx` Step1View gets a third button between
Skip and Start working. Forest-toned outline ("Not ready yet — come back
later") matches the quieter / reading-side register.

Cross-cutting state filtering:
- `web/lib/types.ts` `QueueItemState` extended with `'deferred'`.
- `web/app/problem/[id]/page.tsx` redirect now excludes deferred items.
- `web/lib/queueHelpers.ts` open-pick filter excludes deferred items (so
  if a surfaced item was deferred, the daily card list re-hydrates without
  it). Python `/surface-daily` only picks `state='pending'` so deferred
  items are excluded from fresh picks by construction.

Note on the original plan note "a signal is sent to /assess-engagement
with not_ready_deferred: true" — implementation chose a different design:
the state transition + `deferred_at` timestamp IS the signal. Step 3's
/check-deferred reads `queue_items WHERE state='deferred'` directly;
/assess-engagement is for engagements, defer is a non-engagement. This is
the locked decision from the 2g plan (silent defer, no reason field).

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

#### 3a — `/assess-engagement` (Haiku) ✅ DONE

Endpoint lives in `api/routes/curator.py` (three routes consolidated into
one router since they share helpers + prompts). Called after every graded
attempt or completed paper engagement.

Input/output shapes match
[curriculum-curator-design.md §5.2](../curriculum-curator-design.md).
Updates `user_node_states` (struggle_score, state, last_engaged_at,
engagement_count) and executes `immediate_action`
(`queue_reinforcement`, `accelerate`, `surface_prerequisite`, or `null`).
Logs the call to `llm_calls`.

Wired into:
- `api/routes/grade_solution.py:135` (after notebook entry write)
- `api/routes/grade_paper_answer.py:147` (when `is_last` triggers state='completed')

Both hooks are best-effort: any exception is logged and swallowed so the
user's grade response is never blocked.

The four `derive_*` helpers from `generate_problem.py` (Step 2f) plus three
new `load_engagement_signals_*` and `load_node_state` helpers are now
consolidated in `api/curator_inputs.py` so all three curator routes (and
the generator) share one source. Paper-engagement assessments run the
Haiku call for logging but skip `user_node_states` writes because
`paper_engagements` does not carry a `topic_node_id` in v2 schema.

#### 3b — `/plan-queue` (Sonnet) ✅ DONE

Endpoint in `api/routes/curator.py` (same router as 3a). Designed to run
once per active user per day from the background job (3d).

Input shape per
[curriculum-curator-design.md §4.2](../curriculum-curator-design.md) is
built by `build_curator_context()` in `api/curator_inputs.py`. Returns
recommendations (`add`, `reprioritise`). Execution:

- For `add` with `kind='problem'`: pool lookup on
  `(topic_node_id, intent, difficulty, tags @> [subtopic])`. On hit:
  insert `queue_items` row with the curator's reason + priority. On miss:
  call `/generate-problem` inline, then overwrite the row it wrote with
  the curator's `added_reason` + `priority_score`.
- For `add` with `kind='refresher'`: direct queue insert keyed on the
  resolved node id.
- For `add` with `kind='paper_engagement'`: logged + skipped — paper
  recommendations are produced by `/propose-papers`, not the curator.
- For `reprioritise`: update `priority_score` on `queue_item_id` scoped to
  this user. Curator must echo back UUIDs from
  `recent_engagement.deferred_items[].queue_item_id`.

Duplicate-pending guard: `_queue_item_already_exists` skips adds whose
`(kind, ref_id)` is already pending/surfaced for the user.

`added_reason` flows through from the curator's `reason` field verbatim
— it is the source for daily-card "why this" copy.

#### 3c — `/check-deferred` (deterministic) ✅ DONE

Endpoint in `api/routes/curator.py`. No LLM call.

For each `queue_items` row with `state = 'deferred'`, looks up the
problem's `topic_node_id`, pulls prerequisite edges into that topic, and
checks `user_node_states` for each prereq against the spec §8 threshold:
`state = 'comfortable'` OR `(struggle_score < 0.3 AND engagement_count >= 2)`.
When all prerequisites are addressed, transitions to `state = 'pending'`
with `priority_score = 0.55` (the next `/plan-queue` pass sets a final
priority). `deferred_at` is intentionally preserved for analytics.

Edge cases handled: deferred problem with zero prerequisite edges
re-queues unconditionally; orphaned ref_id rows are kept deferred and
flagged in logs.

#### 3d — Daily background job ✅ DONE (cron deferred to Phase 11-deploy)

The endpoint and cold-start path shipped; the cron schedule is deferred
until the FastAPI service is deployed to a public host.

What landed:
- `/run-daily-planner` endpoint in `api/routes/curator.py` — per-user
  wrapper that calls `run_plan_queue()` then `run_check_deferred()`,
  writes a `curator_job_runs` log row, and treats sub-call failures as
  recorded errors (not 500s) so partial progress survives.
- New `curator_job_runs` table — migration
  [`20250023_curator_job_runs.sql`](../../supabase/migrations/20250023_curator_job_runs.sql)
  (applied). Service-role-only RLS; columns capture both sub-calls'
  counts + status + error_message + finished_at.
- pg_cron schedule — migration
  [`20250024_curator_daily_job.sql`](../../supabase/migrations/20250024_curator_daily_job.sql)
  (NOT applied). Enables `pg_cron` + `pg_net`, schedules `0 7 * * *` UTC
  fan-out, idempotent on `cron.unschedule`. Header documents required
  dashboard prereqs (Vault secret `internal_api_token`, Postgres config
  `app.python_api_url`).
- Cold start: `web/app/api/survey/complete/route.ts` now calls
  `planQueue({userId, triggeredBy: 'cold_start'})` instead of the three
  legacy `updateQueue` + `suggestPapers` + `proposePapers` calls. Stage 7
  confirm triggers a fresh /plan-queue pass within the dev session.
- Cross-pollination accept (`web/app/api/interest/route.ts`) also
  migrated to `planQueue({triggeredBy: 'manual'})`.
- 5 new tests in `api/tests/test_run_daily_planner.py` cover the 401
  plumbing, happy path, plan-queue-fails-but-check-deferred-still-runs,
  and check-deferred-fails-with-plan-queue-counts-preserved cases.

Deferred to Phase 11-deploy: applying 20250024 (the cron schedule),
deploying FastAPI to Fly/Railway, configuring Vault + Postgres config
that the cron needs. Migration file remains on disk as a Phase 11
reference; Sam's manual SQL-editor application workflow means it's not
auto-applied.

#### 3e — Reroll signal capture ✅ DONE

`web/app/api/queue/reroll/route.ts` now writes one `surfaced_picks` row
per passed-over item with `chosen_item_id=null`,
`queue_item_ids=[single_id]`, `surfaced_at`/`replaced_at=now()`. The
top-level pick row continues to get its `replaced_at` stamp as before.
Per-item rows are what
[`api/curator_inputs.py:load_recent_engagement`](../../api/curator_inputs.py)
counts by node for the curator's
`recent_engagement.reroll_patterns` block.

Future-aware: when a "choose one, reroll the rest" UX lands, the chosen
item gets a row with `chosen_item_id=<id>`. For now every reroll path
produces null-chosen rows.

This subsumes drift #4: the data side of reroll feedback is in place;
the curator consumes it on the next daily plan.

#### 3f — Deprecate `/update-queue` ✅ DONE

Handover claimed one call site; four were found:
1. `web/app/api/survey/complete/route.ts` — migrated to `planQueue`.
2. `web/app/api/interest/route.ts` — migrated to `planQueue`.
3. `web/app/api/problem/[id]/submit/route.ts` — deleted
   (redundant with the `/assess-engagement` hook in
   `api/routes/grade_solution.py:135`).
4. `web/app/api/paper/[id]/answer/route.ts` — deleted
   (redundant with the `/assess-engagement` hook in
   `api/routes/grade_paper_answer.py:147`).

Also deleted: `api/routes/update_queue.py`, `api/tests/test_update_queue.py`,
the two `/update-queue` smoke tests in `api/tests/test_surface_daily.py`,
`UpdateQueueRequest`/`UpdateQueueResponse` from `api/schemas.py`,
`updateQueue` export from `web/lib/pythonApi.ts`, `update_queue_router`
import + `include_router` in `api/main.py`, the `/update-queue` row in
`ARCHITECTURE.md`. Stale comment at
`web/app/api/queue/request/route.ts:239` rephrased.

Known deferred (called out in pivot-plan): refresher scheduling from
10-day-old notebook entries into `refresher_schedule`, and pruning of
`queue_items.state in ('done','dismissed')` rows older than 30 days.
The curator can recommend refreshers ad hoc but the systematic
deterministic schedule is gone. Acceptable per spec; Phase 6
cost-dashboard work can pick them up.

Tests after Step 3 close: 153/153 passing
(was 160 pre-Step-3d, net –10 from `test_update_queue.py` deletion +2
removed from `test_surface_daily.py` +5 added to
`test_run_daily_planner.py`).

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
