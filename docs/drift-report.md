# Drift Report — office-hours v2

Generated: 2026-05-17. Source of truth: SPEC.md, ARCHITECTURE.md, docs/graph-design.md, docs/personas.md, docs/pivot-plan.md, docs/phase-plans/phase-8-rev-plan.md.

## Status legend

| Status | Meaning |
|--------|---------|
| `todo` | Not yet addressed |
| `in-progress` | Currently being worked on |
| `done` | Fixed or implemented |
| `deferred` | Acknowledged; intentionally postponed to a later phase |
| `dismissed` | Won't fix — reason recorded in the Notes column |

## Severity legend

| Severity | Meaning |
|----------|---------|
| `missing` | Spec says it should exist; it doesn't yet |
| `diverged` | Exists but behaves differently than spec'd |
| `contradicts` | Violates a core philosophy or persona constraint |

## Findings

| # | Area | Finding | Severity | Status | Notes |
|---|------|---------|----------|--------|-------|
| 1 | Queue / Daily | Cards show a static fallback reason ("A problem is ready for you.") instead of a dynamically generated "why this" tied to the user's interests or recent work | `diverged` | `todo` | Conflicts with SPEC.md §Daily experience — "Brief 'why this'…" |
| 2 | Queue / Daily | Cards show no item title (problem statement title or paper title) — only the mode badge and reason string | `diverged` | `todo` | Conflicts with SPEC.md §Daily experience — "Title and short description." |
| 3 | Queue / Daily | `concept_review` queue items render a "coming soon" placeholder; the click-through is not implemented | `missing` | `todo` | Conflicts with ARCHITECTURE.md §Queue — `kind` enum includes `concept_review` as surfaceable content |
| 4 | Queue / Daily | Reroll swaps the item but the event is never recorded and never feeds back into `/update-queue` priority reweighting | `missing` | `todo` | Conflicts with SPEC.md §Daily experience — "Repeated rerolls … adjust future queue composition." |
| 5 | Queue / Daily | `POST /api/queue/request` with `kind_hint="paper"` silently returns nothing for topics not yet in the `papers` table instead of triggering `/propose-papers` | `diverged` | `todo` | Conflicts with SPEC.md §Daily experience — "Find me a paper on [topic]"; docs/pivot-plan.md Deferred note - should bring back into v2|
| 6 | Onboarding / Survey | `web/app/survey/page.tsx` uses `bg-white` instead of `bg-background` (`#FAF7F0`) | `contradicts` | `done` | Conflicts with CLAUDE.md §Colour tokens — `--background` used for all page backgrounds |
| 7 | Onboarding / Survey | Comfort-calibration step is entirely absent; `SurveyForm.tsx` submits `comfort_responses: {}` hardcoded as empty | `missing` | `todo` | Conflicts with SPEC.md §Onboarding step 3 — "Comfort calibration." |
| 8 | Onboarding / Survey | Step 1 presents a flat list of nodes rather than an interactive skill-tree exploration view | `diverged` | `todo` | Conflicts with SPEC.md §Onboarding step 2 — "Skill tree exploration … users click around and mark nodes." |
| 9 | Onboarding / Survey | After submission the app redirects to `/daily` with no confirmation of which interests were created or deduplicated | `diverged` | `todo` | Conflicts with SPEC.md §Adding an interest — "brief confirmation"; docs/graph-design.md §Deduplication |
| 10 | Skill Tree | `NodePanel` omits `unlocks_text` ("unlocks: X, Y, Z") and the user's problem/paper history on the node | `diverged` | `todo` | Conflicts with docs/graph-design.md §User-facing skill tree view |
| 11 | Skill Tree | Panel offers only "Get a problem" and "Add to my interests"; bookmark, mark-comfortable, and request-paper affordances are absent | `missing` | `todo` | Conflicts with docs/graph-design.md §User-facing skill tree view — "request problem, request paper, mark as bookmark, mark as comfortable." |
| 12 | Skill Tree | Clicking an edge does nothing; no relationship type is shown | `missing` | `todo` | Conflicts with docs/graph-design.md §User-facing skill tree view — "Click an edge: shows the relationship." |
| 13 | Skill Tree | No "what's nearby?" affordance to expand the visible adjacent region beyond one hop | `missing` | `todo` | Conflicts with docs/graph-design.md §User-facing skill tree view — "'what's nearby?' prompt expands the region." |
| 14 | Skill Tree | Skill-tree server component uses the service-role client for regular-user reads, leaking admin privilege scope into a user-facing route | `diverged` | `todo` | Conflicts with docs/phase-plans/phase-8-rev-plan.md §Risks — "Do not use [admin client] for non-admin reads." |
| 15 | Admin Curation | Admin nav bar includes a "Users" link not in the phase-8-rev-plan §D10 spec; the plan document was not updated | `diverged` | `dismissed` | Conflicts with docs/phase-plans/phase-8-rev-plan.md §D10 — nav lists "Curation \| Megagraph \| Costs" only. Decided to add as a new feature. |
| 16 | Admin Curation | Megagraph node click panel does not show aggregate `engagement_count` across users | `missing` | `todo` | Conflicts with docs/phase-plans/phase-8-rev-plan.md §Step 3 — "total `engagement_count` across users." |
| 17 | Admin Curation | Cost dashboard "Full log" slices to 50 rows with no page-navigation UI | `diverged` | `todo` | Conflicts with docs/phase-plans/phase-8-rev-plan.md §Step 5 — "paginated table (50 rows per page)." |
| 18 | API Routes | `suggest_papers.py` pre-filters on `interest_titles[0]` only instead of `ILIKE ANY(ARRAY[...])` across all titles | `diverged` | `done` | Conflicts with docs/pivot-plan.md §F16 — full ILIKE ANY across all interest titles, capped at 20 rows |
| 19 | API Routes | `update_queue.py` recomputes node state only on `attempt_submit`; completing a paper engagement does not update `user_node_states` | `missing` | `done` | Conflicts with ARCHITECTURE.md §Engaging with a paper step 5; SPEC.md §Adaptation |
| 20 | API Routes | `compute_cross_pollination.py` cooldown uses `added_at >= cutoff` only; a dismissed suggestion doesn't block re-suggestion of a different node in the same week | `diverged` | `done` | Conflicts with docs/graph-design.md §Cross-pollination — "hold off on similar suggestions for a while." |
| 21 | API Routes | `add_interest.py` handles `same`/`related`/`new` only; `split` and `vague` verdicts fall through silently to the `new` branch | `diverged` | `done` | Conflicts with docs/graph-design.md §Deduplication; ARCHITECTURE.md §Adding an interest |
| 22 | API Routes | `ingest_paper_user.py` does not deduplicate on `(user_id, paper_id)` before generating an engagement; re-submitting the same URL creates a duplicate | `diverged` | `done` | Conflicts with ARCHITECTURE.md §Generating a paper engagement — "dedupe by arxiv_id / doi / title." |
| 23 | API Routes | `suggest_papers.py` and `propose_papers.py` can both insert duplicate queue items for the same engagement if called concurrently | `diverged` | `done` | Conflicts with ARCHITECTURE.md §Queue — single-item-per-engagement-per-user; docs/pivot-plan.md §update_queue dedup step |
| 24 | Problem Page | Problem page has no key-concepts / equations-needed preamble before the problem statement | `missing` | `deferred` | Phase 10 — polish-notes intake 2026-05-17 |
| 25 | Problem Page | Generated problems often exceed 3 sub-questions; should be capped | `diverged` | `deferred` | Phase 10 — polish-notes intake 2026-05-17 |
| 26 | Problem Page | Hints don't clearly map to individual sub-questions; sometimes rendered out of order | `diverged` | `deferred` | Phase 10 — polish-notes intake 2026-05-17 |
| 27 | Problem Page | No "this is too hard" action on the problem page with meaningful follow-through | `missing` | `deferred` | Phase 10 — polish-notes intake 2026-05-17 |
| 28 | Problem Page | No problem-level feedback affordance (like / dislike / flag issue) | `missing` | `deferred` | Phase 10 — polish-notes intake 2026-05-17 |
| 29 | Paper Page | Paper context paragraph written in 3rd person ("addresses the reader's interest…") instead of addressing the user directly | `diverged` | `deferred` | Phase 10 — polish-notes intake 2026-05-17; requires prompt fix in `generate_paper_engagement` |
| 30 | Paper Page | Paper page does not display the abstract | `missing` | `deferred` | Phase 10 — polish-notes intake 2026-05-17 |
| 31 | Paper Page | Missing from paper page: citation count, how-to-find instructions, SciHub suggestion, and "I cannot find this paper" option | `missing` | `deferred` | Phase 10 — polish-notes intake 2026-05-17 |
| 32 | Paper Page | No paper-level feedback (like / dislike / flag) or difficulty actions (too hard, mark comfortable) | `missing` | `deferred` | Phase 10 — polish-notes intake 2026-05-17 |
| 33 | Notebook | Completed paper engagements are not saved to `notebook_entries` | `missing` | `deferred` | Phase 10 — polish-notes intake 2026-05-17; spec requires notebook to capture all completed work |
| 34 | Notebook | Notebook cards show minimal information; no tab-by-topic view | `diverged` | `deferred` | Phase 10 — polish-notes intake 2026-05-17 |
| 35 | Skill Tree | Transitive edges clutter the graph (A→C shown even when A→B→C already exists) | `diverged` | `deferred` | Phase 10 — polish-notes intake 2026-05-17 |
| 36 | Queue / Daily | Daily page has no explainer for new users about what the queue is or what item types mean | `missing` | `deferred` | Phase 10 — polish-notes intake 2026-05-17 |
| 37 | Queue / Daily | Queue cards should show item difficulty; time estimate display removed by S7 fix | `missing` | `deferred` | Phase 10 — polish-notes intake 2026-05-17 |
| 38 | Admin | Admin users page layout shifts in width when a user row is expanded | `diverged` | `deferred` | Phase 10 — polish-notes intake 2026-05-17 |

## Spirit and intention gaps (personas.md)

Gaps in tone, framing, or product feel derived from the three persona journeys — not explicit spec violations, but places where the current implementation would break or cheapen the intended experience.

| # | Area | Finding | Severity | Status | Notes |
|---|------|---------|----------|--------|-------|
| S1 | Paper Engagement | Returning to an in-progress paper engagement does not show progress state — which questions remain and where the user stopped | `missing` | `todo` | Persona 2: "the multi-session resume worked well — they came back, the system showed where they were" (personas.md §Paper-follower, weeks 1–2) |
| S2 | Paper Engagement | Orienting concepts (`context_hooks`) appear to be rendered as static text with no affordance to branch into a refresher for an unrecognised term before starting the paper | `missing` | `todo` | Persona 1: "The Meissner effect they didn't recognise — the system offered a 5-minute refresher first, which they took" (personas.md §Recovering condensed-matter scientist, week 3) |
| S3 | Paper Engagement | No interactive pre-reading step surfaces orienting concepts as named terms the user can react to before reading begins | `diverged` | `todo` | Persona 1: system "provided orienting concepts: organic superconductor, gate-induced superconductivity, Meissner effect" as an active pre-read step, not a metadata field (personas.md §Recovering condensed-matter scientist, week 3) |
| S4 | Cross-pollination | Cross-pollination suggestions are surfaced without the anonymous social framing ("another user in adjacent areas recently engaged with this") that makes the suggestion feel trustworthy rather than arbitrary | `missing` | `todo` | All three personas encounter this framing in weeks 3–4; patterns §2: "other users in adjacent areas explored this" (personas.md §Patterns) |
| S5 | Refreshers | Refresher copy risk: if framed as corrective ("it's been a while since you covered this") rather than as a confidence-building rerun, it violates the no-guilt constraint | `contradicts` | `done` | Patterns §3: "they surface as a confidence-building rerun, not a 'you forgot this' guilt trip" (personas.md §Patterns); Persona 3: "the rerun was a confidence boost" |
| S6 | Adaptation | Any UI surface that reveals queue reweighting (toast, label, copy) violates the intended invisibility of adaptation | `contradicts` | `done` | Patterns §6: "none of the personas notices when the queue is reweighted; they just notice the daily three feels right" (personas.md §Patterns); Confirmed: `items_reweighted` exists only as an API type field, never rendered in any UI component. |
| S7 | Copy / UX-wide | Any copy that references time — item duration estimates, "quick problem", "30-min read" — violates the core constraint that time is never asked about or implied | `contradicts` | `done` | Patterns §8: "No one is asked how much time they have. Ever."; SPEC.md §Core philosophy — "Time is not a commitment — never ask users to budget time." |
| S8 | Bookmarks | Bookmarks have no forward path: bookmarked nodes never feed back into the interest-addition or queue-seeding flow when the user is ready to commit | `missing` | `todo` | Personas 1, 2, 3 all bookmark terms encountered mid-journey as "I'll come back to this"; Persona 2 bookmarks *Christoffel symbols* and later they become active interests (personas.md) |
| S9 | Notebook | Notebook may not be prominently accessible enough to naturally become the "treasured artefact" the personas describe; if it is buried in navigation the value never emerges | `diverged` | `todo` | Patterns §4: "all of them end up with it being the lasting artefact"; Persona 2 values it most and reaches for export (personas.md §Patterns) |
| S10 | Queue / Daily | Mode balance (% problems vs % papers) set at survey time has no visible post-survey setting and may be silently eroded by reroll-based adaptation signals | `missing` | `todo` | Persona 2: "their explicit signal (90% papers) outweighs the reroll-based adjustments" — implies the stated preference durably overrides inferred signals (personas.md §Paper-follower, week 4) |
| S11 | Copy / UX-wide | App copy is bland and generic throughout; needs dry warmth and slight personality matching the academic-cosy aesthetic | `diverged` | `deferred` | Phase 10 — polish-notes intake 2026-05-17 |
| S12 | Profile | No clear way for users to understand their current interests, activity history, or progression | `missing` | `deferred` | Phase 10 — polish-notes intake 2026-05-17 |

## Summary

_Updated after polish-notes intake 2026-05-17 (Phase 9-rev step 1). Counts include deferred items._

| Severity | Count |
|----------|-------|
| `missing` | 14 |
| `diverged` | 18 |
| `contradicts` | 4 (2 `done`, 2 remaining) |
| **Spec total** | **38** |
| — | — |
| `missing` | 6 |
| `diverged` | 3 |
| `contradicts` | 3 (all `done`) |
| **Spirit total** | **12** |
| **Grand total** | **50** |
