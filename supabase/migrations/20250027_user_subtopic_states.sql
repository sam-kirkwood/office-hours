-- Phase 10-rev Step 6 (survey-and-difficulty-design.md §7) — user_subtopic_states.
--
-- Per-subtopic self-report state from the concept tour (Stage 5) and from
-- future per-subtopic actions in the skill tree node panel. Previously the
-- only place this signal lived was surveys.comfort_responses_json, which is
-- coupled to the survey record and only populated during onboarding. This
-- table is the durable per-subtopic store the skill tree node panel reads
-- when rendering subtopic state badges.
--
-- One row per (user, node, subtopic_slug). subtopic_slug is the canonical
-- key inside nodes.subtopics_json (foundation nodes use {slug, title}; this
-- table only covers those — interest nodes whose subtopics_json is string[]
-- are out of scope, since no foundation-style tour data lands there).
--
-- The backfill at the bottom of this migration ports existing
-- surveys.comfort_responses_json.subtopics entries (keyed
-- "<node_slug>:<subtopic_key>") into rows here, so users who completed the
-- new survey see their reported state immediately.

create table public.user_subtopic_states (
  user_id        uuid not null references public.profiles(id) on delete cascade,
  node_id        uuid not null references public.nodes(id) on delete cascade,
  subtopic_slug  text not null,
  state          text not null check (state in ('familiar','refresh','new')),
  updated_at     timestamptz not null default now(),
  primary key (user_id, node_id, subtopic_slug)
);

create index user_subtopic_states_user_node_idx
  on public.user_subtopic_states (user_id, node_id);

alter table public.user_subtopic_states enable row level security;

create policy user_subtopic_states_own_select on public.user_subtopic_states
  for select using (auth.uid() = user_id);

create policy user_subtopic_states_own_modify on public.user_subtopic_states
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Backfill from surveys.comfort_responses_json.
-- Shape: { subtopics: { "<node_slug>:<subtopic_key>": "familiar"|"refresh"|"new" } }
insert into public.user_subtopic_states (user_id, node_id, subtopic_slug, state)
select
  s.user_id,
  n.id as node_id,
  split_part(kv.key, ':', 2) as subtopic_slug,
  kv.value #>> '{}' as state
from public.surveys s,
     lateral jsonb_each(coalesce(s.comfort_responses_json -> 'subtopics', '{}'::jsonb)) kv
join public.nodes n on n.slug = split_part(kv.key, ':', 1)
where (kv.value #>> '{}') in ('familiar', 'refresh', 'new')
  and split_part(kv.key, ':', 2) <> ''
on conflict (user_id, node_id, subtopic_slug) do nothing;
