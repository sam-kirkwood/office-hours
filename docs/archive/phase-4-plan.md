# Phase 4 — execution plan

Forward-looking plan for the multi-session Phase 4 build. Source-of-truth for
the product is still [SPEC.md](../SPEC.md) and [ARCHITECTURE.md](../ARCHITECTURE.md);
this file captures the *execution* decisions and step ordering. Mirrors the
shape of [phase-3-plan.md](./phase-3-plan.md) — proposed decisions are flagged
so they can be confirmed or overridden before we start.

## Where we are

- **Phases 1–3**: done. End-to-end: a user with an approved plan opens
  [/daily](../web/app/daily/page.tsx) and gets an AI-generated problem with
  hints + historical context, cached across users on
  `(canonical_topic_id, difficulty, context_hook_id)`. See
  [phase-3-plan.md](./phase-3-plan.md) for the record.
- **Phase 4**: not started. The [/upload](../web/app/upload/page.tsx) page is
  still the Phase 1 stub — images land in Supabase Storage and the "Submit"
  button just flips local React state.

## Phase 4 goal

When a user with today's assignment opens [/upload](../web/app/upload/page.tsx),
they can:

1. Take one or more photos of their handwritten solution (camera or file).
2. Submit them and see the parsed markdown+LaTeX rendered in a review pane.
3. Edit the parse inline (plain textarea, live preview underneath).
4. Confirm. The row in `attempts` now has `parsed_markdown`,
   `user_edited_markdown`, `hint_levels_used[]`, `raw_image_paths[]`, and
   `submitted_at`. `daily_assignments.status = 'submitted'`. Phase 5 will pick
   it up from here.

Every Claude vision call is logged to `llm_calls`. Parse failures don't lose
the user's submission — raw images stay in storage and the UI lets the user
hand-type a solution as a fallback.

Out of scope for Phase 4: grading, feedback, plan adaptation (Phase 5);
operator dashboards (Phase 6).

## Decisions locked in (2026-05-14)

Worked through with the operator before execution. Don't re-litigate.

| Decision | Choice | Why |
|---|---|---|
| HEIC handling | **Client-side conversion** via [heic2any](https://github.com/alexcorvi/heic2any) before upload | Saves bandwidth, storage gets a directly-usable JPG, no second service to maintain. iPhones default to HEIC and Claude vision rejects it — this is a real production trap. |
| Review editor | **Plain `<textarea>`** + live `<MarkdownLatex>` preview | Edit volume is light; saves ~300 KB of editor lib; mobile-friendly. |
| Hint click logging | **Client-side** React state on /daily, forwarded to the attempts row at upload time | Server-side per-click is overkill for ~10 trusted friends. Reconsider in Phase 5 if grading needs richer signals. |
| Attempts uniqueness | `unique (assignment_id)` on `attempts` | Matches the one-problem-per-day v1 gate. Bonus-problem path goes through `bonus_assignments` later (Phase 3 follow-up #5). |
| Parse-failed pre-fill | **Scaffold**, not empty | Operator's friends may forget markdown / LaTeX syntax — give them a starting structure with inline examples. |
| Stored-image rendering after page reload | `GET /api/storage/sign-download?path=...`, gated to `path` starting with `${user.id}/` | One-time ~30 LoC cost; alternative (session-only blob URLs) breaks resume-mid-flow. |
| Vision model | `claude-sonnet-4-6` | Already in use; supports vision; same pricing constants in [api/anthropic_client.py](../api/anthropic_client.py). |
| Parsing prompt fidelity | **Transcribe, do not correct** | Grader (Phase 5) is the place to flag mistakes. The parser should reproduce the user's work faithfully — including errors — so the user reviews exactly what they wrote, and the grader sees the actual solution they're being graded on. |
| Caching | **None** | Each user's handwriting + each photo is unique. No useful cache key. |
| Prompt caching | **Yes on system prompt only** | Same pattern as `call_json` in [api/anthropic_client.py](../api/anthropic_client.py); the per-call image blobs are not cache-friendly anyway. |
| Failure mode | `attempts.parse_status='parse_failed'` after retry exhaustion; raw images retained; UI offers scaffolded textarea | Per [CLAUDE.md](../CLAUDE.md) §Key design constraints — "Original images are always retained even if parsing fails." |
| Attempt row creation | **At upload time, not hint-open time** | Simpler. Hint click history rides into the row at creation via the client-side list. |
| Review UI on mobile | **Tabs** (image \| edit \| preview) | Side-by-side is unusable on phone width. Tabs are mandatory per [SPEC.md](../SPEC.md) §Non-functional. |

## Step status

| # | Step | Status |
|---|---|---|
| 1 | DB migration `20250007_phase4_attempts.sql` | **Written, not yet applied** |
| 2 | `call_json_vision` helper in `api/anthropic_client.py` | Pending |
| 3 | Python `POST /parse-solution` route | Pending |
| 4 | HEIC → JPG client-side conversion on upload | Pending |
| 5 | Next.js API routes: `/api/attempts*` + `/api/storage/sign-download` | Pending |
| 6 | Upload page rewrite: upload → parsing → review → confirm | Pending |
| 7 | Hint tracking wiring on `/daily` | Pending |
| 8 | Tests + live smoke test + docs touch-ups | Pending |

## Step 1 — DB migration

File: `supabase/migrations/20250007_phase4_attempts.sql`

Extend [public.attempts](../supabase/migrations/20250001_phase1_schema.sql#L39-L47):

```sql
alter table public.attempts
  add column parsed_markdown        text,
  add column user_edited_markdown   text,
  add column hint_levels_used       smallint[] not null default '{}',
  add column parse_status           text not null default 'pending'
    check (parse_status in ('pending','parsing','parsed','parse_failed','confirmed')),
  add column parsed_by_llm_call_id  uuid references public.llm_calls(id);

-- v1: one attempt per assignment. Drop this if bonus retries arrive.
alter table public.attempts
  add constraint attempts_one_per_assignment unique (assignment_id);
```

Notes worth not re-litigating later:

- **`parse_status` is an explicit enum, not field-null semantics.** `parse_failed`
  is a real terminal state the UI must distinguish from "not parsed yet".
  Cheaper than five nullable timestamps.
- **`hint_levels_used smallint[]`** matches the `problem_hints.level` smallint
  column. Default `'{}'` so the column is non-null at insert time when the
  client hasn't sent any hints.
- **`parsed_by_llm_call_id`** mirrors `problems.generated_by_llm_call_id` for
  Phase 6 cost attribution.
- **No new RLS policies needed**: `attempts_select_own` / `attempts_insert_own`
  / `attempts_update_own` from migration 20250001 already gate on
  `auth.uid() = user_id`. The new columns inherit the same policy.

### Step 1 — what shipped (2026-05-15)

- File [supabase/migrations/20250007_phase4_attempts.sql](../supabase/migrations/20250007_phase4_attempts.sql)
  written. Matches the SQL block above; the migration body itself documents
  the `parse_status` lifecycle inline (pending → parsing → parsed | parse_failed →
  confirmed) so a Phase 5 reader doesn't have to come back to this plan.
- **NOT YET APPLIED.** Operator hasn't run `npx supabase db push` yet. Until
  then: don't start step 5 (Next.js API routes that INSERT into attempts
  expecting the new columns) and don't start step 3 (Python parse route that
  UPDATEs `parsed_markdown` / `parse_status`). Steps 2, 4, 6, 7 don't touch
  the DB and can proceed independently.
- **Initial `parse_status` for new rows is `'pending'`, not `'parsing'`.** A
  small design call: an attempt row briefly exists in 'pending' between the
  `POST /api/attempts` insert (step 5) and the `POST /api/attempts/[id]/parse`
  invocation (also step 5). The Python parse route (step 3) is what flips it
  to 'parsing'. Alternative considered: skip 'pending' and have the Next.js
  route insert with 'parsing' directly — rejected because it conflates "row
  exists" with "parse in flight". Keep 'pending' so a stale-row sweep in a
  future phase has a clean signal.
- **Existing-data safety**: relies on the assumption that
  `public.attempts` is empty in dev / prod. True as of 2026-05-15 because
  the upload page has been a Phase-1 mocked stub since the start — clicking
  Submit only flips React state. If a row somehow exists, the unique
  constraint and the `not null default '{}'` on `hint_levels_used` will both
  be satisfied; the new nullable columns are fine.
- **Constraint name** is `attempts_one_per_assignment`. Worth using the
  named constraint when catching the unique violation in step 5's
  `POST /api/attempts` handler (so a two-tabs race produces a recognizable
  error instead of a generic 23505).

### Step 1 — to apply

```powershell
npx supabase db push --db-url <your-supabase-db-url>
```

Verify after apply: `\d public.attempts` should show the five new columns +
the `attempts_one_per_assignment` unique constraint.

## Step 2 — `call_json_vision` helper

[api/anthropic_client.py](../api/anthropic_client.py) currently has `call_json`
for text-only Claude calls. Phase 4 needs an image-content variant. Refactor:

1. Factor a private `_call_and_log(client, supabase, model, system, messages,
   schema, route, ...) -> T` that owns the retry + JSON parse + `llm_calls`
   write. Same body that `call_json` currently has, just with `messages`
   passed in instead of constructed inline.
2. Keep `call_json` as a thin wrapper that builds the text-only user message.
3. Add `call_json_vision(client, supabase, model, system_prompt, user_prompt,
   images: list[VisionImage], schema, route, ...)` where `VisionImage` is
   `{media_type: str, data: bytes}`. Builds the multimodal user message:
   ```python
   {"role": "user", "content": [
       {"type": "image", "source": {"type": "base64",
                                    "media_type": img.media_type,
                                    "data": base64.b64encode(img.data).decode()}}
       for img in images
   ] + [{"type": "text", "text": user_prompt}]}
   ```
4. Same retry-once-on-parse-failure semantics. Same `log_llm_call` invocation
   on every API call.

Pricing constants in `PRICING` already cover Sonnet 4.6 — vision tokens count
as input tokens in Anthropic's usage report, no schema change needed.

## Step 3 — Python `POST /parse-solution`

New file: `api/routes/parse_solution.py`. New prompt file:
`api/prompts/parse_solution.py`.

Request schema (in [api/schemas.py](../api/schemas.py)):

```python
class ParseSolutionRequest(BaseModel):
    user_id: UUID
    attempt_id: UUID

class ParsedSolution(BaseModel):
    """Strict shape the Sonnet vision call must return as JSON."""
    markdown: str
    parse_notes: str | None = None  # e.g., "left margin of page 2 illegible"

class ParseSolutionResponse(BaseModel):
    attempt_id: UUID
    parsed_markdown: str
    parse_status: str  # 'parsed' | 'parse_failed'
```

Flow:

1. Load `attempts` by `id` with the service-role client. 404 if missing or if
   `user_id` mismatch. 400 if `parse_status` is already `confirmed`.
2. Optimistically set `parse_status = 'parsing'`.
3. For each path in `raw_image_paths`, download bytes from the `solutions`
   bucket via the service-role storage client. Infer media type from
   extension (`.jpg` / `.jpeg` / `.png` / `.webp`). Reject HEIC at this layer
   too as a defensive check (the client should already have converted — Q1).
4. Call `call_json_vision` with the parse prompt + all images in one message.
5. On success: persist `parsed_markdown`, `parse_status='parsed'`, and
   `parsed_by_llm_call_id` (the helper needs to surface the last logged
   call's id — small extension to `_call_and_log`).
6. On exhaustion: persist `parse_status='parse_failed'` and a sentinel
   `parsed_markdown` like `""`. **Return 200 with `parse_status='parse_failed'`
   rather than raising** — the UI needs to render the fallback path; this is
   not an unexpected error.
7. Return the response.

Prompt design (in `api/prompts/parse_solution.py`):

- System: "You transcribe handwritten math/physics work into markdown+LaTeX.
  Your job is **fidelity, not correction** — reproduce what the student wrote
  verbatim, including errors. The grader is a separate pass." Plus output
  format (single JSON, no fences, schema as above). Plus hint ladder around
  LaTeX (`$...$` inline, `$$...$$` display). Plus a rule against inventing
  steps the student didn't write.
- User: "Below are N photos of a handwritten solution. Transcribe them in
  reading order. Use markdown headings for any structural breaks. Note
  illegible regions in `parse_notes` but transcribe your best guess in
  `markdown`."

## Step 4 — HEIC → JPG client-side conversion

- Add `heic2any` to `web/package.json`.
- In `web/app/upload/page.tsx`, before the existing upload loop: if
  `file.type === 'image/heic' || file.name.toLowerCase().endsWith('.heic')`,
  pipe through `heic2any({blob: file, toType: 'image/jpeg', quality: 0.85})`
  and replace `file` with the resulting blob. Show a small "Converting…"
  state.
- `accept="image/*,.heic"` so iOS Safari surfaces HEIC files in the picker.
- `heic2any` is browser-only (uses `FileReader` / canvas). Lazy-import it
  with `await import("heic2any")` inside the conversion branch so the lib
  isn't pulled into the initial bundle for users who never upload HEIC.

## Step 5 — Next.js API routes

New routes under `web/app/api/attempts/`:

| Route | Body | Returns |
|---|---|---|
| `POST /api/attempts` | `{ assignment_id, raw_image_paths: string[], hint_levels_used: number[] }` | `{ attempt_id }` |
| `POST /api/attempts/[id]/parse` | `{}` | `{ parsed_markdown, parse_status }` |
| `POST /api/attempts/[id]/confirm` | `{ user_edited_markdown }` | `{ ok: true }` |

Plus one storage route:

| Route | Body | Returns |
|---|---|---|
| `GET /api/storage/sign-download?path=<path>` | — | `{ signedUrl }` |

Implementation notes:

- All four routes verify `auth.getUser()` first and 401 if missing — same
  pattern as [/api/upload/sign](../web/app/api/upload/sign/route.ts).
- `POST /api/attempts`:
  - Service-role client.
  - Verify the assignment belongs to the caller.
  - Insert `attempts` row with `parse_status='pending'`, `raw_image_paths`,
    `hint_levels_used`. Set `daily_assignments.status='in_progress'`.
- `POST /api/attempts/[id]/parse`:
  - Service-role; verify ownership.
  - Call Python `/parse-solution` via a new `parseSolution()` helper in
    `web/lib/pythonApi.ts` (same shape as `generateProblem`).
  - Return whatever the Python side wrote (the route doesn't need to
    re-select).
- `POST /api/attempts/[id]/confirm`:
  - Service-role; verify ownership; verify `parse_status in ('parsed',
    'parse_failed')`.
  - Update `attempts.user_edited_markdown`, `attempts.submitted_at = now()`,
    `attempts.parse_status='confirmed'`, and
    `daily_assignments.status='submitted'`.
- `GET /api/storage/sign-download`:
  - Verify `path` starts with `${user.id}/` (defence-in-depth on top of any
    storage RLS).
  - `createSignedUrl(path, 60 * 10)` from the `solutions` bucket.

## Step 6 — Upload page rewrite

[web/app/upload/page.tsx](../web/app/upload/page.tsx) becomes a state machine
with four UI phases. Keep it a client component (mobile camera + file
handling).

```
upload  ──submit──▶  parsing  ──ok──────▶  review  ──confirm──▶  done
                              └─fail────▶  fallback (blank editor)
```

Per-state UI sketch:

- **upload**: existing dropzone + previews. Add per-preview "Remove" button.
  Disable the main CTA until ≥1 image. On submit: HEIC conversions (if Q1
  client-side) → upload to storage via existing flow → `POST /api/attempts` →
  transition to `parsing`.
- **parsing**: full-page skeleton matching the
  [/daily loading state](../web/app/daily/loading.tsx). Calls
  `POST /api/attempts/[id]/parse` on mount. ~10–20s cold call; tell the user.
- **review** (parse_status='parsed') and **fallback** (parse_status='parse_failed'):
  Mobile tabs `[ Image | Edit | Preview ]`. Desktop: side-by-side
  image+editor with preview underneath the editor.
  - Image tab/pane: each `raw_image_path` rendered via a signed download URL
    fetched from `/api/storage/sign-download`. Pinch-zoom is browser-native;
    no library needed.
  - Edit tab/pane: `<textarea>` bound to React state. Pre-filled from
    `parsed_markdown` in the parsed case, **pre-filled with a scaffold** in
    the parse_failed case — operator's friends shouldn't have to remember
    LaTeX syntax cold. Proposed scaffold (keep short, inline examples):

    ```markdown
    ## Working

    Write your solution here. Use `$...$` for inline math (e.g. `$x^2 + 1$`)
    and `$$...$$` for display equations:

    $$
    \int_0^\infty e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2}
    $$

    ## Final answer

    ```

    Define this scaffold as a single exported const in
    `web/lib/parseFallback.ts` so it's easy to tweak in one place.
  - Preview tab/pane: `<MarkdownLatex source={edited} />`. Re-render on every
    keystroke is fine at this size; debounce only if observed sluggish.
  - "Submit for grading" CTA: disabled if `edited.trim() === ''`. Calls
    `POST /api/attempts/[id]/confirm` then transitions to `done`.
- **done**: "Submitted! Grading is coming in Phase 5." Link back to /daily.
  Keep the wording honest — operator's friends know this is in development.

File-level changes:

| File | Change |
|---|---|
| `web/app/upload/page.tsx` | Rewrite as the state machine above. |
| `web/lib/pythonApi.ts` | Add `parseSolution({attemptId})`. |
| `web/app/api/attempts/route.ts` *(new)* | `POST` handler. |
| `web/app/api/attempts/[id]/parse/route.ts` *(new)* | `POST` handler. |
| `web/app/api/attempts/[id]/confirm/route.ts` *(new)* | `POST` handler. |
| `web/app/api/storage/sign-download/route.ts` *(new)* | `GET` handler. |
| `web/lib/types.ts` | Add `Attempt` type with the new columns. |
| `web/package.json` | Add `heic2any` if Q1 lands client-side. Add
  `@tailwindcss/typography` — flagged as Phase 3 follow-up #2 and the review
  UI's preview pane wants the `prose` styling that's currently dead. |

## Step 7 — Hint tracking on `/daily`

Client-side for v1.

- Add React state on [/daily](../web/app/daily/page.tsx) — but that's a
  server component today. Convert the hints panel into a small client
  component (`web/components/HintsPanel.tsx`) that tracks an internal
  `Set<number>` of opened levels and writes it to `sessionStorage` keyed by
  `problem_id`.
- On the [/upload](../web/app/upload/page.tsx) page, read the same
  `sessionStorage` key and include `hint_levels_used` in the
  `POST /api/attempts` body. Clear the key after a successful confirm so a
  user starting tomorrow's problem doesn't inherit yesterday's hint list.
- Caveat carried to handoff: clears only if the same browser completes the
  flow. Cross-device (open hints on phone, upload on laptop) loses the list.
  Acceptable for v1; server-side logging fixes it in Phase 5 if needed.

## Step 8 — Tests + live smoke + docs

- **Python tests** mirror Phase 3 style — fakes in
  [api/tests/fake_anthropic.py](../api/tests/fake_anthropic.py) and
  [api/tests/fake_supabase.py](../api/tests/fake_supabase.py). New file
  `api/tests/test_parse_solution.py` covering: auth (401), missing attempt
  (404), happy path (single image → parsed_markdown set + llm_call logged),
  multi-image happy path, retry path (parse failure on attempt 1, success on
  attempt 2 — both logged), terminal failure path (parse_status='parse_failed'
  + 200 returned). Fake the storage download — pass image bytes directly via
  a fake `_load_image_bytes(path) -> bytes`.
- **Next.js**: no Jest setup; `npm run build` + `npm run lint` clean.
- **Live smoke test** (mirror Phase 3's 2026-05-14 run):
  - Real photo from operator's phone → upload → parse → review → confirm.
  - Verify `attempts` row has all four new columns populated, `llm_calls`
    row exists with sane vision token counts, and `daily_assignments.status
    = 'submitted'`.
  - Force a parse failure path (e.g., upload a non-handwriting image like a
    landscape photo) and verify the UI fallback.
- **Docs**:
  - Update [../CLAUDE.md](../CLAUDE.md) `LLM usage` section: mention that
    vision parsing uses Sonnet 4.6.
  - Update [../web/.env.local.example](../web/.env.local.example) only if
    new env vars are added (likely none).

## Risks to watch

- **HEIC**. Real risk for any iPhone user. Without conversion, upload
  silently succeeds and parse 415s on the Anthropic side — step 4 fixes
  this client-side. Test on a real iPhone before declaring step 4 done;
  desktop emulation doesn't produce HEIC.
- **Vision cost**. Each image is ~1500 input tokens at typical sizes. Five
  images per attempt × $3/1M = ~$0.02 per submission. Acceptable, but worth
  logging carefully so the Phase 6 dashboard shows per-attempt cost.
- **Mobile camera quirks**. iOS Safari + `<input capture="environment">` can
  behave unexpectedly with `multiple`. Test on a real device early; do not
  trust desktop emulation.
- **Parse-failed UX dead-end**. If we silently strand the user with a blank
  textarea, the trust hit is real. The fallback message must explain "vision
  couldn't read this — please type your solution as markdown" with a link
  to a short LaTeX cheat-sheet (one-liner is fine).
- **Stale React state on /upload page reload mid-flow**. If the user
  refreshes between submit and review, we need to recover state from the
  attempt row (`attempts.parse_status` + `raw_image_paths` + signed-download
  URLs). Server-load attempt-for-today on mount; resume in the matching UI
  state.
- **Race: two tabs open**. Same user submits two upload sessions for today.
  The `attempts_one_per_assignment` unique constraint will fire on the
  second `POST /api/attempts` — return a 409 with the existing attempt id so
  the second tab transitions into review on the existing row.
- **`@tailwindcss/typography` not installed**. Carried as Phase 3 follow-up
  #2. The review preview wants `prose` styling. Install during step 6.

## Things easy to forget (from CLAUDE.md / SPEC.md / ARCHITECTURE.md)

- **Vision parse is always user-reviewed** before grading. UI cannot ever
  auto-submit the parse directly to grading. [SPEC.md §4](../SPEC.md#L78-L87)
- **Original images always retained** — even on parse failure. Never delete
  from storage as part of any failure cleanup.
- **Every Claude call logged to `llm_calls`** including vision calls. The
  `call_json_vision` helper inherits this from `_call_and_log`.
- **Sonnet 4.6 = `claude-sonnet-4-6`**. Pricing in
  [api/anthropic_client.py](../api/anthropic_client.py) `PRICING`.
- **Next.js 16, not 15.** Auth proxy at
  [web/proxy.ts](../web/proxy.ts); exported function `proxy`. Tailwind v4
  `@import "tailwindcss"`. `web/` has its own `.git`.
- **No Jest setup in `web/`** — same as Phase 3, smoke-test through the dev
  server.

## Handoff to Phase 5 (preview)

Phase 5 picks up an `attempts` row with `parse_status='confirmed'`,
`user_edited_markdown` set, `submitted_at` set, and `daily_assignments.status
= 'submitted'`. It adds:

- `POST /grade-solution` in Python.
- Grade + feedback columns on `attempts` (already sketched in
  [ARCHITECTURE.md](../ARCHITECTURE.md) §Attempts).
- A feedback UI on /daily showing the verdict + a dispute flag.
- `POST /update-plan` and the plan-adaptation flow.

Decisions deferred out of Phase 4 that Phase 5 will need to revisit:

- Server-side hint click logging — Phase 4 ships with `sessionStorage`,
  which loses cross-device opens.
- Per-user timezone for the day-key (Phase 3 follow-up #1) — increasingly
  load-bearing once grading drives streak/cadence signals.
- Multi-attempt support (Phase 3 follow-up #5) — if it lands, the
  `attempts_one_per_assignment` constraint from step 1 has to be replaced
  with a separate `bonus_assignments` path.
