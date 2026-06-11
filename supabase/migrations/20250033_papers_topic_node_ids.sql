-- Phase 10.5-rev Step 3 (d22 follow-up) — papers.topic_node_ids.
--
-- Queue cards now show the topic(s) an item is drawn from. Problems carry a
-- first-class topic_node_id; concept reviews and suggested interests ARE
-- nodes. Papers were the gap: the papers table has no node link at all, so a
-- paper engagement card had no topic to show.
--
-- topic_node_ids is the set of graph nodes a paper is about. It is populated
-- by /propose-papers (the curator asks the model which of the user's
-- interests each paper maps to, and those resolve to node ids). The
-- association is intrinsic to the paper's subject, so it is stored per-paper
-- and shared — different users reaching the same paper union their framings
-- into the same list.
--
-- uuid[] (not a join table) matches the existing context_hooks.related_topic_ids
-- precedent and suits the hard-cap-30 no-scale-engineering rule. Empty by
-- default: user-added papers and any not yet classified simply show no chip.

alter table public.papers
  add column topic_node_ids uuid[] not null default '{}';

create index papers_topic_node_ids_idx
  on public.papers using gin (topic_node_ids);
