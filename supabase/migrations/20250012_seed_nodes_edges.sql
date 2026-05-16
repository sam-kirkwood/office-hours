-- ── Seed nodes from canonical_topics (step 5) ────────────────────────────────
-- Preserves UUIDs so context_hooks.related_topic_ids continues to resolve.
-- 13 slugs become foundation nodes; the remaining 8 become interest nodes.

insert into public.nodes
  (id, slug, title, description_md, domain, kind, difficulty_hint, subtopics_json, created_at)
select
  id,
  slug,
  title,
  coalesce(description, ''),
  domain,
  case when slug in (
    'calculus-1', 'calculus-2', 'multivariable-calculus', 'linear-algebra', 'odes',
    'probability', 'statistics',
    'classical-mechanics', 'waves-oscillations', 'electromagnetism-1',
    'thermodynamics', 'statistical-mechanics', 'quantum-mechanics-1'
  ) then 'foundation' else 'interest' end,
  difficulty_band,
  coalesce(subtopics, '[]'::jsonb),
  created_at
from public.canonical_topics
on conflict (id) do nothing;

-- ── Seed edges from canonical_edges (all prerequisite in v1) ─────────────────

insert into public.edges
  (source_node_id, target_node_id, edge_kind, weight)
select
  prerequisite_topic_id,
  dependent_topic_id,
  'prerequisite',
  weight::real
from public.canonical_edges
on conflict (source_node_id, target_node_id) do nothing;

-- ── Wire up problems.topic_node_id FK now that nodes rows exist ───────────────
-- Column was renamed canonical_topic_id → topic_node_id in migration 20250011;
-- values are already the correct UUIDs.

alter table public.problems
  add constraint problems_topic_node_id_fkey
  foreign key (topic_node_id) references public.nodes(id);

-- ── Deprecate v1 tables (step 6) ─────────────────────────────────────────────
-- No physical drop yet — preserve seed history for operator introspection.
-- Physical drops land in Phase 8-rev step 6.

comment on table public.canonical_topics        is 'DEPRECATED — superseded by nodes. No new writes. Drop in Phase 8-rev.';
comment on table public.canonical_edges         is 'DEPRECATED — superseded by edges. No new writes. Drop in Phase 8-rev.';
comment on table public.user_plans              is 'DEPRECATED — superseded by queue_items. No new writes. Drop in Phase 8-rev.';
comment on table public.plan_nodes              is 'DEPRECATED — superseded by queue_items. No new writes. Drop in Phase 8-rev.';
comment on table public.daily_assignments       is 'DEPRECATED — superseded by surfaced_picks. No new writes. Drop in Phase 8-rev.';
comment on table public.pending_topic_requests  is 'DEPRECATED — superseded by /add-interest. No new writes. Drop in Phase 8-rev.';

-- Revoke INSERT and UPDATE from client roles; service role retains access.
revoke insert, update on public.canonical_topics       from anon, authenticated;
revoke insert, update on public.canonical_edges        from anon, authenticated;
revoke insert, update on public.user_plans             from anon, authenticated;
revoke insert, update on public.plan_nodes             from anon, authenticated;
revoke insert, update on public.daily_assignments      from anon, authenticated;
revoke insert, update on public.pending_topic_requests from anon, authenticated;
