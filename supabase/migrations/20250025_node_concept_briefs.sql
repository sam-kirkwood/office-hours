-- Step 5.5 — concept briefs for the /concept-review reading surface.
--
-- The reading-surface miss path on /concept-review-resolve previously rendered
-- just the node's description_md + subtopic titles, which read as a bare list.
-- This table caches a generated concept brief (Haiku, ~250 words) plus per-
-- subtopic glosses, keyed by node_id. Briefs are derived artefacts — the
-- nodes table stays descriptive, briefs live separately so they can be
-- regenerated or versioned without touching node metadata.
--
-- Briefs are not user-specific: the first user to land on a node generates the
-- brief and every subsequent user on the same node reuses it. RLS is enabled
-- with no end-user policy; the API generates and reads via service role.

create table public.node_concept_briefs (
  node_id              uuid primary key references public.nodes(id) on delete cascade,
  brief_md             text not null,
  subtopic_glosses_json jsonb not null default '[]',
  generated_at         timestamptz not null default now(),
  generated_by_model   text not null
);

alter table public.node_concept_briefs enable row level security;
-- No end-user RLS policy: service role only.
