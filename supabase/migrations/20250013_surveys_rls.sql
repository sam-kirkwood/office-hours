-- surveys: each user can read their own row.
-- (Writes go through the admin/service-role client and bypass RLS.)
create policy "surveys_select_own" on public.surveys
  for select using (auth.uid() = user_id);
