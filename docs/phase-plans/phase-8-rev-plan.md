# Phase 8-rev — execution plan

> **Status: Complete.** All 8 steps done. Phase 9-rev is next.

Forward-looking plan for Phase 8-rev. Source-of-truth for the product is
[../SPEC.md](../SPEC.md), [../ARCHITECTURE.md](../ARCHITECTURE.md),
[../graph-design.md](../graph-design.md), and [../personas.md](../personas.md).
This file captures *execution* decisions and step ordering.

---

## Where we are

Phase 7-rev is complete and committed. All seven steps landed:

- Paper ingestion (user-provided, arXiv/DOI/title), `/propose-papers`, real
  `/update-queue`, `user_node_states` recomputation, refresher surfacing,
  explicit request flow, and `/compute-cross-pollination`.
- Cross-pollination exists and is callable, but returns
  `reason='no_curation_yet'` until a `megagraph_snapshots` row with
  `taken_by='system'` exists. Phase 8-rev step 4 (apply + snapshot) writes
  that row and unlocks it.
- The `curation_proposals` and `megagraph_snapshots` tables exist (migration
  `20250008`) with no rows.
- No admin UI exists yet. `/admin/*` routes are absent.
- Six deprecated tables remain in place from migration `20250012`:
  `canonical_topics`, `canonical_edges`, `user_plans`, `plan_nodes`,
  `daily_assignments`, `pending_topic_requests`. No production code writes to
  them, but `web/app/page.tsx` still reads `user_plans` to decide where to
  redirect. That reference must be cleaned up before the DROP.

---

## Phase 8-rev goal

After Phase 8-rev:

- The operator can click "Run curation report" in an admin UI. The system
  reads the megagraph's recent changes and engagement signals, calls Sonnet,
  and presents a list of structured proposals (merges, splits, renames,
  promotions, demotions, new edges, deprecations) for review.
- The operator approves or rejects each proposal in the UI. After clicking
  "Apply approved proposals", the approved changes are executed against
  `nodes` and `edges`, a `megagraph_snapshots` row is written, and
  cross-pollination becomes live.
- The operator can view the full megagraph in a React Flow + Dagre canvas
  with layer toggles (foundation vs. interest, by domain) and a time scrubber
  over historical snapshots.
- The operator can see the cost dashboard: all LLM calls broken out by route,
  model, tokens, and estimated cost.
- The six deprecated v1 tables are physically dropped.
- **Acceptance:** operator runs a full curation round end-to-end; megagraph
  is maintainable via the admin UI.

---

## Out of scope

- **Vercel cron for weekly curation.** The operator triggers the curation
  report manually via a button in the admin UI. Automating the schedule is
  Phase 9-rev or post-launch polish.
- **Vercel cron for cross-pollination.** `/compute-cross-pollination` is now
  live (gate unlocked), but calling it on a schedule is Phase 9-rev.
  The operator can call it manually or via a test.
- **Bespoke D3 megagraph visualisation.** The admin view uses React Flow +
  Dagre — the same stack as the user-facing skill tree. A D3 showcase version
  is deferred to v2.1.
- **Notebook export, return-after-absence prompts, BYO API key,
  hand-authored problems, live arXiv search.** All deferred.
- **Phase 9-rev** (design-system polish, mobile polish, error monitoring).
  Do not start phase 9 items here.

---

## Decisions locked in

Resolve these before execution. Don't re-litigate during implementation.

### D1 — Admin auth gating mechanism

**`ADMIN_EMAIL` environment variable.** Set once in `web/.env.local` (and in
the Vercel project settings). The value is the operator's email address.

In `web/app/admin/layout.tsx` (server component): fetch the current Supabase
user, compare `user.email` against `process.env.ADMIN_EMAIL`. If no match,
redirect to `/daily`.

In each `/api/admin/*` route handler: call a shared
`assertAdmin(supabase)` helper that performs the same check and throws 403 if
it fails.

No `profiles.is_admin` column is added. One operator, hard cap of 30 users —
a simple env var is proportionate and avoids an extra migration.

### D2 — payload_json contract between Sonnet and apply logic

The curation report Sonnet call must output proposals whose `payload_json`
matches the shapes the apply logic consumes. The schemas for each kind:

| Kind | payload_json fields |
|---|---|
| `merge` | `{source_node_id, target_node_id, source_title, target_title, rationale}` |
| `split` | `{source_node_id, source_title, new_node_title, new_node_slug, new_node_description_md, new_node_domain, new_node_difficulty_hint, rationale}` |
| `rename` | `{node_id, old_title, new_title, new_slug, rationale}` |
| `promote` | `{node_id, title, rationale}` |
| `demote` | `{node_id, title, rationale}` |
| `add_edge` | `{source_node_id, target_node_id, source_title, target_title, edge_kind, weight, rationale}` |
| `deprecate` | `{node_id, title, rationale}` |

`rationale` is always present (one sentence) so the operator can read the
reasoning before deciding. The Sonnet prompt must enforce these shapes.

### D3 — Apply logic for `split` is simplified in v2

Full user-state redistribution across a split is complex and low-value at
our scale. Simplified implementation:

1. Create the new node from `payload_json` fields (title, slug,
   description_md, domain, difficulty_hint). `kind='interest'`,
   `pool_status='active'`.
2. Insert edges from payload if specified; otherwise leave edge-generation to
   the next curation round.
3. User state stays entirely on the source node. New node starts fresh
   (no `user_node_states`, no `user_interests` rows).

Document this simplification in the apply UI with a note: "User associations
remain on the original node. Add relationships manually via the megagraph
view if needed."

### D4 — Rename slug propagation

A `rename` proposal may change the node's slug. After updating `nodes.slug`,
run:

```sql
UPDATE notebook_entries
SET topic_node_slugs = array_replace(topic_node_slugs, $old_slug, $new_slug)
WHERE $old_slug = ANY(topic_node_slugs);
```

This is the only table that stores slugs as data (rather than FKs). All
other references to nodes use UUID `node_id` FKs. Log a warning if more than
50 entries are affected.

### D5 — Curation report input window

The curation report reads changes since the last snapshot. The route computes
the window automatically:

```python
last_snap = supabase.table("megagraph_snapshots") \
    .select("taken_at") \
    .order("taken_at", desc=True) \
    .limit(1).execute()
since = last_snap.data[0]["taken_at"] if last_snap.data else "1970-01-01T00:00:00Z"
```

All nodes and edges created after `since` are "recent additions". Engagement
signals are always loaded over all time (not windowed) so the report can spot
neglected nodes regardless of when they were added.

### D6 — Apply atomicity

Apply runs as a sequential series of Supabase calls from the Next.js API
route — not in a Postgres transaction (the JS client does not support
multi-statement transactions). If a mid-batch call fails, partial state may
exist. At our scale this is acceptable: log each apply step, note which
proposals were applied before the failure, and let the operator re-run or
manually correct the remainder. The `curation_proposals.status` field tracks
which proposals have been applied.

### D7 — Apply runs in Next.js, not Python

Apply logic involves no LLM calls — only database mutations. It lives in
the Next.js API route (`/api/admin/proposals/apply/route.ts`) using the
**service-role Supabase client** (not the anon/user client) so it can:
- Write to `nodes`, `edges` (admin-write RLS).
- Update `user_interests`, `user_node_states`, `queue_items` across all users
  (bypasses per-user RLS).
- Write `megagraph_snapshots`.

The service-role key is `SUPABASE_SECRET_KEY` in the env (per project memory:
`service_role` → `secret`). It must never be exposed to the browser.

### D8 — Snapshot JSON schema

Compact — sufficient for the time scrubber to re-render the graph. Full
`description_md` is excluded to keep blobs small.

```json
{
  "version": 1,
  "taken_at": "<ISO 8601>",
  "nodes": [
    {"id": "uuid", "slug": "str", "title": "str", "kind": "foundation|interest",
     "domain": "math|physics|applied", "pool_status": "active|deprecated"}
  ],
  "edges": [
    {"id": "uuid", "source_node_id": "uuid", "target_node_id": "uuid",
     "edge_kind": "prerequisite|related", "weight": 0.9}
  ]
}
```

The time scrubber loads snapshot_json on demand per snapshot (not all at
once); a separate `GET /api/admin/megagraph/snapshot/[id]` route serves
individual blobs.

### D9 — `web/app/page.tsx` redirect logic after DROP

Currently redirects to `/daily` if `user_plans` has an active row, or to
`/survey` otherwise. After dropping `user_plans`, the redirect logic becomes:
check for a `surveys` row for the authenticated user (a completed survey means
onboarding is done). If found → `/daily`. If not → `/survey`. This is the
correct v2 semantic.

### D10 — Admin navigation layout

`web/app/admin/layout.tsx` renders a top nav bar:
`Curation | Megagraph | Costs`

Links: `/admin/curation`, `/admin/megagraph`, `/admin/costs`. Styled with
`font-sans text-xs font-semibold uppercase tracking-widest text-muted-foreground`.
Active link gets an amber underline. The operator's email is shown in the
top-right corner.

The admin layout lives inside the auth gate (layout checks ADMIN_EMAIL before
rendering children). Non-admin users see a redirect, not a 403 page.

---

## Step table

| # | Step | One commit | Status |
|---|---|---|---|
| 1 | FastAPI `POST /generate-curation-report` | Sonnet call; reads megagraph deltas + engagement signals; writes `curation_proposals` rows | Done |
| 2 | Next.js: admin auth gating + proposal review UI | `admin/layout.tsx`, `admin/curation/page.tsx`, approve/reject API routes | Done |
| 3 | Next.js: operator megagraph view | `admin/megagraph/page.tsx`, React Flow + Dagre, layer toggles, time scrubber | Done |
| 4 | Apply action + snapshot write | `POST /api/admin/proposals/apply`; per-kind apply logic; writes `megagraph_snapshots`; cross-pollination gate unlocked | Done |
| 5 | Cost dashboard | `admin/costs/page.tsx`; reads `llm_calls` table | Done |
| 6 | Drop deprecated tables | Verify no production writes; fix `web/app/page.tsx`; migration `20250016` | Done |
| 7 | Users + queue view | `admin/users/page.tsx`; all users with interests count + live queue items (non-dismissed) | Done |
| 8 | Phase 8-rev acceptance | End-to-end curation round; pivot-plan.md status line update | Done |

**Post-acceptance fixes applied in the same session:**
- Migration `20250017` — changed `curation_proposals.decided_by` from `uuid` FK to `text` (was blocking approve/reject with 500).
- `web/app/admin/layout.tsx` — changed `min-h-screen` to `h-screen flex-col` so the megagraph time scrubber is not clipped below the viewport.
- `web/lib/queueHelpers.ts` — reset still-`surfaced` items to `pending` when closing a stale pick, fixing a queue-limbo bug where daily showed nothing despite non-empty queue.

---

## Step 1 — FastAPI `POST /generate-curation-report`

### New files

- `api/routes/generate_curation_report.py`
- `api/prompts/curation_report.py`

### Schema additions (`api/schemas.py`)

```python
class GenerateCurationReportRequest(BaseModel):
    pass  # system-level; no user_id — called by the operator UI

class CurationProposalOutput(BaseModel):
    kind: str  # merge|split|rename|promote|demote|add_edge|deprecate
    payload_json: dict  # shape per D2

class CurationReportLLMOutput(BaseModel):
    proposals: list[CurationProposalOutput]

class GenerateCurationReportResponse(BaseModel):
    proposals_created: int
    since: str  # ISO timestamp of the input window start
```

### Route flow (`api/routes/generate_curation_report.py`)

1. Auth check.
2. Compute input window `since` (per D5).
3. Load recent additions:
   - `new_nodes`: `SELECT id, slug, title, kind, domain, subtopics_json FROM nodes WHERE created_at > since AND pool_status='active'`
   - `new_edges`: `SELECT source_node_id, target_node_id, edge_kind, weight FROM edges WHERE created_at > since`
   - `recent_dedup_decisions`: `SELECT kind, payload_json FROM curation_proposals WHERE proposed_at > since AND status='applied'` (prior autonomous dedup decisions the operator should know about)
4. Load engagement signals:
   - `high_engagement`: `SELECT node_id, engagement_count FROM user_node_states WHERE engagement_count >= 5 ORDER BY engagement_count DESC LIMIT 20`
   - `struggling`: `SELECT node_id, struggle_score FROM user_node_states WHERE struggle_score >= 0.6 ORDER BY struggle_score DESC LIMIT 20`
   - `neglected`: `SELECT id, slug, title FROM nodes WHERE pool_status='active' AND id NOT IN (SELECT DISTINCT node_id FROM user_node_states WHERE last_engaged_at > now() - interval '60 days') LIMIT 20`
   - Resolve node IDs to titles for the above three sets.
5. Load full current graph (for Sonnet context):
   - All `nodes` where `pool_status='active'` (id, slug, title, kind, domain)
   - All `edges` (source_node_id, target_node_id, edge_kind, weight) — resolve source/target to titles
6. Call Sonnet with `CurationReportLLMOutput` schema:
   - `model=SONNET_MODEL`, `max_tokens=4096`
   - System: cached prompt from `api/prompts/curation_report.py`
   - User: structured JSON of all loaded data
   - On parse failure: retry once (standard `call_json` pattern)
7. Validate output: 0–20 proposals. Log warning if >20 (probably Sonnet
   getting carried away); truncate to 20.
8. For each proposal, insert `curation_proposals`:
   ```python
   supabase.table("curation_proposals").insert({
       "kind": p.kind,
       "payload_json": p.payload_json,
       "status": "pending",
       "proposed_at": "now()",
   }).execute()
   ```
9. Log to `llm_calls`.
10. Return `GenerateCurationReportResponse`.

### Prompt (`api/prompts/curation_report.py`)

System (cacheable — describes the task, all valid kinds, payload schemas):

```
You are a knowledge-graph curator. You review a science learning platform's
shared megagraph and propose maintenance actions for the operator to review.

The megagraph has two node kinds:
- "foundation": operator-curated, stable math/physics topics.
- "interest": user-added organic interests, deduplicated across users.

You may propose the following actions. For each, output the exact JSON payload
described.

merge: Two nodes are effectively the same topic. Combine them.
  payload: {source_node_id, target_node_id, source_title, target_title, rationale}

split: One node has accumulated enough engagement across distinct subtopics to
  warrant splitting into two.
  payload: {source_node_id, source_title, new_node_title, new_node_slug,
            new_node_description_md, new_node_domain, new_node_difficulty_hint,
            rationale}
  new_node_slug: lowercase-kebab-case, unique.
  new_node_domain: "math" | "physics" | "applied"
  new_node_difficulty_hint: "intro" | "core" | "advanced"

rename: A node's title or slug should be standardised.
  payload: {node_id, old_title, new_title, new_slug, rationale}

promote: An interest node that appears as a prerequisite for many others and
  deserves foundation status.
  payload: {node_id, title, rationale}

demote: A foundation node that has seen little use and should become an interest.
  payload: {node_id, title, rationale}

add_edge: A relationship between two nodes that is missing from the graph.
  payload: {source_node_id, target_node_id, source_title, target_title,
            edge_kind, weight, rationale}
  edge_kind: "prerequisite" | "related"
  weight: float between 0.1 and 1.0

deprecate: A node that has not been engaged with in months and clutters the graph.
  payload: {node_id, title, rationale}

Rules:
- Only propose actions that are clearly warranted. Fewer good proposals are better
  than many speculative ones.
- Always include rationale (one sentence explaining the evidence).
- Every node_id in your output must be a node_id from the input data.
- Output 0–15 proposals as a JSON object:
  {"proposals": [{kind, payload_json}, ...]}
```

User (per-call):
```
=== Current megagraph ===
Nodes ({n} total):
{node_list_formatted}

Edges ({e} total):
{edge_list_formatted}

=== Recent additions (since {since}) ===
New nodes: {new_nodes_formatted}
New edges: {new_edges_formatted}
Recent autonomous dedup decisions: {dedup_decisions_formatted}

=== Engagement signals ===
Highly engaged nodes: {high_engagement_formatted}
Nodes where users are struggling: {struggling_formatted}
Neglected nodes (no engagement in 60 days): {neglected_formatted}
```

### Tests (`api/tests/test_generate_curation_report.py`)

| Test | What it verifies |
|---|---|
| `test_missing_bearer_returns_401` | Auth required |
| `test_no_nodes_returns_empty` | Empty megagraph → 0 proposals, no crash |
| `test_proposals_written_to_db` | Happy path: Sonnet returns 2 proposals → 2 `curation_proposals` rows with `status='pending'` |
| `test_since_window_uses_last_snapshot` | `megagraph_snapshots` row exists → `since` set to its `taken_at` |
| `test_since_window_all_time_when_no_snapshot` | No snapshot → `since` = epoch |
| `test_llm_call_logged` | `llm_calls` row written after Sonnet call |
| `test_output_truncated_at_20` | Sonnet returns 25 proposals → only 20 inserted, warning logged |

---

## Step 2 — Next.js: admin auth gating + proposal review UI

### New files

- `web/app/admin/layout.tsx` — admin layout with auth gate + nav
- `web/app/admin/page.tsx` — admin index (redirect to `/admin/curation`)
- `web/app/admin/curation/page.tsx` — proposal review UI (Server Component)
- `web/app/api/admin/proposals/route.ts` — `GET` pending/approved proposals
- `web/app/api/admin/proposals/[id]/decide/route.ts` — `POST` approve/reject

### New helper

`web/lib/adminAuth.ts`:
```typescript
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export async function requireAdmin() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user || user.email !== process.env.ADMIN_EMAIL) {
    redirect("/daily");
  }
  return user;
}

export async function assertAdminApi(supabase: SupabaseClient) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user || user.email !== process.env.ADMIN_EMAIL) {
    throw new Response(JSON.stringify({ error: "Forbidden" }), { status: 403 });
  }
  return user;
}
```

### `web/app/admin/layout.tsx`

Server component. Calls `requireAdmin()` at the top. Renders the admin nav
(per D10) and `{children}`.

### `web/lib/pythonApi.ts` addition

```typescript
interface GenerateCurationReportResponse { proposals_created: number; since: string; }
export async function generateCurationReport(): Promise<GenerateCurationReportResponse> {
  return pythonPost("/generate-curation-report", {});
}
```

### `web/app/admin/curation/page.tsx`

Server Component. On load:

1. Calls `requireAdmin()`.
2. Fetches proposals from Supabase: all `curation_proposals` ordered by
   `proposed_at DESC`.
3. Renders two sections:
   - **Pending** — proposals with `status='pending'`. One card per proposal
     with kind badge, human-readable description, rationale, Approve / Reject
     buttons (client-side action → `POST /api/admin/proposals/[id]/decide`).
   - **Approved (ready to apply)** — proposals with `status='approved'`.
     Shows the "Apply approved proposals" button. This button calls
     `POST /api/admin/proposals/apply` (a stub that returns 501 until step 4).
4. At the top: a "Run curation report" button that calls
   `POST /api/admin/curation/run` (a Next.js route that calls
   `generateCurationReport()` then refreshes the page).

Add `web/app/api/admin/curation/run/route.ts`:
```typescript
export async function POST() {
  await assertAdminApi(...);
  await generateCurationReport();
  return Response.json({ ok: true });
}
```

### `describeProposal` helper (`web/lib/describeProposal.ts`)

Human-readable one-liners for each proposal kind, used in the review UI:

```typescript
export function describeProposal(proposal: CurationProposal): string {
  const p = proposal.payload_json;
  switch (proposal.kind) {
    case "merge":     return `Merge "${p.source_title}" into "${p.target_title}"`;
    case "split":     return `Split "${p.source_title}" — create "${p.new_node_title}"`;
    case "rename":    return `Rename "${p.old_title}" → "${p.new_title}" (slug: ${p.new_slug})`;
    case "promote":   return `Promote "${p.title}" from interest → foundation`;
    case "demote":    return `Demote "${p.title}" from foundation → interest`;
    case "add_edge":  return `Add ${p.edge_kind} edge: "${p.source_title}" → "${p.target_title}" (weight ${p.weight})`;
    case "deprecate": return `Deprecate "${p.title}"`;
    default:          return `Unknown: ${proposal.kind}`;
  }
}
```

### Design notes

- Kind badges use `variant="outline"` with a colour per kind:
  - `merge`, `split` → amber border (structural changes)
  - `rename`, `add_edge` → forest border (refinements)
  - `promote`, `demote` → amber-subtle background (tier changes)
  - `deprecate` → destructive border
- Rationale text: `font-serif text-sm text-muted-foreground`
- Approve button: primary (amber filled). Reject button: outline.
- The "Run curation report" button uses `variant="secondary"` (forest).
- The "Apply approved proposals" button: `variant="default"` (amber), disabled
  when zero approved proposals exist. Shows count: "Apply 3 approved proposals".

### `POST /api/admin/proposals/[id]/decide`

```typescript
// Body: { action: "approve" | "reject" }
// Sets curation_proposals.status = action === "approve" ? "approved" : "rejected"
// Sets decided_at = now(), decided_by = operator email
// Uses service-role client (bypasses RLS)
```

### Schema additions

None — `curation_proposals` table already exists from migration `20250008`.

Add `ADMIN_EMAIL` to `web/.env.local` (and document in `web/.env.local.example`
if one exists):
```
ADMIN_EMAIL=samkirkwood07@gmail.com
```

### Tests

Manual verification (no automated tests for admin UI steps):

1. Sign in as a non-admin user → `/admin` redirects to `/daily`.
2. Sign in as the operator → `/admin/curation` renders.
3. Click "Run curation report" → proposals appear.
4. Approve one, reject one → status updates correctly.
5. "Apply approved proposals" button is present (stub — expect 501 until step 4).

---

## Step 3 — Next.js: operator megagraph view

### New files

- `web/app/admin/megagraph/page.tsx`
- `web/app/api/admin/megagraph/route.ts` — `GET` full graph + snapshot list
- `web/app/api/admin/megagraph/snapshot/[id]/route.ts` — `GET` single snapshot JSON

### `GET /api/admin/megagraph`

Returns:
```typescript
interface AdminMegagraphData {
  nodes: { id: string; slug: string; title: string; kind: "foundation" | "interest";
           domain: string; pool_status: string; }[];
  edges: { id: string; source_node_id: string; target_node_id: string;
           edge_kind: string; weight: number; }[];
  snapshots: { id: string; label: string; taken_at: string; taken_by: string; }[];
  pending_proposals: CurationProposal[];  // status='pending'
}
```

Snapshots list does NOT include `snapshot_json` (too large). Load individual
snapshot JSON via the `[id]` route when the scrubber is dragged.

### `web/app/admin/megagraph/page.tsx`

Client Component (React Flow must be client-side).

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  Admin nav                            [Take snapshot]   │
├────────────┬────────────────────────────────────────────┤
│  Filters   │                                            │
│            │        React Flow canvas                   │
│  □ Found.  │        (full width, ~70vh)                 │
│  □ Interest│                                            │
│  □ Math    │                                            │
│  □ Physics │                                            │
│  □ Applied │                                            │
│  □ Deprecated                                          │
│  □ Proposals                                           │
├────────────┴────────────────────────────────────────────┤
│  [●──────────────────────────────────●] Time scrubber  │
│   oldest snapshot                    current           │
└─────────────────────────────────────────────────────────┘
```

**React Flow + Dagre:**

Reuse the same Dagre layout helper from `web/app/skill-tree/page.tsx` (Phase
5-rev). The admin view adds:
- Foundation nodes: rounded-full circle, amber-subtle background, amber border.
- Interest nodes: rounded-full circle, forest-subtle background, forest border.
- Deprecated nodes: dashed border, muted background, smaller.
- Nodes with a pending proposal: orange dashed overlay ring.
- Edges: grey thin lines; prerequisite edges solid, related edges dashed.

Node click: right panel (Radix Sheet or simple sidebar `div`) showing:
- Title, slug, kind, domain
- `pool_status`
- Engagement stats: total `engagement_count` across users (query
  `SUM(engagement_count) FROM user_node_states WHERE node_id = ?`)
- Pending proposals affecting this node (from the `pending_proposals` array)

**Layer toggles:**

State: `Set<string>` of active filters. Toggling a filter hides/shows nodes
via React Flow's `hidden` node property. Foundation and interest are checked
by default; all domains checked by default; deprecated unchecked by default;
proposals overlay unchecked by default.

**Time scrubber:**

- A `<Slider>` component (shadcn) ranging from 0 to `snapshots.length`.
- Position 0 = oldest snapshot; last position = current live state.
- Dragging to a snapshot position: fetch `GET /api/admin/megagraph/snapshot/[id]`
  → replace nodes and edges in React Flow state with the snapshot's data.
- Current live state: always held in memory as the "rightmost" position.
- Label shown below the slider: snapshot's `label` and `taken_at`.
- If no snapshots exist: slider is visible but disabled; label reads
  "No snapshots yet — run curation to create the first."

**"Take snapshot" button:**

`POST /api/admin/megagraph/snapshot` (new Next.js route):
```typescript
// Reads all current nodes + edges
// Serialises to snapshot_json (per D8)
// Inserts megagraph_snapshots(label, snapshot_json, taken_by='operator')
// Returns { id, label, taken_at }
```

This is a manual operator snapshot (`taken_by='operator'`). It does NOT
unlock cross-pollination (the gate requires `taken_by='system'`, written by
the apply action in step 4).

### Schema additions

None — `megagraph_snapshots` already exists.

### `web/lib/pythonApi.ts` addition

No Python calls for this step (all Supabase direct reads).

### Tests

Manual verification:

1. `/admin/megagraph` renders with all current nodes and edges.
2. Toggle "Foundation only" → interest nodes disappear from canvas.
3. No snapshots yet → scrubber is disabled with correct label.
4. "Take snapshot" → snapshot appears in scrubber; dragging to it shows the
   same graph state (since it was just taken).

---

## Step 4 — Apply action + snapshot write

This step implements the "Apply approved proposals" action. It mutates the
graph, writes the snapshot, and unlocks cross-pollination.

### New files

- `web/app/api/admin/proposals/apply/route.ts` — `POST` apply all approved proposals
- `web/lib/applyProposal.ts` — per-kind apply logic (pure functions operating
  on the service-role Supabase client)

### `POST /api/admin/proposals/apply`

```typescript
// 1. assertAdminApi()
// 2. Load all curation_proposals WHERE status='approved'
// 3. For each proposal, call applyProposal(supabaseAdmin, proposal)
// 4. Mark proposal: status='applied', decided_at=now(), decided_by=adminEmail
// 5. After all proposals: serialise current graph and write megagraph_snapshots
// 6. Return { applied_count, snapshot_id }
```

Uses the **service-role Supabase client**:
```typescript
import { createClient } from "@supabase/supabase-js";
const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SECRET_KEY!,
);
```

### `web/lib/applyProposal.ts` — per-kind logic

**`merge`** — `{source_node_id, target_node_id}`:
1. Repoint edges: `UPDATE edges SET source_node_id = target WHERE source_node_id = source`.
2. Repoint edges (target side): `UPDATE edges SET target_node_id = target WHERE target_node_id = source`.
3. Dedup edges: for each (source, target, kind) pair that now has duplicates,
   keep the one with the highest weight; delete the rest.
4. Repoint `user_interests`:
   - For users who have `source` but not `target`: `UPDATE ... SET node_id = target`.
   - For users who have both: `DELETE ... WHERE node_id = source` (they keep `target`).
5. Repoint `user_node_states` (same pattern as `user_interests`).
6. Repoint `queue_items` where `ref_id = source AND kind IN
   ('concept_review','suggested_interest')`: set `ref_id = target`.
7. Repoint `problems.topic_node_id` where `topic_node_id = source`.
8. Set `nodes.pool_status = 'deprecated'` for source node.

**`split`** — `{source_node_id, new_node_title, new_node_slug, ...}`:
1. Insert new node:
   ```sql
   INSERT INTO nodes (slug, title, description_md, domain, kind,
     difficulty_hint, pool_status) VALUES (...)
   ```
2. Insert edges from payload (if any provided by Sonnet).
3. Log: "Split simplified — user state remains on source node."

**`rename`** — `{node_id, new_title, new_slug}`:
1. Load `old_slug` from `nodes WHERE id = node_id`.
2. `UPDATE nodes SET title = new_title, slug = new_slug, updated_at = now()
   WHERE id = node_id`.
3. `UPDATE notebook_entries SET topic_node_slugs = array_replace(
   topic_node_slugs, old_slug, new_slug) WHERE old_slug = ANY(topic_node_slugs)`.

**`promote`** — `{node_id}`:
1. `UPDATE nodes SET kind = 'foundation', updated_at = now() WHERE id = node_id`.

**`demote`** — `{node_id}`:
1. `UPDATE nodes SET kind = 'interest', updated_at = now() WHERE id = node_id`.

**`add_edge`** — `{source_node_id, target_node_id, edge_kind, weight}`:
1. Upsert into `edges` (on conflict `(source_node_id, target_node_id, edge_kind)`
   → update `weight`). If no unique constraint exists on edges, use
   select-before-insert.

**`deprecate`** — `{node_id}`:
1. `UPDATE nodes SET pool_status = 'deprecated', updated_at = now() WHERE id = node_id`.
2. `UPDATE queue_items SET state = 'dismissed' WHERE ref_id = node_id
   AND kind IN ('concept_review','suggested_interest')`.

### Snapshot write (after all proposals applied)

```typescript
const nodesResp = await supabaseAdmin.from("nodes")
  .select("id, slug, title, kind, domain, pool_status").execute();
const edgesResp = await supabaseAdmin.from("edges")
  .select("id, source_node_id, target_node_id, edge_kind, weight").execute();

const snapshotJson = {
  version: 1,
  taken_at: new Date().toISOString(),
  nodes: nodesResp.data,
  edges: edgesResp.data,
};

const { data: snap } = await supabaseAdmin.from("megagraph_snapshots").insert({
  label: `curation-${new Date().toISOString().slice(0, 10)}`,
  snapshot_json: snapshotJson,
  taken_by: "system",  // <-- unlocks cross-pollination gate
  taken_at: new Date().toISOString(),
}).select("id").single();
```

**Cross-pollination gate is now open.** `/compute-cross-pollination` will
return `reason='ok'` from this point forward.

### Update the curation page (step 2)

Replace the 501 stub `POST /api/admin/proposals/apply` with the real route.
The button now triggers the full apply flow. On success, redirect to
`/admin/curation` with a toast: "Applied N proposals. Megagraph snapshot
taken."

### Schema additions

None — all tables already exist.

### Tests (`api/tests/test_compute_cross_pollination.py` — verify gate opens)

After step 4, add a test:

| Test | What it verifies |
|---|---|
| `test_after_snapshot_written_by_system_gate_opens` | Insert a `megagraph_snapshots` row with `taken_by='system'` → `/compute-cross-pollination` returns `reason='ok'`, not `'no_curation_yet'` |

Manual verification:

1. Run curation report → proposals created.
2. Approve proposals in the UI.
3. Click "Apply approved proposals" → success toast.
4. `SELECT * FROM megagraph_snapshots` → one row, `taken_by='system'`.
5. Call `POST /compute-cross-pollination` → `reason='ok'`.
6. Megagraph view time scrubber → now shows the snapshot point.

---

## Step 5 — Cost dashboard

### New files

- `web/app/admin/costs/page.tsx`
- `web/app/api/admin/costs/route.ts` — `GET` llm_calls data

### `GET /api/admin/costs`

Query parameters: `period` (`7d` | `30d` | `all`). Default: `30d`.

Returns:
```typescript
interface CostEntry {
  id: string;
  route: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  created_at: string;
  user_id: string | null;
}

interface CostSummary {
  total_cost_usd: number;
  total_calls: number;
  by_route: { route: string; calls: number; cost: number; }[];
  by_model: { model: string; calls: number; cost: number; }[];
  entries: CostEntry[];  // individual rows, most recent first
}
```

### `web/app/admin/costs/page.tsx`

Server Component (or client with SWR; server is simpler here).

**Layout:**

Top row: summary cards (total calls, total cost, period selector).

Summary breakdown section: two small tables side-by-side:
- By route: route | calls | total cost
- By model: model | calls | total cost

Full log section: paginated table (50 rows per page):
- Date | Route | Model | Input tokens | Output tokens | Cost

**Design:**
- Numbers: `font-mono text-sm`.
- Route names: `font-mono text-xs text-muted-foreground`.
- Cost column: `font-mono text-amber` for rows over $0.05 (visual emphasis
  on expensive calls; amber is already the primary accent).
- Headers: `text-xs font-semibold uppercase tracking-widest text-muted-foreground`.
- No charts — a sortable table is more actionable for debugging costs.

### Schema additions

None — `llm_calls` table is unchanged since Phase 3.

### Tests

Manual verification:

1. `/admin/costs` loads without error.
2. All LLM calls made during Phase 8-rev acceptance appear in the table.
3. Period selector changes the date range.
4. By-route breakdown shows `/generate-curation-report` as a line item.

---

## Step 6 — Drop deprecated tables

### Verification before migration

Run these checks and confirm all return no production code references:

**Web codebase:**
```bash
# In web/
grep -r "user_plans\|plan_nodes\|daily_assignments\|canonical_topics\|canonical_edges\|pending_topic_requests" --include="*.ts" --include="*.tsx"
```

Known finding: `web/app/page.tsx` references `user_plans`. Fix before running
the migration.

**Python codebase:**
```bash
# In api/
grep -r "user_plans\|plan_nodes\|daily_assignments\|canonical_topics\|canonical_edges\|pending_topic_requests" --include="*.py"
```

Known finding: `api/tests/test_hook_match.py` references `canonical_topics`
in fixture data. Update or remove the fixture reference.

### Changed files

**`web/app/page.tsx` — rewrite redirect logic (per D9):**

```typescript
// Old: check user_plans for an active plan
// New: check surveys for a completed onboarding

const { data: survey } = await supabase
  .from("surveys")
  .select("id")
  .eq("user_id", user.id)
  .maybeSingle();

if (survey) redirect("/daily");
else redirect("/survey");
```

**`api/tests/test_hook_match.py` — update fixtures:**

Remove any fixture that inserts into or selects from `canonical_topics`.
Replace with `nodes` fixtures if the test still needs a topic reference, or
delete the test if it was testing v1-only behaviour.

### Migration `20250016_drop_deprecated_tables.sql`

```sql
-- Drop v1 tables that have had no new writes since Phase 4-rev.
-- All references have been removed from application code (verified above).

DROP TABLE IF EXISTS public.pending_topic_requests CASCADE;
DROP TABLE IF EXISTS public.daily_assignments CASCADE;
DROP TABLE IF EXISTS public.plan_nodes CASCADE;
DROP TABLE IF EXISTS public.user_plans CASCADE;
DROP TABLE IF EXISTS public.canonical_edges CASCADE;
DROP TABLE IF EXISTS public.canonical_topics CASCADE;
```

Note: `daily_assignments` was referenced by the v1 `attempts.assignment_id`
FK, which was dropped in migration `20250011`. `CASCADE` ensures any remaining
FK stubs are cleaned up.

Apply:
```bash
npx supabase db push --db-url <your-supabase-db-url>
```

Verify after migration:
```sql
SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename
  IN ('canonical_topics','canonical_edges','user_plans','plan_nodes',
      'daily_assignments','pending_topic_requests');
-- Should return 0 rows.
```

### Schema additions

None (this step only removes schema).

### Tests

- `web/app/page.tsx` redirect logic: verify manually — a user who has
  completed the survey is redirected to `/daily`; a brand-new user is
  redirected to `/survey`.
- `api/tests/test_hook_match.py` must pass after fixture cleanup: run
  `uv run pytest api/tests/test_hook_match.py`.

---

## Step 7 — Phase 8-rev acceptance

End-to-end smoke test. All steps must be committed before running this.

1. **Curation report:** Click "Run curation report" in `/admin/curation`.
   Verify proposals appear within ~10 seconds. Check `curation_proposals`
   table has new `pending` rows. Check `llm_calls` has a
   `/generate-curation-report` row.

2. **Review UI:** Approve at least one proposal. Reject at least one. Verify
   `status` updates correctly in the DB.

3. **Apply + snapshot:** Click "Apply approved proposals". Success toast
   appears. Verify:
   - `megagraph_snapshots` now has one row with `taken_by='system'`.
   - Applied proposals have `status='applied'`.
   - If a `merge` was applied, the source node's `pool_status='deprecated'`.

4. **Cross-pollination unlocked:** Call `POST /compute-cross-pollination`
   directly (or via `curl.exe` / Postman with the bearer token). Verify
   response is `reason='ok'` and `suggestions_created` is an integer (may
   be 0 if no users have sufficient engaged nodes yet — that is correct).

5. **Megagraph view:** Navigate to `/admin/megagraph`. Canvas renders all
   nodes and edges. Toggle "Foundation only" — interest nodes disappear.
   Time scrubber now shows one snapshot point — drag to it and verify the
   graph matches the current live state.

6. **Operator snapshot:** Click "Take snapshot" in the megagraph view.
   Verify a second row appears in `megagraph_snapshots` with `taken_by='operator'`.
   Time scrubber now has two points.

7. **Cost dashboard:** Navigate to `/admin/costs`. Verify at least the
   curation-report Sonnet call is visible. Check the by-route summary shows
   `/generate-curation-report`.

8. **Deprecated tables gone:** Run the drop migration if not already applied.
   Confirm `SELECT * FROM canonical_topics` returns an error. Confirm
   `web/app/page.tsx` correctly redirects a new user to `/survey`.

9. **Auth gate:** Sign in as a non-operator user → `/admin` redirects to
   `/daily`. Sign in as operator → `/admin` loads.

Update `docs/pivot-plan.md` status line:

```
Status: Phase 8-rev complete.
Next step: Phase 9-rev step 1 — Mobile polish.
```

---

## Step 7 — Users + queue view

### New files

- `web/app/admin/users/page.tsx` — server component; shows all users + their queues
- `web/app/api/admin/users/route.ts` — `GET` users with queue summaries (used for
  future programmatic access; the page queries Supabase directly for simplicity)

### `web/app/admin/users/page.tsx`

Server Component. Queries:

1. `profiles` — all users ordered by `created_at ASC`
2. `queue_items` — all non-dismissed items ordered by `priority_score DESC`
3. `nodes` — all nodes to resolve titles for `concept_review` / `suggested_interest` refs
4. `user_interests` — to compute per-user interest count

Groups queue items by `user_id`. For each user, renders a card with:
- Header: email, display name (if set), interest count, queue item count, join date
- Table: Kind badge | State (colour-coded) | Topic / reason | Priority score

Kind badge colours follow the queue badge colour semantics in CLAUDE.md:
`problem` = amber filled, `paper_engagement` = forest filled, `refresher` = forest
outline, `suggested_interest` = ghost, `concept_review` = outline.

State colours: `surfaced` / `in_progress` → amber; `done` → forest; `pending` /
`skipped` / `dismissed` → muted.

For `concept_review` and `suggested_interest` items, the node title is resolved via
the node map and shown in the Topic column. For `problem` and `paper_engagement`
items, `added_reason` is shown if present.

### Nav update

`web/components/AdminNav.tsx` — add `{ href: "/admin/users", label: "Users" }` to
the `LINKS` array.

### Design notes

- Page: `max-w-4xl px-4 py-10` (slightly wider than curation page to fit the table)
- Cards: `rounded-md border border-border bg-card`
- Table headers: `text-[10px] font-semibold uppercase tracking-widest text-muted-foreground`
- Queue items exclude `state='dismissed'` (noise reduction)
- Empty queue: italic muted note inside the card

---

## Risks to watch

- **Sonnet proposals reference non-existent node IDs.** Sonnet sees node IDs
  in its prompt and is instructed to use them — but may still hallucinate an
  ID. Before calling `applyProposal`, validate that every `node_id` in the
  payload exists in `nodes`. If not, mark the proposal `rejected` with a
  note: "Invalid node_id in payload — proposal skipped during apply." Do not
  raise an uncaught error.

- **`merge` apply races a concurrent user write.** If a user is mid-engagement
  on the source node at apply time, their queue items may still reference the
  source `ref_id` momentarily. The apply logic updates `queue_items` for
  `concept_review` and `suggested_interest` kinds; `problem` and
  `paper_engagement` kinds reference problems/engagements by their own IDs
  (not directly by node_id), so they are unaffected. This race is negligible
  at 30 users.

- **React Flow admin view performance.** The megagraph may reach several hundred
  nodes over a year of use. React Flow handles this comfortably at our scale.
  Do not add pagination or virtual rendering prematurely.

- **`snapshot_json` size.** At several hundred nodes and edges, the JSON blob
  is <1 MB — well within Postgres jsonb limits and Supabase storage. No
  special handling needed.

- **`array_replace` on notebook_entries for rename.** If `new_slug` was
  inadvertently already present in some `topic_node_slugs` arrays, the
  array will have a duplicate. After the rename apply, run:
  `SELECT id FROM notebook_entries WHERE cardinality(topic_node_slugs) !=
  cardinality(array_agg(DISTINCT e) FROM unnest(topic_node_slugs) AS e)`.
  At our scale, dedup is safe to do in a follow-up manual SQL if needed.

- **Admin routes bypass RLS — treat with care.** The service-role client
  used in the apply route has full access to all tables. Do not use it
  for non-admin reads. Ensure `SUPABASE_SECRET_KEY` is not in any
  client-side bundle (it is set as a server-only env var in Vercel).

---

## Things easy to forget

- **Register `generate_curation_report` router in `api/main.py`.**
  This is a new FastAPI router; it must be `include_router`-ed.
- **`ADMIN_EMAIL` must be set in both `web/.env.local` (dev) and Vercel
  project environment variables (prod).** If absent, `requireAdmin()` will
  always redirect to `/daily` — the admin will be locked out.
- **Apply uses the service-role client, not the default server client.**
  The default `createClient()` from `web/lib/supabase/server.ts` uses the
  publishable (anon) key and respects RLS. The apply route needs to bypass
  RLS for cross-user writes — explicitly import and construct the admin client.
- **Snapshot `taken_by='system'`** — this exact string value is what the
  cross-pollination gate checks. Do not change it to `'operator'` or anything
  else. The "Take snapshot" manual button writes `taken_by='operator'`; the
  apply flow writes `taken_by='system'`.
- **`web/` has its own `.git`** — commit the Next.js changes there separately.
- **Run `uv run pytest` after step 6** before committing the migration, to
  confirm no Python test references a deprecated table.
- **The megagraph view is desktop-optimised** (per SPEC.md §Non-functional
  requirements: "Desktop optimised for ... admin"). No mobile layout required.
- **Every Claude call in the curation report must be logged to `llm_calls`.**
  The route uses `call_json(...)` from `api/anthropic_client.py` which handles
  this; do not bypass it with a raw `anthropic.messages.create()` call.

---

## Handoff to Phase 9-rev (preview)

Phase 9-rev is polish only:

- Mobile polish on the daily-three view, problem submission, and notebook.
  (Skill tree and admin pages are intentionally desktop-only.)
- Error monitoring (Sentry or equivalent).
- Vercel cron jobs for weekly curation report and daily cross-pollination
  (replacing the current manual-trigger UI buttons).
- Final design-system pass — check every page against the `/design` route.

Phase 9-rev acceptance = v2 ready for friends.
