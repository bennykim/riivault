# riivault

Turns public discussion into **derived time-series intelligence** — daily mention
counts, sentiment trends, and recurring pain points / feature requests for a single
niche (SaaS / indie-hacker communities). A non-commercial research project.

Raw content is never a permanent asset: it lives in a ≤48h processing buffer, then
is purged. Only de-identified aggregates are retained.

## Sources

- **Hacker News** — public Algolia API, no key required
- **GitHub Issues** — real product feedback (bugs / feature requests) on mapped
  repos; feeds the VoC ledger. Token optional (`GH_API_TOKEN`, 60/hr without)
- **GitHub stars/releases + npm/PyPI downloads** — adoption time-series
  ("what people use" vs "what people say"), no key required
- **Product Hunt** — new launches in niche topics; ecosystem mentions of
  tracked entities in launch copy (needs `PRODUCTHUNT_TOKEN`)
- **Stack Exchange** — daily new-question counts per mapped tag
  (technical-interest proxy), no key required
**Reddit is not a source.** A Data API access request was declined under the
[Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy),
so no Reddit data is collected, stored, or displayed. The collector code remains
in the tree but is inert without credentials.

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

cd ../web && pnpm install && pnpm dev     # Next.js :3000
```

Collect real data:

```bash
uv run riivault collect-hn        # Hacker News (no key)
uv run riivault collect-gh        # GitHub Issues on mapped repos
uv run riivault collect-ph        # Product Hunt launches (needs token)
uv run riivault collect-adoption  # stars / releases / downloads / SE questions
uv run riivault collect-once      # Reddit (needs API keys)
uv run riivault aggregate         # recompute derived time-series (all sources)
```

## Compliance (Reddit Responsible Builder Policy)

1. Raw content is auto-purged after 48h — only derived aggregates persist.
2. Deleted / removed content is purged on detection and its references invalidated.
3. Read-only and non-commercial, within the free-tier rate limit.
4. Only derived metrics are exposed — no raw content is redistributed.

## Deploy

Durable, serverless collection (managed Postgres + GitHub Actions cron):
see [docs/DEPLOY.md](docs/DEPLOY.md).
