-- Phase 13 Step 4a — orientation tutor session state.
--
-- The conversational orientation tutor (orientation-and-calibration-design.md
-- §B4) replaces the seven-stage survey. This table is its resumable working
-- store: the running transcript plus the extracted A/B/C/D signal struct.
--
-- Kept OFF the surveys row deliberately: the seven-stage survey still reads/
-- writes surveys.{background_json,completed_stages,pending_interests_json} and
-- stays live until Phase 13 Step 4c ships. Isolating the tutor's state here
-- keeps the two flows from colliding, and keeps a potentially large transcript
-- off the hot surveys row.
--
-- signals_json shape (OrientationSignals in api/schemas.py):
--   { interests: [{raw_text, node_slug?, altitude?, path_key?, path_json?,
--                  resolved}],
--     foundation_marks: {slug: 'solid'|'rusty'|'new'},
--     foundation_swept: bool,
--     mode: 'problems'|'papers'|'balanced'|null,
--     work_context: str|null }
-- transcript_json shape: [{role: 'user'|'assistant', content: str}]

create table public.orientation_sessions (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references public.profiles(id) on delete cascade,
  status          text not null default 'in_progress'
                    check (status in ('in_progress', 'completed')),
  transcript_json jsonb not null default '[]'::jsonb,
  signals_json    jsonb not null default '{}'::jsonb,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

-- At most one in-progress session per user (the resume target). Completed
-- sessions are historical, so the partial index still allows many of them.
create unique index orientation_sessions_one_active_per_user
  on public.orientation_sessions (user_id)
  where status = 'in_progress';

alter table public.orientation_sessions enable row level security;

-- Users can read their own sessions. Writes go through the service-role client
-- (Python API) and bypass RLS; the server client still needs an explicit
-- SELECT policy or own-row reads silently return null.
create policy "orientation_sessions_select_own" on public.orientation_sessions
  for select using (auth.uid() = user_id);
