# Phase 10-rev Step 9 — remediation plan from the persona walkthroughs

This plan resolves the issues that surfaced from the two persona walkthroughs:

- [walkthrough #1 (Maya)](../persona_walkthrough/REPORT.md) — neuroscience postdoc, out-of-scope interest profile
- [walkthrough #2 (Hank)](../persona_walkthrough_2/REPORT.md) — quant taking semi-retirement, in-scope physics profile

It covers **Felt off** + **Broken** from both reports, ordered for ship-ability.

---

## Consolidated issue inventory

Across the two walkthroughs, six distinct issues appeared:

| ID | Issue | Confirmed reproductions | Severity |
|---|---|---|---|
| **A** | Duplicate queue items — same problem queued multiple times under different recommendation rationales | Both runs; **Hank's daily three contained the same problem at slots 1 and 3** | **Ship-blocking** |
| **B** | New interest nodes are orphans — edges silently fail to insert on `related`-verdict resolves | 3× (Maya dynsys, Hank phase-transitions, Hank RG) | High |
| **C** | Refresher cards encoded with `ref_id` = interest node when `added_reason` clearly targets a foundation | Both runs | High |
| **D** | Concept tour over-covers prereq subtopics with no destination-relevance filter | Maya's info-theory tour (5 stats tiles for info-theory) | Medium |
| **E** | Stage 3 padding fallback rationale lies (*"Adjacent to the foundations you flagged"* when no edge exists) | Both runs, severe for Maya | Medium |
| **F** | Parser intent misreads explicit denial of mastery as `consolidate` | Maya's dynsys interest; did not recur for Hank | Low |

Plus one structural gap that isn't a code bug but bites the experience:

| ID | Issue | Mitigation today |
|---|---|---|
| **G** | Seed megagraph has only 3 physics interest nodes | "Only physics and math available" copy in place — bites again the moment domains open up |

---

## Proposed work order

Three commits, each closes a coherent slice. The plan is to make Phase 10-rev shippable for the operator's own walkthrough plus a small invite cohort.

### Step 9a — queue-items hygiene (issues A + C)

**Scope.** Defensive fix in two layers so dups can't reach the user even if one layer misbehaves.

1. **Curator dispatch dedup.** In `api/routes/curator.py`, before inserting a `queue_items` row from a pool-hit recommendation, check:
   ```python
   exists = supabase.table("queue_items").select("id").eq("user_id", user_id) \
       .eq("ref_id", problem_id).in_("state", ["pending", "surfaced"]).execute()
   if exists.data:
       skipped += 1
       continue
   ```
   Pick the recommendation with the stronger `priority` to keep; discard the weaker (don't merge `added_reason`s — keep one whole one).

2. **Surface-daily variety filter on `ref_id`.** In `api/routes/surface_daily.py`, the existing variety sweep checks `kind` and `interest`. Add a `ref_id` check: no two surfaced items may share `ref_id`. If only duplicates remain after kind+interest+ref_id dedup, fall back to whatever has the highest priority.

3. **Refresher ref_id routing.** In the curator's recommendation-to-queue-items translation, when `kind='refresher'` and the recommendation's `assumed_background` or `subtopic` names a foundation node, set `ref_id = <foundation_node_id>` rather than the interest node. Spec the rule as:
   > For a `kind='refresher'` recommendation, `ref_id` should be whichever node the user will actually land on — the node whose subtopics or problem pool the reason references. If the recommendation's `interest_node` is the topic the refresher prepares the user *for* (not the topic to be refreshed), route to the prerequisite foundation instead.

**Files.** `api/routes/curator.py`, `api/routes/surface_daily.py`. New tests:
- `test_curator_skips_duplicate_pool_hit` — two recommendations on the same problem pool-hit; only one queue_item written.
- `test_surface_daily_no_duplicate_ref_id` — queue contains two rows with the same `ref_id`; surface picks at most one.
- `test_curator_refresher_routes_to_foundation` — recommendation cites a foundation; ref_id is the foundation, not the interest.

**Sizing.** Half a day. Tests are tight; the logic is local.

**Acceptance.** Re-run [`walkthrough.py cold_start surface_daily inspect`](../persona_walkthrough_2/walkthrough.py) on Hank's user_id. The daily three should be 3 distinct problems / refreshers, none duplicated, and the refresher card should land on the right foundation node.

---

### Step 9b — edges-insert reliability (issue B)

**Scope.** Fix the silent batch-rollback that's leaving new interest nodes orphaned, and add the logging that would have surfaced it during the walkthroughs.

1. **Split the edges insert.** In `api/routes/add_interest.py:451-456`, replace the batched `.insert(edge_rows)` with either:
   - per-row inserts wrapped individually in `try/except _is_unique_violation`, OR
   - a pre-insert dedup of `edge_rows` by `(source_node_id, target_node_id)` so the batch is guaranteed to be unique.

   The first is more defensive (handles races); the second is cheaper. Prefer the first if it's not a noticeable perf hit at the ~5-10 edges scale this runs at.

2. **Log the swallowed exception.** Add `logger.warning("edge insert failed (unique violation likely): %s", exc)` in the existing except branch. The original walkthroughs failed in silence; the next instance should leave a breadcrumb.

3. **Backfill the existing orphans.** Three nodes are currently floating in the DB (Maya's `dynamical-systems-neural-circuits`, Hank's `phase-transitions-critical-phenomena`, Hank's `renormalization-group-fixed-points`). For each, write the `related` edge to its declared `related_node_slug` plus any plausible prereq edges. One-off script in `scripts/persona_walkthrough/` is fine; the operator can run it once.

**Files.** `api/routes/add_interest.py`. New test:
- `test_resolve_writes_edges_when_related_slug_overlaps_prereqs` — Sonnet output includes the related slug in `proposed_prerequisite_slugs`; both edges still get written (or one gets written and the duplicate is skipped explicitly, not silently).

**Sizing.** Two hours, including the backfill script.

**Acceptance.** Resolve a new interest with `related_node_slug` set and verify edges exist post-resolve. Re-run Stage 7 on Maya/Hank; their orphan interests should now connect.

---

### Step 9c — calibration tweaks (issues D + E + F)

**Scope.** Three small prompt/string changes that tighten the front door for users.

1. **Parser intent rule expansion** (issue F). Add to `api/prompts/add_interest.py:69`, after the existing intent rules:
   > Explicit denial of current mastery combined with want-to-learn language → `teach`, not `consolidate`. Examples: *"I want to actually understand X"*, *"I want to stop hand-waving X"*, *"I want to know X properly instead of just referencing it"* → all `teach`. `consolidate` is reserved for users who assert existing mastery and want harder work.

   One paragraph of prompt; would have correctly classified Maya's dynsys input.

2. **Stage 3 fallback rationale** (issue E). In `api/routes/suggest_survey_interests.py:231`, when padding from the unfiltered shortlist after the domain scope was empty, either:
   - replace *"Adjacent to the foundations you flagged."* with *"Available in the megagraph — not strongly matched to your background, feel free to skip."*, OR
   - **(preferred)** return only the Haiku-ranked suggestions, no padding, even if that drops below `SUGGESTION_MIN=6`. Six bad suggestions are worse than three good ones. The free-text "Curious about something specific?" input is right there as the safety net.

   Either change is a 5-minute fix. The preferred option also makes Hank's third suggestion (LIGO with the bare fallback) consistent with how the other two read.

3. **Concept tour subtopic relevance** (issue D). When the tour is built from multiple prereq foundations, score each subtopic for relevance to the interest before truncating to 6-10. Two options:
   - **Cheap:** token-overlap between the subtopic name + gloss and the interest's `title + description_md + subtopics_json`. Reorder by overlap count desc, truncate.
   - **Better:** a Haiku call that picks the top tiles given the interest title. Adds ~$0.001 per resolve; worth it.

   Start with the cheap one. The implementation lives in `api/routes/add_interest.py:_concept_tour`. Would have fixed Maya's "5 stats tiles for an information-theory interest" finding.

**Files.** `api/prompts/add_interest.py`, `api/routes/suggest_survey_interests.py`, `api/routes/add_interest.py`. Tests:
- Update existing `test_parse_*` to include a "denial-of-mastery + want-to-learn" fixture and assert intent=`teach`.
- `test_suggest_interests_returns_only_haiku_ranked_when_shortlist_empty` (or the analogous test for the fallback-string change).
- `test_concept_tour_ranks_subtopics_by_relevance` — given a synthetic interest with description mentioning "conditional probability", the conditional-probability subtopic ranks above linear-regression.

**Sizing.** Three hours including tests.

**Acceptance.** Re-run Maya's stage4 and stage3 with the persona's dynsys input verbatim. Parser returns `teach`. Stage 3 returns either zero suggestions (preferred) or honest-fallback strings. Info-theory tour leads with probability/conditional-probability tiles rather than statistics tiles.

---

### Step 9d — operator seed pass (issue G)

**Scope.** Not engineering work. The operator hand-seeds 8-12 non-physics interest nodes so the Stage-3 surface has something to return when bio/comp domains unlock.

Candidate list (drawn from the personas that *do* exist or are likely):
- Information theory & neural coding
- Dynamical systems & neural circuits
- Statistical inference & Bayesian methods
- Machine learning fundamentals (gradient descent, backprop)
- Computational neuroscience
- Bioinformatics & genomics
- Numerical methods for PDEs
- Signal processing & Fourier analysis
- Optimisation & convex methods
- Cryptography & number theory (math-adjacent interest)

For each: title, slug, 2-3 sentence description, 6-8 subtopics, 2-4 prereq foundation slugs. Reuses the same shape that `/add-interest/resolve` produces; could be a hand-written SQL migration.

**Sizing.** Half a day for the operator. Defer until the "only physics and math available" copy is removed.

**Acceptance.** A non-physics persona walking Stage 3 sees plausible suggestions; the "honest fallback" from Step 9c rarely fires.

---

## Suggested commit order

1. **Step 9a** first (highest user-visible severity)
2. **Step 9b** second (unblocks Stage 5 tour content + makes Step 9c's concept-tour rerank demonstrable)
3. **Step 9c** third (calibration; can ship in parallel with 9b at the operator's discretion)
4. **Step 9d** when domains unlock; not on the Phase 10-rev critical path

Each step is independently shippable. 9a is the ship-blocker for the friends-cohort launch; 9b + 9c are the next polish pass; 9d is the cold-start gap to land before opening to non-physics users.

---

## Regression safety

Two regression surfaces should be put in place:

1. **Pytest coverage for the new bugs.** Each step lists the specific tests above. Total new tests: ~6. Existing 180 tests should still pass.

2. **Re-runnable persona harness.** The two walkthrough scripts (`scripts/persona_walkthrough/walkthrough.py`, `scripts/persona_walkthrough_2/walkthrough.py`) are already idempotent — re-running them after the fixes should produce different output without database resets. Make this explicit: add a `python walkthrough.py reset` action that wipes the persona's `user_interests`, `user_node_states`, `queue_items`, `surveys`, etc. so the operator can re-walk either persona post-fix to confirm.

The personas themselves are sustainable cheap smoke tests — Maya's full walkthrough was $0.23, Hank's was $0.21. Running both monthly during Phase 11 work is $0.50/month with strong signal.

---

## Out of scope for Step 9

Explicitly defer:

- **LLM-driven Stage-3 reranker overhaul.** Issue E's preferred fix (drop padding, return only Haiku-ranked) is small; a larger rerank-quality pass isn't needed.
- **Replacing the concept tour mechanic.** Step 9c's relevance rerank is a tweak, not a redesign. The "tour at subtopic level of prereq foundations" idea is sound; it just needs ranking.
- **Curator output schema redesign.** The `interest_node` / `subtopic` / `assumed_background` fields are fine. Step 9a's refresher routing is a translation fix at the dispatch layer, not a schema change.
- **Anything related to grading, paper engagement, or the notebook.** None of those surfaces showed problems in either walkthrough.
- **Anything that touches Phase 11-deploy** (FastAPI deploy, pg_cron migration 20250024 enablement, Sentry).

---

## Estimated total

- Engineering: ~1.5 working days for 9a + 9b + 9c combined, plus ~half a day of regression testing using the existing walkthrough scripts as harnesses.
- Operator seeding (9d): half a day, deferred.

After 9a + 9b + 9c land, Phase 10-rev is ready for the operator's own walkthrough plus a small invite cohort. The two persona scripts can be re-run post-fix as the final go/no-go check.
