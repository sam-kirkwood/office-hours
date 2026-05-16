-- Drop the stale FK that still points problems.topic_node_id → canonical_topics.
-- This constraint was created in 20250002 on the original canonical_topic_id column,
-- survived the column rename in 20250011, and was never dropped when
-- 20250012 added the replacement FK (problems_topic_node_id_fkey → nodes).
-- Interest nodes created by /add-interest exist only in nodes, not canonical_topics,
-- so inserts against those nodes fail the old constraint.

alter table public.problems
  drop constraint if exists problems_canonical_topic_id_fkey;
