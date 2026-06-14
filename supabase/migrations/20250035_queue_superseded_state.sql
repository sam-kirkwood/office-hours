-- Phase 12 Step 3 — add 'superseded' to queue_items.state CHECK.
--
-- 'superseded' is the terminal state for a queue item whose slot has been
-- taken over by a sibling (easier/harder/assume-less). The original problem
-- row stays in the shared pool; only this user's queue_item goes terminal so
-- the original doesn't re-surface as if new. The new sibling queue_item
-- carries parent_queue_item_id pointing back to this row (for the fallback
-- "← Back to the previous version" link).
--
-- Uses the same discover-drop-readd pattern as 20250034 because the CHECK
-- constraint was originally anonymous (20250009).

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
    'skipped','dismissed','deferred','bookmarked','superseded'
  ));
