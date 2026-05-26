-- Phase 10-rev Step 2a — schema additions for the add-interest dialog,
-- the queue's "deferred" state, and the per-attempt "assume less" signal.
--
-- References:
--   docs/survey-and-difficulty-design.md §8 (schema changes)
--   docs/phase-plans/phase-10-rev-plan.md Step 2a

-- ── user_interests.intent_context ─────────────────────────────────────────────
-- Soft text capturing the resolved path and intent from the add-interest
-- dialog (Section 2.6). Read by the problem generator and the curriculum
-- curator. Existing rows backfill to '' via the column default; the default
-- is dropped immediately after so new inserts that omit the field fail
-- loudly rather than silently storing ''.

alter table public.user_interests
  add column intent_context text not null default '';

alter table public.user_interests
  alter column intent_context drop default;

-- ── queue_items.state: add 'deferred' ─────────────────────────────────────────
-- The inline check constraint on queue_items.state is anonymously named in
-- 20250009 (Postgres conventionally calls it `queue_items_state_check`). Drop
-- it by discovering whichever check constraint actually references the state
-- column, to survive any rename, then re-add with 'deferred' in the value set.

do $$
declare
  conname text;
begin
  select c.conname into conname
  from pg_constraint c
  join pg_class t on t.oid = c.conrelid
  join pg_namespace n on n.oid = t.relnamespace
  join pg_attribute a on a.attrelid = c.conrelid and a.attnum = any(c.conkey)
  where n.nspname = 'public'
    and t.relname = 'queue_items'
    and c.contype = 'c'
    and a.attname = 'state'
  limit 1;

  if conname is not null then
    execute format('alter table public.queue_items drop constraint %I', conname);
  end if;
end$$;

alter table public.queue_items
  add constraint queue_items_state_check
  check (state in (
    'pending','surfaced','in_progress','done',
    'skipped','dismissed','deferred'
  ));

-- ── attempts.requested_assume_less ────────────────────────────────────────────
-- Per-attempt signal for the "explain more / assume less" control
-- (survey-and-difficulty-design.md §3.5). Mirrors the existing
-- requested_easier / requested_harder columns.

alter table public.attempts
  add column requested_assume_less boolean not null default false;
