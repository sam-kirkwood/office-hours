# Pivot plan — status & phase map

**Where things are (2026-06-16):** Phase 12 (the responsive daily loop) is complete.
Phase 13 (conversational orientation) is underway — Step 1 (§3.4 amendment) done.

| Phase | What | Status |
|---|---|---|
| 4-rev … 10-rev | graph migration → queue → skill tree → papers → adaptation → curation → polish → survey/curator/UX redesign | ✅ done |
| 10.5-rev | operator-walkthrough remediation (queue/refresher/problem-page/survey-rendering/skill-tree fixes) | ✅ done |
| **12** | the responsive daily loop — card actions, the correction loop, the curiosity-box router, steering | ✅ done (2026-06-16) |
| **13** | conversational orientation — four-signal tutor, rich paths, the entry-point amendment | 🔄 Step 1 done |
| 11-deploy | FastAPI deploy + cron + Sentry + README (keeps its number; runs **last**, once happy) | ▢ deferred to end |

Design source of truth: SPEC.md, ARCHITECTURE.md, docs/graph-design.md,
docs/personas.md, docs/orientation-and-calibration-design.md (Phases 12/13), and
the per-phase plans under docs/phase-plans/. The dated log below is the **build
record** — a running narrative of each step and the review rounds that opened the
next. It is history, not the current plan; read top-to-bottom it tells the story of
how the project grew.

### Backlog & pending operator actions

Not lost, not currently scheduled into a phase. (Carried-over **p1/p2** paper
balance + the **paper-chip backfill** are scheduled — Phase 12 Step 5.)

**Deferred features** (from the closed Phase 10.5-rev features bucket; build when
wanted):
- ~~**fb1 — report-a-problem / feedback catch-all.**~~ ✅ Built (Phase 12 Step 4a, 2026-06-14): `feedback_reports` table, `POST /api/feedback`, `FeedbackDialog` in the nav, `/admin/feedback` operator list with mark-resolved.
- **d14 — Q&A on the feedback page.** Synergistic with the Phase 13 tutor (reuses
  the conversational machinery); natural Phase 13 follow-on.
- **t6 — curriculum-path overlay on the skill tree.** Enabled by Phase 13's rich
  paths (the persisted path makes the route drawable).
- **d19 — pause/resume for paper engagements**; **fb2 — "I can't find this paper"
  escape hatch**; **fb3 — community PDF store** (fb2+fb3 are a paper-sourcing pair;
  copyright caveat on fb3). Unrelated to 12/13 — schedule or push to v2.1.
- *(s17 — "what we learned about you" — is **not** here; it's absorbed into the
  Phase 13 tutor's graph mirror-back.)*
- **Curator down-weight for dismissed problem/paper topics** (Phase 12 Session
  12.1 follow-up). "Not for me" writes `queue_items.state='dismissed'`;
  cross-pollination already reads that to down-weight a dismissed *suggested-
  interest*'s domain, but the curator does not yet consume dismissed
  *problem/paper* rows as a negative preference on their topic node. Left out of
  12.1 to keep the card-actions session tight (operator-approved). Wire into the
  planner's signal-loading (`api/curator_inputs.py`) when convenient — natural
  fit alongside the Step 4 steering/feedback work.

**Pending operator actions** (from Phase 10.5-rev Step 3, not yet run): apply
migrations `20250032` + `20250033`, restart the web dev server (picks up
remark-gfm), then run `scripts/reformat_problems.py` (`--dry-run` → spot-check →
`--apply`).

---

Status: Phase 10-rev Step 1 done (three design docs landed). Steps 2a–2g done — Step 2 of Phase 10-rev is complete: schema migrations (intent_context, deferred state, requested_assume_less, user_preferences, problems.intent, queue_items.deferred_at); add-interest dialog API (/parse + /resolve + /rewrite-summaries); seven-stage onboarding survey UI; add-interest dialog UI + post-onboarding modal integration (daily-tab RequestBox, NodePanel Add, SurveyNodePanel Edit, profile Edit); profile page with auto-saving mode balance slider, four high-level feedback toggle chips persisting to `user_preferences`, expandable interest list showing queued problems under each interest with a "Rewrite summaries" backfill button (Haiku batch rewrites `intent_context` into descriptive "Topic: what it covers" prose using node description + subtopics), and a read-only foundation-state list; three-dial problem generation (difficulty / intent / assumed background as independent dials, `intent_context` source of truth for intent, entry-point default for new interests, practical-generation-test in the prompt, required subtopic tags with topic-slug validation, feedback biases passed through softly, intent in the cache key + unique index); "Not ready yet" deferral action (defer transitions queue_items.state to 'deferred' + stamps deferred_at, no attempt row, no node-state change, only allowed from pending/surfaced). Step 3a done — /assess-engagement (Haiku, post-engagement) endpoint live with all four immediate_action branches (queue_reinforcement, accelerate, surface_prerequisite, null); shared derive helpers extracted from generate_problem.py into api/curator_inputs.py; route wired into grade_solution.py and grade_paper_answer.py (best-effort, never blocks the user's grade response); 11 new tests. Steps 3b + 3c done — /plan-queue (Sonnet, daily per-user) builds the full §4.2 context (mode_balance, active interests, prerequisite-closure-scoped foundation states, prerequisite edges, 14-day recent engagement including rerolls + deferred items, queue summary, feedback signals), calls Sonnet with cache-eligible system prompt, executes add/reprioritise recs (pool-hit-or-generate dispatch with inline /generate-problem on miss, refresher kind, paper-engagement-noop, duplicate-pending-skip); /check-deferred (deterministic, no LLM) walks queue_items.state='deferred', checks all prerequisite edges via spec §8 threshold (state='comfortable' OR struggle_score<0.3 AND engagement_count>=2), transitions to 'pending' with priority_score=0.55 while preserving deferred_at for analytics; 15 new tests across both routes (160/160 passing).
Steps 3d + 3e + 3f done — Phase 10-rev Step 3 complete. /run-daily-planner is the per-user wrapper that calls /plan-queue then /check-deferred and writes a curator_job_runs row (new table in 20250023). Cold start: web/app/api/survey/complete/route.ts now calls planQueue(userId, triggeredBy='cold_start'). Daily cadence: pg_cron + pg_net (extensions enabled in 20250024) fan out one HTTP POST per active user (engagement in past 14 days via attempts.submitted_at OR paper_answers.submitted_at→paper_engagements). Migration 20250024's header documents required dashboard setup before push: enable pg_cron + pg_net extensions, create Vault secret `internal_api_token`, set `app.python_api_url` Postgres config. Cross-pollination accept (web/app/api/interest/route.ts) also calls planQueue. Reroll signal capture: web/app/api/queue/reroll/route.ts now writes one surfaced_picks row per passed-over item with chosen_item_id=null, feeding the curator's recent_engagement.reroll_patterns block. /update-queue deleted: 4 call sites removed (problem submit + paper answer now redundant with /assess-engagement hooks; survey complete + interest accept migrated to planQueue), route + schemas + test_update_queue.py gone, ARCHITECTURE.md updated. Known deferred: refresher_schedule.due_at firing (the deterministic "10-day-old notebook entry → refresher" path) and queue_items done/dismissed pruning are no longer replaced by anything; curator can recommend refreshers ad-hoc but the systematic schedule is gone. Acceptable per spec; pick up in Phase 6 cost-dashboard work if needed.
Cron deferred to Phase 11-deploy: FastAPI service is not yet deployed to a public host, so migration 20250024 (pg_cron schedule for /run-daily-planner) is NOT applied. The file remains in supabase/migrations/ as a Phase 11 reference. Only 20250023 (curator_job_runs log table) is applied; the table records cold-start + manual /run-daily-planner invocations in the meantime. Phase 11-deploy will: deploy FastAPI to Fly/Railway, set Vault secret `internal_api_token` + Postgres config `app.python_api_url`, then apply 20250024.
Step 4 done — Phase 10-rev Step 4 complete. D3 locked at entry (option b → option a fallback). concept_review view shipped: new FastAPI route /concept-review-resolve in api/routes/concept_review.py (pool lookup at intent='teach', difficulty=1, primary-subtopic tag; pool hit atomically enqueues kind='problem' row and marks the concept_review row done; pool miss returns node description_md + subtopics_json for serif reading). New web route /concept-review/[queue_item_id] (server) + ConceptReadingView (client) + /api/concept-review/[id]/done route. DailyView routes concept_review cards to the new page; resolveTitles lifts node titles for them. Paper request fallback chain (#5): /api/queue/request paper branch now does suggestPapers → DB → on miss: proposePapers → suggestPapers → DB. Idempotent (propose-papers dedups by title/arxiv_id/doi). Fire-and-forget UX (#39): installed sonner@2.0.7; new web/lib/optimisticQueueRequest.ts helper shows toast.loading immediately, upgrades to toast.success with "Go to it now →" action on resolve with queue_item_id, or toast.message on null id, or toast.error on reject; calls router.refresh() so /daily reloads silently. Wired into NodePanel (Get a problem / Request a paper, 800ms button debounce) and RequestBox (all queueProblemOnNode call sites + paper/refresher handleSubmit branch). Tone pass on DailyView KIND_CTA + defaultDescription + MoreComingCard strings per survey-and-difficulty-design §5. 7 new tests, 160/160 passing. Build clean. Known deploy follow-up: paper-fallback chain can take 30-60s, may need detaching as `void proposePapers(...)` in Phase-11-deploy if Vercel function timeouts trigger.

Step 5 done — Phase 10-rev Step 5 complete (D5 locked to option a: explicit "Promote to interest" CTA on bookmarked nodes). Shipped: S1 paper resume progress (PaperProgress.tsx — "Question N of M" + per-question dots), S2/S3 interactive orienting concepts (paper_engagements.orienting_concepts_json shape change to [{term, definition_md}] with legacy string[] tolerance; new OrientingConceptsPanel with click-to-expand definition + "Get a refresher on this" wrapped in optimisticQueueRequest; /api/queue/request refresher branch tightened to fall back to concept_review when raw_text targets a node with no notebook history), S4 cross-pollination copy ("Someone studying adjacent topics recently explored this." — literal-string update in compute_cross_pollination.py), S8 bookmark→interest CTA (hoisted to slot 2 and re-styled solid amber on bookmarked-not-yet-interest nodes in NodePanel), S9 notebook nav with past-7-day entry count in /layout.tsx (async root layout + admin Supabase client). Continue-paper CTA on /daily for in-progress paper engagements (queueHelpers.ts derives in_progress from current_question_index>0 OR state='in_progress'). Mid-step incidental fixes: suggest-papers PostgREST escape bug (titles with `&`/`,`/`(`/`)` now double-quoted in or= filter); concept_review.py subtopics_json string-tolerance (legacy interest nodes coerce string[] → {slug,title}[]). optimisticQueueRequest.targetPath widened to (id, kind) so callers can route refresher→/problem vs concept_review→/concept-review. pytest 168/168, npm build clean.

Step 5.5 done — concept brief + lineage + notebook persistence (scope addition from walkthrough). D3 reversed: the bare description_md + subtopic-titles reading surface was insufficient; added a Haiku-generated concept brief cached per node. Migration 20250025 (node_concept_briefs: brief_md + subtopic_glosses_json [{slug,title,gloss_md}], keyed on node_id, service-role-only RLS); new /generate-concept-brief route (~250-word three-paragraph brief + per-subtopic glosses, cache-check first, Haiku on miss, upsert); generate_brief_for_node helper called inline from /concept-review-resolve's miss path with try/except graceful degradation if Anthropic is down. Migration 20250026 (queue_items.parent_queue_item_id FK ON DELETE SET NULL with partial index; extended notebook_entries.entry_kind CHECK to allow 'concept_review'). Lineage: /api/queue/request accepts parent_queue_item_id (set by OrientingConceptsPanel from PaperView's queueItemId), propagates to concept_review and refresher inserts; ConceptReadingView renders "← Back to <paper title>" at the top and redirects back to the paper on done. Notebook persistence: /api/concept-review/[id]/done writes a notebook_entries row (idempotent per (user, node)); /notebook list shows forest-outlined "Concept" badge; /notebook/[id] renders the cached brief + glosses. Original /concept-review/<queue_item_id> URL becomes a dead end post-done (returns 409 → redirect to /daily); notebook is the persistent surface. pytest 168/168, npm build clean.

Step 6 done — Phase 10-rev Step 6 complete (skill-tree interaction completeness). Three sub-items shipped: (1) #12 edge click — clicking an edge in SkillTreeView opens an EdgePanel showing the relationship type ("Prerequisite" / "Related") and a one-line description ("Calculus I is a prerequisite for Differential Equations."). Selection state mutually excludes node selection. (2) #13 "What's nearby?" affordance — new /api/graph/me?depth=2 parameter returns adjacent_nodes_2hop alongside the existing adjacent_nodes (1-hop, backwards-compatible default); SkillTreeView renders a "Show what's nearby" toggle in the top-right when enableWhatsNearby is set (post-onboarding /skill-tree only; survey confirm suppresses it), 2-hop nodes render with even lighter dashed borders and more transparent text than 1-hop, legend gains a "Further nearby" entry when the toggle is on. (3) Survey-design §7 per-subtopic refresh — NodePanel now renders a Subtopics section for foundation nodes (filtered by node.kind === "foundation" + non-empty {slug,title}[] shape) showing subtopic title + cached gloss (from node_concept_briefs.subtopic_glosses_json when present) + per-subtopic state badge (Familiar/Refresh/Unseen) + "Request a refresher" link that wraps optimisticQueueRequest({raw_text, kind_hint: "refresher"}) — same plumbing as OrientingConceptsPanel, resolving to a concept_review on the parent node since the user has no notebook history at subtopic granularity.

Subtopic state durability: new migration 20250027 adds user_subtopic_states (user_id, node_id, subtopic_slug, state ∈ familiar/refresh/new, PK on the triple) with RLS on user_id; the concept-tour route (/api/add-interest/concept-tour) now writes to this table on every addressed tile alongside its existing comfort_responses_json + user_node_states bumps. The migration includes a backfill that ports existing surveys.comfort_responses_json.subtopics entries (keyed "<node_slug>:<subtopic_key>") into rows by joining on nodes.slug. New GET /api/node/[id]/subtopic-states returns the user's per-subtopic states + cached subtopic glosses in one round-trip.

Files added: supabase/migrations/20250027_user_subtopic_states.sql, web/app/api/node/[id]/subtopic-states/route.ts, web/components/EdgePanel.tsx. Files modified: web/app/api/add-interest/concept-tour/route.ts (writes user_subtopic_states), web/app/api/graph/me/route.ts (depth param + ring-2 BFS), web/components/SkillTreeView.tsx (onEdgeClick + EdgePanel + Show what's nearby toggle + 2-hop node type + ring-2 layout + Further-nearby legend entry), web/components/NodePanel.tsx (Subtopics section + state fetch + refresher handler), web/app/skill-tree/page.tsx (enableWhatsNearby={true}).

Step 6 revision — walkthrough surfaced two issues with the initial Step 6 shape: (a) the EdgePanel body was empty calorie ("X is a prerequisite for Y" just restated the header), and (b) the global "Show what's nearby" toggle conflicted visually with NodePanel (occluded when right-side panel was open) and made more sense scoped to a node. Both fixed in this revision:

(a) **Edge descriptions are now LLM-generated and cached.** New migration 20250028 adds an edge_descriptions table (edge_id PK, description_md, generated_at, generated_by_model — same pattern as node_concept_briefs). New Haiku route /generate-edge-description (api/routes/generate_edge_description.py + prompts/edge_description.py + schemas) produces a 3-5 sentence paragraph naming 2-3 specific bridging concepts (e.g. "Band theory and Bloch's theorem carry forward into nanotube electronic structure — especially how chirality determines whether a tube is metallic or semiconducting"). Cache-check first; shared across users. New web proxy /api/edge/[id]/description GET that calls the Python route. EdgePanel rewritten to fetch on mount and render via MarkdownLatex; "Drawing the connection…" loading state during the first call. 4 new pytests (172/172 total).

(b) **"What's nearby" is now node-driven, not global.** Removed the SkillTreeView toggle, the `enableWhatsNearby` prop, the Adjacent2HopNode render path, and the "Further nearby" legend entry. Reverted /api/graph/me to its pre-Step-6 shape (1-hop only). Added a "Connected topics" section to NodePanel listing all 1-hop neighbors of the selected node (fetched from new /api/node/[id]/neighbors which returns nodes + edges with edge_kind, so we can label each row as "prereq" / "unlocks" / "related"). Each row click swaps NodePanel to that neighbor by id. Below the list, a "Highlight on canvas" link triggers SkillTreeView to add a forest ring around the selected node + its visible neighbors and fitView to fit them, auto-clearing after 4 seconds. SkillTreeView now wraps in ReactFlowProvider so the inner component can call useReactFlow().fitView. The `renderPanel` prop signature widened to receive `onHighlightNeighbors` so context-specific panels can opt in too.

Files added (this revision): supabase/migrations/20250028_edge_descriptions.sql, api/prompts/edge_description.py, api/routes/generate_edge_description.py, api/tests/test_generate_edge_description.py, web/app/api/edge/[id]/description/route.ts, web/app/api/node/[id]/neighbors/route.ts. Files modified: api/main.py, api/schemas.py, web/lib/pythonApi.ts, web/components/EdgePanel.tsx (rewrite), web/components/SkillTreeView.tsx (toggle/2-hop removed, highlight state + ReactFlowProvider added), web/components/NodePanel.tsx (Connected topics section + Highlight on canvas), web/app/api/graph/me/route.ts (reverted to 1-hop), web/app/skill-tree/page.tsx (dropped enableWhatsNearby prop).

Migrations 20250025, 20250026, 20250027, and 20250028 need to be pushed manually before testing: npx supabase db push --db-url <db-url>.

pytest 172/172, npm build clean.

Step 7 code done (manual validation pending) — Phase 10-rev Step 7 mobile polish. New `web/lib/useIsMobile.ts` (matchMedia hook keyed to Tailwind's `md` breakpoint, 767px). `/skill-tree` gets a list-view fallback below `md`: new `SkillTreeListView` (Your interests + Nearby sections; "Get a problem" on yours, "Add to my interests" via existing DialogModal on nearby; no EdgePanel/Connected-topics/Highlight-on-canvas per handover); new thin `SkillTreeShell` client wrapper branches `useIsMobile()` → ListView vs `SkillTreeView`. Stage 7 confirm (`ConfirmGraph.tsx`) gains an inline `ConfirmListView` mobile fallback rendering three sections (Your interests with Edit/Remove via `DialogModal` preNode + `DELETE /api/interest/[id]`; Foundations to refresh; Nearby — last two read-only); header copy + Back / "Your queue is ready →" CTAs unchanged. Targeted small fixes elsewhere: `ProblemView.tsx` Step 1 actions stack `flex-col` on mobile then `sm:flex-row` (Start working keeps `sm:flex-1`); `RequestBox.tsx` confirmation panel buttons got `flex-wrap` so Cancel can drop a line at 375px; `ProfileView.tsx` interest row stacks the Edit/Remove group below the title block on mobile; `layout.tsx` nav `gap-4 sm:gap-6` so the four nav links breathe at 375px. Survey stages 1-6 unchanged (already responsive via existing `sm:` rules). pytest unchanged (no API touched), `npm run build` clean (Next.js 16.2.6, 54 routes generated).

Validation outstanding before flipping the status to "Step 7 complete": (1) visual sweep at 375×667 in browser devtools across /daily, /notebook, /problem, /profile, /skill-tree, and all seven survey stages — watch for horizontal overflow, touch-target crowding, or broken-vs-merely-compact layouts; Stage 7 should swap to list view below 768px and back above. (2) Camera→upload→parse→review→submit on a real phone (LAN dev server or deployed preview); ProblemView already uses `<input type="file" accept="image/*" capture="environment" multiple>` so the camera primitive is right — what needs verifying is the upload-to-parse round trip end-to-end on a phone (EXIF orientation, image sizes, slow uploads being the fragile bits).

Step 8 in progress — Phase 10-rev Step 8: scope adjusted at entry. Sentry deferred to Phase 11-deploy (more useful once services are publicly deployed). Pre-walkthrough audit surfaced one blocker: curator-emitted refresher cards (`ref_id` = a node, not a `refresher_schedule.id`) fell through DailyView's "coming soon" placeholder — `surface_daily._resolve_refresher_content` only recognised the legacy refresher_schedule shape. Fixed via new click-time resolver: `POST /refresher-resolve` (api/routes/refresher.py) mirrors `/concept-review-resolve` — verifies kind='refresher' + ownership, tries refresher_schedule first then falls back to nodes; on the curator-style path it does a pool lookup at (topic_node_id, intent='refresh', difficulty=1) and inserts a fresh kind='problem' queue_items row on hit, or kind='concept_review' on miss so the user lands on the cached brief. Both legacy attempt/engagement paths now also insert fresh queue_items rather than returning the original 'done' queue_item_id (which would bounce off /problem). New web page /refresher/[queue_item_id] (server component, redirects on resolved kind); DailyView refresher branch unified to route through it. 9 new pytests. Cleanup pass: removed now-dead `subject_kind`/`subject_queue_item_id` fields from SurfacedItem schema + SurfacedQueueItem type + toItem mapping; deleted `_resolve_refresher_content` helper (140-line SQL chain through refresher_schedule → attempts/engagements → problems/papers → nodes); trimmed test_surface_daily.py (deleted test_refresher_resolved_to_content_title, slimmed two refresher tests). pytest 180/180, build clean. Doc once-over also applied: ARCHITECTURE.md route tree + deprecated-tables note (migration 20250016 dropped them); CLAUDE.md routes list + cache key + deprecated-tables note + phase list (Phase 10-rev + Phase 11-deploy added); curriculum-curator-design.md /update-queue clarification (deleted, not "superseded"); phase-10-rev-plan.md Step 8 entry expanded.

Step 8 remaining (user actions): persona-1 walkthrough on a fresh user (`POST /api/survey/reset` admin-gated to wipe + re-walk); fold in Step 7 manual validations (375×667 sweep + real-device camera→upload→parse round-trip) during the walkthrough; on success flip this status line to "Phase 10-rev complete. v2 ready for friends." Phase 11-deploy is the next phase entirely (FastAPI deploy + apply migration 20250024 cron + Vault secret/Postgres config + Sentry on both services).

Step 9 in progress — Phase 10-rev Step 9 emerged from two persona walkthroughs run pre-launch (Maya: neuroscience postdoc, out-of-scope math+comp+bio profile; Hank: quant taking semi-retirement, in-scope physics profile). Reports live under scripts/persona_walkthrough/ and scripts/persona_walkthrough_2/; consolidated work plan at scripts/persona_walkthrough/PLAN.md; handover at scripts/persona_walkthrough/HANDOVER.md. Step 9a done — three queue-items hygiene fixes: (a) /generate-problem dedups against existing pending/surfaced queue_items rows before unconditional insert (was the root cause of Hank's daily three containing the same problem at slots 1 and 3); shared helper find_pending_queue_item in api/curator_inputs.py used by both curator dispatch and generator; (b) surface-daily _pick_varied now tracks picked_ref_ids and skips duplicates with bounded-rounds-without-progress termination; (c) curator's _execute_add_refresher tries find_foundation_owning_subtopic before falling back to interest_node, with token-overlap matching (5-char-prefix stems so "energy"/"energies" both match) — synthetic test passes; live Sonnet output sometimes phrases subtopics in ways the matcher can't bridge, addressed upstream in Step 9c-iii. 5 new pytests (185/185 passing, was 180). Megagraph seed Slice 1 done: 8 v1-demoted interest node YAMLs under supabase/seeds/interests/ (PDEs, real analysis, complex analysis, Lagrangian mechanics, special relativity, EM-2, optics, QM-2) + idempotent loader scripts/seed_megagraph.py with --dry-run/--apply/--reclaim-slug, applied to live DB with created_by_user_id=NULL marking system-seeded rows; ARCHITECTURE.md had documented 8 v1-demoted interests as the migration outcome but none were in the DB — gap closed. Foundation rename migration 20250029 applied: calc-1/2, em-1, qm-1 renamed from Roman-numeral course-catalogue forms to descriptive titles indicating boundaries (e.g. "Quantum Mechanics: Wavefunctions, Operators, and the Hydrogen Atom"); slugs unchanged; docs/graph-design.md foundation table updated; api/prompts/add_interest.py:163 rewrite-summary example string updated. Stage 3 re-verified post-seed: Maya now gets 3 honest in-domain math suggestions (PDEs, complex analysis, real analysis) with content-grounded rationales naming "neural systems" and "dynamical systems theory"; Hank now gets 7 suggestions (was 3) with rationales naming "partition functions", "phase-transition singularities", "statistical field theory" — padding fallback no longer fires.

Step 9b done — the silent batched-edges-insert failure at api/routes/add_interest.py (was lines 451-456) that orphaned four interest nodes across the personas is fixed: edges now insert one row at a time, each wrapped in try/except _is_unique_violation with a logger.warning breadcrumb on the swallowed collision, so a duplicate (source,target) row no longer rolls the whole batch back (the bug fired whenever the resolved related_slug also appeared in Sonnet's proposed_prerequisite_slugs). The four orphans were reclaimed as seed YAMLs under supabase/seeds/interests/ (information-theory-neural-coding, dynamical-systems-neural-circuits, phase-transitions-critical-phenomena, renormalization-group-fixed-points) — descriptions/subtopics read off the live DB so the seeds match the existing Sonnet-generated content; loader --apply set created_by_user_id=NULL and backfilled 6 missing edges (info-theory already had its prereq edges). New test test_resolve_writes_edges_when_related_slug_overlaps_prereqs asserts the surviving edge is kept when the duplicate collides.

Step 9c done — three calibration items: (i) parser system prompt (build_parse_system_prompt) gains a denial-of-mastery rule: "I want to actually understand X" / "stop hand-waving X" / "understand X instead of just dropping the words" → teach, with consolidate scoped to users asserting existing mastery (Maya's dynsys case); (ii) Stage-3 padding fallback dropped entirely in suggest_survey_interests.py — the route now returns only Haiku-ranked suggestions rather than padding from the unfiltered shortlist with the false "Adjacent to the foundations you flagged" rationale (the free-text input is the safety net for thin in-domain pools); (iii) curator system prompt gains a line directing Sonnet to put the foundation node title in interest_node for foundation-skill refresher recs (partition functions → "Statistical Mechanics", not the interest the skill prepares the user for), the upstream complement to Step 9a's dispatch-layer matcher. 5 new tests across test_add_interest.py, test_suggest_survey_interests.py (new file), test_plan_queue.py — pytest 190/190 passing (was 185). With 9b + 9c landed, Phase 10-rev Step 9 is closed bar optional content.

Slice 3 done — operator content authoring complete. Authored 14 new interest YAMLs (3 chosen "unusual" picks: quantum-information, coding-theory-error-correction, computational-complexity; plus the 11 from the SEED_PROPOSAL target list: solid-state-physics, band-structure-electron-states, general-relativity, tensor-calculus-differential-geometry, signal-processing, fourier-analysis, digital-filter-design, superconductivity, chaos-and-nonlinear-dynamics, numerical-methods-pdes, probability-stochastic-processes) and reclaimed the 3 remaining user-created nodes (semiconductor-physics, gravitational-waves-ligo, cosmology-lambda-cdm) as seed YAMLs. The megagraph is now 42 nodes (13 foundation, 29 interest — all 29 seeded with created_by_user_id=NULL), 109 edges (76 prerequisite, 33 related), zero orphan interest nodes, and every domain clears the Stage-3 SUGGESTION_MIN=6 threshold (applied 7, math 7, physics 15). Added 7 interest↔interest "related" bridges for richer cross-pollination (semiconductor↔band-structure, fourier↔optics, signal-processing↔info-theory, signal-processing↔stochastic-processes, numerical-methods↔chaos, stochastic-processes↔chaos, tensor-calculus↔lagrangian) and dropped a stray gravitational-waves-ligo→cosmology prerequisite mis-curation. New read-only diagnostic scripts/megagraph_report.py snapshots node/edge/orphan/density state for ongoing curation. With Slice 3 landed, Phase 10-rev Step 9 is fully closed. Known balance note for a future pass: physics interests (15) outweigh math (7) and applied (7); next authoring should tilt math/applied.

Refresher routing follow-up (found in testing) ✓ fixed: refresher cards were mis-routing to the wrong foundation node via token-overlap false positives in find_foundation_owning_subtopic (a subtopic mentioning "phase" matched ODEs' "phase plane analysis"; a "...distribution" subtopic matched Probability). The added_reason stayed correct; only ref_id was wrong. Fixed in api/routes/curator.py (_execute_add_refresher now trusts an explicitly foundation-named interest_node per Step 9c-iii before consulting the matcher) and api/curator_inputs.py (a _OVERLOADED_PREFIXES stopword guard drops generic cross-domain tokens so a lone overloaded word can't bridge two unrelated foundations, while distinctive matches like "partition"→statistical-mechanics still resolve). 2 new tests; 192 passing (was 190).

**Phase 10-rev complete; Phase 10.5-rev opened.** The operator self-walkthrough (the real Next.js UI end-to-end, the in-app companion to the scripted persona walkthroughs) was Phase 10-rev's final validation gate. It surfaced 47 items — bugs, polish, and four feature requests — captured in docs/operator-walkthrough-notes.md (gitignored, local-only). Rather than reopen the otherwise-closed Phase 10-rev, these are tracked in a new bounded phase, **Phase 10.5-rev — pre-launch remediation** ([docs/phase-plans/phase-10.5-rev-plan.md](phase-plans/phase-10.5-rev-plan.md)), grouped into seven build sessions plus a features bucket. The plan restates every item so it stands alone (the walkthrough notes are not committed). Launch gating: the product's no-guilt/forgiving nature allows a soft launch while polish lands in parallel, so **Phase 11-deploy is gated only by the launch-blocking subset** (Steps 1, 2, 4 + the t4 bookmark bug), not all of 10.5-rev.

**Phase 10.5-rev Step 1 done — queue lifecycle & correctness.** Q1 resolved and written up in curriculum-curator-design.md §11.1/§11.4/§13.4: reroll re-surfaces the next pending items (no regen on click); the queue is bounded (hard cap 15, refill-on-drain when non-terminal stock drops below 6); duplicates are blocked at every write path; the F17 starter fallback now fires at most once (only for an account with zero queue rows), killing the duplicate-concept spam (d16/d15); cold-start seeds papers via propose-papers when the mode slider gives papers a meaningful share, fixing "no papers ever" (d17); refresher pool-miss generates a distinct refresh-intent problem instead of duplicating the node's concept brief (d5); orientation copy added to /daily (d1). The planner (curator.py) enforces the cap; surface-daily returns pending_remaining and the web layer fires a background refill on drain. 197 pytest passing (was 192); web typecheck + lint clean. Two non-blocking follow-ups carried to Step 2 (p1 ongoing paper-balance replenishment; p2 proportional propose-papers count).

**Phase 10.5-rev Step 2 done — refresher subsystem reframed (🔴 launch-blocking).** Resolution-model decision (operator-approved): a refresher is no longer a content *kind* resolved by a navigation side-effect; it is a *framing flag* (`via_refresher`) on a concrete `problem`/`concept_review`/`paper_engagement` item, resolved once at **creation** time. This dissolves the whole bug cluster rather than patching instances. Migration 20250030 adds `queue_items.via_refresher` and dismisses legacy non-terminal `kind='refresher'` rows (the planner re-creates them concretely). `api/routes/refresher.py` now exposes `resolve_refresher_to_content` (pool-first refresh problem → generate on miss → concept fallback; legacy refresher_schedule → problem/paper) + a `POST /create-refresher` HTTP wrapper; the click-time `/refresher-resolve` route and the `web/app/refresher/[id]` page are deleted. Creation sites wired: planner `_execute_add_refresher` and post-engagement `_execute_surface_prerequisite` (both thread `anthropic`), and the web `/api/queue/request` refresher branch (now returns the concrete kind). Fixes: **d2** titles resolve for free (concrete kinds); **d3** "Refresher" badge + revisit CTA via the flag, distinct from plain Concept cards, routing by real kind; **d4** opening never consumes (done-on-completion); **d18** prevent-at-source + graceful empty (resolver returns None → no dead row); **d20** in-paper popup restyled to the forest/paper family with motion tokens; **d21** `queueItemPath` helper routes problem/concept/paper correctly from OrientingConceptsPanel, NodePanel, RequestBox; **g2** parent lineage recorded for the paper back-link, queue-mediated round trip documented (deep node back-link rides Step 7 n2). Carried-over p1/p2 left for the curator/paper session (non-blocking). **Refresher-basis follow-up (caught in the reset-walk):** a cold-start queue showed a "Refresher / look at this again" on linear algebra the user had neither engaged nor marked — because the planner front-loaded a prerequisite as a `refresher`. Fixed by requiring a *basis* for refresher framing: `resolve_refresher_to_content` checks `user_node_states` (engagement_count>0, or state active/struggling/comfortable — the latter covers Stage-2 'refresh' marks and concept-tour familiarity) and, when absent, downgrades to **groundwork** (a plain `via_refresher=false` Concept orientation read, curator reason preserved) instead of a refresher; the planner prompt now also instructs Sonnet to emit `problem`/`teach` framed as groundwork for unmet prerequisites (resolver guard is the deterministic backstop). The web request route drops its own no-history special-case and delegates basis to Python. 199 pytest passing; web typecheck clean (pre-existing set-state-in-effect lint untouched). **Operator action: apply migration 20250030 (`npx supabase db push`), then reset-walk a fresh user to a refresher.** Also captured during the reset-walk and added to the Phase 10.5-rev features bucket (non-blocking, paper-sourcing pair): **fb2** — an "I can't find this paper" escape hatch (clears the uncompletable engagement from the queue, flags the operator to source it); **fb3** — a community PDF store (upload a found PDF so the next user who hits the same paper doesn't re-hunt; copyright caveat: scope to arXiv/open-access or operator-curated). Next: Phase 10.5-rev Step 4 (survey rendering & concept-tour bugs — the last 🔴 step before Phase 11-deploy gating).

**Phase 10.5-rev Step 4 done — survey rendering & concept-tour (🔴 launch-blocking).** Four items, diagnosed against the verbatim walkthrough output (t2 reproduced by adding *Cosmology & the Lambda-CDM Model*). **s5/s9** card truncation: dropped `line-clamp-2` from the foundation-tile and interest-suggestion explainer lines (it always truncated the foundation nodes' long comma-list descriptions). **t2 apostrophe** was a *seed-data* bug, not a renderer bug: `01_curriculum.sql` wrote the `subtopics` JSONB inside `$$…$$` dollar-quoting but used SQL `''` apostrophe-escaping, which is literal there — titles stored as "Newton''s", "Coulomb''s", etc. Migration 20250031 collapses `''→'` in `nodes.subtopics_json` (idempotent), and the six titles in the seed source are fixed. **t2 wrong prereqs** was *bad megagraph edges*, not a lookup bug — the tour correctly read the resolved node's own prereq edges; Cosmology's seeded prereqs wrongly included `electromagnetism-1` and omitted statistical mechanics. Operator chose "edges + tour granularity": migration 20250031 drops the EM edge and adds `statistical-mechanics` + `multivariable-calculus` prereqs plus a `general-relativity` *related* edge (cosmology YAML updated to match), **and** `_concept_tour` now takes tiles round-robin across prerequisites (foundations first) so one foundation's long intro list can't monopolise the tour. **s15** dedup over-fire: the cross-tour seen-set keyed on subtopic *name* alone and marked every *shown* tile seen; now node-scoped (`node_id:subtopic_key`) and records only tiles the user actually *answered* (§1.6.5 "unless the state was not captured"). 200 pytest passing (was 199); web typecheck clean. **Operator action: apply migration 20250031 (`npx supabase db push`), reload the web dev server, then reset-walk the survey through the concept tour to confirm s5/s9/t2/s15.** Only remaining 🔴 before Phase 11-deploy is **t4** (bookmark persistence) in Step 7.

**Phase 10.5-rev Step 7 done — skill tree & notebook (clears the last 🔴, t4).** **t4 root cause** was *not* the RLS-SELECT footgun (the bookmark route uses the admin client for read+write): node bookmarks were written to the `bookmarks` table, but the skill tree colours nodes purely from `user_node_states.state`, and nothing ever writes `state='bookmarked'` — the two notions were disconnected, so the bookmark never surfaced and re-clicking silently toggled it off. Fix (operator decision: **overlay flag**, keeping `bookmarks` as the single source of truth — bookmark is orthogonal to engagement state): `/api/graph/me` and the `/skill-tree` loader now read the user's `kind='node'` bookmarks, attach a `bookmarked` boolean per node, and fold bookmarked *adjacent* nodes into the rendered slice; SkillTreeView draws an amber dot overlay (legend entry added), NodePanel inits its toggle from the flag and `router.refresh()`es so the canvas updates live. A per-node `isUserNode` flag (interest **or** has-state) is threaded through so bookmark-only nodes still offer "Add / promote to interest". **t3** "struggling" is folded into "Active" (amber) across SkillTreeView/SkillTreeListView/ProfileView — three user-facing colours only (neutral/amber/forest), the internal red signal removed (no-guilt). **t1/t5** NodePanel actions retiered: a contextual promotion banner for nearby nodes, a primary engage pair (problem/paper), a quieter annotation pair (bookmark/comfortable), each with a one-line inline explainer (operator chose inline text over tooltip — works in the mobile list view). **n1/g1** the notebook gains a tab strip: **All** · a **Topics ▾** dropdown (by interest — operator chose by-interest) · **Come back to this**, the unified home (operator decision) for both bookmarked nodes and deferred items (`queue_items.state='deferred'`), each deferred row carrying topic badges, an inline read-only **Preview** of the problem statement/context, and a "Queue it now" manual resume (new `POST /api/queue/resume`, the inverse of defer). **Tab styling** went through a `/design` comparison: four candidate strips (wrapping pills, wrapping underline tabs, fixed-tabs-plus-dropdown, hidden-scrollbar scroll) added as an interactive `NotebookTabsOptions` demo under `/design → Notebook tabs`; operator picked the dropdown ("Option C"), which removed the original scrollbar entirely. Follow-up polish: the Topics trigger label truncates (`max-w-[14rem]`) and the notebook column widened to `max-w-3xl` so long interest titles can't overflow the strip. (The four-option `/design` demo is left in place for future tweaks.) **n2** "See in skill tree" (notebook come-back + ProfileView interest list) deep-links via `/skill-tree?node=<slug>`; the page resolves the slug to a rendered node id and SkillTreeView opens its panel (initial selection state, no set-state-in-effect) + fitViews to it. New routes: `/api/interest/list`, `/api/notebook/come-back`, `/api/queue/resume`. No API (Python) touched → **200 pytest still green**; web typecheck clean; no net-new lint vs HEAD baseline. No new migration (the `bookmarks` table already exists). **No operator migration needed; just reload the web dev server, then walk: bookmark a node → dot persists on return; check the notebook's Come back to this tab.** With t4 cleared, the launch-blocking subset (Steps 1, 2, 4, t4) is complete — **Phase 11-deploy is now unblocked.** Remaining 🟡 (Steps 3, 5, 6 + features bucket) can overlap the soft launch.

**Phase 10.5-rev Step 3 done — problem page presentation & template + queue-card topics (🟡).** Three operator-approved decisions at entry: enforce the template in **both** layers (render now + prompt for new rows) plus a Haiku content-preserving reformat of existing problems; **stored** `part_label` + chip for d10; d12 as a **prompt constraint**. Diagnosis (against the live DB) found two latent renderer bugs behind d6/d8 — `remark-gfm` was missing (GFM tables rendered as raw `| pipe |` text) and `ProblemView` styled no headings/tables/hr — and confirmed d9 empirically (parts numbered `(a)`/`1.`/"Part" inconsistently across the 24-problem pool). **Render layer** ([ProblemView.tsx](../web/components/ProblemView.tsx), [markdown.tsx](../web/lib/markdown.tsx)): added remark-gfm; one shared `READING_PROSE` styles `##`/`###`/`---`/tables/blockquotes + gives display equations breathing room (d8) with a mobile overflow guard; reordered to topic metadata line + serif title (d6, the page never even selected `problems.title`) → context **first/always-open** (d7) → statement → hints with **part-label chips** (d10); d13 answer-layout tip on the upload step. **Generation** ([prompts/problem.py](../api/prompts/problem.py)): canonical statement skeleton (context-first, `## Setup`/`## The problem`, bold `**(a)**` parts, display math, valid GFM tables); hints switched to structured `[{text, part_label}]` ([schemas.py](../api/schemas.py) `GeneratedHint`); d12 constraint — hints obey the same assumed-background dial as the statement, never introducing machinery the statement withheld. Migration 20250032 (`problem_hints.part_label`). **d22 (operator request, queue-card topics):** switched `SurfacedQueueItem` to `topics: string[]`; [queueHelpers.ts](../web/lib/queueHelpers.ts) `resolveTitles` rewritten to resolve topics for **all** kinds — problem (topic node), concept (the node), suggested_interest (the node), and **paper** via new `papers.topic_node_ids` (migration 20250033, GIN-indexed, populated by `/propose-papers` which now has the model map each paper to interest titles → node ids and unions them onto the shared paper row); [DailyView.tsx](../web/components/DailyView.tsx) renders a chip per topic, suppressing any equal to the title. **Backfill tool:** new [scripts/reformat_problems.py](../scripts/reformat_problems.py) (Haiku, `--dry-run`/`--apply`/`--id`/`--limit`) reformats existing problems to the template content-preservingly + backfills `part_label`, deleting test attempts to preserve the immutability invariant; validated on one problem in dry-run (correctly relocated a Cayley-1858 opener into `context_md` and labelled the hints by part). 201 pytest passing (was 200; added structured-hint + paper-topic-association tests); web typecheck + lint clean. **Operator actions: apply migrations 20250032 + 20250033, restart the web dev server (picks up remark-gfm), then run the reformat backfill (`--dry-run` → spot-check → `--apply`).** **Deferred (non-blocking):** user-added papers (`/ingest-paper-user`) carry no topic chip (only `/propose-papers` sets `topic_node_ids`) — graceful, optional Haiku-classify follow-up; existing queued papers won't show a chip until re-proposed. **s18 surfaced + parked for Step 6:** re-walking add-interest with "astrophysics" (→ resolved to *Stellar Evolution, Compact Objects & Accretion*) showed the concept tour surfacing Thermo/Stat-Mech/QM **prerequisite** subtopics, not the interest's own content — the screen promised a preview but delivered prereq calibration. Traced the calibration data flow (Q2 in the phase plan): the curator only reads node-level prereq state, never the tour's per-subtopic marks, so the 10-tile drill is over-collection. An **interim honesty copy fix** landed ([ConceptTour.tsx](../web/components/addInterest/ConceptTour.tsx) — "the groundwork X builds on", not "what will come up for X"); the structural redesign (preview the interest's own subtopics + node-level calibration + decide whether per-subtopic calibration survives + include topical SR/GR prereqs) is folded into **Step 6** (same surface as s12/s13/s14, ties to s17). Next 🟡: Step 5 (survey copy) or Step 6 (Stage-4 + s18 redesign), any order; Phase 11-deploy can proceed in parallel.

**Phase 10.5-rev closed; design-review round → Phases 12 & 13.** Rather than patch
the remaining 10.5 items (Step 5 survey copy, Step 6 Stage-4 + s18) in their old
shape, a design-review round (2026-06-08/09) stepped back and asked how onboarding
and the daily loop *should* work for the median friend — someone rebuilding rusty
physics/maths intuition. It reframed the work around *what signal the system needs
and when* (the three-legged learning loop: a light prior + frictionless in-flight
correction + slow engagement), and produced
[docs/orientation-and-calibration-design.md](orientation-and-calibration-design.md).
The remaining work reorganized into two forward phases: **Phase 12 — the responsive
daily loop** (card action set, the easier/harder/assume-less correction loop, the
curiosity box as an intent router, steering; the design doc's Part A) and **Phase
13 — conversational orientation** (a four-signal tutor, rich per-interest paths, the
§3.4 entry-point amendment, node-level calibration, the daily add-interest reshape;
Part B). Key decisions captured along the way: the survey is over-engineered vs. the
content model's own adaptation; collect only four signals (interests / altitude+path
/ node-level readiness / mode), not biography or subtopic drills; bookmark = a
polymorphic "save it, I'll manage the return," distinct from "not ready" (system
manages the return); the input box is a *router* not an add-interest box; requested
items are pinned+badged, not priority-ordered. The launch-gating framing (🔴/🟡,
soft launch) is **retired** — the app is finished before release; Phase 11-deploy
keeps its name but runs last, once the operator is happy (localhost until then).
Carried-over p1/p2 + the paper-chip backfill fold into Phase 12 Step 5.

**Phase 12 Step 5 follow-up — paper top-up cap clamp (2026-06-16).** `propose_papers` now also counts total non-terminal stock and returns early if `cap_room <= 0`; `target_count` is additionally clamped by `cap_room` so a papers-heavy topup after a full planner run can't push total non-terminal above 15 (§11.1). 243/243 pytest; tsc/build clean.

**Phase 12 Step 5 done — carry-in housekeeping; Phase 12 complete (2026-06-16).** Three carry-ins from earlier sessions, plus one preamble fix. (0) **Preamble fix**: `_resolve_and_queue_one_off` now returns `(None, node_title)` when a node is found but generation fails, so the topic_new handler gives an honest "try again" rather than "isn't in my library yet" — distinct from the truly-not-found case. Added a try/except around the inline generate step so a generation failure stays graceful rather than 500. (p2) **Proportional propose-papers count**: `ProposePapersRequest` gains `mode_balance`; the route computes `target_count = max(1, min(5, round(balance × 15) − pending_papers))` and early-exits if the queue is already at the paper target; the user prompt is parameterised on `target_count`; `pythonApi.ts` and `survey/complete` pass `modeBalance` through. (p1) **Paper balance on refill**: `_run_paper_topup` in `curator.py` runs propose_papers (SEPARATELY from the planner — the planner-no-papers rule is intact) after `plan_queue` + `check_deferred` inside `run_daily_planner`. Gated on `mode_balance >= 0.3`; best-effort (non-fatal try/except). Papers now replenish on drain, not just at cold-start. (paper-chip backfill) **Ingest topic classify**: `ingest_paper_user` runs a best-effort Haiku classify step after ingesting, matching the paper against the user's interest titles to set `papers.topic_node_ids`; user-added papers now show a topic chip on the queue card. 241/241 pytest; tsc/lint at baseline. **Phase 12 complete — Phase 13 is next.**

**Phase 12 Session 12.4b done — §A6 pinned/badged requests + §A5 steering chips (2026-06-14).** Two related pieces over the surfacing/reroll core.

**§A6 — Requested items pinned + badged.** New `pinned boolean NOT NULL DEFAULT false` on `queue_items` (migration 20250037, applied). `/generate-sibling` now writes `pinned=True` on every sibling row — the only source of pinned items for now; the curiosity-box router (Step 4c) will reuse the same column. `surface_daily` was split into two passes: `_load_pinned_surfaced` fetches `state='surfaced' AND pinned=True` items that survived the previous reroll (they stay surfaced rather than being reset to pending), then `_pick_varied` fills the remaining slots from the pending pool (with their ref_ids pre-committed to avoid duplicates). The reroll route loads `pinned` flags before acting: only non-pinned surfaced items are reset to pending; only non-pinned items get pass-over rows (pinned items aren't being passed over). `getOrSurfacePick`'s stale-pick reset also respects pinned. DailyView renders an amber-outlined "Requested" badge before the kind badge for pinned cards; the existing `added_reason` carries the first-person copy ("You asked for a more challenging version…").

**§A5 — Steering chips.** Optional `steer` / `steer_excluded_ref_ids` / `steer_topic_node_id` fields added to `SurfaceDailyRequest`. Python `_apply_steer()` runs before `_pick_varied` with four hints: `shorter` (time_high ≤ 20 min), `more_papers` (paper_engagement items stable-sorted to front), `different` (exclude passed-in ref_ids), `less_topic` (secondary `problems` query to find the topic's ref_ids, then filter). All hints fall back to the full pool rather than stranding the user. New `POST /api/queue/steer` Next.js route mirrors the reroll preamble (skip pinned, record pass-overs as curator signal) then calls `surfaceDaily` with the hint; `less_topic` passes `topic_node_id` from the client's resolved topics. DailyView shows a row of small chip buttons below the header: Shorter · More papers · Something different · Less [topic] (last one is dynamic — populated from the first non-pinned item that has resolved topics). `reshuffleCount` (incremented on every reroll or steer) combined with `pending_remaining === 0` triggers pool-thin honesty: the MoreComingCard is replaced with "That's about all that's queued right now — give it a moment, or ask for something specific below." Pinned items survive steering the same way they survive rerolls.

217 pytest passing (was 208; +9 new: 3 for pinned-surfaced logic, 1 for sibling-insert `pinned=True`, 5 for steer filters + fallback). tsc clean; lint net −1 warning (removed unused variable introduced in this session). **Operator action: migration 20250037 applied.**

**Phase 12 Step 3 follow-ups done (2026-06-14).** Three correctness fixes on top of 12.2: (1) **Sibling revert is now a real action** — new `POST /api/problem/[id]/revert-sibling` flips the too-hard sibling to 'superseded' and restores the original to 'pending' at priority 0.85 before navigating back; the rejected sibling no longer resurfaces. (2) **"Mark solid" writes a coherent node state** — `POST /api/profile/foundation-state` now upserts both `state` and `struggle_score` together (`solid → comfortable + 0.0`; `still learning → active + 0.3`) so the curator never sees a contradictory high-struggle/comfortable pair. (3) **Fit-feedback acknowledged** — `toast.success("Thanks — we'll factor that in.")` fires immediately on click so the button doesn't feel dead. tsc clean; lint baseline unchanged; 208/208 pytest.

**Phase 12 Session 12.2 done — the correction loop (Step 3).** The pre-start per-problem correction controls (easier / harder / explain-more / assume-less) are now live. Architecture: `POST /generate-sibling` (Python) fetches from the shared pool for easier/harder (`(topic_node_id, difficulty, intent)` key) or always generates fresh for assume-less (tagged `assume-less`, excluded from regular `cache_lookup` via `.not_.cs` filter). The original queue_item goes terminal via a new `'superseded'` state (migration 20250035); the sibling queue_item carries `parent_queue_item_id` pointing back. The ProblemView Step-1 "This version ▾" DropdownMenu (shadcn) triggers the swap and navigates to the sibling; if `parent_queue_item_id` is present (user followed a "harder" link), a "← Too hard? Back to the previous version" link is shown. Step-4 (Feedback) adds a compact "How did this feel?" fit-feedback row (Too easy · Too hard · Assumed too much) that fire-and-forgets `POST /fit-feedback` → writes `requested_easier/harder/assume_less` on the attempt for the curator to consume. Direct foundation-state editing: the Foundations section of the Profile is now interactive — "Mark solid" / "Still learning" buttons write `user_node_states.state` via `POST /api/profile/foundation-state`. 7 new pytest tests (208/208); web tsc clean; npm build clean; no new lint issues. Operator action: **apply migration 20250035** (`npx supabase db push`). Reset-walk: open a problem → "This version ▾" → "Harder" → sibling navigates in; original is superseded; "← Too hard?" link reverts; profile Foundations section buttons update state live.

**Phase 12 Session 12.1 done — card action set + polymorphic bookmark (Steps 1+2).**
The §A1 daily card now stays calm — primary CTA the hero, the from-the-card
judgments tucked behind an unobtrusive "···" overflow ([DailyView.tsx](../web/components/DailyView.tsx)),
each gated by kind and routed to a *distinct* curator signal: **I know this**
(problem-only, reuses the existing `/api/problem/[id]/skip` → `marked_refreshed`
+comfort), **Bookmark for later**, **Not for me**. This splits the previously
conflated comfort/skip button — the problem-page "Skip — I've got this" is
relabelled **"I already know this"** ([ProblemView.tsx](../web/components/ProblemView.tsx)),
the comfort half; "Not for me" is now its own negative signal. Fixed the
resolved-decision-6 smell: the suggested-interest "Not for me" handler wrote a
dismiss *through a route named `bookmark`*; it now hits a real **`/api/queue/dismiss`**
(`state='dismissed'` — the honest down-weight; cross-pollination already reads it
for suggested-interest domains). **Bookmark is now a polymorphic save** (§A2):
`/api/queue/bookmark` was repurposed from that dismiss-smell into a real save —
problem→`problem`, paper_engagement→`paper` (engagement→`paper_id` hop),
concept/suggested→`node` — writing a `bookmarks` row (the table's `kind` was
already polymorphic) and taking the queue item out of rotation via a **new
terminal `state='bookmarked'`** (migration 20250034; positive, distinct from
`dismissed`/`done`). The notebook's "Come back to this" tab ([come-back route](../web/app/api/notebook/come-back/route.ts) +
[notebook page](../web/app/notebook/page.tsx)) now renders all three bookmark kinds with
a kind badge; problem/paper bookmarks get **"Queue it now"** (new
**`/api/queue/requeue`**: flips `bookmarked`→`pending`, retires the bookmark via
`promoted_at`), nodes keep "See in skill tree". **Decisions:** "I know this"
scoped to problems this session (the only clean comfort path); "Not for me"
records `dismissed` but does *not* yet wire curator-side topic down-weight for
problem/paper — deliberately left tight (see backlog). **Verification:** pytest
201 green, tsc clean, lint no net-new findings (2 pre-existing in touched files),
`npm run build` clean with all three new routes registered, plus a service-role
functional walk on throwaway-and-deleted rows against the migrated live DB —
bookmark→come-back→requeue→dismiss state machine + the engagement→paper mapping
all green, the user's real queue untouched. **Operator action: migration
20250034 is already applied (operator confirmed); commit includes it.** Next:
Step 3 — the easier/harder/assume-less correction loop + direct foundation-state
editing.

---

# Reconciliation plan: v1 → v2 pivot

## Context

The product was redesigned mid-build. v1 was a plan-walking curriculum tutor with a static topic graph (`canonical_topics`/`canonical_edges`) and one-problem-per-day assignments driven by a generated `user_plans`/`plan_nodes` tree. v2 ([SPEC.md](../SPEC.md), [ARCHITECTURE.md](../ARCHITECTURE.md), [docs/graph-design.md](graph-design.md), [docs/personas.md](personas.md)) replaces the plan with an evolving **queue**, splits the topic graph into a **two-layer megagraph** (operator-curated foundation nodes + user-grown interest nodes, deduplicated and shared across the user base), and adds **paper engagement** as a first-class content mode alongside problems.

The repo currently contains:
- 7 applied migrations (`20250001`–`20250007`), seeding 21 canonical topics, 28 edges, ~30 context hooks, and a vision-parsing-ready `attempts` table.
- A Next.js app with survey → plan-review → daily-assignment flow wired end-to-end.
- A FastAPI service exposing only `/generate-problem` (with Haiku hook-matching + Sonnet generation + `llm_calls` logging).

No real user data exists yet — the pivot is structural, not data-preserving. The reconciliation is therefore a code-and-schema migration, not a data migration.

This plan answers six prompts (A–F) and lays out the phased execution order from `ARCHITECTURE.md → Build phases (revised)`, broken into per-step commits.

---

## A. Survives unchanged

These carry forward as-is; no schema or behaviour change required.

### Tables
- `profiles` — auth/identity unchanged.
- `problem_hints` — `(problem_id, level, text)` shape still matches v2's pre-generated-at-creation-time constraint.
- `context_hooks` — still used; v2 keeps the curated historical hooks. Note `related_topic_ids uuid[]` references rows that will be migrated into `nodes` (same UUIDs preserved — see section B), so the FK semantics survive even though the target table changes.
- `llm_calls` — schema is already what `ARCHITECTURE.md` calls for. Continue logging every Claude call here.

### Code
- [api/anthropic_client.py](../api/anthropic_client.py) — `call_json`, `log_llm_call`, pricing dict, retry-once-on-parse-failure pattern. Reused unchanged by all v2 routes.
- [api/config.py](../api/config.py), [api/auth.py](../api/auth.py), [api/supabase_client.py](../api/supabase_client.py) — internal-token auth and Supabase client factory.
- [api/difficulty.py](../api/difficulty.py) — `difficulty_for(curve, band)` still applies; v2 keeps difficulty bands per node.
- [api/prompts/hook_match.py](../api/prompts/hook_match.py) — hook-matching prompt unchanged.
- [web/proxy.ts](../web/proxy.ts) — Next.js 16 auth middleware. The pages it gates change, but the proxy itself doesn't.
- [web/lib/supabase/client.ts](../web/lib/supabase/client.ts), [web/lib/supabase/server.ts](../web/lib/supabase/server.ts) — Supabase client factories.
- [web/lib/markdown.tsx](../web/lib/markdown.tsx) — markdown+LaTeX rendering; v2 needs this in more places, not fewer.
- [web/app/signin/page.tsx](../web/app/signin/page.tsx), [web/app/api/auth/callback/route.ts](../web/app/api/auth/callback/route.ts) — auth flow.

### Seed data
- All 21 canonical topics (rows, slugs, descriptions, subtopics) and all 28 prerequisite edges — preserved as the seed for `nodes` and `edges` (see B and D).
- All ~30 context hooks (slugs, summaries, related-topic UUIDs) — survive untouched.

---

## B. Modified (column-level deltas)

### Tables

**`surveys`** — restructured for v2 onboarding (free-text intent + node ratings + comfort responses + mode-balance slider).

| Action | Column | Notes |
|---|---|---|
| DROP | `background_json` | Replaced by `free_text_intent` (single sentence). |
| DROP | `topic_states_json` | Replaced by `node_ratings_json` keyed by node slug. |
| DROP | `difficulty_curve` | v2 has per-problem easier/harder dial; no global curve. |
| KEEP | `id`, `user_id`, `created_at` | Unchanged. |
| ADD | `free_text_intent text` | Required. |
| ADD | `node_ratings_json jsonb` | `{node_slug: "interested" | "comfortable" | "refresh"}`. |
| ADD | `comfort_responses_json jsonb` | Open-ended question responses. |
| ADD | `mode_balance real` | 0.0 = all problems, 1.0 = all papers (interpretation needs confirmation — see F2). |
| ADD | `updated_at timestamptz default now()` | Required for the "revisit survey" flow personas mention. |

**`problems`** — pivot off the new graph, add immutability-by-versioning, paper-tied marker, pool status, time estimates, and the inline-context column.

| Action | Column | Notes |
|---|---|---|
| RENAME | `canonical_topic_id` → `topic_node_id` | FK target changes from `canonical_topics(id)` to `nodes(id)`. Same UUIDs after seed migration. |
| KEEP | `statement_md`, `solution_md`, `rubric_md`, `difficulty`, `context_hook_id`, `generated_context_md`, `generated_by_llm_call_id`, `created_at` | All survive. |
| ADD | `version smallint not null default 1` | Immutability via versioning. |
| ADD | `previous_version_id uuid references problems(id)` | Edit-history chain. |
| ADD | `tags text[] not null default '{}'` | For queue-side filtering and "requested subtopic" surfacing. |
| ADD | `paper_id uuid references papers(id)` | Non-null = paper-tied; excluded from generic pool reuse (CLAUDE.md). |
| ADD | `pool_status text default 'active'` | check in `('active','retired','flagged')`. |
| ADD | `time_estimate_minutes_low smallint`, `time_estimate_minutes_high smallint` | For the "why this" line on queue items. |
| RENAME | `generated_context_md` → `context_md` | Same column, cleaner name. No new column added. |
| MODIFY | The two partial unique indexes `problems_cache_key_with_hook` and `problems_cache_key_no_hook` must be rewritten to use `topic_node_id` and to exclude rows with `paper_id IS NOT NULL` (paper-tied problems aren't pool-reusable). |

**`attempts`** — add the three v2 user-control flags + sibling-chain link.

| Action | Column | Notes |
|---|---|---|
| KEEP | All existing columns from `20250001` and `20250007`: `id`, `user_id`, `problem_id`, `raw_image_paths`, `parsed_markdown`, `user_edited_markdown`, `hint_levels_used`, `parse_status`, `parsed_by_llm_call_id`, `submitted_at`, `created_at`. |
| DROP | `assignment_id` | No live data; dropped in step 4-rev.4 alongside the `daily_assignments` deprecation. Replaced by `queue_item_id`. |
| DROP | `attempts_one_per_assignment` unique constraint | Coupled to deprecated `daily_assignments`. |
| ADD | `queue_item_id uuid references queue_items(id)` | Replaces `assignment_id` as the link from an attempt to its queue context. |
| ADD | `marked_refreshed boolean not null default false` | Set by user via "mark as refreshed". |
| ADD | `requested_easier boolean not null default false` | Set at submit time. |
| ADD | `requested_harder boolean not null default false` | Set at submit time. |
| ADD | `parent_attempt_id uuid references attempts(id)` | For sibling-attempt chains after easier/harder requests. |
| ADD | `grade_response_md text` | Claude's dialogic response to the submission. Stored on `attempts` (not only in `notebook_entries`) so the problem-completion screen can show it without a cross-table join. |
| ADD | `disputed boolean not null default false` | Set by user if they disagree with the feedback; flagged for operator review in curation. |

### Code

**FastAPI service**
- [api/main.py](../api/main.py) — register all new route modules listed in section D.
- [api/routes/generate_problem.py](../api/routes/generate_problem.py) — change every reference to `canonical_topics`, `plan_nodes`, `surveys.difficulty_curve`. Inputs now arrive from the queue, not the plan. Lookups switch to `nodes`. Difficulty is derived from `user_node_states.struggle_score` + per-problem easier/harder request, not from a global curve.
- [api/prompts/problem.py](../api/prompts/problem.py) — minor: prompt still produces `(statement, solution, rubric, hints, context)` but is now parametrised on node title/description/subtopics from the `nodes` table.
- [api/schemas.py](../api/schemas.py) — add request/response models for every new endpoint (see D).

**Next.js app**
- [web/app/api/survey/route.ts](../web/app/api/survey/route.ts) — rewrite to write the new survey shape, call `/add-interest` for any free-text-derived interests, and seed `queue_items` instead of `user_plans`/`plan_nodes`.
- [web/app/survey/page.tsx](../web/app/survey/page.tsx) and [web/components/SurveyForm.tsx](../web/components/SurveyForm.tsx) — UI rewrite: free-text intent, node-rating step, comfort questions, mode-balance slider.
- [web/lib/dailyAssignment.ts](../web/lib/dailyAssignment.ts) — replaced by a new `surfaceDaily` helper that hits the queue, not `daily_assignments`. Existing race-safe-insert pattern is reusable.
- [web/lib/types.ts](../web/lib/types.ts) — replace `CanonicalTopic`, `CanonicalEdge`, `UserPlan`, `PlanNode`, `TopicState`, `TopicStateMap`, `SurveyPayload`, `DailyAssignment` with the v2 equivalents (`Node`, `Edge`, `QueueItem`, `SurfacedPick`, `UserNodeState`, `UserInterest`, etc.).
- [web/lib/pythonApi.ts](../web/lib/pythonApi.ts) — add typed wrappers for every new FastAPI route.
- [web/app/daily/page.tsx](../web/app/daily/page.tsx) — repurposed to show the three surfaced items rather than a single daily assignment.

---

## C. Deprecated

Kept briefly (no new writes) so the v1 seed history isn't lost; dropped in Phase 8-rev or later once the operator UI no longer references them.

### Tables (no new writes from Phase 4-rev onward; physical DROP later)
- `canonical_topics` — replaced by `nodes` (kind='foundation' for the 13, kind='interest' for the 8).
- `canonical_edges` — replaced by `edges` (edge_kind='prerequisite').
- `user_plans` — replaced by `queue_items` + `surfaced_picks`.
- `plan_nodes` — replaced by `queue_items`.
- `daily_assignments` — replaced by `surfaced_picks` (and `queue_items` for the underlying content).
- `pending_topic_requests` — **not listed in CLAUDE.md's deprecation list**, but it's the v1 mechanism for "user typed an extra topic during survey" and is fully superseded by `/add-interest` + autonomous dedup. See F5.

### Code to delete or rewrite end-to-end
- [web/app/api/plan/approve/route.ts](../web/app/api/plan/approve/route.ts) — entire route; no plan-approval flow in v2.
- [web/app/api/plan/adjust/route.ts](../web/app/api/plan/adjust/route.ts) — entire route.
- [web/app/plan/page.tsx](../web/app/plan/page.tsx) — entire page (the plan-review UI). Skill tree view in Phase 5-rev is functionally different (it's discovery, not review-and-approve).
- [web/lib/plan.ts](../web/lib/plan.ts) — `generatePlan(...)` graph-traversal helper. The queue is built by `/update-queue` (FastAPI), not by client-side BFS.
- [web/components/PlanGraph.tsx](../web/components/PlanGraph.tsx), [web/components/SkillTree.tsx](../web/components/SkillTree.tsx), [web/components/SkillTreeView.tsx](../web/components/SkillTreeView.tsx) — the v1 plan-graph components. v2's skill tree view (Phase 5-rev) uses React Flow + Dagre against `nodes`/`edges` with state from `user_node_states`. The old components don't carry forward.

---

## D. New (tables and code)

### Tables (Phase 4-rev migration)

```
nodes               foundation | interest, slug, title, description_md, domain,
                    difficulty_hint, subtopics_json, unlocks_text, pool_status,
                    created_by_user_id (null for foundations), created_at, updated_at

edges               source_node_id → target_node_id, edge_kind (prerequisite|related),
                    weight, created_at

user_node_states    user_id, node_id, state (unseen|bookmarked|active|struggling|comfortable),
                    engagement_count, struggle_score, last_engaged_at

user_interests      user_id, node_id, weight, added_via (survey|explicit_request|cross_pollination),
                    created_at

queue_items         user_id, kind (problem|paper_engagement|refresher|concept_review|suggested_interest),
                    ref_id (polymorphic), state (pending|surfaced|in_progress|done|skipped|dismissed),
                    priority_score, time_estimate_minutes_low/high, added_reason,
                    added_at, updated_at

surfaced_picks      user_id, queue_item_ids uuid[] (length 3 — see F8), surfaced_at,
                    replaced_at, chosen_item_id

papers              title, authors_json, year, arxiv_id (nullable unique),
                    doi (nullable unique), external_url, abstract_md, created_at

paper_engagements   user_id, paper_id, why_this_md, orienting_concepts_json,
                    questions_json, state, current_question_index, created_at,
                    updated_at, completed_at

paper_answers       engagement_id, question_id, user_response_md, claude_response_md,
                    submitted_at

paper_qa            engagement_id, turn_index, user_message_md, claude_response_md, created_at

notebook_entries    user_id, entry_kind (problem_attempt|paper_engagement), ref_id,
                    title, topic_node_slugs text[], created_at, updated_at  +  FTS index

bookmarks           user_id, kind (node|paper|problem|concept), ref_id_or_text,
                    created_at, promoted_at

refresher_schedule  user_id, subject_kind (attempt|engagement|concept),
                    subject_ref_id, due_at, surfaced_at

curation_proposals  kind (merge|split|rename|promote|demote|add_edge|deprecate),
                    payload_json, status (pending|approved|rejected|applied),
                    proposed_at, decided_at, decided_by

megagraph_snapshots label, snapshot_json, taken_at, taken_by (system|operator)
```

RLS: every per-user table (`user_node_states`, `user_interests`, `queue_items`, `surfaced_picks`, `paper_engagements`, `paper_answers`, `paper_qa`, `notebook_entries`, `bookmarks`, `refresher_schedule`) gates on `auth.uid() = user_id` like existing tables. `nodes`/`edges`/`papers`/`curation_proposals`/`megagraph_snapshots` are admin-or-read-all (RLS TBD per route).

### FastAPI routes (new modules under `api/routes/`)

| Route | Model | Purpose |
|---|---|---|
| `POST /generate-problem` | Sonnet | Existing — adapted to read from `nodes` instead of `canonical_topics`. |
| `POST /parse-solution` | Sonnet (vision) | **Not yet implemented** — Phase 4 step 1 in v1 plan only got as far as the migration. Phase 4-rev or 5-rev finishes this. See F6. |
| `POST /grade-solution` | Sonnet | Dialogic feedback (not graded). Writes to `attempts.grade_response_md` (column name TBD) and creates a `notebook_entries` row. |
| `POST /generate-paper-engagement` | Sonnet | Pre-generates why-this, orienting concepts, questions when paper enters queue. |
| `POST /grade-paper-answer` | Sonnet | Per-question dialogic response. |
| `POST /paper-question` | Sonnet | Free-form Q&A turn. |
| `POST /suggest-papers` | Haiku | Pool-ranker: scores relevance of papers already in `papers` against `user_interests`; pre-generates engagements; inserts `queue_items`. Does not propose papers not already in the pool. |
| `POST /propose-papers` | Sonnet | **Phase 7-rev step 2.** Propose papers from training knowledge: given user's interest nodes and recent engagement history, returns title/authors/year/arXiv ID or DOI/rationale for each candidate; results flow through the shared dedup helper before insertion into `papers`. Expands the pool that `/suggest-papers` then ranks. |
| `POST /surface-daily` | none (deterministic) | Picks 3 varied items from `queue_items` → writes `surfaced_picks`. |
| `POST /update-queue` | Haiku/Sonnet | Recompute priority, prune, add refreshers after each attempt/engagement. |
| `POST /add-interest` | Haiku (dedup) + Sonnet (generate) | The interest-add flow from graph-design.md. |
| `POST /generate-curation-report` | Sonnet | Weekly. Reads recent megagraph changes, produces `curation_proposals` rows. |
| `POST /compute-cross-pollination` | none (deterministic ranking) | Daily background; gated on first curation having completed. |

### Next.js API routes (new under `web/app/api/`)

`/api/queue` (GET surfaced items), `/api/queue/reroll`, `/api/queue/request`, `/api/queue/bookmark`, `/api/interest` (POST add new), `/api/graph/me`, `/api/graph/admin`, `/api/problem/[id]`, `/api/problem/[id]/submit`, `/api/paper/[id]`, `/api/paper/[id]/submit-answer`, `/api/paper/[id]/ask`, `/api/notebook`, `/api/admin/*`. `/api/upload/sign` stub is upgraded to real signed-URL issuance.

### Next.js pages
- `/daily` rewritten to show three surfaced items (was: single assignment).
- `/skill-tree` — new (Phase 5-rev). React Flow + Dagre.
- `/notebook` — new (Phase 5-rev/6-rev). List + read views with FTS.
- `/paper/[id]` — new (Phase 6-rev). Engagement UI with multi-session resume.
- `/admin/*` — new (Phase 8-rev). Curation review, megagraph view, snapshot management, cost dashboard.
- `/survey` UI rewritten for new survey shape.

---

## E. Recommended phase order (per ARCHITECTURE.md, broken into commit-sized steps)

Each step is one commit. The pivot-plan status line (top of this file) tracks the current step. Steps within a phase must land in order. Do not start phase N until the prior phase is committed and the status line is updated.

### Phase 4-rev — Graph migration & queue foundation

1. **`20250008_graph_schema.sql`** — create `nodes`, `edges`, `user_node_states`, `user_interests`, `bookmarks`, `curation_proposals`, `megagraph_snapshots`. Indexes + RLS.
2. **`20250009_queue_schema.sql`** — create `queue_items`, `surfaced_picks`, `refresher_schedule`. Indexes + RLS.
3. **`20250010_papers_schema.sql`** — create `papers`, `paper_engagements`, `paper_answers`, `paper_qa`, `notebook_entries` (with FTS index). Indexes + RLS.
4. **`20250011_modify_problems_attempts_surveys.sql`** — apply the column-level changes from section B to `problems`, `attempts`, `surveys`. Specifically: drop `attempts.assignment_id` and `attempts_one_per_assignment` constraint (no live data); add `queue_item_id`, `marked_refreshed`, `requested_easier`, `requested_harder`, `parent_attempt_id`, `grade_response_md`, `disputed` to `attempts`; rename `problems.generated_context_md` → `context_md`; add remaining `problems` columns; restructure `surveys`. Rewrite the two `problems_cache_key_*` partial unique indexes using `topic_node_id`.
5. **`20250012_seed_nodes_edges.sql`** — copy 13 canonical_topics → nodes (kind='foundation') and 8 → nodes (kind='interest'), preserving UUIDs so `context_hooks.related_topic_ids` still resolves; copy 28 canonical_edges → edges (edge_kind='prerequisite'); update `problems.topic_node_id` from the old `canonical_topic_id`.
6. **`20250013_deprecate_v1_tables.sql`** — leave `canonical_topics`, `canonical_edges`, `user_plans`, `plan_nodes`, `daily_assignments`, `pending_topic_requests` in place; revoke INSERT/UPDATE privileges (or add `comment on table … is 'DEPRECATED'` + a deferred-drop ticket). Don't drop yet — operator might want to introspect history.
7. **FastAPI `POST /add-interest`** — Haiku-dedup + Sonnet-generate (see graph-design.md). New module `api/routes/add_interest.py` + prompts.
8. **FastAPI `POST /surface-daily` + `POST /update-queue` (initial)** — deterministic surfacing logic; queue update is initially a no-op skeleton.
9. **Next.js: new survey UI** — rewrite `web/app/survey/page.tsx`, `web/components/SurveyForm.tsx`, `web/app/api/survey/route.ts`. Free-text intent → `/add-interest` calls; node ratings → seed `user_node_states`; mode-balance slider; comfort responses.
10. **Next.js: queue read endpoint** — `web/app/api/queue/route.ts` (GET surfaced items). `web/app/api/interest/route.ts` (POST add new).
11. **Next.js: daily-three page (mocked content acceptable)** — rewrite `web/app/daily/page.tsx`. Validates layout end-to-end with stub data.
12. **Delete deprecated code** — remove `web/app/api/plan/*`, `web/app/plan/page.tsx`, `web/lib/plan.ts`, `web/components/Plan*.tsx`, `web/components/SkillTree*.tsx`. Update [CLAUDE.md](../CLAUDE.md) once removed.
13. **Phase 4-rev acceptance** — new user signs up, completes new survey, megagraph populated with their interests, lands on `/daily` and sees three (mocked) items. Update status line.

### Phase 5-rev — Skill tree & graph-driven problem flow

1. **FastAPI `POST /parse-solution`** — vision route. Schema already in place from `20250007`. This is the unfinished v1 Phase 4 step.
2. **FastAPI `POST /grade-solution`** — dialogic feedback. Writes back to `attempts` and creates a `notebook_entries` row.
3. **FastAPI: refactor `/generate-problem`** — read from `nodes` not `canonical_topics`; tie to queue_item, not plan_node.
4. **Next.js: real problem flow** — `web/app/problem/[id]/page.tsx`, `web/app/api/problem/[id]/route.ts`, `web/app/api/problem/[id]/submit/route.ts`. Connects upload → parse → review → submit → grade → notebook.
5. **Next.js: "mark as refreshed"** — sets `attempts.marked_refreshed=true` and updates `user_node_states`.
6. **Next.js: notebook browse + read** — `web/app/notebook/page.tsx`, `web/app/notebook/[id]/page.tsx`, `/api/notebook` endpoint.
7. **Next.js: skill tree view** — `web/app/skill-tree/page.tsx`. React Flow + Dagre. `/api/graph/me` returns the user's slice + adjacent regions.
8. **Phase 5-rev acceptance** — real problem flow works end-to-end; user can browse skill tree. Update status line.

### Phase 6-rev — Paper engagement

1. **FastAPI: papers ingestion** — minimal `/admin/papers` ingestion endpoint (manual title/authors/arxiv_id entry; v2.1 will replace with live arXiv).
2. **FastAPI `POST /generate-paper-engagement`** — pre-generates why-this, orienting concepts, questions when a paper enters a user's queue.
3. **FastAPI `POST /grade-paper-answer`** — dialogic per-question response.
4. **FastAPI `POST /paper-question`** — free-form Q&A turn.
5. **FastAPI `POST /suggest-papers`** — background job; reads `user_interests`, produces paper candidates.
6. **Next.js: paper engagement UI** — `web/app/paper/[id]/page.tsx`, `/api/paper/[id]/*` routes. Multi-session resume on `current_question_index`.
7. **Next.js: notebook entries for papers** — extend the Phase 5-rev notebook to render paper engagements (questions, answers, Q&A turns).
8. **Phase 6-rev acceptance** — paper loop works including system-suggested papers. Update status line. NOTE: Two of the three SPEC.md paper discovery sources are absent from this acceptance: user-provided ingestion (planned in Phase 7-rev step 1) and adjacent surfacing (no planned phase — see Deferred). The "recent papers chosen for you" claim in SPEC.md's lede is not yet true; see F16 and the Deferred section.

### Phase 7-rev — Adaptation, refreshers, cross-pollination

1. **Next.js + FastAPI: user-provided paper ingestion** — Implements SPEC.md paper discovery source 2: "Paste an arXiv URL, DOI, or title. System ingests." New Next.js route `/api/paper/ingest` accepting a URL, DOI, or bare title from a UI affordance in the daily view or paper section. Resolution strategy: arXiv URL/ID → arXiv export API (`export.arxiv.org`, no auth); DOI → CrossRef API (`api.crossref.org`, no auth); bare title → `ILIKE` against `papers.title` then title-only insert if no match. Promote the existing `/admin/ingest-paper` dedup logic into a shared helper callable from both the admin and user-facing routes. On success, immediately queues a `paper_engagement` for the user. Without this step, the "recent papers chosen for you" claim in SPEC.md is not true — system-suggested papers depend on operator-ingested content and Claude's training knowledge (cutoff ~August 2025). Also verify at this step that the empty-queue fallback from F17 is in place.
2. **FastAPI `POST /propose-papers`** — Implements SPEC.md paper discovery source 1 for the training-knowledge mechanism. Sonnet is given the user's interest nodes and recent engagement history and proposes candidate papers from its training knowledge: title, authors, year, arXiv ID or DOI if known, and a one-line rationale. Each proposed paper flows through the shared dedup helper from step 1 before insertion into `papers`, so a paper Claude proposes that already exists is not duplicated — the existing row is reused. **Runtime relationship with `/suggest-papers`:** `/propose-papers` expands the pool (new titles into `papers`); `/suggest-papers` selects from the pool (ranks existing `papers` rows against user interests). They are complementary, not overlapping. `/propose-papers` fires per-user on a background trigger (after `/add-interest` or on a periodic schedule); `/suggest-papers` then ranks the expanded pool for that user. Dedup at ingestion time ensures no duplicate `papers` rows regardless of which discovery source proposed a title first.
3. **FastAPI: real `/update-queue`** — after each attempt/engagement, recompute `priority_score`, retire done items, add refreshers to `refresher_schedule`. Fix the `/suggest-papers` pre-filter (F16) before or as part of this step.
4. **FastAPI: `user_node_states` recomputation** — engagement_count, struggle_score, state transitions (unseen → active → struggling/comfortable).
5. **FastAPI: refresher surfacing** — refresher items inserted into queue based on `refresher_schedule.due_at`.
6. **Next.js: explicit request flow** — `/api/queue/request` (user typing "give me more X").
7. **FastAPI `POST /compute-cross-pollination`** — daily background; produces `suggested_interest` queue items. Gated on first curation having completed.
8. **Phase 7-rev acceptance** — user-provided paper ingestion works; propose-from-knowledge expands the pool automatically; queue feels responsive; cross-pollination quietly surfaces. Update status line.

### Phase 8-rev — Weekly curation & operator surfaces

1. **FastAPI `POST /generate-curation-report`** — weekly; reads `nodes`/`edges` deltas, autonomous dedup decisions, engagement signals; writes `curation_proposals` rows.
2. **Next.js: admin proposal review UI** — `web/app/admin/curation/page.tsx`. Approve/reject/apply.
3. **Next.js: operator megagraph view** — `web/app/admin/megagraph/page.tsx`. Full graph render, layer toggles, time scrubber over `megagraph_snapshots`.
4. **Snapshot job** — write `megagraph_snapshots` row after every curation round.
5. **Cost dashboard** — `web/app/admin/costs/page.tsx`. Reads `llm_calls`.
6. **Drop deprecated tables** — finally remove `canonical_topics`, `canonical_edges`, `user_plans`, `plan_nodes`, `daily_assignments`, `pending_topic_requests`.
7. **Phase 8-rev acceptance** — operator runs curation; megagraph is maintainable. Update status line.

### Phase 9-rev — Polish

1. ~~Design-system pass on every surface.~~ **Done early** (interstitial session between Phase 5 and Phase 6). All pages and components use design tokens; CLAUDE.md documents the system.
2. Mobile polish (queue/notebook are mobile-relevant; skill tree probably desktop-only).
3. Error monitoring (Sentry or similar).
4. Phase 9-rev acceptance — v2 ready for friends.

### Deferred (v2.1+)

**Operator-only ingestion until Phase 7-rev step 1.** Paper ingestion is operator-only (`/admin/ingest-paper`) until user-provided ingestion ships. Between Phase 6-rev and Phase 7-rev step 1, there is no path for users to add papers they found themselves.

**Three paper-discovery mechanisms — keep them named and distinct.** SPEC.md § Paper discovery lists three sources; they land in different phases and must not be conflated:
1. **Propose-from-knowledge (`/propose-papers`)** — Sonnet proposes titles from its training knowledge; ships in Phase 7-rev step 2. Bounded by training cutoff (~August 2025). Genuinely recent papers (post-cutoff) are not reachable by this mechanism.
2. **User-provided (`/api/paper/ingest`)** — user pastes an arXiv URL, DOI, or bare title; ships in Phase 7-rev step 1. User-initiated; resolves a resource the user already has. Compensates for the training cutoff on any paper the user can name.
3. **Live search (v2.1)** — background job querying arXiv/Semantic Scholar APIs without user action; deferred. The only mechanism that proactively surfaces post-cutoff papers without user involvement. Not the same as user-provided ingestion.

**Adjacent surfacing (no planned phase).** SPEC.md paper discovery source 3 — "Papers mentioned in other papers' engagements, or referenced in problem context, become bookmarks or suggestions" — is not planned in any current phase. It requires the engagement-generation prompt to surface paper references and a mechanism to materialise them as bookmarks. This discovery source is absent from v2 and deferred to v2.1 at earliest.

**SPEC.md claim status (revised).**
- *"System-suggested. Claude proposes papers based on the user's interests and recent work."* (§ Paper discovery, source 1) — **Accurate after Phase 7-rev step 2.** The mechanism is `/propose-papers` (Sonnet, training knowledge). `/suggest-papers` alone is a pool-ranker and does not satisfy this claim on its own.
- *"For v2, Claude proposes from its training knowledge."* (§ Paper discovery, closing sentence) — **Accurate after Phase 7-rev step 2.**
- *"The papers are recent and chosen for you"* (lede, first paragraph) — "chosen for you" via training-knowledge proposal is **accurate after Phase 7-rev step 2**. "Recent" is not guaranteed: training-knowledge proposals are bounded by cutoff (~August 2025), so post-cutoff papers are unreachable. The full claim holds only after Phase 7-rev step 1 (user-provided ingestion) or v2.1 live search. Do not correct the SPEC lede — it describes the intent — but do not use it as a launch claim until Phase 7-rev step 1 ships.
- *"User-provided. Paste an arXiv URL, DOI, or title. System ingests."* (§ Paper discovery, source 2) — **Not true until Phase 7-rev step 1.**
- *"Adjacent surfacing. Papers mentioned in other papers' engagements..."* (§ Paper discovery, source 3) — **No planned phase; see above.**

**Paper request via RequestBox should trigger `/propose-papers` for niche topics.** Currently `POST /api/queue/request` with `kind_hint="paper"` only calls `/suggest-papers`, which ranks papers already in the `papers` table. For niche or novel topics the pool will be empty and the user sees "check back soon" with nothing actually added. The fix: when `kind_hint="paper"` and `resolvedNodeId` is available, call `/propose-papers` first (to expand the pool with Sonnet-proposed titles for that specific node) before calling `/suggest-papers` to rank and queue. Optionally, if no existing `user_interest` covers the resolved node, add it (same as the explicit-request flow does today). This ensures "paper on Fourier series" always returns something rather than silently no-oping. Deferred to a v2.0 polish step; implement before launch.

**Bespoke D3 megagraph visualisation, notebook calendar view, return-after-absence prompts, BYO API key, notebook export, hand-authored problems, per-user difficulty calibration.** Unchanged from ARCHITECTURE.md deferred list.

---

## F. Design decisions log

Items resolved before implementation started. Deferred items are flagged with the step where they must be decided.

### Resolved

**F1 — `attempts.assignment_id`:** Drop it outright in step 4-rev.4 (no live data to preserve). Replace with `queue_item_id uuid references queue_items(id)`. The `attempts_one_per_assignment` unique constraint drops with it. Section B updated accordingly.

**F2 — `surveys.mode_balance` direction:** `0.0` = all problems, `1.0` = all papers. Matches the lexical ordering of `queue_items.kind`.

**F3 — Dialogic-grading storage:** `grade_response_md text` and `disputed boolean` live on `attempts` (not only in `notebook_entries`). Rationale: the problem-completion screen fetches the attempt row anyway; adding a cross-table join through `notebook_entries` just to show feedback is unnecessary. `notebook_entries.ref_id` still points at the attempt, so the notebook can surface the response without any schema change. Section B updated accordingly.

**F4 — `context_md` vs `generated_context_md`:** Rename `generated_context_md` → `context_md` in step 4-rev.4. No second column added. Section B updated accordingly.

**F5 — `pending_topic_requests` deprecation:** Confirmed deprecated. Added to the step 4-rev.6 DROP list alongside the other v1 plan tables.

**F6 — Vision parsing phase placement:** `/parse-solution` ships in Phase 5-rev step 1, not Phase 4-rev. Phase 4-rev's daily-three page uses mocked content per ARCHITECTURE.md's deliverable wording.

**F7 — Paper dedup key when no `arxiv_id`/`doi`:** Add a unique constraint on `external_url` for the non-null case; fall back to `(lower(title), year)` as a soft duplicate check for the no-identifier case. Implement in step 6-rev.1.

**F8 — `surfaced_picks` with fewer than 3 eligible items:** Relax to `length ≤ 3`. Surface 1 or 2 with a "more coming" placeholder rather than blocking surfacing entirely. Implement in step 4-rev.8.

**F11 — `paper_engagements.questions_json` schema:** `[{id: uuid, kind: 'comprehension'|'critical'|'connective', prompt_md: string, order: int}]`. Claude generates this array in `/generate-paper-engagement`; `paper_answers.question_id` references the `id` field. Implement in step 6-rev.2.

**F12 — Hint click logging:** Server-side. `attempts.hint_levels_used` (already a `smallint[]`) is written each time a hint is opened via the problem API, not only at submit. Implement in step 5-rev.4.

**F13 — Timezone handling:** `refresher_schedule.due_at` stored as `timestamptz`; resolved against the user's IANA timezone. Add `profiles.timezone text` column in step 4-rev.1 (alongside the `nodes` schema migration is fine). Implement surfacing resolution in step 7-rev.5 (refresher surfacing; renumbered from 7-rev.3 by the addition of user-provided ingestion as step 7-rev.1, then again from 7-rev.4 by the addition of `/propose-papers` as step 7-rev.2).

**F14 — Race-safety on `/add-interest` dedup:** Unique constraint on `nodes.slug` (enforced in step 4-rev.1). On slug-collision at insert time, fold the collision into a `curation_proposals` merge row rather than erroring. Implement in step 4-rev.7.

**F15 — `subtopics` → `subtopics_json` rename:** Confirmed. The `nodes` table uses `subtopics_json` to match the `_json` suffix convention on jsonb columns throughout ARCHITECTURE.md. Implement in step 4-rev.1.

### Deferred (must be decided before the blocking step)

**F9 — `queue_items.ref_id` type-by-kind mapping.** Resolved (pinned for step 4-rev.8):

| kind | ref_id → |
|---|---|
| `problem` | `problems(id)` |
| `paper_engagement` | `paper_engagements(id)` |
| ~~`refresher`~~ | **Retired in Phase 10.5-rev Step 2.** Refreshers are no longer a queue kind; they are concrete `problem`/`concept_review`/`paper_engagement` rows carrying `via_refresher=true`, resolved at creation time. |
| `concept_review` | `nodes(id)` |
| `suggested_interest` | `nodes(id)` |

`ref_id` is nullable (some queue item kinds could in principle be content-free placeholders), but in practice all five kinds above populate it.

**F10 — What user action writes `user_interests` with `added_via='cross_pollination'`.** Cross-pollination produces a `suggested_interest` queue item. The follow-on write to `user_interests` must be triggered by a specific user action (accept / first engage / bookmark → promote). Decide the trigger and whether `dismissed` items should also write a row (with a different state) before implementing step 7-rev.6.

**F16 — `/suggest-papers` unbounded candidate set.** The current implementation loads all `papers` rows (`SELECT id, title, abstract_md`) and passes full abstracts to Haiku for relevance scoring. This is the same unbounded-candidate-set problem as the dedup flow in `/add-interest`, which we deliberately pre-filtered with a Postgres trigram/LIKE step before the Haiku call. The fix: before the Haiku call in `/suggest-papers`, run a Postgres pre-filter — `WHERE to_tsvector('english', title || ' ' || coalesce(abstract_md, '')) @@ websearch_to_tsquery('english', <interest_titles_concatenated>)` (or `ILIKE ANY (ARRAY[...])` as a simpler fallback), limited to 20 rows. This caps Haiku input at O(20) regardless of pool growth and mirrors the pattern already in the dedup flow. Implement as part of Phase 7-rev step 3 (real `/update-queue`, which calls `/suggest-papers` as a follow-on action).

**F17 — New-user empty-queue fallback.** F8 addresses fewer-than-3 eligible items but not a fully empty queue. A new user whose `/add-interest` calls all fail (network error, prompt failure), or who completes the survey with no free-text intent, could reach `/daily` with zero queue items. The `/add-interest` flow is the primary defence — it synchronously inserts a starter problem or paper per interest when called from survey submission. Secondary fallback: if `queue_items` is empty at surfacing time, insert one `concept_review` queue item pointing to a foundation node matching the user's interests (or the calculus foundation node if no interests exist). This requires no LLM call and creates a non-empty queue. Verify during Phase 7-rev step 1 that this fallback is in place; it may already be partially covered by the Phase 4-rev skeleton but should be tested explicitly on a fresh account with forced `/add-interest` failure.
