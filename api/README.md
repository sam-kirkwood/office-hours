# office-hours API

Python FastAPI service. Hosts all Claude API calls for the personalized science
tutor. The Next.js web app at [../web](../web) is stateless and proxies all AI
operations here.

See [../ARCHITECTURE.md](../ARCHITECTURE.md) for the system overview and
[../dev-docs/phase-3-plan.md](../dev-docs/phase-3-plan.md) for current build
state.

## Routes

| Method | Path | Status |
|---|---|---|
| GET | `/healthz` | live |
| POST | `/generate-problem` | step 4 |
| POST | `/parse-solution` | phase 4 |
| POST | `/grade-solution` | phase 5 |
| POST | `/update-plan` | phase 5 |
| POST | `/generate-plan` | phase 5+ |

## Run locally

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
cd api
cp .env.example .env          # fill in the values
uv sync                       # installs runtime + dev deps into .venv
uv run uvicorn main:app --reload
```

The service starts on `http://localhost:8000`. Confirm with:

```bash
curl http://localhost:8000/healthz
# {"status":"ok"}
```

## Tests

```bash
uv run pytest
```

## Environment variables

See [.env.example](./.env.example). All variables are required except `PORT`
and `LOG_LEVEL`.

- `ANTHROPIC_API_KEY` — Claude API key.
- `SUPABASE_URL`, `SUPABASE_SECRET_KEY` — same Supabase project as the web app.
  Uses the secret (service-role) key so the service can bypass RLS and write to
  `llm_calls`, `problems`, `problem_hints`.
- `INTERNAL_API_TOKEN` — shared bearer token. The Next.js app sends
  `Authorization: Bearer $INTERNAL_API_TOKEN` on every call; this service 401s
  otherwise. Must match `web/.env.local`.

## Models

Pinned in [config.py](./config.py):

- `SONNET_MODEL = "claude-sonnet-4-6"` — problem generation, grading, vision.
- `HAIKU_MODEL = "claude-haiku-4-5-20251001"` — cheap classification (e.g.
  context-hook matching).

Changing models is a code change with a corresponding prompt re-test, not a
config tweak.

## Logging Claude calls

Every Claude call must go through `anthropic_client.log_llm_call(...)` so it
lands in the `llm_calls` table for cost observability. No bypassing — the cost
dashboard in Phase 6 reads exclusively from that table.

## Deployment

Deferred to Phase 6. Target hosting is Railway or Fly.io (single container, no
autoscaling needed at this scale). When we get there, deploy notes will live
in this section.
