# Phase 5-rev — execution plan

> **Status: COMPLETE.** This document is a closed execution and decision record. Do not use it as an active plan. Current work is tracked in `docs/pivot-plan.md`.

Forward-looking plan for Phase 5-rev. Source-of-truth for the product is
[../SPEC.md](../SPEC.md), [../ARCHITECTURE.md](../ARCHITECTURE.md),
[../graph-design.md](../graph-design.md), and [../personas.md](../personas.md).
This file captures *execution* decisions and step ordering.

## Where we are

- **Phase 4-rev complete.** New user can sign up, complete the v2 survey
  (free-text intent + node ratings + mode-balance), see their interests added to
  the megagraph (Haiku dedup + Sonnet generate), and land on `/daily` showing
  surfaced queue items. The queue currently holds `suggested_interest` placeholder
  items seeded by the survey route.
- **`generate_problem.py` is stale.** It still reads from `plan_nodes` +
  `canonical_topics` and `surveys.difficulty_curve` — all gone or changed in
  Phase 4-rev migrations. It must be refactored in step 3.
- **`web/lib/pythonApi.ts` is stale.** `generateProblem` still passes
  `plan_node_id`. Update in step 3 alongside the route refactor.
- **`/parse-solution` was never implemented.** The v1 plan got as far as
  the DB columns (`parsed_markdown`, `parse_status`, etc.) in migration
  `20250011`. Phase 5-rev step 1 implements the route.
- **No `/grade-solution` exists.** Step 2.
- **No real problem flow.** Daily-page problem cards link nowhere. Step 4.
- **No notebook UI.** Step 6.
- **No skill tree view.** Steps 7. React Flow + Dagre not yet installed.

## Phase 5-rev goal

Real problem flow works end-to-end: user opens a problem from their daily three,
reads the statement, uses hints, photographs their solution, reviews and edits the
parse, submits for dialogic feedback, and gets a notebook entry. The skill tree
view shows the user's slice of the megagraph with adjacent regions greyed out.

Out of scope: paper engagement (Phase 6-rev); real queue adaptation and refresher
scheduling (Phase 7-rev); cross-pollination (Phase 7-rev); operator admin surfaces
(Phase 8-rev).

---

## Decisions locked in

Resolve these before execution. Don't re-litigate them during implementation.

| Decision | Choice | Why |
|---|---|---|
| `GenerateProblemRequest` schema | `{user_id, node_id}` — drop `plan_node_id` | Plans deprecated; `nodes` is the v2 anchor |
| Difficulty derivation (v2) | `difficulty_hint` → int: `intro`=2, `core`=3, `advanced`=4; no adaptive adjustment yet | Full adaptation is Phase 7-rev; a simple map is sufficient to produce calibrated problems |
| `/generate-problem` writes a `queue_items` row | Yes — returns `{problem_id, queue_item_id}` | Every content item must enter the queue for the daily surface to work; callers (survey route, skill tree) simply call the endpoint and get a linkable queue item back |
| Duplicate queue items for same node/user | Accepted for Phase 5-rev | No unique constraint on `(user_id, kind, ref_id)` in `queue_items`; Phase 7-rev's real `/update-queue` handles deduplication and pruning |
| Problem page URL | `/problem/[queue_item_id]` where `[id]` = queue_item id | `attempts.queue_item_id` FK must be populated; queue item state (→ `done`/`dismissed`) must be updated on completion; problem id alone is not enough context |
| Attempt creation timing | On "Start working" click, via `POST /api/problem/[id]/start` | Avoids SSR race conditions on page load; gives a stable `attempt_id` anchor for per-hint server writes |
| Hint tracking | Server-side per click: `POST /api/problem/[id]/hint` updates `attempts.hint_levels_used` | F12 (pivot-plan.md) says implement in step 5-rev.4; client-state-only tracking risks data loss if the user abandons without submitting |
| Image URL handling for vision | Next.js signs storage URLs (using the existing admin client in `api/upload/sign/route.ts`) and passes them to Python as `image_urls: list[str]` | Python service doesn't need a separate storage credential; aligns with the existing signing pattern; simplifies test infrastructure |
| Vision call implementation | Direct `client.messages.create(...)` + `log_llm_call(...)` in `parse_solution.py` — does NOT use `call_json` | `call_json` only accepts `user_prompt: str`; vision requires a list of content blocks (text + image URLs). Calling the API directly and logging manually satisfies the "every call logged" rule from `anthropic_client.py`'s docstring |
| `/grade-solution` response format | `call_json` with a `GradeResponse(response_md: str)` schema | Reuses the existing retry/logging infrastructure; the JSON wrapper (`{"response_md": "..."}`) adds minimal overhead |
| `_subtopic_titles` dual-shape handling | Handle both `{slug, title}` dict (v1-seeded foundation/interest nodes) and bare `str` (new interest nodes from `/add-interest`) | Both shapes exist in `nodes.subtopics_json`; failing silently on the new shape would give empty subtopic lists to the problem generator |
| `context_md` rename in schema + prompt | Rename `GeneratedProblem.generated_context_md` → `context_md`; update prompt text and test fixture `VALID_PROBLEM_JSON` | DB column is `context_md` after migration 20250011; the mismatch means problem inserts currently use the wrong key |
| Survey route problem seeding | After all `/add-interest` calls, call `generateProblem` for up to 2 user interest nodes (parallel, best-effort — errors silently swallowed) | Seeds the queue with real `problem` kind items; capped at 2 to keep survey latency acceptable; errors don't block survey completion |
| `web/app/upload/page.tsx` | Left in place, not linked from the new problem flow | Upload is now integrated into the problem page's step 2; no reason to delete the standalone page in this phase |
| Skill tree adjacency | 1 hop only from user's engaged nodes | The 2-hop frontier is Phase 7-rev's cross-pollination domain; 1 hop is enough for Phase 5-rev discovery |
| Skill tree "Engage" button | `POST /api/queue/request` with `{node_id}` | Matches ARCHITECTURE.md route list; the route adds the node as an interest (if not already), calls Python `/generate-problem`, and returns `{queue_item_id}` for navigation to the problem page |
| React Flow + Dagre packages | `reactflow` + `@dagrejs/dagre` | Standard combination for React Flow v11+; install in step 7 |
| Notebook entry title for problems | `"{node_title} — Problem"` | Descriptive enough to browse; Phase 9-rev polish can refine |

---

## Step table

| # | Step | One commit | Status |
|---|---|---|---|
| 1 | FastAPI `POST /parse-solution` | New module, prompt, schema additions, tests, register in main.py | done |
| 2 | FastAPI `POST /grade-solution` | New module, prompt, schema additions, tests, register in main.py | done |
| 3 | FastAPI: refactor `/generate-problem` | Read from `nodes`, write queue item; schema + prompt + test rewrite; update `pythonApi.ts` and survey route | done |
| 4 | Next.js: real problem flow | `web/app/problem/[id]/page.tsx` + five API sub-routes + `ProblemView` component + `DailyView` link fix | done |
| 5 | Next.js: "mark as refreshed" | `POST /api/problem/[id]/skip` route + skip button in `ProblemView` | done |
| 6 | Next.js: notebook browse + read | `/notebook` + `/notebook/[id]` pages + `/api/notebook` route + types | done |
| 7 | Next.js: skill tree view | `web/app/skill-tree/page.tsx` + `/api/graph/me` + `/api/queue/request` + `SkillTreeView` + `NodePanel`; install npm deps | done |
| 8 | Phase 5-rev acceptance | Smoke test + pivot-plan.md status line update | done |

---

## Step 1 — FastAPI `POST /parse-solution`

### New files
- `api/routes/parse_solution.py`
- `api/prompts/parse_solution.py`

### Schema additions (`api/schemas.py`)

```python
class ParseSolutionRequest(BaseModel):
    user_id: UUID
    attempt_id: UUID
    image_urls: list[str]  # pre-signed Supabase Storage URLs (signed by Next.js)

class ParseSolutionResponse(BaseModel):
    attempt_id: UUID
    parsed_markdown: str
    parse_status: str  # 'parsed' | 'failed'
```

### Route flow (`api/routes/parse_solution.py`)

1. Auth check (`require_internal_token`).
2. Load the `attempts` row by `attempt_id` — verify it exists and `user_id` matches
   the request. 404 if not found; 403 if user_id mismatch.
3. Build Anthropic API message with content blocks:
   - One `{"type": "text", "text": "Transcribe the handwritten work below to Markdown + LaTeX."}` block
   - One `{"type": "image", "source": {"type": "url", "url": image_url}}` block per URL
4. Call `client.messages.create(model=SONNET_MODEL, max_tokens=4096, system=[...], messages=[...])`.
   - System: cached prompt from `api/prompts/parse_solution.py`.
   - Because the response is plain markdown (not JSON), this call does NOT use
     `call_json`. Log manually with `log_llm_call(...)`.
5. Extract text from response. If extraction fails or content is suspiciously short
   (< 10 chars), set `parse_status = 'failed'`; otherwise `'parsed'`.
6. Update `attempts` row:
   - `parsed_markdown = extracted_text`
   - `parse_status = parse_status`
   - `parsed_by_llm_call_id = llm_call_id` (the id returned by `log_llm_call`)
7. Return `ParseSolutionResponse`.

### Prompt (`api/prompts/parse_solution.py`)

System (cache-eligible — same across all calls):
```
You are transcribing handwritten mathematical work into clean Markdown + LaTeX.

Rules:
- Preserve the student's approach and reasoning faithfully, even if it contains errors.
- Use $...$ for inline math, $$...$$ for display math.
- Where text is unclear or ambiguous, note it in [brackets] and make your best effort.
- Preserve the logical structure: steps, sub-steps, headings if present.
- Output Markdown only — no JSON wrapper, no commentary, no preamble.
```

User (per-call, not cached):
```
The following image(s) show a handwritten solution to a math/physics problem.
Transcribe the work faithfully to Markdown + LaTeX.
```
(followed by image content blocks)

### Registration (`api/main.py`)
```python
from routes.parse_solution import router as parse_solution_router
app.include_router(parse_solution_router)
```

### Tests (`api/tests/test_parse_solution.py`)

| Test | What it verifies |
|---|---|
| `test_missing_bearer_returns_401` | Auth required |
| `test_wrong_bearer_returns_401` | Bad token rejected |
| `test_attempt_not_found_returns_404` | Missing attempt row → 404 |
| `test_user_id_mismatch_returns_403` | Wrong user → 403 |
| `test_happy_path_parses_and_updates_attempt` | Sonnet called; attempt row updated; `parsed_markdown` + `parse_status='parsed'` in response; `llm_calls` row written |
| `test_empty_response_sets_failed_status` | When Anthropic returns very short text → `parse_status='failed'` |

Note: `FakeAnthropic.queue(...)` takes a plain string — for vision responses this
is the markdown text (not JSON). The test can queue a markdown string directly.
The `FakeSupabase` needs a responder for `("attempts", "select")` and
`("attempts", "update")`.

`FakeSupabase` currently lacks an `update` dispatch path in `FakeTable`. The
`fake_supabase.py` update stub already exists on `FakeTable` (line 79) — confirm
`_dispatch` handles the `"update"` op (currently it doesn't route `update` to
responders). Add `update` support in `fake_supabase.py` as part of this step if
needed.

---

## Step 2 — FastAPI `POST /grade-solution`

### New files
- `api/routes/grade_solution.py`
- `api/prompts/grade_solution.py`

### Schema additions (`api/schemas.py`)

```python
class GradeResponse(BaseModel):
    """Sonnet grade call output — wrapped in JSON for call_json compatibility."""
    response_md: str

class GradeSolutionRequest(BaseModel):
    user_id: UUID
    attempt_id: UUID
    user_edited_markdown: str  # the user's (possibly-edited) parsed solution

class GradeSolutionResponse(BaseModel):
    grade_response_md: str
    notebook_entry_id: UUID
```

### Route flow (`api/routes/grade_solution.py`)

1. Auth check.
2. Load attempt → verify user_id matches; load `problem_id`.
3. Load problem → `statement_md`, `rubric_md`, `topic_node_id`.
   (Do NOT pass `solution_md` to Claude — that's the answer key; we don't want
   the model to accidentally echo it.)
4. Load node by `topic_node_id` → `title`, `slug`.
5. `call_json(...)` with `GradeResponse` schema:
   - `model=SONNET_MODEL`
   - `route="/grade-solution"`
   - System: cached grading prompt
   - User: problem statement + rubric + user's work (see prompt section below)
6. Update `attempts`:
   - `user_edited_markdown = body.user_edited_markdown`
   - `grade_response_md = result.response_md`
   - `submitted_at = now()` (ISO string)
7. Insert `notebook_entries` row:
   ```python
   {
       "user_id": str(body.user_id),
       "entry_kind": "problem_attempt",
       "ref_id": str(body.attempt_id),
       "title": f"{node_title} — Problem",
       "topic_node_slugs": [node_slug],
   }
   ```
   Note: `fts_vector` is a generated column — do not include it in the insert.
8. Return `GradeSolutionResponse`.

### Prompt (`api/prompts/grade_solution.py`)

System (cacheable):
```
You are a science tutor reviewing a student's written solution.

Respond like a thoughtful colleague — not a teacher scoring a rubric. Your response should:
- Engage with what the student actually did, in their order.
- Acknowledge correct steps and reasoning directly.
- Point out what's missing, incomplete, or could be clearer — without condescension.
- Raise one observation or question the student might not have considered.
- Keep it to 2–4 paragraphs.

Never say "correct" or "incorrect" as a verdict. Never reveal the full solution.
Output plain Markdown with LaTeX ($...$ inline, $$...$$ display) where needed.

Output JSON with a single field: {"response_md": "<your markdown response here>"}.
```

User (per-call):
```
Problem statement:
{statement_md}

What a correct solution demonstrates:
{rubric_md}

The student's work:
{user_edited_markdown}
```

### Tests (`api/tests/test_grade_solution.py`)

| Test | What it verifies |
|---|---|
| `test_missing_bearer_returns_401` | Auth required |
| `test_attempt_not_found_returns_404` | Missing attempt → 404 |
| `test_user_id_mismatch_returns_403` | Wrong user → 403 |
| `test_happy_path_grades_and_creates_notebook_entry` | Sonnet called with correct prompt; attempt updated (`grade_response_md`, `user_edited_markdown`, `submitted_at`); `notebook_entries` row written; response contains `grade_response_md` and `notebook_entry_id` |
| `test_solution_md_not_sent_to_claude` | Verify `solution_md` does not appear in the Sonnet user message |

`FakeSupabase` needs responders for `attempts/select`, `problems/select`,
`nodes/select`, `attempts/update`, `llm_calls/insert`, `notebook_entries/insert`.

---

## Step 3 — FastAPI: refactor `/generate-problem`

This step is the biggest surgery of the phase. Four files change.

### Schema changes (`api/schemas.py`)

```python
# Before
class GenerateProblemRequest(BaseModel):
    user_id: UUID
    plan_node_id: UUID

class GeneratedProblem(BaseModel):
    ...
    generated_context_md: str | None = None  # old field name

class GenerateProblemResponse(BaseModel):
    problem_id: UUID

# After
class GenerateProblemRequest(BaseModel):
    user_id: UUID
    node_id: UUID  # replaces plan_node_id

class GeneratedProblem(BaseModel):
    ...
    context_md: str | None = None  # matches DB column name

class GenerateProblemResponse(BaseModel):
    problem_id: UUID
    queue_item_id: UUID  # new — the queue item written for this user
```

### Prompt changes (`api/prompts/problem.py`)

- Change every occurrence of `"generated_context_md"` → `"context_md"` in the
  system prompt text.

### Route changes (`api/routes/generate_problem.py`)

Replace steps 1–2 (plan_node + survey lookup) with:

```python
# 1. Load node from nodes table by node_id
node_resp = (
    supabase.table("nodes")
    .select("id, title, description_md, difficulty_hint, subtopics_json")
    .eq("id", str(body.node_id))
    .limit(1)
    .execute()
)
if not node_resp.data:
    raise HTTPException(status_code=404, detail="node not found")
node = node_resp.data[0]

# 2. Derive difficulty from difficulty_hint (no adaptive adjustment until Phase 7-rev)
DIFFICULTY_MAP = {"intro": 2, "core": 3, "advanced": 4}
difficulty = DIFFICULTY_MAP.get(node["difficulty_hint"], 3)
topic_node_id = node["id"]
```

Update `_subtopic_titles` to handle both shapes:
```python
def _subtopic_titles(subtopics_field: Any) -> list[str]:
    if not subtopics_field:
        return []
    titles: list[str] = []
    for entry in subtopics_field:
        if isinstance(entry, dict) and "title" in entry:
            titles.append(entry["title"])
        elif isinstance(entry, str):
            titles.append(entry)
    return titles
```

Update `cache_lookup` parameter name (semantic only — the DB column is already
`topic_node_id` after migration 20250011):
```python
def cache_lookup(supabase, *, topic_node_id, difficulty, context_hook_id):
    query = (
        supabase.table("problems")
        .select("id")
        .eq("topic_node_id", str(topic_node_id))
        .eq("difficulty", difficulty)
    )
    ...
```

Update problem insert dict (steps 7–8):
```python
problem_row = {
    "topic_node_id": topic_node_id,
    "difficulty": difficulty,
    "context_hook_id": context_hook_id,
    "statement_md": generated.statement_md,
    "solution_md": generated.solution_md,
    "rubric_md": generated.rubric_md,
    "context_md": generated.context_md,  # was generated_context_md
}
```

Add queue item write after problem is secured (step 8.5, after both the new-insert
and the race-won-by-other-worker paths converge on a `problem_id`):
```python
queue_row = {
    "user_id": str(body.user_id),
    "kind": "problem",
    "ref_id": problem_id,
    "state": "pending",
    "priority_score": 0.5,      # Phase 7-rev computes this dynamically
    "added_reason": f"A problem on {node['title']}",
    "time_estimate_minutes_low": 15,
    "time_estimate_minutes_high": 30,
}
queue_resp = supabase.table("queue_items").insert(queue_row).execute()
queue_item_id = queue_resp.data[0]["id"]
```

Return `GenerateProblemResponse(problem_id=UUID(problem_id), queue_item_id=UUID(queue_item_id))`.

### Test rewrite (`api/tests/test_generate_problem.py`)

All existing tests use `plan_node_id` and mock `plan_nodes` / `surveys`. Rewrite:

Rename `_prime_node_and_survey` → `_prime_node(supabase, *, node_id, band, hooks)`:
```python
def _prime_node(supabase, *, node_id, band="core", hooks=None):
    supabase.respond("nodes", "select", lambda _: [{
        "id": node_id,
        "title": "Special Relativity",
        "description_md": "Lorentz invariance and consequences.",
        "difficulty_hint": band,
        "subtopics_json": [
            {"slug": "time-dilation", "title": "Time dilation"},
            {"slug": "length-contraction", "title": "Length contraction"},
        ],
    }])
    supabase.respond("context_hooks", "select", lambda _: hooks or [])
```

Add a `queue_items` insert responder in every test that reaches the queue write
(all happy-path tests):
```python
supabase.respond("queue_items", "insert", lambda _: [{"id": str(uuid4())}])
```

Updated test request body: `{"user_id": str(uuid4()), "node_id": str(uuid4())}`.

Update `test_happy_path_generates_problem_and_hints`:
- `VALID_PROBLEM_JSON` fixture: rename `"generated_context_md"` → `"context_md"`.
- Assert `problems_insert.payload["context_md"]` (not `"generated_context_md"`).
- Assert `problems_insert.payload["topic_node_id"]` (not `"canonical_topic_id"`).
- Assert response contains both `problem_id` and `queue_item_id`.

Update `test_cache_hit_skips_anthropic`:
- On a cache hit the problem already exists but a new queue item is still written.
  Update assertion: response has `queue_item_id`; there IS a `queue_items` insert
  even on cache hit.

Rename difficulty tests: `_prime_node(supabase, node_id=..., band="intro")` →
difficulty=2; `band="core"` → 3; `band="advanced"` → 4.

Remove `test_missing_survey_returns_404` (surveys no longer queried).

### `web/lib/pythonApi.ts` changes

```typescript
interface GenerateProblemArgs {
  userId: string;
  nodeId: string;  // was planNodeId
}

interface GenerateProblemResponse {
  problem_id: string;
  queue_item_id: string;  // new
}

export async function generateProblem(
  args: GenerateProblemArgs,
): Promise<GenerateProblemResponse> {
  return pythonPost("/generate-problem", {
    user_id: args.userId,
    node_id: args.nodeId,
  });
}
```

Also add:
```typescript
interface ParseSolutionArgs {
  userId: string;
  attemptId: string;
  imageUrls: string[];
}
interface ParseSolutionResponse {
  attempt_id: string;
  parsed_markdown: string;
  parse_status: string;
}
export async function parseSolution(args: ParseSolutionArgs): Promise<ParseSolutionResponse> {
  return pythonPost("/parse-solution", {
    user_id: args.userId,
    attempt_id: args.attemptId,
    image_urls: args.imageUrls,
  });
}

interface GradeSolutionArgs {
  userId: string;
  attemptId: string;
  userEditedMarkdown: string;
}
interface GradeSolutionResponse {
  grade_response_md: string;
  notebook_entry_id: string;
}
export async function gradeSolution(args: GradeSolutionArgs): Promise<GradeSolutionResponse> {
  return pythonPost("/grade-solution", {
    user_id: args.userId,
    attempt_id: args.attemptId,
    user_edited_markdown: args.userEditedMarkdown,
  });
}
```

### Survey route update (`web/app/api/survey/route.ts`)

After all `addInterest` calls complete, seed 1–2 problem queue items (best-effort):

```typescript
// Best-effort: generate problems for the first 2 interest nodes.
// Errors are swallowed — a failed generation doesn't block survey completion.
const { data: seedInterests } = await supabase
  .from("user_interests")
  .select("node_id")
  .eq("user_id", userId)
  .limit(2);

await Promise.all(
  (seedInterests ?? []).map((ui) =>
    generateProblem({ userId, nodeId: ui.node_id }).catch(() => null)
  )
);
```

---

## Step 4 — Next.js: real problem flow

This is the largest Next.js step. One commit containing:

### New page: `web/app/problem/[id]/page.tsx`

Server component. `[id]` = queue_item_id.

```tsx
// Loads: queue_item, problem, hints, existing pending attempt (if any)
// Auth guard → redirect('/signin')
// Redirect to /daily if queue_item.state is already 'done' or 'dismissed'
// Renders: <ProblemView queueItem={...} problem={...} hints={...} existingAttempt={...} />
```

Data loaded directly from Supabase (no self-referential HTTP call):
- `queue_items` → by id, verify `user_id === user.id`
- `problems` → by `queue_item.ref_id`
- `problem_hints` → by `problem_id`, ordered by `level`
- `attempts` → most recent pending attempt for `(user_id, queue_item_id)`, if any

### New component: `web/components/ProblemView.tsx`

Client component. Manages step state:

```
Step 1 — View
  Statement (markdown+LaTeX via existing web/lib/markdown.tsx)
  Context paragraph (context_md, rendered)
  Hints panel (collapsed; each hint click calls POST /api/problem/[id]/hint)
  Buttons: "Start working" (→ Step 2), "Skip — I've got this" (→ POST /api/problem/[id]/skip → /daily)

Step 2 — Upload
  Drag-drop / file picker (reuse pattern from web/app/upload/page.tsx)
  Each file: POST /api/upload/sign → signed URL → PUT to Supabase Storage
  Image previews
  On first upload: POST /api/problem/[id]/start → creates attempt, stores attempt_id in state
  "Parse my solution" button → POST /api/problem/[id]/parse with {attempt_id, image_paths}
  Loading state during parse

Step 3 — Review parse
  Rendered parsed markdown (markdown+LaTeX)
  Editable <textarea> (the raw markdown)
  Re-render on change
  "Submit for feedback" → POST /api/problem/[id]/submit with {attempt_id, user_edited_markdown}
  "Re-upload" → back to Step 2

Step 4 — Feedback
  Claude's response (grade_response_md, rendered as markdown+LaTeX)
  "Done" button → marks queue item done, navigates to /daily
  Notebook entry auto-created in the grade step; no extra action needed
```

Note: keep the existing `web/lib/markdown.tsx` for rendering (already handles
LaTeX via KaTeX or similar — confirm it's available).

### New API routes

All live under `web/app/api/problem/[id]/`:

**`route.ts` (GET)**
- Auth check
- Load queue_item + problem + hints + existing attempt
- Return JSON payload (same shape as what the page server component loads)
- Used for client-side refreshes if needed

**`start/route.ts` (POST)**
- Auth check
- Verify queue_item belongs to user
- Insert `attempts` row: `{user_id, problem_id, queue_item_id, hint_levels_used: [], parse_status: 'pending', raw_image_paths: []}`
- Return `{attempt_id}`

**`hint/route.ts` (POST)**
- Body: `{attempt_id, level: number}`
- Auth check; verify attempt belongs to user
- Read current `hint_levels_used`; append `level` if not already present; update row
- Return `{ok: true}`

**`parse/route.ts` (POST)**
- Body: `{attempt_id, image_paths: string[]}` (Supabase storage paths)
- Auth check; verify attempt belongs to user
- For each `image_path`: call Supabase admin client `.storage.from("solutions").createSignedUrl(path, 300)` → collect signed URLs
- Call `pythonApi.parseSolution({userId, attemptId, imageUrls: signedUrls})`
- Update attempt's `raw_image_paths` with the storage paths
- Return `{parsed_markdown, parse_status}`

**`submit/route.ts` (POST)**
- Body: `{attempt_id, user_edited_markdown: string}`
- Auth check; verify attempt belongs to user
- Call `pythonApi.gradeSolution({userId, attemptId, userEditedMarkdown})`
- Update `queue_items.state = 'done'`, `queue_items.updated_at = now()`
- Return `{grade_response_md, notebook_entry_id}`

### `web/lib/types.ts` additions

```typescript
export interface Attempt {
  id: string;
  user_id: string;
  problem_id: string;
  queue_item_id: string | null;
  raw_image_paths: string[];
  parsed_markdown: string | null;
  user_edited_markdown: string | null;
  hint_levels_used: number[];
  parse_status: string | null;
  parsed_by_llm_call_id: string | null;
  grade_response_md: string | null;
  submitted_at: string | null;
  marked_refreshed: boolean;
  requested_easier: boolean;
  requested_harder: boolean;
  parent_attempt_id: string | null;
  disputed: boolean;
  created_at: string;
}

export interface NotebookEntry {
  id: string;
  user_id: string;
  entry_kind: "problem_attempt" | "paper_engagement";
  ref_id: string;
  title: string;
  topic_node_slugs: string[];
  created_at: string;
  updated_at: string;
}
```

### `web/components/DailyView.tsx` change

Change the problem card CTA from a `<span>` to a `<Link>`:

```tsx
// Before
<span className="text-sm font-medium text-zinc-400 cursor-default">
  {kindCta(item.kind)}
</span>

// After (for problem kind)
{item.kind === "problem" && item.ref_id ? (
  <Link href={`/problem/${item.queue_item_id}`}
    className="text-sm font-medium text-zinc-900 underline-offset-2 hover:underline">
    Work on this →
  </Link>
) : (
  <span className="text-sm font-medium text-zinc-400 cursor-default">
    {kindCta(item.kind)}
  </span>
)}
```

(`item.queue_item_id` is the id field of `SurfacedQueueItem` — confirm that
`queueHelpers.ts` maps this from the Supabase row id correctly.)

---

## Step 5 — Next.js: "mark as refreshed"

### New file: `web/app/api/problem/[id]/skip/route.ts`

POST handler:
1. Auth check; verify queue_item belongs to user; load problem_id.
2. Insert `attempts` row: `{user_id, problem_id, queue_item_id, marked_refreshed: true, hint_levels_used: [], parse_status: null, raw_image_paths: []}`.
3. Update `queue_items.state = 'done'`.
4. Upsert `user_node_states`: for the problem's `topic_node_id`, increment
   `engagement_count`, set `state = 'comfortable'` if currently `'unseen'` or
   `'active'`. Use a read-then-write (not a raw upsert) because we need the
   current value to compute the new engagement_count.
5. Return `{ok: true}`.

This is entirely in the Next.js route handler — no Python LLM call needed.

### `web/components/ProblemView.tsx` change

Wire the "Skip — I've got this" button in Step 1 to call `POST /api/problem/[id]/skip`
and redirect to `/daily` on success.

---

## Step 6 — Next.js: notebook browse + read

### New files

- `web/app/notebook/page.tsx` — server component (list view)
- `web/app/notebook/[id]/page.tsx` — server component (detail view; `[id]` = notebook_entry_id)
- `web/app/api/notebook/route.ts` — GET endpoint

### `GET /api/notebook`

Query params: `?q=` (FTS search), `?topic=` (node slug filter), `?limit=&offset=` (pagination; default limit=20 offset=0).

```typescript
// Auth check
// Build query against notebook_entries for this user
// If q: .textSearch('fts_vector', q, { type: 'websearch', config: 'english' })
// If topic: .contains('topic_node_slugs', [topic])
// .order('created_at', { ascending: false }).range(offset, offset + limit - 1)
// Return { entries: NotebookEntry[], total: number }
```

`total` is a separate `.count()` query (or use Supabase's `count: 'exact'`
option on the same query).

### Notebook list page (`/notebook/page.tsx`)

Server component that loads entries (first 20, no filters) and renders:
- Page header: "Your notebook"
- Search box (client component — fetches `/api/notebook?q=...` on change)
- Entry cards: title, date (`created_at` formatted), kind badge (Problem / Paper),
  topic slugs as small tags

Clicking an entry → `/notebook/[id]`.

### Notebook detail page (`/notebook/[id]/page.tsx`)

Server component. For `entry_kind = 'problem_attempt'`:
1. Load `notebook_entries` row by id.
2. Load `attempts` row by `ref_id`.
3. Load `problems` row by `attempt.problem_id`.
4. Load `problem_hints` by `problem_id`, ordered by level.
5. Load `nodes` row by `problem.topic_node_id`.

Render:
- Breadcrumb: Notebook → [entry title]
- Node slug tag + date
- **Problem statement** (markdown+LaTeX)
- **Context** (`context_md`, if present)
- **Hints you opened**: list of hint texts for levels in `hint_levels_used` (or "None" if empty)
- **Your solution** (`user_edited_markdown ?? parsed_markdown`, rendered)
- **Feedback** (`grade_response_md`, rendered as markdown)

For `entry_kind = 'paper_engagement'`: render a "Phase 6-rev" placeholder — don't
implement paper rendering in this step.

### Navigation link

Add "Notebook" to the main nav in `web/app/layout.tsx` (or wherever global nav lives).
Check the current layout to find the right place. Also add "Skill Tree" link (for step 7).

---

## Step 7 — Next.js: skill tree view

### Install npm dependencies

```bash
npm install reactflow @dagrejs/dagre
npm install --save-dev @types/dagre
```

Run from `web/`.

### New files

- `web/app/skill-tree/page.tsx` — server component shell
- `web/app/api/graph/me/route.ts` — GET user graph
- `web/app/api/queue/request/route.ts` — POST generate problem for a node
- `web/components/SkillTreeView.tsx` — new React Flow client component
- `web/components/NodePanel.tsx` — side panel for clicked node

### `GET /api/graph/me`

```typescript
// Auth check
// 1. user_interests for this user (node_ids)
// 2. user_node_states for this user
// 3. Foundation nodes touched: nodes where kind='foundation' AND user_node_states exists
// 4. All interest nodes in user_interests
// 5. All edges where both endpoints are in the above node set
//    (or where at least one endpoint is a user node — include dangling edges to adjacents)
// 6. Adjacent nodes: nodes reachable via one hop from user_nodes, NOT in user_nodes
//    Implement as: select all edges where source OR target is in user_node_ids;
//    collect the other endpoint; exclude any that are already user nodes.

interface GraphResponse {
  user_nodes: Array<{ node: Node; state: UserNodeState | null }>;
  adjacent_nodes: Node[];
  edges: Edge[];
}
```

Keep the query simple given the 30-user, ~30-node scale:
load all nodes + edges, filter client-side (or use targeted Supabase queries —
either is fine at this scale).

### `POST /api/queue/request`

```typescript
// Body: { node_id: string }
// Auth check
// 1. Check if node is in user_interests for this user:
//    if not, call addInterest({ userId, rawText: node.title, addedVia: 'explicit_request' })
// 2. Call generateProblem({ userId, nodeId: node_id })
// 3. Return { queue_item_id }
// Redirect or let client navigate to /problem/[queue_item_id]
```

### `web/app/skill-tree/page.tsx`

Server component:
1. Auth check → redirect('/signin')
2. Fetch graph data from `/api/graph/me` (or directly from Supabase)
3. Render `<SkillTreeView graphData={...} />`

### `web/components/SkillTreeView.tsx`

Client component using React Flow + Dagre:

**Layout strategy:**
- Use Dagre with `rankdir: 'TB'` (top to bottom).
- Foundation nodes form the top layer (they are prerequisites for interest nodes).
- User's interest nodes form the middle layer.
- Adjacent nodes form a periphery (greyed out, smaller).

**Node types:**
- Foundation (user's): dark grey border, square-ish, state-coloured fill
- Interest (user's): rounded, state-coloured fill
  - `unseen`: white / light grey
  - `active`: blue-tinted
  - `comfortable`: green-tinted
  - `struggling`: orange-tinted
  - `bookmarked`: violet-tinted
- Adjacent: dashed border, grey fill, reduced opacity

**Edge types:**
- `prerequisite`: solid directed arrow
- `related`: dashed, no arrowhead (bidirectional implied)

**Interactions:**
- Click any node → set `selectedNode` state → renders `<NodePanel />`
- Click background → deselect

**Controls:**
- React Flow's built-in zoom + pan controls

### `web/components/NodePanel.tsx`

Side panel (fixed right side or a drawer):
- Node title, domain badge, difficulty badge
- Description (`description_md`, rendered)
- Subtopics list
- User state indicator (from `user_node_states`)
- Engagement history: `engagement_count`, `last_engaged_at`
- Buttons:
  - "Get a problem" → `POST /api/queue/request` → navigate to `/problem/[queue_item_id]`
  - "Bookmark" → `POST /api/queue/bookmark` (stub: just write to `bookmarks` table) — can be a simple client-side Supabase call
  - "Add to interests" (shown only for adjacent nodes not in user_interests) → calls `POST /api/interest` then refreshes graph data

---

## Step 8 — Phase 5-rev acceptance

End-to-end smoke test:

1. New user signs up → completes survey → survey route calls `generateProblem` for 1–2 interests.
2. `/daily` shows at least one `problem` kind card with "Work on this →" linked.
3. User clicks the problem card → `/problem/[queue_item_id]` loads with statement, context, and collapsed hints.
4. User opens 2 hint levels → each click updates `attempts.hint_levels_used` (verify in Supabase).
5. User clicks "Start working" (creates attempt); then uploads a photo → storage PUT succeeds; parse returns markdown.
6. User edits parsed markdown (minor edit); clicks "Submit for feedback" → Claude's response renders.
7. "Done" → redirected to `/daily`; the problem card is gone (queue item state = `done`).
8. `/notebook` → shows one entry. Click it → renders statement, hints used, solution, feedback.
9. `/skill-tree` → renders user's nodes and edges; adjacent nodes visible greyed out.
10. Click an adjacent node → NodePanel shows; "Get a problem" generates a new queue item and navigates to the problem page.
11. `llm_calls` table: rows for parse (Sonnet), grade (Sonnet), and for any generate-problem calls (Haiku hook-match + Sonnet if cache miss).

Update pivot-plan.md status line:
```
Status: Phase 5-rev complete.
Next step: Phase 6-rev step 1 — FastAPI: papers ingestion endpoint.
```

---

## Risks to watch

- **`FakeSupabase.update` not dispatched.** Looking at `fake_supabase.py`, the
  `FakeTable.update(payload)` stub exists but `_dispatch` may not route `"update"`
  ops to responders (the responder dict is keyed by `(table, op)` and `"update"`
  might fall through to the empty-list default). Tests for `parse_solution` and
  `grade_solution` that assert attempt row updates will fail silently if this
  isn't fixed. Check and fix `fake_supabase.py` in step 1.

- **`context_md` rename propagation.** The test fixture `VALID_PROBLEM_JSON` in
  `test_generate_problem.py` still has `"generated_context_md"`. If not updated
  in step 3, the test will fail to match the DB column name assertion. Rename in
  the same commit.

- **Supabase signed URL for vision.** The `parse/route.ts` calls
  `.storage.from("solutions").createSignedUrl(path, 300)`. The bucket is named
  `"solutions"` (confirmed in `api/upload/sign/route.ts`). Verify that the admin
  Supabase client in Next.js (using `SUPABASE_SECRET_KEY`) can sign read URLs for
  this bucket — the bucket may only have upload permission set. If read signing
  fails, the parse call will error with a 500.

- **React Flow peer dependencies.** `reactflow` requires `react@>=18` and a
  specific `react-dom` version. Run `npm install` in `web/` and confirm there are
  no peer dependency warnings before building the skill tree.

- **`SurfacedQueueItem.queue_item_id` field name in DailyView link.** The
  `DailyView` component receives `SurfacedQueueItem` items. Looking at `toItem`
  in `queueHelpers.ts`, the `queue_item_id` field is set from `raw.id ?? raw.queue_item_id`.
  When building the link href `/problem/${item.queue_item_id}`, confirm the field
  is populated (it should be — the surface_daily Python route returns `queue_item_id`
  in each item). Test this manually in step 4.

- **`suggested_interest` + `problem` queue item mix.** After step 3's survey
  route update, the queue will contain both kinds. The daily page shows all of
  them. Problem cards link correctly; `suggested_interest` cards still have no
  link (CTA remains a `<span>`). This is expected — the mix clears up once
  Phase 7-rev's real `update_queue` prunes placeholder items.

- **Dagre node sizing.** React Flow + Dagre needs explicit node widths and heights
  to compute a non-overlapping layout. Estimate based on label length or use a
  fixed size. Iterate visually — the first pass layout may need adjustment.

---

## Things easy to forget

- **Register every new FastAPI router in `api/main.py`** — both `parse_solution`
  and `grade_solution` in steps 1 and 2.
- **`notebook_entries.fts_vector` is a generated column** — never include it in
  an insert payload; Postgres computes it automatically.
- **`topic_node_slugs` is `text[]`** — pass as a Python list of strings; Supabase
  serialises to Postgres array.
- **`queue_items.updated_at`** — the schema has this column; update it when
  marking an item `done` in the submit/skip routes.
- **`problems.context_md`** is the DB column name (post-migration 20250011). Do
  not use `generated_context_md` in any query or insert — it no longer exists.
- **`hints` insert on race-lost path** — in the refactored `generate_problem.py`,
  do NOT insert hints if the race was lost (another worker's row is used). This is
  already the existing behaviour; preserve it.
- **`queue_items` insert on cache hit** — a queue item IS written even when the
  problem already exists in the pool (cache hit). The cache is about problem
  content reuse, not queue item reuse.
- **Sonnet 4.6 = `claude-sonnet-4-6` (from `config.py`).** Use `SONNET_MODEL`
  constant, not a hardcoded string.
- **`problem_hints` are pre-generated at creation time** — never generate them
  on demand. The step 4 problem page loads them via a Supabase select and shows
  them progressively; no LLM call happens when the user opens a hint.
- **No `solution_md` in the grade prompt.** Pass only `statement_md` and
  `rubric_md` to Claude's grading call — `solution_md` is the answer key and
  must not be in the prompt context where it might be echoed to the user.
- **`web/` has its own `.git`** — commit there separately from the repo root when
  running `git status`.
- **Tailwind v4 uses `@import "tailwindcss"`** — no `@tailwind` directives.
- **Next.js 16 auth proxy at `web/proxy.ts`** — new pages automatically inherit
  the proxy's auth redirect behaviour if they are listed as protected routes. Verify
  `/problem/*`, `/notebook*`, `/skill-tree` are gated.

---

## Acceptance notes (recorded after smoke test)

Issues found and resolved during Phase 5-rev acceptance testing. These are not
re-opened — they are fixed and merged. Recorded here as a decision log.

**A1 — `max_tokens` too low on `/generate-problem`**
The default `call_json` limit of 4096 tokens was insufficient for problems that
include a full solution, rubric, and five hints. The response was truncated
mid-JSON on both attempts, causing a 500. Fixed by passing `max_tokens=8192`
explicitly to the `call_json` call in `generate_problem.py`. This is the maximum
non-extended output for Sonnet 4.6.

**A2 — Supabase migration gap on `attempts`**
Migrations `20250007` (adding `parsed_markdown`, `user_edited_markdown`,
`parse_status`, `parsed_by_llm_call_id`, `hint_levels_used`) had not been fully
applied to the hosted Supabase database. PostgREST reported "Could not find
column X in schema cache" at runtime. Applied the missing columns manually via
the SQL editor and ran `NOTIFY pgrst, 'reload schema'`. Future schema work must
confirm `npx supabase db push` has been run against the target database.

**A3 — Stale `surfaced_picks` masked new problem items**
After the first (failed, 500-error) survey run, `surface_daily` was called and
surfaced `suggested_interest` queue items into a `surfaced_picks` row. After the
second (successful) survey run, new `problem` queue items entered the queue in
`pending` state, but the open `surfaced_picks` row from the first run remained
(its `replaced_at` was NULL). Subsequent `/daily` loads returned the old Explore
cards. Resolution: the user clicked "Show me something else" (reroll), which
marked the old pick as replaced and called `surface_daily` again, surfacing the
problem items. No code change required — this is correct queue behaviour, but it
was confusing during first-run testing. The reroll button is the intended escape
hatch.

**A4 — `suggested_interest` cards were unclickable**
The `DailyView` rendered `suggested_interest` cards as a grey non-interactive
span, which was confusing. Fixed by:
- Adding a "View in Skill Tree →" button that links to `/skill-tree`.
- Upgrading the `problem` card CTA from a text link to a dark rounded button
  for clearer affordance.

**A5 — React Flow edges: "Couldn't create edge for source handle id: null"**
Two root causes:

1. *Missing `<Handle>` components.* Custom `UserNode` and `AdjacentNode`
   components had no `<Handle>` elements. React Flow requires explicit handles
   for edge routing; without them it can't find the attachment point and logs the
   error. Fixed by adding invisible top (target) and bottom (source) handles to
   both components (`opacity: 0, pointerEvents: none`).

2. *Edges referencing nodes absent from the rendered graph.* The server-side
   edge filter in `skill-tree/page.tsx` included edges where only one endpoint
   was a user node, but the other endpoint might not exist in `nodeById` (and
   therefore not in `adjacentNodes`). Fixed by computing `renderedIds` (the union
   of all nodes actually passed to the graph) and filtering edges to require both
   endpoints to be present.

**A6 — Duplicate problem cards after reroll**
After reroll, two `problem` cards appeared referencing the same problem. This
happened because the survey route's step 5a calls `generateProblem` for up to
two `user_interests` rows; when both interests deduplicate to the same `nodes`
row, the cache lookup returns the same `problem_id` for both calls, but two
separate `queue_items` rows are still written. Accepted as a known limitation for
Phase 5-rev (documented in the "Decisions locked in" table). Phase 7-rev's real
`/update-queue` will prune duplicate queue items for the same node.

---

## Handoff to Phase 6-rev (preview)

Phase 6-rev picks up with:
- Full problem loop working end-to-end.
- Notebook accepting `problem_attempt` entries.
- Skill tree showing the user's graph.

Phase 6-rev adds:
- Papers ingestion (manual, `POST /admin/papers`).
- `POST /generate-paper-engagement` — pre-generates why-this, concepts, questions.
- Paper engagement UI: why-this, orienting concepts, link out, question answering,
  multi-session resume on `current_question_index`.
- `POST /grade-paper-answer` and `POST /paper-question`.
- `POST /suggest-papers` background job.
- Notebook rendering for `paper_engagement` entries.
