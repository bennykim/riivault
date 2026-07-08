# Deploy — durable collection (Neon + GitHub Actions)

Goal: accumulate the derived time-series every day with **no always-on server**
and **near-zero cost**. The DB is managed Postgres (Neon free tier); the
collector runs on a GitHub Actions cron. TimescaleDB is not required at this
scale — the schema runs on plain Postgres + pgvector (verified).

## 1. Database — Neon (free tier)

1. Create a project at [neon.tech](https://neon.tech) (region close to you).
2. In the SQL editor, enable pgvector and load the schema:
   - `CREATE EXTENSION IF NOT EXISTS vector;` (Neon supports it)
   - Paste the contents of [`schema.sql`](../schema.sql) and run it.
   - Expect 16 tables, `vector` extension, no timescaledb.
3. Copy the **pooled** connection string (`...-pooler...`, `sslmode=require`).

> Alternatives if not Neon: any managed Postgres with pgvector works
> (Supabase, Railway, Fly Postgres). Only the connection string changes.

## 2. Collector — GitHub Actions

The workflow [`.github/workflows/collect.yml`](../.github/workflows/collect.yml)
runs every 2h: `collect-once` (Reddit) → `collect-hn` → `aggregate` → `purge`.

Set repository secrets (**Settings → Secrets and variables → Actions**):

| Secret | Required | Notes |
|--------|----------|-------|
| `DATABASE_URL` | yes | Neon pooled connection string |
| `REDDIT_CLIENT_ID` | no* | Reddit step no-ops until this is set (before API approval) |
| `REDDIT_CLIENT_SECRET` | no* | |
| `REDDIT_USER_AGENT` | no* | `web:riivault:v0.1 (by /u/yourname)` |
| `ANTHROPIC_API_KEY` | no | Enables LLM VoC extraction; else VADER sentiment only |

\* Add the Reddit secrets once the Data API request is approved. Until then HN
collects on its own and the Reddit step logs "skipped".

## 3. First run + verify

- Push `main`, then **Actions → collect → Run workflow** (manual trigger).
- Confirm the run is green and the steps log ingested/aggregated counts.
- Check data landed: `SELECT s.name, count(*) FROM mention_daily m JOIN source s USING(source_id) GROUP BY 1;`

After this, collection is durable: every 2h the moat grows, no server to babysit.

## Not covered here (separate step)

- **Public site (API + web)**: the FastAPI service and Next.js frontend need
  their own hosting (e.g. web → Vercel, API → Fly.io/Railway) and the API must
  point at the same `DATABASE_URL`. Collection does not depend on this.
- **Weekly issue**: `publish-issue` is currently manual/weekly; wire it as a
  separate scheduled workflow once the editorial format from live data is set.
  A published `weekly_issue` row is required for `/issue/current` (else it 404s
  and the frontend falls back to sample data).
- **Cross-source data**: the API already combines all sources (Reddit + HN);
  surfacing it on the site only needs the API hosted and a weekly issue published.
