-- Phase 12 Step 2 (§A2) — a 'bookmarked' terminal state for queue_items.
--
-- Bookmark means "save this, find it later, I manage the return" (§A2). The
-- saved object lives durably in the `bookmarks` table; the queue row must
-- leave the active rotation without masquerading as something else:
--   · not 'dismissed' — that's the negative "Not for me" signal, read as a
--     down-weight by compute_cross_pollination; a save is positive.
--   · not 'done'      — that implies the user engaged with / completed it.
-- So bookmarking needs its own terminal state. "Queue it now" flips it back
-- to 'pending' (see /api/queue/requeue), mirroring the deferred → resume path.
--
-- Same discover-drop-readd dance as 20250018: the check constraint on
-- queue_items.state was anonymously named in 20250009, so find whichever check
-- constraint references the state column before dropping it.

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
    'skipped','dismissed','deferred','bookmarked'
  ));
