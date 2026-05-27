-- Phase 10-rev Step 2f — problems.intent column + extend the cache-key
-- unique indexes so that distinct intents on the same (topic, difficulty,
-- hook) tuple coexist as separate pool rows.
--
-- Background: survey-and-difficulty-design.md §3 defines intent as a
-- separate dial from difficulty (teach / refresh / consolidate). Two
-- problems on the same topic+difficulty but different intent are genuinely
-- different content (a teach problem builds the apparatus; a consolidate
-- problem assumes it). They must be cacheable side-by-side.
--
-- Existing rows have intent = null. The cache lookup treats null as
-- distinct from any non-null intent value, so legacy rows are not reused
-- for new intent-qualified requests. Over time new writes carry intent
-- explicitly and legacy rows fade out of rotation.

alter table public.problems
  add column intent text;

alter table public.problems
  add constraint problems_intent_check
  check (intent is null or intent in ('teach','refresh','consolidate'));

-- Drop and rebuild the partial unique indexes that define the cache key.
-- See migration 20250011 for the prior shape.

drop index if exists problems_cache_key_with_hook;
drop index if exists problems_cache_key_no_hook;

create unique index problems_cache_key_with_hook on public.problems
  (topic_node_id, difficulty, context_hook_id, intent)
  where context_hook_id is not null and paper_id is null;

create unique index problems_cache_key_no_hook on public.problems
  (topic_node_id, difficulty, intent)
  where topic_node_id is not null and context_hook_id is null and paper_id is null;
