-- Phase 10.5-rev Step 2 — Refresher subsystem reframe.
--
-- A "refresher" is no longer a distinct content kind resolved by a navigation
-- side-effect at click time. It is now a *framing flag* on a concrete queue
-- item (problem / concept_review / paper_engagement) that the curator chose for
-- spaced revisiting. Resolution happens once, at creation time, so the queue
-- only ever contains directly-routable items. See
-- docs/curriculum-curator-design.md §11.4 and docs/phase-plans/phase-10.5-rev-plan.md.
--
-- 1. Add the framing flag. Drives the "Refresher" badge + revisit copy in the
--    daily queue, while the row's own `kind` controls routing and title lookup.
alter table queue_items
  add column if not exists via_refresher boolean not null default false;

-- 2. Retire pre-existing kind='refresher' rows. Their content was never
--    resolved (it was deferred to the now-deleted /refresher-resolve click
--    path), so they cannot be migrated in SQL — the resolver needs the problem
--    pool / LLM. Dismiss the non-terminal ones; the daily planner re-creates
--    equivalent refreshers as concrete via_refresher items on its next pass.
--    (Pre-launch: only operator test data has these rows.)
update queue_items
   set state = 'dismissed',
       updated_at = now()
 where kind = 'refresher'
   and state in ('pending', 'surfaced', 'in_progress');
