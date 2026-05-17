# Phase 9-rev — execution plan

> **Status: Step 2 complete.** Backend API correctness: #18–#23 all `done`. Also fixed S5 trailing copy in surface_daily.py and update_queue.py. Next: Step 3 — skill tree security fix + panel completeness.

Forward-looking plan for Phase 9-rev. Source of truth for the product is
[../SPEC.md](../SPEC.md), [../ARCHITECTURE.md](../ARCHITECTURE.md),
[../graph-design.md](graph-design.md), and [../personas.md](personas.md).
This file captures *execution* decisions and step ordering.

---

## Where we are

Phase 8-rev is complete and committed. All 8 steps landed:

- Weekly curation report generation, proposal review UI, apply action and
  snapshot write, operator megagraph view (React Flow + Dagre, time scrubber),
  cost dashboard, deprecated table drop, admin users/queue view.
- Cross-pollination is live (gate unlocked by the first `megagraph_snapshots`
  row with `taken_by='system'`).
- A systematic drift audit was run on 2026-05-17 and found 33 open issues:
  23 spec violations and 10 spirit/persona gaps. These are tracked in
  [../drift-report.md](../drift-report.md).
- The user maintains a running notes file (`docs/polish-notes.txt`) with
  findings from live site walkthroughs.

---

## Phase 9-rev goal

After Phase 9-rev:

- Every `contradicts`-severity drift finding is resolved.
- All backend API bugs are fixed (suggest_papers, update_queue,
  compute_cross_pollination, add_interest, ingest_paper_user, propose_papers).
- Queue cards show item titles and dynamic "why this" reasons.
- The skill tree is using the correct auth client and NodePanel has its full
  action set.
- Admin surfaces (megagraph engagement_count, cost pagination) are complete.
- Walkthrough notes have been triaged; any new `contradicts` items addressed.
- **Acceptance:** every `contradicts` drift item is `done`; all API bugs are
  `done`; pivot-plan status line updated.

---

## Out of scope

- **Survey redesign.** A full redesign of the survey (feel, flow, tone) is
  Phase 10-rev. Phase 9 only fixes the `bg-white` colour token (#6); the
  structural survey gaps (#7, #8, #9) are Phase 10.
- **Concept review implementation.** Queue `kind='concept_review'` items
  (drift #3) require design decisions; deferred to Phase 10.
- **Reroll feedback loop.** Drift #4 requires a queue-reweighting change;
  deferred to Phase 10.
- **Paper request → propose-papers.** Drift #5 is deferred to Phase 10.
- **Spirit/persona gaps S1–S4, S8–S9.** Engagement quality and notebook
  prominence are Phase 10 experience work.
- **Skill tree interaction polish** (#12, #13 — edge clicks, "what's nearby?").
  Phase 10.
- **Mobile polish and error monitoring.** Original Phase 9-rev items; moved
  to Phase 10 which is the final pre-launch phase.

---

## Decisions locked in

### D1 — Note-intake process

User drops raw notes into `docs/polish-notes.txt`. At the start of Phase 9
step 1, read the file, triage all items into the drift report (assign
severity + status), fix any new `contradicts` items within Phase 9, defer
the rest to Phase 10.

### D2 — Client selection for skill tree

The skill-tree server component must use the user-scoped Supabase client
(`createServerClient` with `cookies()`), not the service-role admin client.
Service-role reads in user-facing routes are a privilege-scope leak regardless
of RLS (drift #14).

### D3 — Queue card "why this" source

The `added_reason` column on `queue_items` is the source of truth for the
card's reason string. If `added_reason` is null or a static fallback, the
backend (`update_queue.py`) is responsible for writing a meaningful reason
at queue-build time. Fix both the card display and the backend population
together in step 4.

---

## Steps

### Step 1 — Note-intake triage + core philosophy violations

**Before writing code:** read `docs/polish-notes.txt`; triage new items into
the drift report; address any new `contradicts` items here; defer the rest.

Then fix the `contradicts`-severity drift items:

- **#6** `web/app/survey/page.tsx`: replace `bg-white` with `bg-background`
  (`#FAF7F0`); check `SurveyForm.tsx` and all child step containers.
- **S7** Audit every surface for time references ("quick problem", "30-min
  read", duration estimates on queue cards, `time_estimate_minutes_*` exposed
  in UI copy). Remove or reframe without reference to duration.
- **S5** Audit refresher copy for guilt framing ("it's been a while since you
  covered this"). Rewrite as confidence-building ("run through this again to
  reinforce it").
- **S6** Check queue and daily surfaces for any toast, label, or copy that
  reveals queue reweighting happening (e.g., "Updated queue based on your
  recent activity"). Remove or neutralise — adaptation must be invisible.

Files: `web/app/survey/page.tsx`, `web/components/SurveyForm.tsx`,
`web/components/DailyView.tsx`, `web/app/daily/page.tsx`

Commit: update drift report — #6, S5, S6, S7 → `done`.

---

### Step 2 — Backend API correctness

Six bugs in the FastAPI service:

- **#18** `api/routes/suggest_papers.py`: replace the single `interest_titles[0]`
  pre-filter with `ILIKE ANY(ARRAY[...])` across all interest titles; cap
  candidate set at 20 rows before passing to Haiku.
- **#19** `api/routes/update_queue.py`: call `user_node_states` recomputation
  on paper engagement completion (`kind='paper_engagement'`), not only on
  `attempt_submit`. Paper completion is a valid engagement signal.
- **#20** `api/routes/compute_cross_pollination.py`: fix the cooldown logic —
  a dismissed suggestion must suppress re-suggestion of nodes in the same
  domain/cluster for the week (e.g., `WHERE domain = $dismissed_domain`),
  not only the exact dismissed node.
- **#21** `api/routes/add_interest.py`: add explicit handling for `split` and
  `vague` dedup verdicts. `split` should surface both sub-topics for
  confirmation; `vague` should prompt for clarification rather than silently
  creating a new node.
- **#22** `api/routes/ingest_paper_user.py`: before generating an engagement,
  check for an existing `paper_engagements` row with `(user_id, paper_id)`.
  If found, return the existing engagement id rather than creating a duplicate.
- **#23** `api/routes/suggest_papers.py` + `api/routes/propose_papers.py`:
  insert queue items with `ON CONFLICT DO NOTHING` (or equivalent upsert) on
  `(user_id, ref_id, kind)` to prevent concurrent duplicate items for the
  same engagement.

Commit: update drift report — #18–23 → `done`.

---

### Step 3 — Skill tree: security fix + panel completeness

- **#14** `web/app/skill-tree/page.tsx`: replace the service-role Supabase
  client with the user-scoped server client (`createServerClient` with
  `cookies()`). Verify that RLS SELECT policies on `nodes`, `edges`, and
  `user_node_states` allow authenticated reads (add policies if missing).
- **#10** `web/components/NodePanel.tsx`: add `unlocks_text` field (from
  `nodes.unlocks_text`) below the node description. Add a compact history
  section showing the user's completed problems and paper engagements on this
  node, sourced from `notebook_entries` filtered by `topic_node_slugs`.
- **#11** `web/components/NodePanel.tsx`: add the missing action affordances
  alongside the existing "Get a problem" and "Add to my interests":
  - Bookmark node (`POST /api/queue/bookmark` or a dedicated bookmark route)
  - Mark as comfortable (update `user_node_states.state = 'comfortable'`)
  - Request a paper on this node (`POST /api/queue/request` with
    `kind_hint='paper'` and the node id)

Files: `web/app/skill-tree/page.tsx`, `web/components/NodePanel.tsx`,
`web/app/api/graph/me/route.ts`

Commit: update drift report — #10, #11, #14 → `done`.

---

### Step 4 — Queue card content

- **#2** `web/components/DailyView.tsx`: queue cards must display the item
  title — the problem statement title or paper title. The `/api/queue` route
  must join through to the content table to return `title`. Update
  `web/app/api/queue/route.ts` to include the title in the response.
- **#1** Replace the static fallback reason string ("A problem is ready for
  you.") with `queue_items.added_reason`. Where `added_reason` is null or
  generic, update `api/routes/update_queue.py` to write a meaningful,
  interest-tied reason string at queue-build time (e.g., "Related to your
  interest in gravitational waves.").

Files: `web/components/DailyView.tsx`, `web/app/api/queue/route.ts`,
`api/routes/update_queue.py`

Commit: update drift report — #1, #2 → `done`.

---

### Step 5 — Admin surface polish

- **#16** `web/app/admin/megagraph/page.tsx`: the node click panel must show
  the aggregate `engagement_count` summed across all users for that node.
  Update the `/api/admin/megagraph` route to include this aggregate (join
  `user_node_states` grouped by `node_id`).
- **#17** `web/app/admin/costs/page.tsx` + `web/app/api/admin/costs/route.ts`:
  the "Full log" table currently slices to 50 rows with no navigation. Add
  pagination: a `page` query parameter, next/prev controls in the UI,
  and a total-count header or field so the UI can show "Showing 1–50 of N".

Files: `web/app/admin/megagraph/page.tsx`, `web/app/admin/costs/page.tsx`,
`web/app/api/admin/costs/route.ts`, `web/app/api/admin/megagraph/route.ts`

Commit: update drift report — #16, #17 → `done`.

---

### Step 6 — Phase 9-rev acceptance

- Verify all steps committed and drift items updated.
- Re-read `docs/polish-notes.txt` for any new notes added since step 1 triage.
  Defer any remaining items to Phase 10 drift report entries.
- Update `docs/pivot-plan.md` status line:
  `Phase 9-rev complete. Next step: Phase 10-rev step 1 — Survey scoping.`
- Create `docs/phase-plans/phase-10-rev-plan.md` (exists already) as the
  active plan for the next phase.
