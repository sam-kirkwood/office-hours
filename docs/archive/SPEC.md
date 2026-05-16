# SPEC.md — Personalized Science Tutor

## What this is

A private web app that acts as a personalized science tutor for a small group
of friends (≤30 users, realistically ~10 active). Each user gets a tailored
learning plan, a daily problem with rich historical/scientific context, hints
that scaffold without solving, handwritten solution submission with
AI-assisted parsing, automated feedback, and a plan that adapts to where the
user actually struggles.

The defining feature is **context**: problems are tied to real scientific
history (papers, scandals, key experiments, biographies) so the experience
feels like education rather than a textbook problem set.

Initial topic focus: undergraduate math and physics. Designed to extend to
other STEM topics later.

## Out of scope (initial release)

- Public sign-ups, marketing, payments, anything commercial
- Multi-tenant or team features
- Mobile native apps (mobile *web* is in scope)
- Real-time collaboration
- Anything below "small group of friends" trust level

## Users

Self-selected friends of the operator. Trusted. Authenticated via email magic
link. No passwords. No sensitive data is expected to be stored — users are
explicitly told not to put personal/financial info in solutions.

## Core user journeys

### 1. Onboarding

- User receives an invite link.
- Signs in via email magic link.
- Completes a survey:
  - Background (degree, years out of study, current field)
  - Self-rated skill across topic areas (e.g., classical mechanics, linear
    algebra, quantum, statistics, E&M, etc.) on a 1–5 scale
  - Topics they want to learn or refresh
  - Optional: free-text "anything else you want to study" (this can introduce
    topics outside the canonical curriculum graph; see ARCHITECTURE.md for
    how those are handled)
  - Preferred problem difficulty curve (gentle / standard / aggressive)
  - Approximate time per day they want to spend

### 2. Learning plan review

- The system generates a proposed learning plan: an ordered path through a
  subset of the canonical curriculum graph.
- User sees a visual "skill tree" — nodes are topics, edges are
  prerequisites, current path is highlighted.
- User can:
  - Approve as-is
  - Request adjustments in free text ("more E&M earlier", "skip thermo")
  - Regenerate
- Once approved, the plan becomes active.

### 3. Daily problem

- One problem per day per user.
- Problem page contains:
  - **Context section**: 2–4 paragraphs tying the topic to a real scientific
    episode, paper, person, or experiment. Sourced from a curated
    `context_hooks` table when possible; generated and reviewed otherwise.
  - **Problem statement**: rendered with LaTeX.
  - **Hint panel** (collapsed by default): 3–5 progressive hint levels,
    pre-generated at problem creation time and stored. Each hint reveals
    strictly more than the last but never solves the problem.
  - **Submit solution** button.
- Each hint click is logged.

### 4. Solution submission

- User writes the solution by hand on paper.
- Takes photo(s) with their phone.
- Uploads via a mobile-friendly upload page (signed URL, direct to object
  storage).
- The system parses the image(s) to Markdown + LaTeX using Claude vision.
- User sees the parsed solution and can edit it inline before submitting.
  - This is non-negotiable UX: vision parsing is imperfect, and user review
    catches errors *and* reinforces learning by forcing the user to read
    their own work back.
- User confirms and submits.

### 5. Grading and feedback

- The system grades the solution against the stored canonical solution and a
  rubric.
- Feedback is shown:
  - Verdict (correct / partially correct / incorrect / unclear)
  - Specific notes on what worked and what didn't
  - Pointers to the underlying concept if the user missed it
- User can flag the grade as wrong/disputed. Flagged attempts are queued for
  operator review. (No automated re-grading on dispute in v1.)
- The attempt — including hints used, time taken, parsed solution, and grade
  — is recorded.

### 6. Plan adaptation

- After each attempt, plan health is recomputed:
  - Topics where the user struggles (wrong answers, many hints, slow time)
    get reinforced — more problems, possibly easier first.
  - Topics where the user is strong are accelerated.
- Plan updates are visible to the user. Big changes are surfaced
  ("I've added two more problems on Lagrangian mechanics — you've used hints
  on the last three").

## Hints: design principles

- Hints are **authored at problem-generation time** and stored. Never
  generated on the fly per request (causes drift and accidental answer
  leakage).
- Hint levels are structured:
  - L1: Identify the relevant concept or principle
  - L2: Identify the governing equation or framework
  - L3: Suggest a setup or starting move
  - L4: Identify a specific first step
  - L5: (optional) Identify a subtle pitfall
- A hint never gives the final answer or the full solution path.
- The grader has access to "hints used" as a signal but does not penalize
  for hint use in v1 — the goal is learning, not scoring.

## Context hooks: design principles

- A curated table of historical/scientific episodes (papers, scandals, key
  experiments, biographies, technologies).
- Each hook has: title, summary, related topics, suggested difficulty band,
  source links.
- The problem generator tries to match a generated problem to a relevant
  hook. If none fits, it generates a lighter context paragraph rather than
  forcing a stretch.
- Operator can add hooks at any time. Seed with 20–30 covering the most
  common undergrad topics (Millikan, Michelson–Morley, Schön, Bardeen et
  al., Noether, Curie, etc.).

## Future features (explicitly deferred)

- Paper-reading days: alternative to a problem, user reads a curated paper
  and answers comprehension questions.
- Annotated solution notebook: every solved problem accumulates into a
  per-user LaTeX notebook, annotated with which hints were used and where.
- Dynamic in-problem hints: user highlights a term, gets a definition or an
  optional extra problem on that term.
- BYO Claude API key: users on Claude Pro/Max plug in their own key to
  offset operator cost.
- Topic deep-dives: user requests an explainer on a topic outside the daily
  problem.
- Spaced repetition for previously solved problems.

## Non-functional requirements

- **Cost monitoring**: every Claude API call is logged with input/output
  tokens and computed cost. Admin page shows daily/weekly/monthly spend.
- **Mobile-first** for the upload and problem-view flows. Desktop fine
  everywhere else.
- **Failure tolerance**: vision parsing or grading failures must not lose
  the user's submission. Always retain the original image.
- **Trust model**: small, known user base. No need to harden against
  abuse beyond standard auth and basic rate limiting.

## Definition of done for v1

- A new user can sign up, complete the survey, review and approve a plan.
- The user gets a daily problem with context and hints.
- The user can photograph a solution, see it parsed, correct it, and submit.
- The user receives automated grading and feedback.
- The plan adapts based on attempt history.
- The operator can see total spend in a dashboard.
