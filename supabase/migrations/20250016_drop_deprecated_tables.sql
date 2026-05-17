-- Drop v1 tables that have had no new writes since Phase 4-rev.
-- All application code references removed before this migration was applied.
-- CASCADE handles any residual FK stubs (e.g. daily_assignments was previously
-- referenced by attempts.assignment_id, which was already dropped in 20250011).

DROP TABLE IF EXISTS public.pending_topic_requests CASCADE;
DROP TABLE IF EXISTS public.daily_assignments CASCADE;
DROP TABLE IF EXISTS public.plan_nodes CASCADE;
DROP TABLE IF EXISTS public.user_plans CASCADE;
DROP TABLE IF EXISTS public.canonical_edges CASCADE;
DROP TABLE IF EXISTS public.canonical_topics CASCADE;
