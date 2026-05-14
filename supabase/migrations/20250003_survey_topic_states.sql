-- Replace coarse 8-area skill ratings + separate desired-topics list with a
-- single per-topic state map. State per canonical_topic_id is one of:
--   "target"    — user wants to learn this (graph destination)
--   "known"     — already comfortable, skip problems (plan_node state = mastered)
--   "refresher" — wants a lighter pass (Phase 3 will use this for problem selection)
-- Topics absent from the map are treated as "unknown" — included if they are
-- prerequisites of a target, otherwise excluded.

alter table public.surveys
  drop column if exists skill_ratings_json,
  drop column if exists desired_topics_json,
  add column topic_states_json jsonb;
