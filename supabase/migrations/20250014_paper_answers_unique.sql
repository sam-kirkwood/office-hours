-- Add unique constraint so paper_answers can be upserted per (engagement, question).
alter table public.paper_answers
  add constraint paper_answers_engagement_question_unique
  unique (engagement_id, question_id);
