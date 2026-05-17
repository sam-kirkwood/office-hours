# Phase 7-rev — execution plan

> **Status: COMPLETE.** All steps committed.

Forward-looking plan for Phase 7-rev. Source-of-truth for the product is
[../SPEC.md](../SPEC.md), [../ARCHITECTURE.md](../ARCHITECTURE.md),
[../graph-design.md](../graph-design.md), and [../personas.md](../personas.md).
This file captures *execution* decisions and step ordering.

---

## Where we are

Steps 1–6 are complete and committed. The remaining work is step 7
(`/compute-cross-pollination`) and step 8 (acceptance).

### Done

- **Step 1 — User-provided paper ingestion.** `POST /ingest-paper-user`
  resolves arXiv URLs/IDs, DOIs, and bare titles; calls `ingest_paper()`
  shared helper; pre-generates an engagement; inserts a high-priority queue
  item. `AddPaperForm` component on the daily view. F17 empty-queue fallback
  verified in `surface_daily.py`.
- **Step 2 — `/propose-papers`.** Sonnet proposes 3–5 papers from training
  knowledge; each flows through `ingest_paper()` dedup; engagements
  pre-generated; queue items inserted. Triggered from survey and interest-add
  routes (best-effort). 109 Python tests passing.
- **Step 3 — Real `/update-queue`.** Priority reweight by kind + node state
  (struggling +0.2, comfortable −0.1); overdue-refresher boost; refresher
  scheduling into `refresher_schedule` (14-day attempts, 21-day engagements,
  10-day minimum age, midnight-aligned to `profiles.timezone`); queue item
  insertion for due schedules with select-before-insert dedup; 30-day prune of
  done/dismissed items; dedup of duplicate pending `(kind, ref_id)` pairs.
  `/suggest-papers` F16 pre-filter (Postgres `text_search` + ILIKE fallback,
  capped at 20 candidates) also landed in this step.
- **Step 4 — `user_node_states` recomputation.** `_recompute_node_state()`
  added to `update_queue.py`; called at end of `/update-queue` for
  `trigger='attempt_submit'`. Two-step attempt lookup → rolling
  `struggle_score` → transition table → upsert. Paper engagements skip
  recomputation (no direct node). 4 new tests.
- **Step 5 — Refresher surfacing.** `_resolve_refresher_content()` in
  `surface_daily.py` resolves a refresher item's `ref_id` (a
  `refresher_schedule.id`) to a content title and original `queue_item_id`.
  `SurfacedItem` schema has two new optional fields (`subject_kind`,
  `subject_queue_item_id`); `DailyView.tsx` refresher card shows "Revisit
  this →" linking back to the original problem or paper. 3 new tests.
- **Step 6 — Explicit request flow.** `/api/queue/request` extended to accept
  `raw_text` + `kind_hint`; calls `/add-interest` to resolve the node; dispatches
  to `generateProblem`, `suggestPapers`, or refresher queue insertion.
  `RequestBox.tsx` component (collapsible; Problem/Paper/Refresher pills;
  navigates to generated content) wired into `DailyView` below `AddPaperForm`.

### Still absent

- **Cross-pollination.** `/compute-cross-pollination` is not implemented.
  No `suggested_interest` queue items are created by the system. The curation
  gate (`megagraph_snapshots WHERE taken_by='system'`) will keep it a no-op
  through all of Phase 7-rev in production anyway — the gate unlocks in
  Phase 8-rev when the curation job writes its first snapshot.

---

## Phase 7-rev goal

After Phase 7-rev:

- A user can paste an arXiv URL, DOI, or bare title from the daily view. The
  system resolves it, inserts it into `papers`, pre-generates an engagement,
  and adds a paper card to their queue immediately.
- `/propose-papers` fires after each interest-adding event and expands the
  `papers` pool with Sonnet-proposed titles from training knowledge. The pool
  `/suggest-papers` ranks is no longer solely operator-seeded.
- Every attempt submission and paper engagement completion triggers
  `/update-queue`: priority scores are recomputed, done items are pruned, and
  refreshers are scheduled into `refresher_schedule`.
- `user_node_states` update after every engagement: `struggle_score` tracks
  recent hint usage; state transitions (unseen → active → struggling /
  comfortable) happen automatically.
- Refresher items surface in the daily three at appropriate intervals.
- A user can type "give me a problem on X" or "give me a paper on X" into the
  daily view request box and get a queue item immediately.
- Cross-pollination runs daily after the first weekly curation and produces
  `suggested_interest` queue items. Accepting a suggestion writes
  `user_interests(added_via='cross_pollination')`.

---

## Out of scope

- **Phase 8-rev:** `/generate-curation-report`, operator curation UI, admin
  megagraph view, snapshot management, cost dashboard, dropping deprecated
  tables.
- **Live arXiv / Semantic Scholar search (v2.1+).** User-provided ingestion
  in step 1 resolves a URL or title the user already has; it does not query
  the arXiv API proactively.
- **Adjacent surfacing** (papers mentioned in other papers' engagements) — no
  planned phase; deferred to v2.1.
- **Notebook export, return-after-absence prompts, per-user difficulty
  calibration beyond per-problem dial.**

---

## Decisions locked in

Resolve these before execution. Don't re-litigate them during implementation.

### Shared dedup helper shape

`api/paper_ingest_shared.py` exposes a single function:

```python
def ingest_paper(
    supabase,
    *,
    title: str,
    authors_json: list[str],
    year: int,
    abstract_md: str,
    arxiv_id: str | None = None,
    doi: str | None = None,
    external_url: str | None = None,
) -> tuple[str, bool]:
    """Returns (paper_id, created). created=False means a duplicate was found."""
```

Resolution order: (1) `arxiv_id` exact match → return existing. (2) `doi`
exact match → return existing. (3) Soft check `(lower(title), year)` → log
warning, proceed with insert. (4) On unique-violation at insert (race), re-select
and return existing with `created=False`. Both `/admin/ingest-paper` and
`/api/paper/ingest` call this function. The admin route is refactored to use it
in step 1; no behaviour change for the operator.

### Trigger for `/propose-papers`

Fired **per-user, event-driven** — not on a periodic schedule. Triggered:

1. From the survey route after all `/add-interest` calls complete (best-effort,
   swallowed on error), same pattern as `suggestPapers`.
2. From `/api/interest/route.ts` after a user adds a new interest explicitly
   (best-effort, swallowed on error).

Does NOT re-run periodically or on every page load. Each trigger fires one
`/propose-papers` call for that user. The Sonnet call proposes up to 5
candidate titles; each flows through `ingest_paper(...)` before insertion into
`papers`, then `/suggest-papers` reranks the expanded pool for that user.
This ensures no duplicate `papers` rows regardless of which discovery source
proposed a title first.

### User-provided ingestion UI location

**Both locations**, but implement daily-view first:

1. **Daily view** — a collapsible "Add a paper you found" affordance below the
   three surfaced cards. One text input accepting an arXiv URL, arXiv ID
   (e.g. `2301.07041`), DOI, or bare title. Submit → spinner → paper card
   injected into the queue and surfaced immediately via reroll.
2. **Not** on the paper engagement page or any existing paper-specific page —
   those are already mid-engagement.

The affordance is collapsed by default (one line: "Found a paper? Add it →").
This respects the "system curates; user trusts" principle — it's available
without being promoted.

### `/update-queue` call sites

Called from three Next.js routes (best-effort, swallowed on error):

| Event | Caller |
|---|---|
| Attempt submitted and graded | `web/app/api/problem/[id]/submit/route.ts` after `gradeSolution(...)` returns |
| Paper engagement completed (all questions answered) | `web/app/api/paper/[id]/answer/route.ts` when `next_question_index === -1` |
| New interest added | `web/app/api/interest/route.ts` after `/add-interest` returns |

NOT called on reroll — reroll is a re-surfacing operation, not a queue
mutation event. NOT called on "mark as refreshed" skip — the skip handler
already updates `user_node_states` directly; `/update-queue` is a heavier
call and the skip is meant to be instant.

The Python `/update-queue` route receives `{user_id}` and performs the full
recompute cycle: reweight pending items, schedule refreshers, prune done/
dismissed items older than 30 days, cap the pending queue at 50 items per
user.

### `user_node_states` recomputation thresholds

Thresholds are intentionally conservative — they track a genuine signal, not a
gamification counter. All transitions are computed in `update_node_state()`
in step 4's new `api/routes/update_queue.py` and called after each engagement
that touches a node.

| Transition | Condition |
|---|---|
| `unseen` → `active` | `engagement_count >= 1` (first engagement of any kind) |
| `active` → `struggling` | `struggle_score >= 0.6` AND `engagement_count >= 2` |
| `active` → `comfortable` | `struggle_score <= 0.2` AND `engagement_count >= 3` |
| `struggling` → `comfortable` | `struggle_score <= 0.2` AND `engagement_count >= 5` |
| Any → `bookmarked` | Set explicitly by user action; never auto-cleared |
| No auto-regression | `comfortable` → `active` never happens automatically |

`struggle_score` is computed as a rolling average of
`1 if len(hint_levels_used) > 0 else 0` across the last 5 attempts for this
node. If fewer than 5 attempts exist, use all available. Paper engagements do
not contribute to `struggle_score` (no hints exist for papers) but do increment
`engagement_count` and reset `last_engaged_at`.

### Cross-pollination gate

"First weekly curation has completed" is defined as: **at least one row in
`megagraph_snapshots` with `taken_by = 'system'`**. This row is written by the
Phase 8-rev snapshot job after every curation round. The cross-pollination
route checks this at the start of each run:

```python
snap = supabase.table("megagraph_snapshots") \
    .select("id").eq("taken_by", "system").limit(1).execute()
if not snap.data:
    return ComputeCrossPollinationResponse(suggestions_created=0, reason="no_curation_yet")
```

This means cross-pollination is a no-op through all of Phase 7-rev and Phase
8-rev (until the first curation round completes). The route exists and is
callable; it just returns early with `suggestions_created=0`. Phase 8-rev's
curation job will unlock it.

### F10 — What writes `user_interests(added_via='cross_pollination')`?

The "Add to interests" button on a `suggested_interest` daily card. Flow:

1. User sees a `suggested_interest` card in the daily three.
2. User clicks "Add to interests" → `POST /api/interest` with body
   `{node_id, added_via: 'cross_pollination'}`.
3. The Next.js route checks: node already exists in megagraph (it must — cross-
   pollination only surfaces existing nodes). Skip the full `/add-interest`
   dedup/generate flow. Write `user_interests(added_via='cross_pollination')`
   directly. Call `/update-queue` for the user.
4. Mark the `suggested_interest` queue item `done`.
5. Return confirmation; client refreshes the daily view.

A dismissed suggestion ("Not for me" or just ignored until reroll) marks the
queue item `dismissed`. No `user_interests` row is written for dismissals.

### Empty-queue fallback (F17 verification)

Step 1 must verify this is in place. The fallback in `/surface-daily`: if
`queue_items` returns zero pending items for the user, insert one
`concept_review` queue item pointing to the foundation node closest to the
user's interests (by node title fuzzy match), or to `calculus-i` if no interests
exist. This requires no LLM call. Test explicitly with a fresh account whose
`/add-interest` calls are forced to fail.

---

## Step table

| # | Step | One commit | Status |
|---|---|---|---|
| 1 | Next.js + FastAPI: user-provided paper ingestion | Shared dedup helper; `/api/paper/ingest` Next.js route; arXiv/DOI/title resolution; daily-view affordance; F17 empty-queue fallback verified | complete |
| 2 | FastAPI `POST /propose-papers` | Sonnet training-knowledge proposals; dedup via shared helper; triggers from survey + interest add routes | complete |
| 3 | FastAPI: real `/update-queue` | Priority recompute; refresher scheduling into `refresher_schedule`; F16 `/suggest-papers` pre-filter fix; pruning | complete |
| 4 | FastAPI: `user_node_states` recomputation | `struggle_score` and state transitions; called from within `/update-queue` after each engagement | complete |
| 5 | FastAPI: refresher surfacing | Refresher items inserted into `queue_items` from `refresher_schedule`; surface-daily picks them up | complete |
| 6 | Next.js: explicit request flow | Daily-view request box; "give me a problem/paper/refresher on X"; wires to existing routes | complete |
| 7 | FastAPI `POST /compute-cross-pollination` | Frontier computation; rank by edge weight + multi-user engagement; `suggested_interest` queue items; curation gate | complete |
| 8 | Phase 7-rev acceptance | End-to-end smoke test; pivot-plan.md status line update | complete |

---

## Step 1 — Next.js + FastAPI: user-provided paper ingestion

### New files
- `api/paper_ingest_shared.py` — shared dedup helper (used by both admin and user routes)
- `api/routes/ingest_paper_user.py` — `POST /ingest-paper-user` (user-facing; resolves URL/DOI/title)
- `web/app/api/paper/ingest/route.ts` — Next.js wrapper
- `web/components/AddPaperForm.tsx` — collapsible form component for the daily view

### Schema changes
None — `papers` table already has all needed columns from migration `20250010`.

### Refactor: `api/routes/ingest_paper.py`

Extract the dedup + insert logic into `paper_ingest_shared.ingest_paper(...)`.
The admin route becomes a thin wrapper:

```python
from paper_ingest_shared import ingest_paper

@router.post("/admin/ingest-paper")
async def admin_ingest_paper(body: IngestPaperRequest, ...):
    paper_id, created = ingest_paper(
        supabase,
        title=body.title,
        authors_json=body.authors_json,
        year=body.year,
        abstract_md=body.abstract_md,
        arxiv_id=body.arxiv_id,
        doi=body.doi,
        external_url=body.external_url,
    )
    return IngestPaperResponse(paper_id=paper_id, created=created)
```

No behaviour change for the operator.

### New route: `POST /ingest-paper-user`

```python
class IngestPaperUserRequest(BaseModel):
    user_id: UUID
    raw_input: str  # arXiv URL, arXiv ID, DOI, or bare title

class IngestPaperUserResponse(BaseModel):
    paper_id: UUID
    queue_item_id: UUID
    created: bool  # False if paper already existed
    engagement_id: UUID
```

### Route flow (`api/routes/ingest_paper_user.py`)

1. Auth check.
2. Parse `raw_input`:
   - arXiv URL pattern (`arxiv.org/abs/...` or `export.arxiv.org/...`) → extract arXiv ID.
   - Bare arXiv ID pattern (`\d{4}\.\d{4,5}(v\d+)?`) → use directly.
   - DOI pattern (`10\.\d{4,}/\S+`) → DOI path.
   - Else → bare title path.
3. **arXiv ID path:** fetch `https://export.arxiv.org/abs/{id}` (no auth; parse
   the `<title>`, `<author>`, `<published>`, `<summary>` fields from the Atom
   feed). Build `IngestPaperRequest`-equivalent fields. Call `ingest_paper(...)`.
4. **DOI path:** fetch `https://api.crossref.org/works/{doi}` (no auth). Parse
   `title`, `author`, `published-print.date-parts`, `abstract`. Call
   `ingest_paper(...)`.
5. **Bare title path:** `SELECT id FROM papers WHERE lower(title) ILIKE lower(%raw_input%)
   LIMIT 1`. If match, return existing row with `created=False`. Else call
   `ingest_paper(...)` with only `title` known; `abstract_md`, `authors_json`,
   `year` are empty strings / empty list / 0. Log a warning — bare-title inserts
   are low-quality.
6. Call `generate_paper_engagement(supabase, user_id, paper_id)` (direct function
   call, same pattern as in `/suggest-papers`).
7. Insert `queue_items` row (kind=`paper_engagement`, ref_id=engagement_id,
   priority_score=0.8 — user-initiated, so high priority).
8. Return `IngestPaperUserResponse`.

### Next.js route: `POST /api/paper/ingest`

```typescript
// Body: { raw_input: string }
// Auth check
// Call pythonPost("/ingest-paper-user", { user_id, raw_input })
// Return { paper_id, queue_item_id, created, engagement_id }
```

Add `ingestPaper` to `web/lib/pythonApi.ts`.

### Component: `web/components/AddPaperForm.tsx`

Client component. Renders as a single line "Found a paper? Add it →" that
expands on click to show:
- Text input: "Paste an arXiv URL, DOI, or title"
- Submit button
- Loading state (spinner; calls `POST /api/paper/ingest`)
- On success: "Added! It's in your queue." + a link to `/paper/[queue_item_id]`
- On error: inline error text

### `web/app/daily/page.tsx` change

Add `<AddPaperForm />` below the three surfaced cards. Import and render
unconditionally (it is always collapsed by default).

### F17 verification

In `api/routes/surface_daily.py`, confirm the empty-queue fallback is implemented.
If it is absent, add it now:

```python
if not pending_items:
    # Fallback: insert one concept_review for a foundation node
    foundation = _closest_foundation(supabase, user_id)  # ILIKE match or 'calculus-i'
    supabase.table("queue_items").insert({
        "user_id": str(user_id),
        "kind": "concept_review",
        "ref_id": foundation["id"],
        "state": "pending",
        "priority_score": 0.3,
        "added_reason": "A starting point while your queue is being built.",
        "time_estimate_minutes_low": 5,
        "time_estimate_minutes_high": 15,
    }).execute()
    # Re-query
    pending_items = _load_pending(supabase, user_id)
```

Test this path by creating a fresh account, skipping free-text intent in the
survey (or forcing all `/add-interest` calls to fail), and hitting `/daily`.

### Schema additions (`api/schemas.py`)

```python
class IngestPaperUserRequest(BaseModel):
    user_id: UUID
    raw_input: str

class IngestPaperUserResponse(BaseModel):
    paper_id: UUID
    queue_item_id: UUID
    created: bool
    engagement_id: UUID
```

### Tests (`api/tests/test_ingest_paper_user.py`)

| Test | What it verifies |
|---|---|
| `test_missing_bearer_returns_401` | Auth required |
| `test_arxiv_id_resolved_and_inserted` | arXiv ID path → external fetch mocked → paper inserted → engagement created → queue item written |
| `test_arxiv_url_parsed_to_id` | Full URL `https://arxiv.org/abs/2301.07041` → same code path as bare ID |
| `test_doi_resolved_and_inserted` | DOI path → CrossRef fetch mocked → paper inserted |
| `test_bare_title_matches_existing` | Existing paper ILIKE match → `created=False`; no new insert |
| `test_bare_title_inserts_new` | No ILIKE match → paper inserted with sparse metadata |
| `test_duplicate_arxiv_returns_existing_with_queue_item` | arXiv ID already in `papers` → `created=False`; engagement + queue item still created for this user |

---

## Step 2 — FastAPI `POST /propose-papers`

### New files
- `api/routes/propose_papers.py`
- `api/prompts/propose_papers.py`

### Schema additions (`api/schemas.py`)

```python
class ProposePapersRequest(BaseModel):
    user_id: UUID

class ProposedPaperCandidate(BaseModel):
    title: str
    authors: list[str]
    year: int
    arxiv_id: str | None = None
    doi: str | None = None
    rationale: str  # one sentence; stored in added_reason

class ProposePapersLLMOutput(BaseModel):
    candidates: list[ProposedPaperCandidate]  # 3–5 items

class ProposePapersResponse(BaseModel):
    papers_added: int       # count of new papers inserted
    papers_reused: int      # count of proposals that matched existing rows
    queue_items_added: int  # may be < papers_added if engagement already exists
```

### Route flow (`api/routes/propose_papers.py`)

1. Auth check.
2. Load `user_interests` → node_ids → load those `nodes` → collect titles.
3. Load last 3 `notebook_entries` for user (most recent engagements, ordered by
   `created_at DESC`) → collect entry titles for recency context.
4. `call_json(...)` with `ProposePapersLLMOutput` schema:
   - `model=SONNET_MODEL`, `max_tokens=2048`
   - System: cached prompt from `api/prompts/propose_papers.py`
   - User: interest titles + recent engagement titles
5. Validate: 3–5 candidates. If count out of range, log warning and continue
   with whatever was returned (don't raise 500 — this is a best-effort call).
6. For each candidate:
   a. Call `ingest_paper(supabase, title=..., authors_json=..., year=...,
      arxiv_id=..., doi=..., abstract_md='')` → `(paper_id, created)`.
   b. Check if `paper_engagements` already exists for this user + paper → skip if so.
   c. Call `generate_paper_engagement(supabase, user_id, paper_id)` → engagement_id.
   d. Insert `queue_items` row (kind=`paper_engagement`, ref_id=engagement_id,
      priority_score=0.4, added_reason=candidate.rationale).
7. Return `ProposePapersResponse`.

### Prompt (`api/prompts/propose_papers.py`)

System (cacheable):
```
You are helping a working scientist discover relevant research papers.

Given the user's current interests and recent reading, propose 3–5 real papers they
would find valuable. Each paper must:
- Exist in the scientific literature (it must be a real published or preprinted paper).
- Be directly relevant to at least one of the user's stated interests.
- Not be a textbook or lecture notes.

For each paper provide:
- title: the exact paper title
- authors: list of author names (last name, first initial format)
- year: publication year (integer)
- arxiv_id: arXiv ID if you are confident it exists (e.g. "1706.03762"), otherwise null
- doi: DOI string if you are confident, otherwise null
- rationale: one sentence explaining why this paper matches this user's interests

If you are not confident about an arXiv ID or DOI, output null — do not guess.

Output JSON matching this schema exactly:
{
  "candidates": [
    {"title": "...", "authors": ["..."], "year": 2023, "arxiv_id": "...", "doi": null, "rationale": "..."},
    ...
  ]
}
```

User (per-call):
```
User's current interests: {interest_titles_comma_separated}

Recent papers and problems they've engaged with: {recent_entry_titles_comma_separated}
```

### Survey + interest routes: trigger propose-papers

In `web/app/api/survey/route.ts`, after the `suggestPapers` call:
```typescript
try {
  await proposePapers({ userId: user.id });
} catch (err) {
  console.error("proposePapers failed:", err);
}
```

In `web/app/api/interest/route.ts`, after `/add-interest` returns:
```typescript
proposePapers({ userId: user.id }).catch(() => null);
```

Add `proposePapers` to `web/lib/pythonApi.ts`:
```typescript
interface ProposePapersArgs { userId: string; }
interface ProposePapersResponse { papers_added: number; papers_reused: number; queue_items_added: number; }
export async function proposePapers(args: ProposePapersArgs): Promise<ProposePapersResponse> {
  return pythonPost("/propose-papers", { user_id: args.userId });
}
```

### Tests (`api/tests/test_propose_papers.py`)

| Test | What it verifies |
|---|---|
| `test_missing_bearer_returns_401` | Auth required |
| `test_no_interests_returns_empty` | User with no interests → Sonnet still called; 0 added if Sonnet returns [] |
| `test_happy_path_inserts_papers_and_queue_items` | Sonnet called; 3 candidates → 3 `ingest_paper` calls; 3 queue items written |
| `test_existing_engagement_skipped` | Candidate whose paper already has an engagement for this user → no duplicate queue item |
| `test_duplicate_paper_reused` | Candidate whose arxiv_id already in `papers` → `created=False`; engagement still created |

---

## Step 3 — FastAPI: real `/update-queue`

### Changed files
- `api/routes/update_queue.py` — replace the no-op skeleton with real logic

### Schema additions (`api/schemas.py`)

```python
class UpdateQueueRequest(BaseModel):
    user_id: UUID
    trigger: str  # 'attempt_submit' | 'engagement_complete' | 'interest_add'
    ref_id: UUID | None = None  # the attempt_id or engagement_id that triggered this

class UpdateQueueResponse(BaseModel):
    items_reweighted: int
    refreshers_scheduled: int
    items_pruned: int
```

### Route flow

1. Auth check.
2. Load all `queue_items` for user where `state IN ('pending', 'surfaced')`.
3. **Priority reweight.** For each pending item:
   - Load the item's node (via ref_id → problem → topic_node_id, or refresher
     → subject_ref_id → problem/engagement → node).
   - Load `user_node_states` for that node.
   - Recompute `priority_score`:
     - Base score by kind: `problem=0.5`, `paper_engagement=0.4`,
       `refresher=0.9`, `concept_review=0.3`, `suggested_interest=0.2`.
     - Boost refresher by time overdue: `due_at` in `refresher_schedule` →
       `max(0, days_overdue * 0.05)` (cap at +0.4).
     - Boost struggling nodes: if `user_node_states.state = 'struggling'`,
       add 0.2 to problem items for that node.
     - Suppress comfortable nodes: if `state = 'comfortable'`, subtract 0.1
       from non-refresher items for that node.
   - Update `queue_items.priority_score`.
4. **Schedule refreshers.** For each `notebook_entries` row for this user
   where no `refresher_schedule` row exists:
   - Skip if `created_at` is < 10 days ago.
   - Skip if a `refresher` queue item already exists for the same `ref_id`.
   - Insert `refresher_schedule(user_id, subject_kind, subject_ref_id,
     due_at=created_at + 14 days)` for problem attempts;
     `created_at + 21 days` for paper engagements.
   (Use the user's `profiles.timezone` if set, else UTC, for midnight
   alignment — F13 from pivot-plan.md.)
5. **Refresher queue items.** For each `refresher_schedule` row where
   `due_at <= now()` AND `surfaced_at IS NULL`:
   - Insert `queue_items(kind='refresher', ref_id=refresher_schedule.id,
     priority_score=0.9, ...)`.
   - Set `refresher_schedule.surfaced_at = now()`.
6. **Prune.** Delete `queue_items` where `state IN ('done', 'dismissed')` AND
   `updated_at < now() - interval '30 days'`. Also delete duplicate pending
   items for the same `(user_id, kind, ref_id)` keeping the one with the
   highest `priority_score`.
7. **F16 fix — `/suggest-papers` pre-filter.** Before the Haiku call in
   `suggest_papers.py`, add a Postgres pre-filter:

   ```python
   interest_terms = " ".join(n["title"] for n in interest_nodes)
   papers_resp = (
       supabase.table("papers")
       .select("id, title, abstract_md")
       .text_search("title", interest_terms, config="english")
       .limit(20)
       .execute()
   )
   if not papers_resp.data:
       # Fallback: ILIKE on title
       papers_resp = (
           supabase.table("papers")
           .select("id, title, abstract_md")
           .ilike("title", f"%{interest_nodes[0]['title']}%")
           .limit(20)
           .execute()
       )
   ```

   This caps the Haiku input regardless of pool size.
8. Return `UpdateQueueResponse`.

### Tests (`api/tests/test_update_queue.py`)

| Test | What it verifies |
|---|---|
| `test_missing_bearer_returns_401` | Auth required |
| `test_no_items_returns_zeros` | Empty queue → no errors; all counts = 0 |
| `test_refresher_scheduled_after_10_days` | notebook_entry older than 10 days → refresher_schedule row written |
| `test_refresher_not_scheduled_before_10_days` | notebook_entry < 10 days old → no schedule row |
| `test_struggling_node_boosts_problem_priority` | Problem for struggling node → priority_score increased |
| `test_done_items_pruned_after_30_days` | Old done items → deleted |
| `test_duplicate_pending_items_pruned` | Two pending items same (user, kind, ref_id) → lower priority one deleted |

---

## Step 4 — FastAPI: `user_node_states` recomputation

### Changed files
- `api/routes/update_queue.py` — add `_recompute_node_state(supabase, user_id, node_id)` helper

### New helper function (within `update_queue.py`)

```python
def _recompute_node_state(supabase, user_id: str, node_id: str) -> None:
    """Called after any attempt or engagement on a node. Updates struggle_score
    and transitions state. No LLM call."""
    # Load last 5 attempts for this user/node
    attempts = (
        supabase.table("attempts")
        .select("hint_levels_used")
        .eq("user_id", user_id)
        .eq("problem_id",
            supabase.table("problems").select("id").eq("topic_node_id", node_id).limit(50).execute().data
            # See note below
        )
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    ).data
    # ... compute struggle_score and apply transition logic
```

**Implementation note on the join:** Supabase's Python client doesn't support
joins in a single call. Load attempt ids via a two-step query:
`problems` → `id WHERE topic_node_id = node_id` → `attempts WHERE problem_id IN (...)`.
At our scale this is fine.

```python
THRESHOLDS = {
    "to_active":    {"min_engagements": 1},
    "to_struggling":{"min_engagements": 2, "min_struggle": 0.6},
    "to_comfortable":{"min_engagements": 3, "max_struggle": 0.2},
    "struggling_to_comfortable": {"min_engagements": 5, "max_struggle": 0.2},
}
```

The function:
1. Computes `struggle_score` (rolling avg of hint-used indicator over last 5 attempts).
2. Counts total `engagement_count` from `user_node_states`.
3. Applies transition table → new `state`.
4. Upserts `user_node_states(user_id, node_id, struggle_score, state, engagement_count, last_engaged_at)`.

### Call sites

`_recompute_node_state` is called at the **end of the `/update-queue` route**, after
the priority reweight, for every node touched by the triggering engagement (looked
up via `ref_id` → problem/engagement → node). It is NOT a separate endpoint — it
runs inside `/update-queue`.

This means all `user_node_states` updates are centralized in one place. The
Phase 5-rev `skip/route.ts` already writes `user_node_states` directly; that can
remain as-is (it's the one case where no full `/update-queue` call is made).

### Tests (`api/tests/test_update_queue.py` — additional cases)

| Test | What it verifies |
|---|---|
| `test_first_engagement_transitions_unseen_to_active` | engagement_count=1 → state='active' |
| `test_high_hint_usage_transitions_to_struggling` | 3 of last 5 attempts used hints → struggle_score=0.6 → state='struggling' |
| `test_clean_attempts_transition_to_comfortable` | 4 attempts, none used hints → struggle_score=0.0, engagement_count=4 → state='comfortable' |
| `test_comfortable_not_auto_regressed` | comfortable node gets one hinted attempt → stays comfortable |

---

## Step 5 — FastAPI: refresher surfacing

### Changed files
- `api/routes/surface_daily.py` — ensure `refresher` kind items are picked up

### What's needed

Step 3 inserts `queue_items(kind='refresher', ref_id=refresher_schedule.id)`.
The `surface_daily` route already selects from `queue_items WHERE state='pending'`
ordered by `priority_score`. Refreshers get `priority_score=0.9`, so they will
naturally float to the top.

The only required change is ensuring the surfacing logic resolves `refresher`
ref_ids into display-ready content for the daily card. The `ref_id` for a
refresher points to `refresher_schedule.id`, which carries `subject_kind` and
`subject_ref_id`. The surfacing route must:

1. For each pending `refresher` item, load `refresher_schedule` by `ref_id`.
2. Load the content row by `subject_kind` + `subject_ref_id`:
   - `attempt` → load `attempts` + `problems` → build card title from problem's
     node title.
   - `engagement` → load `paper_engagements` + `papers` → card title from paper.
3. Return the resolved title and `added_reason` = "A refresher on [topic]".

### Next.js: `DailyView.tsx` update

Add a `refresher` card CTA: "Revisit this →" linking to the original content:
- If `subject_kind='attempt'`: link to `/problem/[original_queue_item_id]`
  (look up via `attempts.queue_item_id`).
- If `subject_kind='engagement'`: link to `/paper/[original_queue_item_id]`
  (look up via `paper_engagements`'s queue item).

Use badge `variant="outline"` with forest border/text per the design system's
queue badge semantics.

### Tests (`api/tests/test_surface_daily.py` — additional cases)

| Test | What it verifies |
|---|---|
| `test_refresher_item_appears_when_due` | refresher_schedule row with due_at in the past → queue item written → appears in surfaced picks |
| `test_refresher_resolved_to_content_title` | refresher ref_id resolves to the original problem/paper title in the surfaced item |
| `test_refresher_priority_above_problem` | refresher (0.9) surfaces before pending problem (0.5) when both available |

---

## Step 6 — Next.js: explicit request flow

### Changed files
- `web/app/daily/page.tsx` — add request box UI
- `web/app/api/queue/request/route.ts` — extend to handle text-based requests

### Current state

`/api/queue/request` from Phase 5-rev accepts `{node_id}` and generates a
problem. It is wired to the skill tree "Get a problem" button.

### What to add

A free-text request box on the daily view: "Get a problem / paper / refresher on [topic]".
User types anything; the route classifies the intent (Haiku) and dispatches.

### `POST /api/queue/request` — extended body

```typescript
// New: accept either node_id (existing behaviour) OR raw_text (new)
interface QueueRequestBody {
  node_id?: string;
  raw_text?: string;
  kind_hint?: "problem" | "paper" | "refresher";  // optional; inferred if absent
}
```

### Route flow (when `raw_text` provided)

1. Auth check.
2. Call `/add-interest` with `raw_text` (same as the interest-add flow, but this
   might match an existing node). The response includes `node_id`.
3. Dispatch based on `kind_hint` (or `kind_hint` inferred from text: "paper on
   X" → `paper`, "refresher on X" → `refresher`, else → `problem`):
   - `problem`: call `generateProblem({ userId, nodeId })` → return
     `{queue_item_id}`.
   - `paper`: call `suggestPapers({ userId })` (or `proposePapers` if pool is
     empty for this node) → return the first new `queue_item_id` for a
     paper_engagement on this node, or indicate "paper coming soon".
   - `refresher`: look up `refresher_schedule` where `subject_kind='attempt'`
     AND the attempt's node matches → surface as a refresher queue item. If no
     scheduled refresher exists, surface the most recent `notebook_entries` row
     for this node as an on-demand `refresher` queue item.
4. Return `{queue_item_id, kind}`.

### `web/components/RequestBox.tsx` — new client component

```tsx
// A single-line text input with "Go →" button
// On submit: POST /api/queue/request with { raw_text: input, kind_hint }
// Loading state while waiting
// On success: navigate to /problem/[queue_item_id] or /paper/[queue_item_id]
// On "paper coming soon": show inline message "Paper added to your queue."
```

Kind-hint radio: "Problem", "Paper", "Refresher" — compact, defaults to Problem.

### `web/app/daily/page.tsx` change

Add `<RequestBox />` below `<AddPaperForm />` at the bottom of the daily view.
Both additions are collapsed by default; one line each.

### Tests

No new Python tests — this step is primarily Next.js. Verify manually that:
1. Typing "give me a problem on complex analysis" → generates and navigates to
   a problem page.
2. Typing "paper on LIGO" → paper suggestion initiated or inline message shown.
3. Typing "refresher on contour integration" → surfaces a refresher queue item.

---

## Step 7 — FastAPI `POST /compute-cross-pollination`

### New file
- `api/routes/compute_cross_pollination.py`

### Schema additions (`api/schemas.py`)

```python
class ComputeCrossPollinationRequest(BaseModel):
    # Called by a background trigger (Vercel cron or manual operator call).
    # No user_id — runs for all active users.
    pass

class ComputeCrossPollinationResponse(BaseModel):
    suggestions_created: int
    reason: str  # 'no_curation_yet' | 'ok'
```

### Route flow

1. Auth check.
2. **Curation gate:** check `megagraph_snapshots WHERE taken_by='system'`. If
   none, return `{suggestions_created: 0, reason: 'no_curation_yet'}`.
3. Load all active users: `SELECT DISTINCT user_id FROM user_interests`.
4. For each user:
   a. Load user's engaged node_ids: all node_ids in `user_node_states` where
      `state IN ('active', 'comfortable', 'struggling')`.
   b. Load 1-hop frontier: all `edges` where `source_node_id` OR
      `target_node_id` is in engaged set; collect the other endpoint; exclude
      nodes already in the engaged set or in `bookmarks` for this user.
   c. Also load 2-hop frontier: repeat from the 1-hop set (one further hop).
      Merge, deduplicate.
   d. Score each frontier candidate:
      - `edge_weight`: max weight of any edge connecting it to the user's
        engaged set.
      - `other_user_count`: count of distinct user_ids in `user_node_states`
        WHERE `node_id = candidate_id` AND `user_id != this_user`.
      - `score = edge_weight * 0.5 + min(other_user_count, 5) * 0.1`
   e. Pick the top candidate if `score > 0.3`. If below threshold, skip.
   f. Check cooldown: `queue_items` where `kind='suggested_interest'` AND
      `ref_id=candidate_node_id` AND `added_at > now() - interval '7 days'`.
      If exists, skip.
   g. Insert `queue_items(kind='suggested_interest', ref_id=candidate_node_id,
      priority_score=0.35, added_reason="Other users working in adjacent areas
      have explored this.")`.
5. Return total count.

### Next.js: `DailyView.tsx` update

Add `suggested_interest` card handling (these are created by cross-pollination,
not the old survey placeholder):

```tsx
} else if (item.kind === "suggested_interest") {
  // Show node title + "Other users in adjacent areas have explored this."
  // Two buttons:
  //   "Add to interests" → POST /api/interest with {node_id, added_via: 'cross_pollination'}
  //   "Not for me" → POST /api/queue/bookmark (mark dismissed)
}
```

Use badge `variant="ghost"` per design system.

### `/api/interest/route.ts` — cross-pollination path

When `added_via === 'cross_pollination'` and `node_id` is provided (no raw
text), skip the `/add-interest` dedup/generate flow. Write `user_interests`
directly:

```typescript
await supabase.from("user_interests").insert({
  user_id: userId,
  node_id: body.node_id,
  weight: 1.0,
  added_via: "cross_pollination",
});
// Mark the suggested_interest queue item done
// Call updateQueue (best-effort)
```

### Background trigger

Register `POST /compute-cross-pollination` in `api/main.py`. Call it from a
Vercel cron job (Phase 8-rev will formalise the scheduler). For Phase 7-rev,
call it manually or from a test to verify it works. The gate ensures it's a
no-op until curation ships.

### Tests (`api/tests/test_compute_cross_pollination.py`)

| Test | What it verifies |
|---|---|
| `test_missing_bearer_returns_401` | Auth required |
| `test_no_curation_returns_early` | No megagraph_snapshots → `suggestions_created=0`, reason='no_curation_yet' |
| `test_happy_path_creates_suggestion` | Snapshot exists; user has engaged nodes; frontier node with score > 0.3 → queue_item written |
| `test_threshold_not_met_skips` | Frontier candidates with score <= 0.3 → no queue item |
| `test_cooldown_prevents_duplicate` | Recent suggested_interest queue item for same node → skipped |
| `test_already_engaged_node_not_suggested` | Node already in user_node_states → not in frontier |

---

## Step 8 — Phase 7-rev acceptance

End-to-end smoke test:

1. **User-provided ingestion:** On the daily view, paste an arXiv URL. Spinner.
   "Added!" appears. Paper card appears (after reroll). Click → paper engagement
   UI loads.
2. **Propose-papers:** Complete survey with a new interest. Check `papers` table
   — new rows should appear that weren't in the DB before (Sonnet proposals).
   `/daily` should show at least one paper card derived from the proposals.
3. **Queue adaptation:**
   - Submit a problem attempt using hints. Check `attempts.hint_levels_used` is
     populated. Check `user_node_states.struggle_score` increased. Check
     `queue_items.priority_score` updated for that node's items.
   - Complete a paper engagement. Check `notebook_entries` row created. Check
     `refresher_schedule` row written for that engagement.
4. **Refresher surfacing:**
   - Manually set `refresher_schedule.due_at = now() - interval '1 hour'` for
     one row. Call `/update-queue`. Check `queue_items` now contains a
     `refresher` kind item. Load `/daily` → refresher card with "Revisit this →"
     should appear.
5. **Explicit request flow:** Type "problem on Fourier series" in the request
   box. A problem should be generated and the page should navigate to it.
6. **Cross-pollination:** (Gate is active — curation not yet run, so this is a
   no-op in production. Verify only that the endpoint returns
   `reason='no_curation_yet'` cleanly without errors.)
7. `llm_calls` table: rows for `/propose-papers` (Sonnet), `/ingest-paper-user`
   (no LLM call for the ingestion itself, but a Sonnet `generate-paper-engagement`
   follows it), and `/update-queue` (no LLM).

Update `docs/pivot-plan.md` status line:
```
Status: Phase 7-rev complete.
Next step: Phase 8-rev step 1 — FastAPI: /generate-curation-report.
```

---

## Post-acceptance fixes (applied after step 8 commit)

Bugs found during manual acceptance testing. All fixed in the same session.

| Bug | Root cause | Fix |
|---|---|---|
| `POST /suggest-papers` 500: `text_search() got unexpected keyword argument 'config'` | `supabase-py` `text_search()` does not accept a `config=` kwarg | Removed `config="english"` |
| `POST /suggest-papers` 500: `SyncQueryRequestBuilder has no attribute 'limit'` | `text_search()` returns a different builder type that doesn't chain `.limit()` | Replaced FTS pre-filter with ILIKE on title; falls back to unfiltered cap-20 |
| Reroll keeps surfacing the same concept_review; real content stuck forever | Reroll closed the surfaced_picks row but left items in `surfaced` state, invisible to the next `/surface-daily` call | Reroll route now resets still-surfaced items in the replaced pick back to `pending` before calling `/surface-daily` |
| After several rerolls, daily view shows empty state with no reroll button | `getOrSurfacePick` returned `items: []` when the open pick's items were all consumed; reroll button was gated on `hasItems` | `getOrSurfacePick` now closes a stale empty pick and falls through to surface fresh; reroll button always visible |
| "Refresher on integration by parts" surfaced Lagrangian mechanics | The refresher branch in `/api/queue/request` ignored `resolvedNodeId` and used the most recent `notebook_entries` row regardless of topic | Now looks up the node's slug and filters `notebook_entries` by `topic_node_slugs` first; falls back to most recent only if no match |

**Deferred during acceptance (added to pivot-plan.md Deferred section):** Paper request via RequestBox should trigger `/propose-papers` for niche topics before `/suggest-papers` so the pool is never empty for the requested node.

---

## Risks to watch

- **arXiv and CrossRef HTTP calls from the Python service.** These are
  external network calls made inside a FastAPI route. They add latency (1–3 s
  each) and can fail. Wrap each fetch in a try/except; on failure, fall back
  to the bare-title path and log the error. Do not let a failed HTTP fetch
  block the entire ingestion response.
- **`/propose-papers` hallucination.** Sonnet may propose papers that don't
  exist, or produce plausible-sounding but wrong arXiv IDs. The `ingest_paper`
  helper inserts what it receives. If `arxiv_id` is present but wrong, the
  `papers` row will have a bad ID — the user clicking "Open paper" will get a
  404 from arXiv. Mitigation: accept this for v2; v2.1 live search will
  validate. Add a comment in the prompt: "Only provide arxiv_id if you are
  highly confident it is correct." Setting arxiv_id to null is safe.
- **`/update-queue` latency.** The route does several round-trips: load all
  pending items, load their nodes, load node states, recompute, write back.
  At 30 users × 50 items each this is trivially fast. Do not optimise
  prematurely. If the call site is synchronous (it is, in the submit route),
  add a hard timeout (10 s) so a stuck update-queue call doesn't block the
  user's feedback render.
- **`_recompute_node_state` two-step join.** The attempt→node lookup requires
  loading all problem IDs for a node, then filtering attempts. This is a
  two-query sequence. At scale it's fine; just don't nest it in a loop over
  all users — it's called per-node, per-user, after a specific engagement.
- **Cross-pollination "other users" framing with fewer than 2 users.** The
  daily card says "Other users in adjacent areas have explored this." If only
  one user exists, `other_user_count` will be 0 and the score will be low (≤ 0.3),
  so the suggestion will not surface. The threshold naturally handles cold start.
- **Refresher due_at timezone.** F13 says resolve against `profiles.timezone`.
  If `profiles.timezone` is null (no column yet), default to UTC. Add the
  `profiles.timezone text` column in this phase if it wasn't added in Phase 4-rev
  step 1 — check migration `20250008` before implementing.

---

## Things easy to forget

- **Register all new FastAPI routers in `api/main.py`:** `ingest_paper_user`,
  `propose_papers`, `compute_cross_pollination`. The real `update_queue` router
  already exists; only the implementation changes.
- **`paper_ingest_shared.py` is a module, not a router.** Do not pass it to
  `app.include_router`. Import `ingest_paper` from it directly in the routes
  that need it.
- **`refresher_schedule.surfaced_at`** — set to `now()` when the queue item is
  inserted, not when it appears in the daily three. Otherwise rerunning
  `/update-queue` will insert duplicate refresher queue items.
- **`queue_items` dedup on refresher insert** — before inserting a new
  `refresher` queue item for a `refresher_schedule` row, check that no
  `pending` or `surfaced` refresher item already exists for the same
  `ref_id`. Use a select-before-insert (not a unique constraint — the
  constraint doesn't exist and adding it mid-phase is more disruptive).
- **`suggested_interest` cards must not be clickable as links.** They are not
  content items; they are a prompt to add an interest. The "Add to interests"
  button is the affordance. Do not link the card title to a problem or paper.
- **`/api/interest` cross-pollination path skips `/add-interest`.** Do not
  call the Python `/add-interest` route when `added_via='cross_pollination'`
  and a `node_id` is provided — the node already exists; dedup is unnecessary
  and the Haiku call is wasted.
- **Every Claude call must be logged to `llm_calls`** — including the Sonnet
  call in `/propose-papers`.
- **`web/` has its own `.git`** — commit there separately.
- **`profiles.timezone`** — check before step 5 whether the column exists.

---

## Handoff to Phase 8-rev (preview)

Phase 8-rev adds:

- `POST /generate-curation-report` (weekly Sonnet call reading megagraph
  deltas; writes `curation_proposals`).
- Operator admin UI at `/admin/curation`: review proposals, approve/reject,
  apply. Approve = execute the merge/split/rename against `nodes`/`edges`;
  write a `megagraph_snapshots` row after each round.
- Snapshot job: a `megagraph_snapshots` row written after every curation
  approval triggers the cross-pollination gate — from that point on,
  `/compute-cross-pollination` is live.
- Operator megagraph view at `/admin/megagraph`: full graph render (React Flow
  + Dagre), layer toggles, time scrubber over snapshots.
- Cost dashboard at `/admin/costs`: reads `llm_calls`.
- Drop deprecated tables: `canonical_topics`, `canonical_edges`, `user_plans`,
  `plan_nodes`, `daily_assignments`, `pending_topic_requests`.
