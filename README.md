# riivault

Turns public discussion into **derived time-series intelligence** — daily mention
counts, sentiment trends, and recurring pain points / feature requests for a single
niche (SaaS / indie-hacker communities). A non-commercial research project.

Raw content is never a permanent asset: it lives in a ≤48h processing buffer, then
is purged. Only de-identified aggregates are retained.

## Sources

- **Hacker News** — public Algolia API, no key required
- **Reddit** — official Data API (read-only, ≤100 QPM; access pending approval).
  Needed for the richest "why users switch / what hurts" feedback — HN skews
  toward technical early-adopter discussion, not product feedback.

## Layout

```
backend/    Python 3.12 — collectors + derived pipeline + FastAPI (uv)
web/        Next.js 15 — editorial frontend
schema.sql  Postgres + pgvector DDL (TimescaleDB optional, deferred to scale)
docs/       API contract (CONTRACT.md), deploy guide (DEPLOY.md)
```

## Quickstart

```bash
cp .env.example .env          # all keys optional — Hacker News needs none
docker compose up -d db       # Postgres :5433, schema auto-applied

cd backend
uv sync
uv run riivault seed-demo     # demo derived data + weekly issue
uv run riivault api           # FastAPI :8000

cd ../web && npm install && npm run dev   # Next.js :3000
```

Collect real data:

```bash
uv run riivault collect-hn    # Hacker News (no key)
uv run riivault collect-once  # Reddit (needs API keys)
uv run riivault aggregate     # recompute derived time-series (all sources)
```

## Compliance (Reddit Responsible Builder Policy)

1. Raw content is auto-purged after 48h — only derived aggregates persist.
2. Deleted / removed content is purged on detection and its references invalidated.
3. Read-only and non-commercial, within the free-tier rate limit.
4. Only derived metrics are exposed — no raw content is redistributed.

## Deploy

Durable, serverless collection (managed Postgres + GitHub Actions cron):
see [docs/DEPLOY.md](docs/DEPLOY.md).
