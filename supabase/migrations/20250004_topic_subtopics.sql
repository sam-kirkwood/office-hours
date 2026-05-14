-- Per-topic subtopics for finer-grained survey input + Phase 3 problem
-- selection. Stored as an ordered array of { slug, title } on each canonical
-- topic. Slugs only need to be unique within a topic.
--
-- After applying this migration, re-run supabase/seed/01_curriculum.sql so
-- existing topics pick up their subtopics (the seed now upserts).

alter table public.canonical_topics
  add column if not exists subtopics jsonb not null default '[]'::jsonb;
