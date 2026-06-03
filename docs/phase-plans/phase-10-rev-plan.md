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

### D3 — Concept review content source ✅ LOCKED (Step 4 entry)

`queue_items.kind = 'concept_review'` points to `nodes(id)` and surfaces
concept-level material on a node without generating a full problem.

**Locked:** option (b) with fallback to option (a). The
`/concept-review-resolve` route queries the pool at
`(topic_node_id, intent='teach', difficulty=1, tags ⊇ [primary_subtopic])`.
On hit, atomically enqueues a `kind='problem'` row pointing at the pool
problem and marks the original concept_review row `done`. On miss, returns
the node's `description_md` + `subtopics_json` for the client to render as
a serif reading surface (`ConceptReadingView`). Implemented in Step 4.

Option (c) (Claude-generated concept brief) was rejected as cost-additive
without sufficient benefit; the reading surface already covers the miss
path adequately for v2.

### D5 — Bookmark → interest promotion trigger ✅ LOCKED (Step 5 entry)

**Locked:** option (a) — explicit "Promote to interest" button surfaced
prominently on bookmarked nodes (re-styled and hoisted in [NodePanel.tsx](../../web/components/NodePanel.tsx)
when the node is bookmarked-not-yet-interest), invoking the existing
add-interest dialog pre-filled. Consistent with "the system curates, but the
user trusts." Options (b) and (c) rejected as too autonomous for v2 — could
revisit as enhancements later.

### D3 (revisited) — Concept review reading-surface depth ✅ LOCKED (Step 5.5)

Walkthrough surfaced that the bare description_md + subtopic-titles reading
surface (locked at Step 4 entry) was insufficiently informative. The
previously-rejected option (c) — Haiku-generated concept brief — was added
as Step 5.5 (see below), keyed on `node_id` and cached in
`node_concept_briefs` so cost is one-shot per node, shared across users.

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

### Step 4 — Queue UX + behavior ✅ DONE

Spec-correct fixes that complement the curator but don't depend on it being
fully wired. D3 locked at entry (option b with fallback to a).

#### 4a — `concept_review` view (#3) ✅ DONE

New FastAPI route `POST /concept-review-resolve` ([api/routes/concept_review.py](../../api/routes/concept_review.py))
takes `{user_id, queue_item_id}`, verifies ownership + `kind='concept_review'`,
then:
- **Pool hit** (re-using `_pool_lookup_for_recommendation` from
  [api/routes/curator.py:507-530](../../api/routes/curator.py#L507-L530) with
  `difficulty=1, intent='teach', subtopic_slug=subtopics_json[0]?.slug`):
  atomically inserts a `kind='problem'` queue_items row pointing at the
  matched problem and marks the original concept_review row `done`. Returns
  `{kind:'problem', queue_item_id: <new>}`. Client redirects to
  `/problem/<new_id>`.
- **Pool miss**: returns the node payload
  (`description_md`, `subtopics_json`, `title`, `slug`, `id`). Client renders
  [`ConceptReadingView`](../../web/components/ConceptReadingView.tsx) as a
  serif reading surface; "I've looked through this" button POSTs to
  [/api/concept-review/[id]/done](../../web/app/api/concept-review/[id]/done/route.ts).

[`DailyView`](../../web/components/DailyView.tsx) routes `concept_review`
cards to `/concept-review/<queue_item_id>`. [`resolveTitles`](../../web/lib/queueHelpers.ts)
extended to lift node titles for concept_review queue cards.

Schema additions: `ConceptReviewResolveRequest`/`Response` +
`ConceptReviewNodeReading` in [api/schemas.py](../../api/schemas.py); router
registered in [api/main.py](../../api/main.py); web helper
`conceptReviewResolve` in [pythonApi.ts](../../web/lib/pythonApi.ts).

7 new tests in [test_concept_review_resolve.py](../../api/tests/test_concept_review_resolve.py)
(auth, wrong kind, not found, already-done, pool hit, pool miss, null
subtopics).

#### 4b — Paper request fallback (#5) ✅ DONE

[web/app/api/queue/request/route.ts](../../web/app/api/queue/request/route.ts)
paper branch now: `suggestPapers` → DB pick → on miss: `proposePapers` +
`suggestPapers` again → DB pick. `propose-papers` is idempotent (dedups by
title/arxiv_id/doi) so the retry is cheap. Empty fallback message changed
from "check back soon" to "Adding a paper to your queue — it'll appear
shortly."

**Known deploy follow-up:** the full chain can take 30–60s server-side. If
Vercel function timeouts trigger (Hobby=10s, Pro=60s), the fix is to detach
`proposePapers` as `void proposePapers(...)` on first miss and return
immediately — `propose-papers` is fully idempotent. Phase-11-deploy item.

#### 4c — Fire-and-forget UX (#39) ✅ DONE

Installed `sonner@2.0.7`; `<Toaster position="bottom-right" closeButton />`
mounted in [web/app/layout.tsx](../../web/app/layout.tsx).

New helper [web/lib/optimisticQueueRequest.ts](../../web/lib/optimisticQueueRequest.ts):
- Shows a `toast.loading(labels.pending)` immediately.
- Awaits `/api/queue/request` in the background.
- On resolve with `queue_item_id`: upgrades to `toast.success("Ready.", {action: "Go to it now →"})`.
- On resolve with null id: upgrades to `toast.message(labels.queued)`.
- On reject: `toast.error("Couldn't add that — try again.")`.
- Always calls `router.refresh()` on resolution so /daily reloads silently.

Wired into:
- [`NodePanel`](../../web/components/NodePanel.tsx) `handleGetProblem` +
  `handleRequestPaper` — handlers are now sync, with an 800ms button
  debounce to prevent double-click.
- [`RequestBox`](../../web/components/RequestBox.tsx) `queueProblemOnNode`,
  the paper/refresher branch in `handleSubmit`, `handleJustThisOnce`, and
  the dialog `onComplete` callback. Form clears on fire.

#### 4d — Tone pass ✅ DONE

[`DailyView`](../../web/components/DailyView.tsx):
- `KIND_CTA.problem`: "Work on this" → "Try this"
- `KIND_CTA.refresher`: "Practice again" → "Look at this again"
- `KIND_CTA.concept_review`: "Review" → "Read"
- `defaultDescription` tightened across all kinds (e.g. problem →
  "A problem on this topic."; suggested_interest gets the §S4-aligned
  "Someone studying adjacent topics recently explored this." framing).
- `MoreComingCard`: "More items are being prepared — check back soon." →
  "More to come — give it a moment."

#### Step 4 acceptance

- `concept_review` cards on `/daily` link to a working surface (pool hit →
  problem; miss → serif reading page with mark-done).
- Paper requests on an empty pool no longer dead-end — `/propose-papers`
  fires server-side and the queue gains a paper.
- "Get a problem" / "Request a paper" / RequestBox no longer block on the
  LLM call; toast confirms immediately and upgrades to "Go to it now →" on
  fast resolution.
- All queue card copy passes §5 tone re-read.
- `uv run pytest`: 160/160 (was 153 + 7 new).
- `npm run build`: clean.

**Drift report reconciliation:** #3, #5, #39 → `done`. (S10 mode balance
post-survey is resolved in Step 2e — the profile page is its home.)

---

### Step 5 — Spirit gaps: engagement quality ✅ DONE

Resolved D5 (option a — explicit "Promote to interest" CTA on bookmarked
nodes) at entry. Shipped:

- **S1** Resume-progress component [PaperProgress.tsx](../../web/components/PaperProgress.tsx)
  at the top of [PaperView.tsx](../../web/components/PaperView.tsx) when
  `phase !== "intro"`: "Question N of M" + per-question dots
  (forest = answered, amber-ringed = current, muted = remaining). Sourced
  from `current_question_index` + the `answers` map already in client state.

- **S2/S3** Orienting concepts are now interactive. Shape change to
  `paper_engagements.orienting_concepts_json` (`string[]` → `[{term,
  definition_md}]`); prompt rewritten in [paper_engagement.py](../../api/prompts/paper_engagement.py);
  legacy `string[]` rows tolerated (non-interactive chip). New
  [OrientingConceptsPanel.tsx](../../web/components/OrientingConceptsPanel.tsx)
  expands a definition card on click with a "Get a refresher on this" button
  that wraps `optimisticQueueRequest({ raw_text, kind_hint: "refresher" })`.
  `/api/queue/request` refresher branch tightened: when raw_text targets a
  node the user has no notebook history on, falls back to inserting a
  `concept_review` queue item on the resolved node (matches survey-design
  §2.7 Case 3) instead of refreshing an unrelated recent entry. The
  optimisticQueueRequest helper's `targetPath` signature widened to
  `(id, kind)` so callers can route refresher→/problem and
  concept_review→/concept-review correctly.

- **S4** Cross-pollination `added_reason` rewritten in
  [compute_cross_pollination.py](../../api/routes/compute_cross_pollination.py):
  "Someone studying adjacent topics recently explored this." (no LLM on
  this path; literal string update).

- **S8** [NodePanel.tsx](../../web/components/NodePanel.tsx): when a node is
  bookmarked-not-yet-interest, the "Add to my interests" button is hoisted
  to slot 2 (under "Get a problem"), re-styled solid amber, and re-labelled
  "Promote to interest." Unbookmarked non-user nodes keep the original
  outline "Add to my interests" CTA at the bottom of the panel.

- **S9** Root [layout.tsx](../../web/app/layout.tsx) is now async; serves a
  past-7-day notebook entry count next to the link as "Notebook (N)" when
  N > 0 (muted text, no badge chrome — restraint rules).

- **Plus, mid-step incidental fixes:**
  - **Concept-review CTA copy** on the queue card: paper engagements the
    user has started now read "Continue paper →" rather than "Read paper →"
    (in-progress flag computed in [queueHelpers.ts](../../web/lib/queueHelpers.ts)
    from `current_question_index > 0` OR `state === "in_progress"`).
  - **suggest-papers PostgREST escape bug** ([suggest_papers.py](../../api/routes/suggest_papers.py)):
    titles containing `&`, `,`, `(`, `)` were breaking the `or=` logic-tree
    parser. ILIKE values now wrapped in double quotes.
  - **subtopics_json tolerance** in [concept_review.py](../../api/routes/concept_review.py):
    legacy `string[]` subtopics on interest nodes are normalized to
    `[{slug, title}]` dicts before pydantic serialization, preventing a 500
    on any pre-shape-migration node.

Files modified: `api/prompts/paper_engagement.py`, `api/schemas.py`,
`api/routes/compute_cross_pollination.py`,
`api/routes/concept_review.py`, `api/routes/suggest_papers.py`,
`web/lib/types.ts`, `web/lib/queueHelpers.ts`, `web/lib/optimisticQueueRequest.ts`,
`web/app/api/queue/request/route.ts`, `web/app/layout.tsx`,
`web/components/PaperView.tsx`, `web/components/NodePanel.tsx`,
`web/components/DailyView.tsx`, `web/app/notebook/[id]/page.tsx`,
`web/components/survey/SurveyNodePanel.tsx` (entry-kind labels propagation
via NodePanel).
New: `web/components/PaperProgress.tsx`, `web/components/OrientingConceptsPanel.tsx`.
Tests updated: `test_generate_paper_engagement.py`, `test_ingest_paper_user.py`,
`test_propose_papers.py`, `test_suggest_papers.py`, `test_concept_review_resolve.py`.

**Drift report reconciliation:** S1, S2, S3, S4, S8, S9 → `done`.

---

### Step 5.5 — Concept brief generation + lineage + notebook persistence ✅ DONE

Scope addition surfaced during Step 5 walkthrough. Two user-driven follow-ups:

1. **The bare concept reading surface (description_md + subtopic titles only)
   read as uninformative** — D3 option (c) (Claude-generated concept brief),
   rejected at Step 4 entry, was reversed.
2. **The user wanted a way back to the source paper** from a concept review
   triggered by an orienting-concept click, and **a way to revisit the
   concept brief later** via the notebook.

Shipped:

- **Migration [20250025_node_concept_briefs.sql](../../supabase/migrations/20250025_node_concept_briefs.sql)** —
  new `node_concept_briefs` table keyed on `node_id` (PK, FK→nodes),
  storing `brief_md` + `subtopic_glosses_json` ([{slug, title, gloss_md}]) +
  `generated_at` + `generated_by_model`. Service-role-only RLS.
- **New Python route `/generate-concept-brief`**
  ([api/routes/generate_concept_brief.py](../../api/routes/generate_concept_brief.py)).
  Cache-check first; on miss, Haiku call ([prompts/concept_brief.py](../../api/prompts/concept_brief.py))
  produces a ~250-word three-paragraph brief plus 1–2 sentence gloss per
  subtopic; upserts cache row. Exposes `generate_brief_for_node` as a
  shared helper.
- **Wired into `/concept-review-resolve`**: reading-surface (miss) path
  now calls `generate_brief_for_node` inline. Glosses merged into
  `subtopics_json[*].gloss_md`. Try/except wrapper means Anthropic outage
  degrades gracefully to bare reading surface (logged warning, no 500).
- **[ConceptReadingView.tsx](../../web/components/ConceptReadingView.tsx)**
  prefers `brief_md` over `description_md`; subtopics render as a
  definition list with title above gloss.
- **Migration [20250026_concept_review_lineage.sql](../../supabase/migrations/20250026_concept_review_lineage.sql)** —
  `queue_items.parent_queue_item_id` (FK ON DELETE SET NULL, partial index
  WHERE NOT NULL), extends `notebook_entries.entry_kind` CHECK to allow
  `'concept_review'`.
- **Lineage**: `/api/queue/request` accepts and propagates
  `parent_queue_item_id` for both concept_review and refresher inserts.
  `OrientingConceptsPanel` takes a `parentQueueItemId` prop from
  `PaperView`. The concept review page reads the parent in parallel with
  resolve, and if it's a paper engagement passes `{queue_item_id,
  paper_title}` to `ConceptReadingView`. Back-link renders at the top of
  the reading view ("← Back to <paper title>"); "I've looked through this"
  redirects back to the paper instead of `/daily`.
- **Notebook persistence**: `/api/concept-review/[id]/done` now writes a
  `notebook_entries` row (entry_kind='concept_review', ref_id=node_id,
  title="<Node> — Concept", topic_node_slugs=[node.slug]). Idempotent — won't
  double-insert for the same (user, node). After done, the original
  `/concept-review/<queue_item_id>` URL is a dead end (route returns 409 in
  terminal state, page redirects to /daily); the notebook is the
  persistent surface.
- **Notebook list + detail** render concept_review entries: forest-outlined
  "Concept" badge in [notebook/page.tsx](../../web/app/notebook/page.tsx);
  cached brief + subtopic glosses rendered in
  [notebook/[id]/page.tsx](../../web/app/notebook/[id]/page.tsx) (fetches
  from `node_concept_briefs` by ref_id at render time).

Files added: `supabase/migrations/20250025_node_concept_briefs.sql`,
`supabase/migrations/20250026_concept_review_lineage.sql`,
`api/prompts/concept_brief.py`, `api/routes/generate_concept_brief.py`,
`api/tests/test_generate_concept_brief.py`.
Files modified: `api/main.py`, `api/schemas.py`, `api/routes/concept_review.py`,
`api/tests/test_concept_review_resolve.py`, `web/lib/types.ts`,
`web/lib/pythonApi.ts`, `web/lib/optimisticQueueRequest.ts`,
`web/app/api/queue/request/route.ts`,
`web/app/api/concept-review/[id]/done/route.ts`,
`web/app/concept-review/[queue_item_id]/page.tsx`,
`web/components/ConceptReadingView.tsx`,
`web/components/OrientingConceptsPanel.tsx`, `web/components/PaperView.tsx`,
`web/components/NodePanel.tsx`, `web/app/notebook/page.tsx`,
`web/app/notebook/[id]/page.tsx`.

Test results at close: pytest 168/168, npm build clean.

**Deferred** to future passes: first-render latency for cold concept briefs
is ~2–4s (synchronous Haiku call). If it bites in practice, move generation
to a background prefetch and add a "preparing your brief…" state. Flag the
trade-off in Step 7 mobile polish or Step 8 hardening if needed.

---

### Step 6 — Skill tree: interaction completeness ✅ DONE

Locked at entry: (a) edge UX = panel-on-click (mirrors NodePanel's pattern,
works on touch); (b) 2-hop shape = split arrays + distinct styling (1-hop
keeps the existing dashed/muted treatment, 2-hop renders even lighter +
smaller); (c) per-subtopic state source = new `user_subtopic_states` table
with backfill from `surveys.comfort_responses_json`.

Shipped:

- **#12** Edge click. New
  [`EdgePanel`](../../web/components/EdgePanel.tsx) renders on `onEdgeClick`
  with the relationship type ("Prerequisite" / "Related") and a one-line
  description sourced from `edge.edge_kind` + the source/target node titles.
  Selection state mutually excludes node selection — clicking a node closes
  the edge panel and vice versa; pane click closes both.

- **#13** "What's nearby?" expansion.
  [`/api/graph/me`](../../web/app/api/graph/me/route.ts) now accepts
  `?depth=1|2`. At `depth=2` the response includes `adjacent_nodes_2hop`
  alongside the existing `adjacent_nodes` (1-hop, kept as the default for
  backwards-compat with `ConfirmGraph`). The route does a second BFS layer
  outward from the 1-hop set and unions both rings of edges.
  [`SkillTreeView`](../../web/components/SkillTreeView.tsx) renders a "Show
  what's nearby" toggle in the top-right when the new `enableWhatsNearby`
  prop is set; the post-onboarding `/skill-tree` page enables it, the
  survey-confirm surface deliberately does not. 2-hop nodes use a third
  custom node type (`adjacent2`) with lighter dashed borders
  (`border-border/30`) and more transparent text
  (`text-muted-foreground/35`), smaller than 1-hop adjacent. The Legend
  conditionally adds a "Further nearby" entry when the toggle is on.

- **Survey-design §7** Per-subtopic refresh in
  [`NodePanel`](../../web/components/NodePanel.tsx). For foundation nodes
  with a `[{slug, title}]`-shaped `subtopics_json`, the panel now renders a
  Subtopics section listing each subtopic with: title, optional cached
  gloss (read from `node_concept_briefs.subtopic_glosses_json[*].gloss_md`,
  the Step 5.5 artefact), per-subtopic state label (Familiar / Refresh /
  Unseen — driven by the new `user_subtopic_states` table; absent when the
  user hasn't reported), and a "Request a refresher" link. The link wraps
  `optimisticQueueRequest({raw_text: subtopic.title, kind_hint: "refresher"})`
  mirroring [`OrientingConceptsPanel`](../../web/components/OrientingConceptsPanel.tsx),
  which routes through the Step 5 refresher→concept_review fallback path
  (the user has no notebook history at subtopic granularity, so the
  fallback in [/api/queue/request](../../web/app/api/queue/request/route.ts)
  inserts a `concept_review` on the parent node). Interest-node `string[]`
  subtopics are filtered out — only the `{slug,title}` shape is rendered,
  since that's the key both the concept tour and `user_subtopic_states` use.

- **Subtopic state durability** — new migration
  [`20250027_user_subtopic_states.sql`](../../supabase/migrations/20250027_user_subtopic_states.sql)
  adds `user_subtopic_states (user_id, node_id, subtopic_slug, state)` with
  PK on the triple, FKs to `profiles(id)` / `nodes(id)` (both ON DELETE
  CASCADE), RLS on `user_id` (SELECT + ALL policies). State enum:
  `familiar | refresh | new` — matches the existing concept-tour write
  payload. The migration includes a backfill that ports existing
  `surveys.comfort_responses_json.subtopics` entries (keyed
  `"<node_slug>:<subtopic_key>"`) into rows by joining on `nodes.slug`.
  Future tours write here on every addressed tile in addition to the
  existing `comfort_responses_json` + `user_node_states` writes.

- **New surface** GET
  [`/api/node/[id]/subtopic-states`](../../web/app/api/node/[id]/subtopic-states/route.ts)
  returns `{states, glosses}` in one round-trip — `states` from the new
  table for the signed-in user, `glosses` from `node_concept_briefs`
  (shared cache, not user-specific). Called by `NodePanel` on node change.

Files added:
- `supabase/migrations/20250027_user_subtopic_states.sql`
- `web/app/api/node/[id]/subtopic-states/route.ts`
- `web/components/EdgePanel.tsx`

Files modified:
- `web/app/api/add-interest/concept-tour/route.ts` (writes
  `user_subtopic_states` rows alongside existing writes)
- `web/app/api/graph/me/route.ts` (depth param + ring-2 BFS,
  `adjacent_nodes_2hop` field)
- `web/components/SkillTreeView.tsx` (onEdgeClick + EdgePanel + nearby
  toggle + Adjacent2HopNode + ring-2 layout + Further-nearby legend +
  `enableWhatsNearby` prop)
- `web/components/NodePanel.tsx` (Subtopics section, subtopic-states fetch,
  per-subtopic refresher handler)
- `web/app/skill-tree/page.tsx` (passes `enableWhatsNearby`)

Test results at close: pytest 168/168, npm build clean.

**Drift report reconciliation:** #12, #13 → `done`. (Survey design §7 is
not a separate drift item but is satisfied here.)

#### Step 6 revision (post-walkthrough)

Walkthrough surfaced two issues:

1. **EdgePanel body was empty calorie.** The original
   "X is a prerequisite for Y" body just restated the header; opening an
   edge panel taught the reader nothing they didn't already see.
2. **The global "Show what's nearby" toggle conflicted with NodePanel.**
   The top-right toggle button was occluded when NodePanel opened from the
   right edge, and the affordance felt detached from the spatial intuition
   of "what does this node connect to?".

Both fixed:

- **Edge descriptions are now LLM-generated and cached.** New migration
  [`20250028_edge_descriptions.sql`](../../supabase/migrations/20250028_edge_descriptions.sql)
  adds an `edge_descriptions` table keyed on `edge_id` (PK, FK→edges,
  ON DELETE CASCADE) with `description_md`, `generated_at`,
  `generated_by_model` — same pattern as `node_concept_briefs`. Service-
  role-only RLS. New Haiku route `/generate-edge-description`
  ([api/routes/generate_edge_description.py](../../api/routes/generate_edge_description.py),
  [api/prompts/edge_description.py](../../api/prompts/edge_description.py))
  produces a 3-5 sentence paragraph naming 2-3 specific bridging concepts
  (e.g. *"Band theory and Bloch's theorem carry forward into nanotube
  electronic structure — especially how chirality determines whether a
  tube is metallic or semiconducting."*). Cache-check first; shared across
  users (the first viewer of an edge pays the Haiku cost, every subsequent
  reader gets the cached row). New web proxy
  [`/api/edge/[id]/description`](../../web/app/api/edge/[id]/description/route.ts)
  GET. [EdgePanel](../../web/components/EdgePanel.tsx) rewritten to fetch
  on mount, render via `MarkdownLatex`, with a "Drawing the connection…"
  loading state. 4 new pytests
  ([test_generate_edge_description.py](../../api/tests/test_generate_edge_description.py))
  covering auth, 404, happy-path cache write, and cache-hit short-circuit.

- **"What's nearby" is now node-driven.** Removed the SkillTreeView toggle,
  the `enableWhatsNearby` prop, the `Adjacent2HopNode` render path, and
  the "Further nearby" legend entry. Reverted
  [/api/graph/me](../../web/app/api/graph/me/route.ts) to its pre-Step-6
  shape (1-hop only). Added a **Connected topics** section to NodePanel
  listing all 1-hop neighbors of the selected node, fetched from new
  [`/api/node/[id]/neighbors`](../../web/app/api/node/[id]/neighbors/route.ts)
  which returns nodes + edges so each row can be labelled "prereq" /
  "unlocks" / "related" depending on the edge_kind and direction. Each row
  click swaps NodePanel to that neighbor (new optional `onSelectNode` prop
  on NodePanel; SkillTreeView wires it to its own `setSelectedNodeId`).
  Below the list, a **Highlight on canvas** link triggers SkillTreeView to
  add a forest ring around the selected node + its visible neighbors and
  `fitView` to fit them — auto-clearing after 4 seconds. SkillTreeView
  now wraps its body in `ReactFlowProvider` so the inner component can
  call `useReactFlow().fitView` directly. The `renderPanel` prop signature
  widened to receive `onHighlightNeighbors` so context-specific panels
  (Stage 7 confirm) could opt in if they wanted, though Stage 7 still
  passes its own panel and doesn't use the highlight path.

Files added (this revision):
- `supabase/migrations/20250028_edge_descriptions.sql`
- `api/prompts/edge_description.py`
- `api/routes/generate_edge_description.py`
- `api/tests/test_generate_edge_description.py`
- `web/app/api/edge/[id]/description/route.ts`
- `web/app/api/node/[id]/neighbors/route.ts`

Files modified (this revision):
- `api/main.py` (router include)
- `api/schemas.py` (request/response models)
- `web/lib/pythonApi.ts` (`generateEdgeDescription` helper)
- `web/components/EdgePanel.tsx` (rewrite — fetch + render)
- `web/components/SkillTreeView.tsx` (removed toggle/2-hop, added
  highlight state, wrapped in `ReactFlowProvider`)
- `web/components/NodePanel.tsx` (Connected topics + Highlight on canvas)
- `web/app/api/graph/me/route.ts` (reverted to 1-hop)
- `web/app/skill-tree/page.tsx` (dropped `enableWhatsNearby`)

Test results at revision close: pytest 172/172 (168 + 4 new), npm build clean.

---

### Step 7 — Mobile polish ✅ CODE DONE (manual validation pending)

Code shipped; visual sweep at 375 px + real-device camera-to-grade flow
remain pending — see "Validation outstanding" below.

Shape:
- **Mobile-detection hook** —
  [`web/lib/useIsMobile.ts`](../../web/lib/useIsMobile.ts) wraps
  `window.matchMedia('(max-width: 767px)')` (Tailwind's `md` breakpoint).
  SSR-safe (`false` during server render, updates on mount). Used only by
  the two graph surfaces below; everything else is already responsive via
  existing `sm:` rules.
- **`/skill-tree` mobile fallback** — new
  [`SkillTreeListView`](../../web/components/SkillTreeListView.tsx) shows
  two list sections ("Your interests & foundations" with a "Get a problem"
  CTA per row; "Nearby" with an "Add to my interests" CTA opening the
  existing `DialogModal` in `preNode` mode) plus a "View on desktop for
  the full graph" footer. No EdgePanel / Connected-topics / Highlight-on-
  canvas in this view — the list stands on its own. New thin client
  wrapper
  [`SkillTreeShell`](../../web/components/SkillTreeShell.tsx) branches
  `useIsMobile()` → ListView vs `SkillTreeView`. The page
  ([`web/app/skill-tree/page.tsx`](../../web/app/skill-tree/page.tsx))
  now renders `<SkillTreeShell>` and drops the fixed `100vh` wrapper that
  forced ReactFlow's height even on phones.
- **Stage 7 confirm mobile fallback** —
  [`ConfirmGraph.tsx`](../../web/components/survey/ConfirmGraph.tsx) gains
  a `useIsMobile()` branch on the canvas block only. Mobile path renders
  three list sections inline (no new file): "Your interests" with
  Edit/Remove (Edit opens `DialogModal` in `preNode` mode pre-filled with
  current `intent_context` via `/api/interest/me`; Remove calls
  `DELETE /api/interest/[node_id]` then `refreshGraph(deletedNodeId)`),
  "Foundations to refresh" (read-only), "Nearby" (read-only, greyed).
  Header copy + Back / "Your queue is ready →" CTAs unchanged. Per-row
  intent fetch is per-row (typically 1-5 rows; not worth batching).
- **Targeted mobile fixes** on existing surfaces (no new files):
  - [`ProblemView.tsx`](../../web/components/ProblemView.tsx) Step 1
    actions: `flex flex-wrap gap-3` → `flex flex-col gap-3 sm:flex-row
    sm:flex-wrap`. "Start working" `flex-1` → `sm:flex-1`. On phone all
    three buttons stack full-width with Start as the primary at the
    bottom, preserving Skip / Defer / Start reading order.
  - [`RequestBox.tsx`](../../web/components/RequestBox.tsx) confirmation
    panel button row: added `flex-wrap` so Cancel can drop to a new line
    at 375 px when Add it + Just this once + Cancel don't fit.
  - [`ProfileView.tsx`](../../web/components/profile/ProfileView.tsx)
    interest row: `flex items-start justify-between gap-4` → `flex
    flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4`,
    with `ml-5 sm:ml-0` on the Edit/Remove button group so it aligns under
    the indented title block on mobile.
  - [`layout.tsx`](../../web/app/layout.tsx) nav:
    `gap-6` → `gap-4 sm:gap-6` so the four nav links breathe at 375 px.
- **Survey mobile sweep** — no code changes anticipated.
  [`BackgroundForm`](../../web/components/survey/BackgroundForm.tsx),
  [`FoundationsGrid`](../../web/components/survey/FoundationsGrid.tsx),
  [`InterestSuggestions`](../../web/components/survey/InterestSuggestions.tsx),
  [`DialogOrchestrator`](../../web/components/survey/DialogOrchestrator.tsx),
  and [`ModeBalanceSlider`](../../web/components/survey/ModeBalanceSlider.tsx)
  already use `sm:grid-cols-2` patterns that fall back to single-column
  below 640 px.

Files added (Step 7):
- `web/lib/useIsMobile.ts`
- `web/components/SkillTreeListView.tsx`
- `web/components/SkillTreeShell.tsx`

Files modified (Step 7):
- `web/app/skill-tree/page.tsx` (uses `SkillTreeShell`)
- `web/components/survey/ConfirmGraph.tsx` (mobile branch + inline
  `ConfirmListView` helper)
- `web/components/ProblemView.tsx` (Step 1 action row stacking)
- `web/components/RequestBox.tsx` (confirmation panel `flex-wrap`)
- `web/components/profile/ProfileView.tsx` (interest row stacking)
- `web/app/layout.tsx` (nav gap)

Build: `npm run build` clean (Next.js 16.2.6, all 54 routes generated).
pytest unchanged (no API surface touched); expected to remain 172/172.

**Validation outstanding** — code is done but Step 7 acceptance requires
two checks that need a human:

1. **Visual sweep at 375 × 667** in browser devtools across /daily,
   /notebook, /problem, /profile, /skill-tree, and all seven survey
   stages. Watch for any horizontal overflow, touch-target crowding, or
   layouts that look broken rather than just compact. Stage 7
   confirmation should swap to the list view at narrow widths and back to
   the graph above 768 px.
2. **Camera → upload → parse → review → submit** on a real phone hitting
   the dev server over LAN (or a deployed preview). The vision parse step
   is the most fragile — image sizes, EXIF orientation, slow uploads.
   ProblemView already uses `<input type="file" accept="image/*"
   capture="environment" multiple>` so the camera primitive is right; what
   needs verifying is that the upload-to-parse round trip works end-to-end
   on a phone.

The status line at the top of `docs/pivot-plan.md` should not flip to
"Step 7 complete" until these two validations pass.

---

### Step 8 — Final hardening + phase close

Scope adjusted at entry: Sentry deferred to Phase 11-deploy (more useful
once the services are public-facing). What ships here is the pre-walkthrough
audit + any blockers it surfaces + the persona-1 walkthrough itself.

#### 8a — Sentry on Next.js — DEFERRED to Phase 11-deploy

Original plan was `@sentry/nextjs` with DSNs in env vars. Decision at entry:
defer until the FastAPI service is publicly deployed, since error monitoring
is most valuable when the deploy/incident path it's instrumenting actually
exists. Phase 11-deploy picks this up alongside the Fly/Railway deploy.

#### 8b — Sentry on FastAPI — DEFERRED to Phase 11-deploy

Same reasoning as 8a.

#### 8c — Pre-walkthrough audit ✅ DONE

Read [persona-1-walkthrough.md](../persona-1-walkthrough.md) against the
current code paths. Findings:

- **🔴 Blocker — curator-created refresher cards dead-ended.** The
  curriculum curator inserts `kind='refresher'` queue items with
  `ref_id = node_id` (see
  [api/routes/curator.py:287-294, :645-660](../../api/routes/curator.py#L287)),
  but `surface_daily._resolve_refresher_content` only recognised the legacy
  shape where `ref_id` is a `refresher_schedule.id`. So curator-emitted
  refreshers came through with `subject_queue_item_id=None`, and
  [DailyView.tsx](../../web/components/DailyView.tsx) fell through to the
  "coming soon" placeholder. Persona-1 Day 1's multivariable refresher
  (sourced from the cold-start `planQueue` call) would have hit this
  dead-end. Fixed in 8d.

- **🟡 Friction (kept).** No inline "mark as refreshed, skip" on the queue
  card itself — semantic exists behind one click into `/problem`. Per spec
  this is acceptable; the walkthrough's narrative compression survives.
  Left alone per user preference.

- **🟠 Cosmetic (deferred).** `/api/queue/bookmark` is misnamed — it
  actually sets `state='dismissed'`. Functional, just confusing. The
  "Skip — I've got this" button label vs the walkthrough's "mark as
  refreshed, skip" — same action, arguably better current label.

#### 8d — Refresher-resolve fix ✅ DONE

Mirrors [/concept-review-resolve](../../api/routes/concept_review.py)'s
pattern: click-time resolver decides where the card lands.

Shape:
- New Python route `POST /refresher-resolve`
  ([api/routes/refresher.py](../../api/routes/refresher.py)) takes
  `{user_id, queue_item_id}`. Verifies `kind='refresher'` + ownership +
  non-terminal state. Tries `refresher_schedule.id` first (legacy path),
  then falls back to `nodes.id` (curator-style). On legacy attempt: looks
  up the original `attempts.problem_id` and inserts a fresh
  `kind='problem'` queue_items row (NOT returning the original
  queue_item_id, which is in state='done' and would bounce off
  `/problem`). On legacy engagement: same shape for `paper_engagement`.
  On curator-style: pool lookup at `intent='refresh', difficulty=1` on
  the node. On hit: inserts a fresh `kind='problem'`. On miss: inserts a
  `kind='concept_review'` on the same node so the user still lands on
  the cached brief. In all branches the original refresher row is
  marked `state='done'`. Schemas added to
  [api/schemas.py](../../api/schemas.py); router registered in
  [api/main.py](../../api/main.py).

- New web page
  [`/refresher/[queue_item_id]/page.tsx`](../../web/app/refresher/[queue_item_id]/page.tsx)
  — thin server component, calls `refresherResolve()`, `redirect()`s to
  `/problem`, `/paper`, or `/concept-review` based on `kind`. Helper
  added to [pythonApi.ts](../../web/lib/pythonApi.ts).

- [DailyView.tsx](../../web/components/DailyView.tsx) refresher branch
  unified: any refresher card with a `ref_id` now routes through
  `/refresher/<queue_item_id>`. The old split between
  `subject_queue_item_id`-based linking and the fall-through placeholder
  is gone.

- **Cleanup** of now-dead `subject_kind` / `subject_queue_item_id`
  surfacing infrastructure (the resolver does click-time resolution, so
  surface-daily no longer needs to pre-resolve refresher subjects):
  - Removed `subject_kind` / `subject_queue_item_id` from
    [SurfacedItem](../../api/schemas.py) and
    [SurfacedQueueItem](../../web/lib/types.ts).
  - Removed `_resolve_refresher_content` helper from
    [surface_daily.py](../../api/routes/surface_daily.py) (plus its 4-step
    SQL chain through refresher_schedule → attempts/engagements →
    problems/papers → nodes, all replaced by the click-time lookup).
  - Trimmed
    [test_surface_daily.py](../../api/tests/test_surface_daily.py) —
    deleted `test_refresher_resolved_to_content_title` (tested deleted
    code); other refresher tests slimmed by dropping unused responders.

- Tests: 9 new in
  [test_refresher_resolve.py](../../api/tests/test_refresher_resolve.py)
  covering auth, 404, wrong-kind, 409, curator pool-hit, curator
  pool-miss, unknown ref_id, legacy attempt path, missing ref_id. Net
  test count: 172 → 180 (added 9, removed 1 deleted test).

- `npm run build` clean (Next.js 16.2.6, 55 routes incl. new
  `/refresher/[queue_item_id]`). `uv run pytest`: 180/180.

#### 8e — Persona-1 walkthrough — PENDING (user)

Walk [persona-1-walkthrough.md](../persona-1-walkthrough.md) end-to-end on
a fresh user. `POST /api/survey/reset` (admin-gated) wipes a user's survey
+ interests + node states + queue items so the seven-stage flow can be
re-walked.

Fold in the two manual validations from Step 7 (mobile sweep at 375×667 +
real-device camera→upload→parse→review→submit) during the walkthrough.

#### 8f — Phase close — PENDING (user)

After 8e passes, update the [pivot-plan](../pivot-plan.md) status line to
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
