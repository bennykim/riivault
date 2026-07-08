# riivault backend

Reddit signal-intelligence backend: async collector (asyncpraw) → raw buffer
(≤48h TTL) → derived/aggregate tables (permanent) → FastAPI (derived data only).
Direct SQL via **asyncpg** (no ORM). Schema is owned by `/schema.sql` — this code
never alters it.

## Stack
Python 3.12 · uv · asyncpg · asyncpraw · APScheduler · FastAPI/uvicorn ·
pydantic-settings · VADER (sentiment) · Anthropic (optional VoC).

## Setup
```bash
cd backend
uv sync                     # installs deps + a managed Python 3.12
```
Config is read from `../.env` (repo root) and `./.env` if present (real env vars
win). Keys: see `/.env.example`. DB defaults to
`postgresql://riivault:riivault@localhost:5433/riivault`.

## CLI (`riivault <command>`)
```bash
uv run riivault --help
uv run riivault collect-once     # one incremental Reddit collection pass
uv run riivault aggregate        # recompute mention/sentiment/VoC (idempotent)
uv run riivault purge            # 48h TTL + [deleted]/[removed] compliance purge
uv run riivault publish-issue    # upsert this week's weekly_issue
uv run riivault scheduler        # APScheduler: collect+aggregate/2h, purge/1h,
                                 #   publish Tue 09:00 UTC, snapshot/daily
uv run riivault seed-demo        # seed demo data (matches design/index.html)
uv run riivault api              # uvicorn on 0.0.0.0:8000
```

## API (prefix `/api/v1`, derived data only — never raw_*)
- `GET /healthz` → `{"status":"ok","db":true}`
- `GET /api/v1/issue/current` → composite main-page payload (404 if no issue)
- `GET /api/v1/entities?tracked=true`
- `GET /api/v1/entities/{id}/series?metric=mentions|sentiment&days=90`
- `GET /api/v1/pain-points?days=7&limit=10`
- `GET /api/v1/signals?limit=6`
- `POST /api/v1/subscribe` `{"email":"a@b.co"}` → 201 (200 `{already:true}` if dup)

CORS is open to `http://localhost:3000`.

## Tests (no DB required)
```bash
uv run pytest
```
Covers the token bucket (fake clock), entity matcher, VADER mapping, VoC JSON
parser, and the pure aggregation functions.

## Local end-to-end (requires Postgres on :5433 with `/schema.sql` applied)
```bash
uv run riivault seed-demo
uv run riivault api &
curl -s localhost:8000/healthz
curl -s localhost:8000/api/v1/issue/current | head
```

## Layout
```
riivault/
  config.py db.py entities.py cli.py
  nlp/        sentiment.py voc.py
  collector/  ratelimit.py reddit.py pipeline.py aggregate.py
              purge.py publish.py scheduler.py seed_demo.py
  api/        main.py deps.py routes/{issue,entities,painpoints,signals,subscribe}.py
tests/
```
