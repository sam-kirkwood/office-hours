# Curriculum Curator Design — Office Hours (v2)

## About this document

This document specifies the curriculum curator: the background intelligence that decides what goes into each user's queue, when prerequisites surface, and how the queue adapts based on engagement signals. It is the operational heart of the product's "the system curates; the user trusts" principle.

Read alongside:
- `SPEC.md` — product philosophy and adaptation principles
- `ARCHITECTURE.md` — data model and service topology
- `docs/graph-design.md` — megagraph model, prerequisite edges
- `docs/survey-and-difficulty-design.md` — difficulty model, intent types, user controls

The curriculum curator is **LLM-driven**. It uses Claude (Sonnet for planning, Haiku for lightweight assessment) with rich context about the user, their history, and the megagraph. It advises; the system executes. LLM calls produce structured recommendations; the system creates or updates queue items based on those recommendations.

---

## 1. Overview

The curriculum curator is responsible for:

1. **Queue planning** — deciding what content to add to the queue for each active interest
2. **Prerequisite timing** — proactively surfacing prerequisite refreshers before they are needed, not after the user struggles
3. **Pacing** — deciding when to go deeper within a topic versus consolidate what is already there
4. **Adaptation** — adjusting queue composition in response to engagement signals (struggle, ease, rerolls, deferrals, feedback)
5. **Multi-interest balancing** — distributing queue slots roughly evenly across active interests
6. **Consolidation scheduling** — surfacing occasional consolidation problems on topics the user has marked comfortable

The curator does not replace the operator's weekly curation (which maintains the megagraph) or the cross-pollination job (which surfaces new interests). It operates on the user's existing interests and queue.

---

## 2. Cadence and triggers

The curator runs in two modes:

### 2.1 Daily planning job

**Frequency:** once per day per active user, run as a background job.

**Purpose:** the main queue-planning operation. Assesses each active interest, looks ahead at prerequisite needs, adds new queue items, and rebalances priorities across the queue. This is where the majority of the intelligence lives.

**When a user is "active":** any user who has engaged with at least one item in the past 14 days.

### 2.2 Post-engagement update

**Frequency:** triggered after every completed engagement — problem attempt, paper completion, or refresher.

**Purpose:** lightweight state update following a single engagement. Updates `user_node_states`, recalculates `struggle_score`, and may immediately queue a follow-up item (e.g. reinforcement after a struggling attempt, or acceleration after a high-ease engagement). Does not run the full daily planning logic.

The daily job and post-engagement update share the same underlying data model but differ in scope. The daily job plans ahead; the post-engagement update reacts immediately.

---

## 3. Inputs: what the curator knows

### 3.1 User profile

- `user_interests` — all active interests with `intent_context` per interest
- `users` — basic profile, mode balance preference

### 3.2 Graph state

- `nodes` — all nodes in the user's slice (interest + relevant foundation nodes)
- `edges` — prerequisite and related edges connecting the user's nodes
- `user_node_states` — current state per node: `unseen / bookmarked / active / struggling / comfortable`, plus `struggle_score`, `engagement_count`, `last_engaged_at`

### 3.3 Queue state

- `queue_items` — current queue: all items with state `pending` or `deferred`, their `kind`, `priority_score`, `added_reason`, `added_at`
- `surfaced_picks` — history of what was surfaced and what the user chose (signals what they engage with vs pass over)

### 3.4 Engagement history

- `attempts` — all problem attempts: hints used, grade, `requested_easier`, `requested_harder`, `requested_assume_less`, `marked_refreshed`, `parent_attempt_id`
- `paper_answers` — all paper engagement answers
- Recent reroll patterns from `surfaced_picks` (items that were surfaced but not chosen, especially repeatedly)

### 3.5 Problem pool state

- Which problems exist in the pool for each of the user's interest and foundation nodes
- Which the user has already seen (via `attempts` and queue history)

### 3.6 Feedback signals

- Profile page feedback (stored as `user_preferences` or equivalent): "too hard", "assume less", "more papers", "harder problems"
- Per-problem signals from recent `attempts`: `requested_easier`, `requested_harder`, `requested_assume_less`
- `queue_items` with `state = 'deferred'` (not ready yet deferrals)

---

## 4. Daily planning job

### 4.1 Process overview

For each active user:

1. Assess the current state of each interest: depth, node states, recent signals
2. Check queue health: is the queue well-stocked? Balanced? Appropriately varied?
3. Call Sonnet with the full context (see 4.2) to get queue recommendations
4. Execute recommendations: create new `queue_items`, update priority scores
5. Check deferred items for conditional re-queue (see Section 8)
6. Check consolidation schedule (see Section 9)

### 4.2 The Sonnet call — queue planning

**Model:** claude-sonnet (latest)

**Purpose:** given everything known about the user, recommend what should be added to or reprioritised in their queue.

#### Input structure (JSON, passed as user message content)

```json
{
  "user_context": {
    "mode_balance": 0.5,
    "active_interests": [
      {
        "node_id": "...",
        "node_title": "Superconductivity",
        "intent_context": "reconnecting, physics-depth angle, teach intent",
        "engagement_count": 4,
        "last_engaged_at": "...",
        "node_state": "active"
      }
    ],
    "foundation_node_states": [
      {
        "node_title": "Ordinary Differential Equations",
        "state": "active",
        "struggle_score": 0.3,
        "engagement_count": 1,
        "last_engaged_at": "..."
      }
    ],
    "prerequisite_edges": [
      {
        "from": "Superconductivity",
        "to": "Quantum Mechanics I",
        "edge_kind": "prerequisite",
        "weight": 0.9
      },
      {
        "from": "Superconductivity",
        "to": "Ordinary Differential Equations",
        "edge_kind": "prerequisite",
        "weight": 0.7
      }
    ]
  },
  "recent_engagement": {
    "last_14_days": [
      {
        "kind": "problem",
        "node": "Superconductivity",
        "subtopic": "Meissner effect",
        "intent": "teach",
        "hints_used": 0,
        "grade": "correct",
        "requested_easier": false,
        "requested_harder": false,
        "marked_refreshed": false
      }
    ],
    "reroll_patterns": [
      {
        "mode": "refresher",
        "node": "Statistical Mechanics",
        "count": 2,
        "period_days": 7
      }
    ],
    "deferred_items": [
      {
        "node": "Superconductivity",
        "subtopic": "Josephson relations",
        "deferred_at": "...",
        "reason": "not_ready"
      }
    ]
  },
  "current_queue": {
    "pending_count": 8,
    "pending_by_interest": {
      "Superconductivity": 3,
      "Semiconductor Devices": 2,
      "Solid State Physics": 2,
      "Topological Insulators": 1
    },
    "pending_by_kind": {
      "problem": 5,
      "paper_engagement": 2,
      "refresher": 1
    }
  },
  "feedback_signals": {
    "profile_feedback": [],
    "recent_assume_less_requests": 0,
    "recent_easier_requests": 1
  }
}
```

#### System prompt (abbreviated — implement in full)

```
You are the curriculum curator for an Office Hours user. Your job is to recommend 
what should be added to or reprioritised in this user's learning queue.

The product's principles:
- Never gate content on prerequisite completion. Math refreshers surface alongside 
  topic content, not before it.
- The first problem on any new depth within a topic should build up the concepts it 
  needs rather than assume them.
- Look ahead: if the user is approaching content that will require a foundation they 
  haven't refreshed, surface that refresher now — before they need it.
- Difficulty, assumed background, and intent (teach/refresh/consolidate) are separate 
  dials. Adjust them independently.
- Distribute queue slots roughly evenly across active interests.
- Mode balance (problems vs papers) is a soft target, not a hard rule.

Struggle signals: hints used, easier requests, not-ready-yet deferrals, slow 
engagement. Ease signals: mark-as-refreshed skips, harder requests, no hints used.

Return a JSON object with your recommendations. Do not return prose.
```

#### Output format

```json
{
  "recommendations": [
    {
      "action": "add",
      "interest_node": "Superconductivity",
      "kind": "problem",
      "intent": "teach",
      "subtopic": "Cooper pairs and pairing mechanism",
      "depth": "conceptual",
      "assumed_background": ["Quantum Mechanics I basics", "Fermi surface concept"],
      "priority": "high",
      "reason": "User has completed Meissner effect at conceptual level. Cooper pairs is the natural next concept before BCS theory. No math required yet."
    },
    {
      "action": "add",
      "interest_node": "Ordinary Differential Equations",
      "kind": "refresher",
      "intent": "refresh",
      "subtopic": "second-order linear ODEs",
      "depth": "foundational",
      "assumed_background": ["first-order ODEs"],
      "priority": "medium",
      "reason": "BCS theory derivation will require second-order ODE fluency. User is 2-3 problems away from needing it. Surfacing now proactively."
    },
    {
      "action": "reprioritise",
      "queue_item_reference": "deferred:Superconductivity:Josephson_relations",
      "new_priority": "low",
      "reason": "User deferred this. ODE and BCS theory refreshers should run first. Keep in queue but hold back."
    }
  ],
  "observations": "User is engaging well at conceptual depth. One easier request on a problem — watch for repeated pattern before adjusting. Statistical Mechanics rerolls suggest they are not in the mood for that thread — hold off for now."
}
```

The `observations` field is logged for operator visibility but not acted on directly by the system.

#### Executing recommendations

After receiving the Sonnet response:

1. For each `add` recommendation: check the problem pool for a matching problem (by `interest_node`, `subtopic`, `intent`). If a suitable problem exists, link it to a new `queue_items` row. If not, trigger problem generation via `/generate-problem` with the recommendation as the generation brief.
2. For each `reprioritise` recommendation: update `priority_score` on the existing `queue_items` row.
3. Log the full Sonnet call (input + output) to `llm_calls`.

---

## 5. Post-engagement update

### 5.1 Trigger

Called after every completed engagement:
- Problem attempt submitted and graded
- Paper engagement completed
- Refresher marked as refreshed or skipped

### 5.2 The Haiku call — engagement assessment

**Model:** claude-haiku

**Purpose:** assess what the engagement signals about the user's current state on this node. Fast, cheap, targeted.

#### Input

```json
{
  "engagement": {
    "kind": "problem",
    "node": "Superconductivity",
    "subtopic": "Meissner effect",
    "intent": "teach",
    "hints_used": 2,
    "grade": "partial",
    "requested_easier": false,
    "requested_harder": false,
    "requested_assume_less": true,
    "marked_refreshed": false,
    "not_ready_deferred": false
  },
  "current_node_state": {
    "state": "active",
    "struggle_score": 0.2,
    "engagement_count": 3
  }
}
```

#### Output

```json
{
  "updated_struggle_score": 0.45,
  "state_transition": null,
  "immediate_action": "queue_reinforcement",
  "reinforcement_target": "Meissner effect",
  "reasoning": "Two hints used plus assume-less request. Not struggling severely but needs more scaffolding on this subtopic before moving on."
}
```

**`immediate_action` values:**
- `null` — no immediate action needed; daily job handles next steps
- `queue_reinforcement` — add a reinforcement problem on this subtopic to the queue now
- `accelerate` — user is clearly comfortable; mark node state up, consider queuing next depth sooner
- `surface_prerequisite` — a specific prerequisite gap was revealed; queue a refresher now

### 5.3 Executing the update

1. Update `user_node_states`: new `struggle_score`, `engagement_count`, `last_engaged_at`. Apply `state_transition` if present.
2. Execute `immediate_action` if present.
3. Log the Haiku call to `llm_calls`.

---

## 6. Struggle definition and state transitions

### 6.1 What counts as struggling

The `struggle_score` for a node is a float (0.0–1.0). It increases on struggle signals and decays over time with successful engagements.

**Signals that increase struggle_score:**
- Hints used: +0.1 per hint used (capped per engagement)
- `requested_easier`: +0.15
- `requested_assume_less`: +0.1
- `not_ready_deferred`: +0.2 (strong signal)
- Poor grade on a problem: +0.1 to +0.2 depending on severity
- Reroll (implicit): +0.05 (weak signal)

**Signals that decrease struggle_score:**
- No hints used: -0.05
- `requested_harder`: -0.15
- `marked_refreshed`: -0.1 (user felt they already had it)
- Clean grade: -0.05

The Haiku call calculates the updated struggle_score. The system does not calculate it with a fixed formula — the Haiku call takes the full engagement signals and returns a calibrated score. The values above are guidance for the Haiku prompt, not a hard algorithm.

### 6.2 State transitions

Node states follow this rough progression: `unseen → active → struggling / comfortable`

| Transition | Trigger |
|---|---|
| `unseen → active` | First engagement with this node/subtopic |
| `active → struggling` | `struggle_score` above ~0.6 after multiple engagements |
| `active → comfortable` | Multiple clean engagements, low struggle score, possibly `marked_refreshed` |
| `struggling → active` | Struggle score decays after reinforcement engagements succeed |
| `comfortable → active` | Long time since last engagement (consolidation timer elapsed); see Section 9 |

State transitions are recommended by the Haiku call (post-engagement) or the Sonnet call (daily planning). The system applies them.

---

## 7. Multi-interest balancing

### 7.1 Default: even rotation

Queue slots are distributed roughly evenly across active interests. "Roughly even" means that over any 7-day window, no interest receives more than twice the queue slots of any other interest.

This is a soft target enforced by the Sonnet call — the system prompt instructs Claude to maintain balance, and the `current_queue.pending_by_interest` input makes the current distribution visible.

### 7.2 Temporary imbalance

The system allows temporary imbalance in specific cases:
- A new interest was just added → it receives extra slots for the first 3–5 days (entry-point content)
- A deferred item's prerequisites are being addressed → the prerequisite interest receives extra reinforcement slots until the deferred item is unblocked
- An interest has a high struggle score across multiple nodes → reinforcement content for that interest temporarily takes priority

The Sonnet call observes these conditions in the input and adjusts recommendations accordingly. No hard rules are needed — Claude reasons about it from context.

### 7.3 User-set priorities (future)

User-controlled interest prioritisation is not implemented in v2. If a user wants to focus on one interest, they can signal this by engaging only with that interest's content and rerolling others. The reroll pattern is picked up by the curator. Explicit priority controls are deferred to v2.1.

---

## 8. Conditional re-queue ("not ready yet")

When a user taps "not ready yet — come back later" on a problem:

1. The `queue_items` row for that problem transitions to `state = 'deferred'`.
2. The post-engagement Haiku call notes the deferral and adds `+0.2` to the relevant node's `struggle_score`.
3. The system identifies which prerequisites are blocking readiness, using the megagraph's prerequisite edges from the problem's `topic_node_id`. These prerequisites are added to the next Sonnet call's context as "unblocked by deferral."
4. The daily Sonnet call receives deferred items as part of its input and is instructed to surface the blocking prerequisites and hold the deferred item back.
5. Daily, the system checks deferred items: have the blocking prerequisites been addressed? A prerequisite is considered "addressed" when the relevant `user_node_states` row has `state = 'comfortable'` or `struggle_score < 0.3` with `engagement_count >= 2`.
6. When prerequisites are addressed, the deferred item transitions back to `state = 'pending'` with refreshed priority. It re-enters the queue naturally.

The check in step 5 does not require an LLM call — it is a deterministic database check.

---

## 9. Consolidation scheduling

Consolidation problems surface for topics the user has marked comfortable (or that the system has transitioned to comfortable via engagement). They are infrequent — spaced practice, not a regular occurrence.

### 9.1 Trigger condition

A consolidation problem is eligible when all of the following are true:
- The node state is `comfortable`
- `last_engaged_at` is more than 21 days ago (initial threshold; tune empirically)
- No consolidation problem has been surfaced for this node in the past 28 days

### 9.2 What a consolidation problem is

- Intent: `consolidate`
- Assumed background: full topic apparatus — the user has confirmed they know this
- Difficulty: moderate to challenging — this is confirmation that knowledge is solid, not a soft reminder
- Does not build up from scratch — assumes the user's comfort level

### 9.3 How it's queued

The daily Sonnet call is aware of nodes eligible for consolidation (included in the input as part of `foundation_node_states` and `user_node_states` with state and last_engaged_at). The Sonnet call recommends when to queue a consolidation problem as part of its normal output. It is not a separate job.

---

## 10. Prerequisite timing

The key principle: **surface prerequisite refreshers before they are needed, not after the user struggles.**

The Sonnet call is responsible for this. It receives:
- The user's current depth within each interest (inferred from engagement history and node states)
- The prerequisite edges from the megagraph for each active interest node
- The current state of each prerequisite node

It reasons: *"Given where this user currently is within this interest, what mathematics or foundational concepts will come up in the next 2–3 problems? Are those prerequisites in a suitable state? If not, queue refreshers now."*

The Sonnet call does not need explicit rules for this — it reasons from context. The system prompt instructs it to look ahead, and the prerequisite edge data in the input makes this possible.

**Example reasoning (from Sonnet):**
> *"User is at the conceptual level for superconductivity — Meissner effect, Cooper pairs. The next natural depth involves BCS theory, which requires second-order ODEs. The user's ODE node state is 'active' with low engagement count. Recommending an ODE refresher focused on second-order linear ODEs now, before BCS theory problems appear."*

---

## 11. Queue composition model

### 11.1 Queue size

The queue is **bounded**. The daily job aims to keep roughly 10–15 non-terminal
items (`pending` + `surfaced` + `deferred`) on hand and **never exceeds a hard
cap of 15** (Phase 10.5-rev Q1 decision — the operator wanted a tighter band
than the original 20–30). This gives the surface-daily job (`/surface-daily`)
enough variety to select three meaningfully varied items without the queue
growing without limit day over day.

If the non-terminal stock drops below **6**, a refill is triggered (see §11.4)
rather than waiting for the next scheduled daily run. The executor enforces the
cap deterministically: once on-deck stock reaches 15 it stops acting on `add`
recommendations (it still applies `reprioritise` recommendations).

### 11.2 Composition targets (soft)

The Sonnet call is given these as targets, not hard constraints:

| Dimension | Target |
|---|---|
| Problems vs papers | Match user's mode balance preference (default 50/50) |
| Teach vs refresh vs consolidate | Majority teach/refresh for active interests; consolidate surfaces rarely |
| Interest distribution | Roughly even across active interests |
| Foundation vs interest | Foundation refreshers appear alongside interest content, not in isolation |
| New content vs reinforcement | Mostly new; reinforcement triggered by struggle signals |

### 11.3 Variety

The surface-daily job selects 3 items from the pending queue using `priority_score`. It applies a variety constraint: the three items should not all be the same kind (e.g. not three problems) or from the same interest. The variety constraint is deterministic logic in the surface-daily job, not an LLM call.

### 11.4 Queue lifecycle (Phase 10.5-rev Q1)

These are the resolved semantics behind the daily-queue surface. They are the
contract the surfacing, reroll, refill, and fallback code implement.

- **Reroll ("Show me something else").** Re-surfaces the *next* highest-priority
  pending items in place of the current three. It is a pure re-pick — it never
  generates content on click and never re-runs the planner. Passed-over items
  are recorded (length-1 `surfaced_picks` rows with `chosen_item_id = null`) so
  the curator can read the reroll pattern, and they drop in effective priority
  but remain in the queue and can resurface later. If fewer than three distinct
  items remain, the user sees what's left plus a "more coming" affordance, and a
  background refill is triggered.
- **Stocking / refill-on-drain.** The queue is kept stocked by the daily planner
  *and* by an on-demand refill: whenever surfacing leaves non-terminal stock
  below 6, a background `run-daily-planner` pass is fired for that user. This
  decouples "queue stays full" from the once-a-day cron, which is what the F17
  fallback was previously (badly) compensating for.
- **Length / growth.** Bounded — see §11.1. Hard cap 15; the queue does not grow
  unbounded across days.
- **Duplicate prevention.** Enforced at every write path, not just the planner:
  `_queue_item_already_exists` already guards planner `add`s; the same
  `(user, kind, ref_id)` guard now also covers the surface-daily F17 fallback and
  the refresher click-time resolver. A user never has two non-terminal queue rows
  pointing at the same content, and never gets a second concept card for a node
  they've already reviewed.
- **Cold start.** On survey completion the system seeds a *varied* queue: the
  planner adds problems and (proactive) refreshers, and — when the user's mode
  balance gives papers a meaningful share — `propose-papers` seeds paper
  engagements so the very first queue honours the slider. Papers are no longer
  orphaned behind a never-run weekly job.
- **The F17 fallback is now a true last resort.** It inserts a single starter
  concept *only when the user has no queue rows at all* (a brand-new or
  generation-failed queue). Because inserting one row makes the total non-zero,
  it can fire at most once and can never spam. Normal stocking is the planner +
  refill path above.
- **Removing items.** Dismissing a suggested interest already removes it
  (`state = 'dismissed'`). A general "remove / not now" affordance for other
  kinds and a clear home for deferred items is tracked in Phase 10.5-rev Step 7
  (g1), not here.

UI copy that communicates this (d1, g3): a one-line orientation under the "Up
next" heading explaining the queue is curated and refreshes itself, and concept
cards carry a short "why this is here" line rather than the bare "A starting
point while your queue is being built."

### 11.5 Refreshers are a framing, not a kind (Phase 10.5-rev Step 2)

A refresher is **not a distinct content type**. It is a concrete queue item — a
`problem` (active recall), a `concept_review` (a gentle read), or a
`paper_engagement` (revisit a paper) — carrying `via_refresher = true`. The
item's own `kind` drives routing and title resolution; the flag drives the
"Refresher" badge and revisit copy in the daily queue.

- **Resolved at creation time, not at click time.** When the curator planner,
  the post-engagement prerequisite path, or an on-demand request decides to
  refresh something, it calls `resolve_refresher_to_content`
  ([api/routes/refresher.py](../api/routes/refresher.py)) immediately:
  pool-lookup a refresh-intent problem on the node → generate one on a pool
  miss → fall back to the node's concept brief only if generation fails (reusing
  an existing concept rather than minting a duplicate). The legacy
  `refresher_schedule` shape (revisit a specific prior attempt/paper) resolves
  to a problem / paper_engagement pointing at that subject. The HTTP entry point
  for the web layer is `POST /create-refresher`.
- **No click-time resolver page.** The old `kind='refresher'` row + the
  `/refresher/[id]` page that resolved on load is gone. That page mutated state
  on navigation: visiting consumed the refresher and minted a replacement, so a
  "back to queue" lost it (d4), a non-resolving refresher silently bounced to
  `/daily` (d18), and a paper-triggered refresher routed to the wrong reader
  (d21). Resolving at creation removes the whole class of bug — a refresher card
  behaves like any other queue card.
- **A refresher needs a basis.** "Refresher" means *look at this again*, so it
  only applies to a node the user has a relationship with: real engagement
  (`user_node_states.engagement_count > 0` or state `active`/`struggling`/
  `comfortable`), a Stage-2 foundation marked "refresh" (which writes
  `state='active'`), or concept-tour familiarity. When the curator wants to
  front-load a prerequisite the user has **not** met (proactive prereq-surfacing
  is a deliberate feature — §10), `resolve_refresher_to_content` downgrades it to
  **groundwork**: a plain orientation read (`via_refresher=false`, a Concept
  card), not a "Refresher / look at this again" card on something never seen. The
  planner prompt is also told to emit `kind:"problem"`/`intent:"teach"` framed as
  groundwork for unmet prerequisites; the resolver guard is the deterministic
  backstop. This was the fix for a cold-start queue showing a "Refresher" on
  linear algebra the user had neither engaged nor marked.
- **Consumed on completion, never on open.** Because the card is a normal
  problem/concept/paper, opening it does nothing destructive; it is marked done
  only when its content is completed. Back-to-queue preserves it.
- **Prevent-at-source.** `resolve_refresher_to_content` returns `None` when
  nothing resolves; callers skip creating a dead row, so a blank refresher never
  enters the queue (d18).
- **Navigate-there-and-back (g2).** A refresher requested from inside another
  surface records `parent_queue_item_id`; the resulting reading view renders a
  "← Back to …" link to its origin (the paper case is wired today, mirroring
  `ConceptReadingView`). A refresher requested from the skill tree lands in the
  daily queue as a clearly-badged card; the round trip is queue-mediated. The
  deep "back to this exact node" link rides on the skill-tree deep-linking work
  tracked under Step 7 (n2).

---

## 12. Mode balance adjustment

The user's mode balance preference is a soft target, not a hard rule. The cursor drifts based on signals:

**Rerolls:** if the user consistently rerolls a particular mode (e.g. always rerolls papers), the effective mode balance shifts away from that mode for this user. This is not a permanent setting change — it is a soft reweighting of priority scores applied by the Sonnet call.

**Explicit feedback:** if the user adjusts the slider on the profile page, that takes precedence immediately. The new value is passed to the Sonnet call.

**Drift decay:** reroll-based drift decays over time if the user stops rerolling. After 14 days with no rerolls of a mode, the drift resets toward the stated preference.

---

## 13. Edge cases

### 13.1 New user — cold start

For a user who just completed the survey, the daily job runs its first pass immediately (not waiting until the next scheduled run). The Sonnet call context includes the concept tour responses and foundation tile marks from the survey as the primary signals. The queue is populated from scratch.

### 13.2 User with no engagement for 14+ days

The user is considered inactive. The daily job does not run. When the user returns and engages:
1. The post-engagement update runs normally.
2. The daily job runs a full pass.
3. The Sonnet call context notes the gap. The system prompt instructs Claude to treat this as a partial cold start — assume some decay in comfortable nodes, pitch re-entry slightly earlier in the topic than where the user left off.

### 13.3 User marks everything as comfortable in a short period

Possible signal of `marked_refreshed` spam (user skipping everything). The Sonnet call is given this information and can recommend slowing down and surfacing something more challenging to test the signal. No hard rule — Claude reasons about it from context.

### 13.4 Queue overflow

Superseded by the §11.1 hard cap of 15 (Phase 10.5-rev Q1). The executor stops
acting on `add` recommendations once non-terminal stock reaches the cap and only
applies `reprioritise` recommendations; the 40-item figure from the original
draft no longer applies.

### 13.5 Single active interest

If the user has only one active interest, all queue slots go to that interest plus its prerequisite foundations. Multi-interest balancing logic does not apply.

---

## 14. LLM call summary

| Call | Model | Trigger | Purpose |
|---|---|---|---|
| Queue planning | Sonnet | Daily, per active user | Main planning: what to add to queue, how to reprioritise, prerequisite timing |
| Engagement assessment | Haiku | After every engagement | Update struggle score, determine immediate action if needed |

Both calls are logged in full to `llm_calls` with tokens, cost, and timestamp.

The Sonnet call is the more expensive call. At 10 active users with one Sonnet call per user per day, this is well within the expected cost envelope. Monitor via the admin cost dashboard.

---

## 15. FastAPI endpoint additions

The following additions to the Python FastAPI service are implied by this design:

| Endpoint | Trigger | Notes |
|---|---|---|
| `POST /plan-queue` | Daily background job (one call per active user) | Runs the Sonnet queue planning call. Input: full user context JSON. Output: recommendations. Executes recommendations (creates/updates queue_items). |
| `POST /assess-engagement` | After every graded attempt or completed paper | Runs the Haiku engagement assessment call. Input: engagement details + current node state. Output: updated struggle score, state transition, immediate action. |
| `POST /check-deferred` | Daily background job (runs after /plan-queue) | Deterministic. Checks all deferred items for re-queue eligibility. No LLM call. |

The earlier `/update-queue` endpoint has been deleted (Phase 10-rev §3f); `/plan-queue` and `/assess-engagement` cover its scope. The `/surface-daily` endpoint remains unchanged (deterministic; selects 3 items from pending queue).

---

## 16. Schema notes

No new tables are required. The following fields are used heavily by this design and must be populated reliably:

| Table | Field | Notes |
|---|---|---|
| `user_node_states` | `struggle_score` | Float, 0.0–1.0. Updated by every `/assess-engagement` call. |
| `user_node_states` | `state` | Must be kept current. State transitions applied by `/assess-engagement` and `/plan-queue`. |
| `user_node_states` | `last_engaged_at` | Used for consolidation scheduling and inactive-user detection. |
| `queue_items` | `state = 'deferred'` | New state value (added in survey-and-difficulty-design.md Section 8.5). Required for conditional re-queue logic. |
| `queue_items` | `priority_score` | Float. Updated by `/plan-queue` recommendations. Used by `/surface-daily` for item selection. |
| `queue_items` | `added_reason` | Short text. Populated from Sonnet recommendation `reason` field. Shown as "why this" on daily cards. |
| `user_interests` | `intent_context` | Required input to every Sonnet queue planning call. Must be populated at interest-creation time (see survey-and-difficulty-design.md). |
| `surfaced_picks` | `chosen_item_id` | Null if user rerolled without choosing. Used to detect reroll patterns. |

---

## 17. What this document does not cover

- **Weekly operator curation** — megagraph maintenance. Specified in `docs/graph-design.md`.
- **Cross-pollination** — surfacing new interests from adjacent megagraph nodes. Specified in `docs/graph-design.md`. The curriculum curator does not handle cross-pollination; it operates only on the user's existing interests.
- **Problem and paper generation** — what makes a good problem, the three dials, entry-point default. Specified in `docs/survey-and-difficulty-design.md`.
- **The survey and add-interest flow** — specified in `docs/survey-and-difficulty-design.md`.
- **The surface-daily job** — the deterministic selection of 3 items from the pending queue. Already specified in `ARCHITECTURE.md`. This document specifies what goes *into* the queue; surface-daily specifies how items are *selected from* it.
