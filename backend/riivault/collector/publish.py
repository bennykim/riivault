"""Weekly issue publication.

Selects the week's lead entity — mentions summed across all sources, ranked
by baseline z-score with a minimum-volume floor (see analysis.normalize; raw
growth alone lets a 1->10 micro-base "win" with +900%) — generates a
headline/dek (LLM if a key is present, otherwise a template), and upserts a
``weekly_issue`` row whose ``payload`` holds the derived render snapshot
(12-week lead series + migration) that the API merges into GET /issue/current.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta

from ..analysis.normalize import lead_scores
from ..config import Settings, get_settings
from ..db import pool_context

logger = logging.getLogger("riivault.publish")

# Growth math needs a source to have been collecting for the full
# last7-vs-prev7 comparison window; a source onboarded mid-window shows a
# fake surge (its history simply starts where collection started).
LEAD_MIN_SOURCE_AGE_DAYS = 14

# Display names for the sources an issue actually drew on. The payload must
# name the real providers: attributing a figure to a platform we do not
# collect from would misrepresent the data to readers.
SOURCE_LABELS = {
    "reddit": "Reddit",
    "hackernews": "Hacker News",
    "github": "GitHub",
    "producthunt": "Product Hunt",
    "stackexchange": "Stack Exchange",
    "google_trends": "Google Trends",
    "npm": "npm",
    "pypi": "PyPI",
}


def _source_label(name: str) -> str:
    return SOURCE_LABELS.get(name, name)


def week_bounds(today: date) -> tuple[date, date]:
    start = today - timedelta(days=today.weekday())  # Monday
    return start, start + timedelta(days=6)


def _signed(value: float) -> str:
    return f"+{value}" if value >= 0 else f"{value}"


async def publish_issue(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    today = datetime.now(UTC).date()
    week_start, week_end = week_bounds(today)

    async with pool_context(settings) as pool:
        async with pool.acquire() as conn:
            lead_sources = await _lead_source_ids(conn)
            lead = await _pick_lead(conn, today, lead_sources)
            if lead is None:
                logger.warning("publish_issue: no mention data for a lead; skipping")
                return {"published": False, "reason": "no_data"}

            lead_entity_id, growth = lead
            lead_name = await conn.fetchval(
                "SELECT canonical_name FROM entity WHERE entity_id = $1", lead_entity_id
            )
            series = await _weekly_series(conn, lead_entity_id, lead_sources, weeks=12)
            momentum_pct = round(growth * 100, 1)
            headline, dek = await _headline(settings, lead_name, momentum_pct)
            threads = sum(point["value"] for point in series)

            payload = {
                "niche": "SaaS",
                "sources": await _active_source_labels(conn),
                "generated_at": datetime.now(UTC).isoformat(),
                "lead": {
                    "eyebrow": f"Lead signal · momentum {_signed(momentum_pct)}%",
                    "momentum_pct": momentum_pct,
                    "threads": threads,
                    "comments": None,
                    "window_weeks": 12,
                    "sources": await _labels_for(conn, lead_sources),
                    "chart_title": f'Mention Index — "{lead_name}"',
                    "delta_label": f"{_signed(momentum_pct)}% w/w",
                    "delta_value": series[-1]["value"] if series else 0,
                    "series": series,
                },
                "sentiment_focus": await _sentiment_focus_ref(conn),
                "migration": None,
            }

            issue_no = await conn.fetchval(
                """
                INSERT INTO weekly_issue
                    (week_start, week_end, headline, dek, lead_entity_id, payload, published_at)
                VALUES ($1, $2, $3, $4, $5, $6, now())
                ON CONFLICT (week_start) DO UPDATE
                    SET week_end = EXCLUDED.week_end,
                        headline = EXCLUDED.headline,
                        dek = EXCLUDED.dek,
                        lead_entity_id = EXCLUDED.lead_entity_id,
                        payload = EXCLUDED.payload,
                        published_at = now()
                RETURNING issue_no
                """,
                week_start, week_end, headline, dek, lead_entity_id, payload,
            )

    result = {"published": True, "issue_no": issue_no, "week_start": str(week_start)}
    logger.info("publish_issue: %s", result)
    return result


async def _active_source_labels(conn, days: int = 7) -> list[str]:
    """Sources that actually contributed mentions in the issue window."""
    rows = await conn.fetch(
        """
        SELECT DISTINCT s.name
          FROM mention_daily md JOIN source s USING (source_id)
         WHERE md.day > CURRENT_DATE - $1::int
         ORDER BY s.name
        """,
        days,
    )
    return [_source_label(r["name"]) for r in rows]


async def _labels_for(conn, source_ids: list[int] | None) -> list[str]:
    """Display names for the lead's source pool (all sources when unfiltered)."""
    if source_ids is None:
        rows = await conn.fetch("SELECT name FROM source ORDER BY name")
    else:
        rows = await conn.fetch(
            "SELECT name FROM source WHERE source_id = ANY($1::int[]) ORDER BY name",
            source_ids,
        )
    return [_source_label(r["name"]) for r in rows]


async def _lead_source_ids(conn) -> list[int] | None:
    """Sources whose history covers the lead's w/w comparison window.

    When no source has been collecting for ``LEAD_MIN_SOURCE_AGE_DAYS`` yet,
    the single longest-collecting source is used (the least-biased window
    available). ``None`` — no filtering — only when collection has never run
    (e.g. seeded demo environments).
    """
    rows = await conn.fetch(
        "SELECT source_id, min(started_at) AS first_run"
        "  FROM collection_run GROUP BY source_id"
    )
    if not rows:
        return None
    cutoff = datetime.now(UTC) - timedelta(days=LEAD_MIN_SOURCE_AGE_DAYS)
    eligible = [r["source_id"] for r in rows if r["first_run"] <= cutoff]
    if eligible:
        return eligible
    oldest = min(rows, key=lambda r: r["first_run"])
    return [oldest["source_id"]]


async def _pick_lead(
    conn, today: date, source_ids: list[int] | None
) -> tuple[int, float] | None:
    # Mentions are combined across the age-eligible sources (subreddit=''
    # overall rows). Ranking is delegated to analysis.normalize.lead_scores:
    # z-score vs the entity's own trailing baseline, with a minimum-volume
    # floor so micro-bases cannot lead.
    rows = await conn.fetch(
        """
        SELECT entity_id, day, SUM(mention_count) AS cnt
          FROM mention_daily
         WHERE subreddit = '' AND day > CURRENT_DATE - 91
           AND ($1::int[] IS NULL OR source_id = ANY($1::int[]))
         GROUP BY entity_id, day
        """,
        source_ids,
    )
    daily_by_entity: dict[int, dict[date, int]] = {}
    for row in rows:
        daily_by_entity.setdefault(row["entity_id"], {})[row["day"]] = int(row["cnt"])
    scores = lead_scores(daily_by_entity, today)
    if not scores:
        return None
    top = scores[0]
    # growth is None on a zero prior week; fall back to the historical
    # "treat the raw count as the ratio" semantics for the display value.
    growth = top["growth"] if top["growth"] is not None else float(top["last7"])
    return top["entity_id"], float(growth)


async def _weekly_series(
    conn, entity_id, source_ids: list[int] | None, weeks: int = 12
) -> list[dict]:
    # Same source pool as the lead pick, so the chart matches the claim.
    rows = await conn.fetch(
        """
        SELECT (date_trunc('week', day))::date AS period, SUM(mention_count) AS value
          FROM mention_daily
         WHERE entity_id = $1 AND subreddit = ''
           AND day > CURRENT_DATE - ($2::int * 7)
           AND ($3::int[] IS NULL OR source_id = ANY($3::int[]))
         GROUP BY 1 ORDER BY 1
        """,
        entity_id, weeks, source_ids,
    )
    return [{"period": r["period"].isoformat(), "value": int(r["value"])} for r in rows]


async def _sentiment_focus_ref(conn) -> dict | None:
    # Lowest pooled sentiment on the latest day, weighted by each source's
    # sample_size (same pooling as the API's _sentiment_focus).
    row = await conn.fetchrow(
        """
        WITH pooled AS (
            SELECT entity_id, day,
                   SUM(sentiment_mean * sample_size)
                       / NULLIF(SUM(sample_size), 0) AS mean
              FROM sentiment_daily
             GROUP BY entity_id, day
        )
        SELECT p.entity_id, e.canonical_name
          FROM pooled p
          JOIN entity e ON e.entity_id = p.entity_id
         WHERE p.day = (SELECT max(day) FROM sentiment_daily)
           AND p.mean IS NOT NULL
         ORDER BY p.mean ASC
         LIMIT 1
        """
    )
    if not row:
        return None
    return {"entity_id": row["entity_id"], "label": f'"{row["canonical_name"]}"'}


async def _headline(settings: Settings, lead_name: str, momentum_pct: float) -> tuple[str, str | None]:
    if settings.voc_enabled:
        try:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            prompt = (
                "Write a concise newsletter headline and one-sentence dek for a weekly "
                "trend report on public founder/indie-hacker communities. "
                "Do not name a specific platform as the data source. "
                "Use ONLY these derived metrics (no raw content): "
                f"entity={lead_name}, weekly mention momentum={momentum_pct}%. "
                'Return JSON only: {"headline": "...", "dek": "..."}'
            )
            message = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = "".join(
                b.text for b in message.content if getattr(b, "type", None) == "text"
            )
            data = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
            return data["headline"], data.get("dek")
        except Exception as exc:  # noqa: BLE001
            logger.warning("headline LLM failed, using template: %s", exc)

    direction = "up" if momentum_pct >= 0 else "down"
    headline = f"{lead_name} mentions {direction} {abs(momentum_pct)}% this week"
    dek = (
        f"{lead_name} is the week's fastest-moving signal across tracked founder "
        f"communities ({_signed(momentum_pct)}% w/w)."
    )
    return headline, dek
