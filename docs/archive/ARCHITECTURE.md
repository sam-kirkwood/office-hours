# ARCHITECTURE.md — Personalized Science Tutor

## Stack

| Layer            | Choice                                 | Why                                                                                  |
|------------------|----------------------------------------|--------------------------------------------------------------------------------------|
| Frontend         | Next.js (App Router, TypeScript)       | Mobile-friendly defaults, good DX, gives the project a real TS/React surface         |
| API (web)        | Next.js API routes                     | Co-located with frontend; handles auth, CRUD, signed uploads                         |
| API (AI service) | Python + FastAPI                       | Hosts all Claude calls; cleaner Python for prompt engineering, future ML work        |
| Database         | Postgres (Neon or Supabase)            | Boring, correct, free tier; handles JSON columns well for flexible data              |
| Auth             | Supabase Auth (email magic links)      | No password handling; integrates with Postgres and Storage                           |
| File storage     | Supabase Storage                       | Signed URLs for handwritten image uploads                                            |
| Hosting (web)    | Vercel                                 | Free tier covers this; first-class Next.js                                           |
| Hosting (AI)     | Railway or Fly.io                      | Cheap Python container hosting; pick whichever is easier on first try                |
| LLM              | Anthropic Claude API                   | Sonnet for most tasks; Haiku for cheap classification/routing                        |
| Observability    | Postgres `llm_calls` table + admin UI  | Custom, simple, sufficient at this scale. Optional: Sentry for errors                |

## Service topology

```
[ Browser (mobile / desktop) ]
            │
            ▼
[ Next.js on Vercel ]
   ├── pages: marketing, auth, survey, plan review,
   │           daily problem, upload, history, admin
   ├── API routes:
   │      /api/auth/*          (Supabase Auth integration)
   │      /api/survey          (save survey, request plan)
   │      /api/plan            (read/approve/edit plan)
   │      /api/problem/today   (fetch today's problem)
   │      /api/upload/sign     (signed URL for image upload)
   │      /api/solution        (submit parsed/edited solution)
   │      /api/admin/*         (cost dashboard, hook editor)
   └── Calls Python service for AI operations
            │
            ▼
[ Python FastAPI service on Railway/Fly ]
   ├── POST /generate-plan
   ├── POST /generate-problem
   ├── POST /parse-solution    (vision: image → markdown+LaTeX)
   ├── POST /grade-solution
   ├── POST /update-plan       (after attempt, recompute)
   └── All Claude API calls live here; logs to llm_calls table

[ Postgres ]
[ Supabase Storage ] — handwritten-solution images
```

## Why split Next.js and Python

The split is justified, not vanity:

- Python is the better language for prompt engineering, LLM orchestration,
  and any future scientific/ML extensions.
- Keeping Next.js stateless and dumb makes deployment trivial on Vercel.
- The Python service can be restarted, scaled, or rewritten without touching
  the frontend.
- The seams force good API design.

The cost is one extra service to deploy. At this scale (one container,
no autoscaling needed) that cost is small.

## Data model (initial)

Sketch, not final DDL. Use snake_case, UUID primary keys, timestamps on
everything.

### Users and onboarding

- `users` (id, email, display_name, created_at)
- `surveys` (id, user_id, background_json, skill_ratings_json,
  desired_topics_json, time_per_day_minutes, difficulty_curve, created_at)

### Curriculum graph (canonical)

- `canonical_topics` (id, slug, title, description, difficulty_band,
  domain, created_at)
- `canonical_edges` (id, prerequisite_topic_id, dependent_topic_id, weight)
- `pending_topic_requests` (id, requested_by_user_id, raw_topic_text,
  proposed_node_json, status [pending/approved/rejected], created_at)
  - When a user's survey introduces an unknown topic, a request is created.
    Operator reviews and approves to add it to `canonical_topics`.

### Plans and progress

- `user_plans` (id, user_id, status, generated_by_llm_call_id, created_at)
- `plan_nodes` (id, plan_id, canonical_topic_id, order_index,
  state [pending/active/struggling/mastered], problems_completed_count)

### Problems

- `problems` (id, canonical_topic_id, statement_md, solution_md, rubric_md,
  difficulty, generated_by_llm_call_id, context_hook_id, created_at)
- `problem_hints` (id, problem_id, level, text)
- `context_hooks` (id, title, summary_md, related_topic_ids[], difficulty,
  sources_json, created_by, created_at)

### Attempts

- `daily_assignments` (id, user_id, problem_id, assigned_for_date,
  status [pending/in_progress/submitted/graded])
- `attempts` (id, assignment_id, user_id, problem_id, raw_image_paths[],
  parsed_markdown, user_edited_markdown, hint_levels_used[], grade,
  feedback_md, disputed bool, submitted_at, graded_at)

### Cost / observability

- `llm_calls` (id, route, model, input_tokens, output_tokens,
  estimated_cost_usd, request_payload_summary, response_summary,
  user_id nullable, created_at)

## Key flows

### Generating a daily problem

1. Cron (or on-demand on first visit each day) checks each active user for
   an unassigned date.
2. Picks the next `plan_node` for that user.
3. Calls Python `/generate-problem` with:
   - The topic (canonical_topic row)
   - User's recent struggle signals on adjacent topics
   - A shortlist of relevant `context_hooks` (matched by topic)
4. Python service prompts Claude for: problem statement, canonical solution,
   rubric, 3–5 hints, and matched context hook (or generated context if no
   hook fits).
5. Persists `problems`, `problem_hints`, and a `daily_assignments` row.

### Submitting a solution

1. User on mobile uploads photo(s). Next.js `/api/upload/sign` returns a
   signed URL; browser uploads directly to Supabase Storage.
2. Browser POSTs image paths to `/api/solution/parse`, which calls Python
   `/parse-solution`.
3. Python service calls Claude with the image(s) and a parsing prompt
   tuned for handwritten math/physics.
4. Returns markdown+LaTeX. Stored in `attempts.parsed_markdown`.
5. User reviews on the frontend in a rendered preview. Edits if needed.
6. User clicks Submit. Next.js calls Python `/grade-solution`.
7. Grade and feedback stored. UI shows result.

### Plan adaptation

- After every graded attempt, Next.js calls Python `/update-plan`.
- Python service reads recent attempts, recomputes node states, decides
  whether to insert reinforcement problems or advance the user.
- Update is summarized for the user on the home page.

## Cost controls

- Log every Claude call to `llm_calls` with token counts and cost.
- Admin dashboard: daily spend chart, top-5 most expensive routes, top-5
  most expensive users.
- Use Haiku for: pending-topic categorization, simple classification.
- Use Sonnet 4.6 for: problem generation, grading, vision parsing.
- Cache problem generation outputs by `(canonical_topic_id, difficulty,
  context_hook_id)` so multiple users on the same topic can share problems
  unless the operator explicitly disables sharing.

## Build phases

### Phase 1 — Skeleton, no AI

- Next.js app deployed to Vercel
- Supabase project: auth + Postgres + Storage
- DB schema migrated (users, surveys, problems, attempts — stub for now)
- Manual login flow works
- A hardcoded sample problem renders on the daily-problem page
- Photo upload works (image lands in Storage, path saved on attempt)
- No Claude calls yet

**Deliverable:** end-to-end click-through with mocked content.

### Phase 2 — Curriculum + survey + plans

- Seed `canonical_topics` and `canonical_edges` (with Claude's help offline)
- Build survey UI and persistence
- Build plan review UI (visual skill tree — basic SVG or a library like
  Reactflow)
- Plans are still chosen from canonical paths, no Claude generation yet
- Pending-topic request flow when a user enters an unknown topic

**Deliverable:** users can sign up, fill in survey, review and approve a
plan made of canonical topics.

### Phase 3 — Problem generation and hints

- Stand up Python FastAPI service on Railway/Fly
- `/generate-problem` working end to end
- Seed 20–30 `context_hooks` manually
- Hints pre-generated and stored at problem creation time
- Daily assignment job

**Deliverable:** users get a real, AI-generated daily problem with hints
and context.

### Phase 4 — Vision parsing + review UI

- `/parse-solution` working
- Mobile upload page polished
- "Review the parse" UI with editable markdown+LaTeX preview

**Deliverable:** users can submit handwritten work and confirm the parse.

### Phase 5 — Grading + feedback + plan adaptation

- `/grade-solution` and `/update-plan`
- Feedback UI
- Dispute flag
- Adapted plan visibility

**Deliverable:** full learning loop closed.

### Phase 6 — Cost dashboard + polish

- Admin pages for spend, pending topics, hooks editor
- Error monitoring
- Mobile polish pass

**Deliverable:** v1 ready for friends.

### Phase 7+ — Deferred features

Paper reading, annotated notebook, dynamic hints, BYO key. Slot in
against existing schema.

## Risks and mitigations

| Risk                                                    | Mitigation                                                                 |
|---------------------------------------------------------|----------------------------------------------------------------------------|
| Vision parsing accuracy on messy handwriting            | Mandatory user review-and-edit step before grading                         |
| Hint drift / accidental answer leakage                  | Pre-generate hints once, store them, never regenerate per request          |
| Grading is wrong and demoralizes user                   | Dispute flag visible; operator review queue; tone of feedback is humble    |
| LLM cost creep                                          | `llm_calls` logging from day one; admin dashboard; problem caching         |
| Skill tree becomes messy as users request new topics    | Pending-topic queue with operator approval; canonical graph stays curated  |
| Operator burnout from too much scope                    | Strict phase order; phases 1–6 ship before any phase 7 work                |
