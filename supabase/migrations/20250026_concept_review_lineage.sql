-- Step 5.5 follow-up — concept_review lineage and notebook persistence.
--
-- 1. queue_items.parent_queue_item_id: when a concept_review or refresher
--    is enqueued from inside another surface (e.g. clicking an orienting
--    concept term while reading a paper), we record the source queue item
--    so the reading view can render a back-link. ON DELETE SET NULL because
--    the parent may be marked done/dismissed independently.
--
-- 2. Extend notebook_entries.entry_kind to include 'concept_review' so
--    finished concept reviews can be persisted in the user's notebook.
--    Old kinds are kept; this is purely additive.

alter table public.queue_items
  add column parent_queue_item_id uuid references public.queue_items(id) on delete set null;

create index queue_items_parent_idx
  on public.queue_items (parent_queue_item_id)
  where parent_queue_item_id is not null;

alter table public.notebook_entries
  drop constraint notebook_entries_entry_kind_check;

alter table public.notebook_entries
  add constraint notebook_entries_entry_kind_check
  check (entry_kind in ('problem_attempt','paper_engagement','concept_review'));
