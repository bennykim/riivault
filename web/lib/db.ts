// Direct Neon queries for the current-issue page + subscribe endpoint.
// 1:1 port of the backend route SQL (backend/riivault/api/routes/{issue,
// entities,painpoints,signals,subscribe}.py) so the site can run Vercel-only,
// without the FastAPI deployment. Derived tables only — raw_* is never read.

import { neon, type NeonQueryFunction } from "@neondatabase/serverless";
import type {
  EmergingSignal,
  IssueData,
  PainPoint,
  SentimentFocus,
  TrackedEntity,
} from "./types";

// Default neon() mode: object rows, no full-results envelope.
type Sql = NeonQueryFunction<false, false>;

function getSql(): Sql {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL is not set");
  return neon(url);
}

/** Python round(value, digits) equivalent (half-up is close enough here). */
function round(value: number, digits: number): number {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

/** entities.py fetch_tracked — 7d-vs-prior-7d change and a 7-day daily spark,
 *  mentions combined across all sources (subreddit='' overall rows). BIGINT
 *  aggregates arrive as strings from the driver, hence the Number() casts. */
async function fetchTracked(sql: Sql): Promise<TrackedEntity[]> {
  const rows = await sql`
    WITH daily AS (
        SELECT entity_id, day, SUM(mention_count) AS cnt
          FROM mention_daily
         WHERE subreddit = '' AND day > CURRENT_DATE - 14
         GROUP BY entity_id, day
    )
    SELECT e.entity_id, e.canonical_name AS name,
           e.metadata->>'context' AS context,
           COALESCE(SUM(d.cnt)
                    FILTER (WHERE d.day > CURRENT_DATE - 7), 0) AS last7,
           COALESCE(SUM(d.cnt)
                    FILTER (WHERE d.day <= CURRENT_DATE - 7
                              AND d.day > CURRENT_DATE - 14), 0) AS prev7,
           COALESCE(array_agg(d.cnt ORDER BY d.day)
                    FILTER (WHERE d.day > CURRENT_DATE - 7), '{}'::bigint[]) AS spark
      FROM entity e
      LEFT JOIN daily d ON d.entity_id = e.entity_id
     WHERE (e.metadata->>'tracked')::boolean IS TRUE
     GROUP BY e.entity_id
     ORDER BY e.entity_id
  `;
  return rows.map((r) => {
    const last7 = Number(r.last7);
    const prev7 = Number(r.prev7);
    return {
      entity_id: Number(r.entity_id),
      name: r.name as string,
      context: r.context as string,
      change_pct: prev7 ? round(((last7 - prev7) / prev7) * 100, 1) : null,
      spark: ((r.spark as unknown[]) ?? []).map(Number),
    } as unknown as TrackedEntity;
  });
}

/** painpoints.py fetch_pain_points — rising VoC entries by momentum. */
async function fetchPainPoints(
  sql: Sql,
  days = 7,
  limit = 10,
): Promise<PainPoint[]> {
  const rows = await sql`
    SELECT fr_id, kind, normalized_text AS text, occurrences, momentum
      FROM feature_request
     WHERE last_seen >= CURRENT_DATE - ${days}::int
     ORDER BY momentum DESC NULLS LAST, occurrences DESC
     LIMIT ${limit}
  `;
  return rows.map((r, i) => ({
    fr_id: Number(r.fr_id),
    rank: i + 1,
    text: r.text as string,
    kind: r.kind as PainPoint["kind"],
    occurrences: Number(r.occurrences),
    momentum_pct: round(Number(r.momentum ?? 0) * 100, 1),
  }));
}

/** signals.py fetch_signals — display strings live in the outcome JSONB. */
async function fetchSignals(
  sql: Sql,
  limit = 6,
  order: "recent" | "strength" = "recent",
): Promise<EmergingSignal[]> {
  const rows =
    order === "strength"
      ? await sql`
          SELECT signal_id, signal_type, strength, detected_at, outcome
            FROM emerging_signal
           ORDER BY strength DESC, detected_at DESC
           LIMIT ${limit}
        `
      : await sql`
          SELECT signal_id, signal_type, strength, detected_at, outcome
            FROM emerging_signal
           ORDER BY detected_at DESC, signal_id DESC
           LIMIT ${limit}
        `;
  return rows.map((r) => {
    const outcome = (r.outcome ?? {}) as Record<string, unknown>;
    return {
      signal_id: Number(r.signal_id),
      signal_type: r.signal_type,
      entity: outcome.entity ?? null,
      description: outcome.description ?? null,
      strength: Number(r.strength),
      detected_label: outcome.detected_label ?? null,
    } as unknown as EmergingSignal;
  });
}

/** issue.py _sentiment_focus — sentiment pooled across all sources per day,
 *  weighted by each source's sample_size. */
async function sentimentFocus(
  sql: Sql,
  focusRef: { entity_id?: number | null; label?: string | null } | null,
): Promise<SentimentFocus | null> {
  if (!focusRef) return null;
  const entityId = focusRef.entity_id;
  const label = focusRef.label ?? null;
  if (entityId == null) {
    return {
      label,
      current: null,
      trend: "flat",
      series: [],
    } as unknown as SentimentFocus;
  }
  const rows = await sql`
    SELECT day::text AS day,
           SUM(sentiment_mean * sample_size) / NULLIF(SUM(sample_size), 0)
               AS sentiment_mean
      FROM sentiment_daily
     WHERE entity_id = ${entityId}
     GROUP BY day
     ORDER BY day
  `;
  const series = rows
    .filter((r) => r.sentiment_mean !== null)
    .map((r) => ({
      period: r.day as string,
      value: round(Number(r.sentiment_mean), 3),
    }));
  const current = series.length ? series[series.length - 1].value : null;
  let trend = "flat";
  if (series.length >= 2) {
    if (series[series.length - 1].value < series[0].value) trend = "falling";
    else if (series[series.length - 1].value > series[0].value) trend = "rising";
  }
  return { label, current, trend, series } as unknown as SentimentFocus;
}

/** issue.py issue_current — latest weekly_issue row (payload render snapshot)
 *  merged with live derived-table queries. Returns null when no issue has been
 *  published (the page then falls back to bundled sample data). */
export async function getCurrentIssue(): Promise<IssueData | null> {
  const sql = getSql();
  const issues = await sql`
    SELECT issue_no, week_start::text AS week_start, week_end::text AS week_end,
           headline, dek, lead_entity_id, payload, published_at
      FROM weekly_issue
     ORDER BY week_start DESC
     LIMIT 1
  `;
  if (!issues.length) return null;
  const issue = issues[0];
  const payload = (issue.payload ?? {}) as Record<string, any>;

  // The backend runs these on one connection; Neon-over-HTTP is stateless, so
  // the four independent reads can go out in parallel.
  const [tracked, painPoints, emerging, focus] = await Promise.all([
    fetchTracked(sql),
    fetchPainPoints(sql, 7, 10),
    fetchSignals(sql, 6, "strength"),
    sentimentFocus(sql, payload.sentiment_focus ?? null),
  ]);

  const lead = {
    ...(payload.lead ?? {}),
    headline: issue.headline,
    dek: issue.dek,
  };

  let generatedAt = payload.generated_at ?? null;
  if (generatedAt == null && issue.published_at != null) {
    const publishedAt = issue.published_at as Date | string;
    generatedAt =
      publishedAt instanceof Date ? publishedAt.toISOString() : publishedAt;
  }

  return {
    issue_no: Number(issue.issue_no),
    week_start: issue.week_start,
    week_end: issue.week_end,
    generated_at: generatedAt,
    niche: payload.niche ?? null,
    sources: payload.sources ?? [],
    lead,
    tracked,
    pain_points: painPoints,
    sentiment_focus: focus,
    migration: payload.migration ?? null,
    emerging,
  } as IssueData;
}

// ---------------------------------------------------------------------------
// Entity detail page (/e/[id]) — mention/sentiment/adoption series + VoC list.
// Mirrors backend routes/entities.py get_entity_series (all sources combined).
// ---------------------------------------------------------------------------

export interface EntityDetail {
  entity_id: number;
  type: string;
  name: string;
  context: string | null;
  /** repo / npm / pypi / se_tag mappings, when present. */
  mappings: Record<string, string>;
  tracked: boolean;
}

export interface AdoptionSeries {
  source: string; // e.g. "github" | "npm" | "pypi" | "stackexchange"
  metric: string; // e.g. "stars_total" | "downloads" | "questions"
  series: { period: string; value: number }[];
}

export interface EntityVocItem {
  fr_id: number;
  kind: PainPoint["kind"];
  text: string;
  occurrences: number;
  momentum_pct: number;
  first_seen: string;
  last_seen: string;
}

const MAPPING_KEYS = ["repo", "npm", "pypi", "se_tag"] as const;

export async function getEntityDetail(
  entityId: number,
): Promise<EntityDetail | null> {
  const sql = getSql();
  const rows = await sql`
    SELECT entity_id, type, canonical_name AS name,
           metadata->>'context' AS context, metadata
      FROM entity WHERE entity_id = ${entityId}
  `;
  if (!rows.length) return null;
  const r = rows[0];
  const metadata = (r.metadata ?? {}) as Record<string, unknown>;
  const mappings: Record<string, string> = {};
  for (const key of MAPPING_KEYS) {
    if (typeof metadata[key] === "string") mappings[key] = metadata[key] as string;
  }
  return {
    entity_id: Number(r.entity_id),
    type: r.type as string,
    name: r.name as string,
    context: (r.context as string) ?? null,
    mappings,
    tracked: metadata.tracked === true,
  };
}

/** Daily mentions summed across all sources (subreddit='' overall rows). */
export async function getMentionSeries(
  entityId: number,
  days: number,
): Promise<{ period: string; value: number }[]> {
  const sql = getSql();
  const rows = await sql`
    SELECT day::text AS day, SUM(mention_count) AS value
      FROM mention_daily
     WHERE entity_id = ${entityId} AND subreddit = ''
       AND day > CURRENT_DATE - ${days}::int
     GROUP BY day ORDER BY day
  `;
  return rows.map((r) => ({ period: r.day as string, value: Number(r.value) }));
}

/** Daily sentiment pooled across sources, sample_size-weighted. */
export async function getSentimentSeries(
  entityId: number,
  days: number,
): Promise<{ period: string; value: number }[]> {
  const sql = getSql();
  const rows = await sql`
    SELECT day::text AS day,
           SUM(sentiment_mean * sample_size) / NULLIF(SUM(sample_size), 0) AS value
      FROM sentiment_daily
     WHERE entity_id = ${entityId} AND day > CURRENT_DATE - ${days}::int
     GROUP BY day ORDER BY day
  `;
  return rows
    .filter((r) => r.value !== null)
    .map((r) => ({ period: r.day as string, value: round(Number(r.value), 3) }));
}

/** Adoption time-series grouped into one series per (source, metric). */
export async function getAdoptionSeries(
  entityId: number,
  days: number,
): Promise<AdoptionSeries[]> {
  const sql = getSql();
  const rows = await sql`
    SELECT s.name AS source, a.metric, a.day::text AS day, a.value
      FROM adoption_daily a JOIN source s USING (source_id)
     WHERE a.entity_id = ${entityId} AND a.day > CURRENT_DATE - ${days}::int
     ORDER BY s.name, a.metric, a.day
  `;
  const grouped = new Map<string, AdoptionSeries>();
  for (const r of rows) {
    const key = `${r.source}:${r.metric}`;
    let entry = grouped.get(key);
    if (!entry) {
      entry = { source: r.source as string, metric: r.metric as string, series: [] };
      grouped.set(key, entry);
    }
    entry.series.push({ period: r.day as string, value: Number(r.value) });
  }
  return [...grouped.values()];
}

/** The entity's VoC ledger entries, most recently seen first. */
export async function getEntityVoc(
  entityId: number,
  limit = 20,
): Promise<EntityVocItem[]> {
  const sql = getSql();
  const rows = await sql`
    SELECT fr_id, kind, normalized_text AS text, occurrences, momentum,
           first_seen::text AS first_seen, last_seen::text AS last_seen
      FROM feature_request
     WHERE entity_id = ${entityId}
     ORDER BY last_seen DESC, occurrences DESC, fr_id DESC
     LIMIT ${limit}
  `;
  return rows.map((r) => ({
    fr_id: Number(r.fr_id),
    kind: r.kind as PainPoint["kind"],
    text: r.text as string,
    occurrences: Number(r.occurrences),
    momentum_pct: round(Number(r.momentum ?? 0) * 100, 1),
    first_seen: r.first_seen as string,
    last_seen: r.last_seen as string,
  }));
}

/** subscribe.py — insert-or-ignore; `created` is false when the email already
 *  existed (the API layer maps that to 201 vs 200). */
export async function subscribeEmail(
  email: string,
): Promise<{ created: boolean }> {
  const sql = getSql();
  const rows = await sql`
    INSERT INTO newsletter_subscriber (email) VALUES (${email})
    ON CONFLICT (email) DO NOTHING
    RETURNING email
  `;
  return { created: rows.length > 0 };
}
