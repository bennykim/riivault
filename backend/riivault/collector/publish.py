"""Weekly issue publication.

Selects the week's lead entity (max 7d-over-prior-7d mention growth), generates
a headline/dek (LLM if a key is present, otherwise a template), and upserts a
``weekly_issue`` row whose ``payload`` holds the derived render snapshot
(12-week lead series + migration) that the API merges into GET /issue/current.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta

from ..config import Settings, get_settings
from ..db import pool_context

logger = logging.getLogger("riivault.publish")


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
            source_id = await conn.fetchval(
                "SELECT source_id FROM source WHERE name = 'reddit'"
            )
            lead = await _pick_lead(conn, source_id)
            if lead is None:
                logger.warning("publish_issue: no mention data for a lead; skipping")
                return {"published": False, "reason": "no_data"}

            lead_entity_id, growth = lead
            lead_name = await conn.fetchval(
                "SELECT canonical_name FROM entity WHERE entity_id = $1", lead_entity_id
            )
            series = await _weekly_series(conn, source_id, lead_entity_id, weeks=12)
            momentum_pct = round(growth * 100, 1)
            headline, dek = await _headline(settings, lead_name, momentum_pct)
            threads = sum(point["value"] for point in series)

            payload = {
                "niche": "SaaS",
                "communities": len(settings.subreddits),
                "generated_at": datetime.now(UTC).isoformat(),
                "lead": {
                    "eyebrow": f"Lead signal · momentum {_signed(momentum_pct)}%",
                    "momentum_pct": momentum_pct,
                    "threads": threads,
                    "comments": None,
                    "window_weeks": 12,
                    "subreddits": [f"r/{s}" for s in settings.subreddits[:3]],
                    "chart_title": f'Mention Index — "{lead_name}"',
                    "delta_label": f"{_signed(momentum_pct)}% w/w",
                    "delta_value": series[-1]["value"] if series else 0,
                    "series": series,
                },
                "sentiment_focus": await _sentiment_focus_ref(conn, source_id),
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


async def _pick_lead(conn, source_id) -> tuple[int, float] | None:
    rows = await conn.fetch(
        """
        SELECT entity_id,
               COALESCE(SUM(mention_count) FILTER (WHERE day > CURRENT_DATE - 7), 0) AS last7,
               COALESCE(SUM(mention_count) FILTER (
                   WHERE day <= CURRENT_DATE - 7 AND day > CURRENT_DATE - 14), 0) AS prev7
          FROM mention_daily
         WHERE source_id = $1 AND subreddit = '' AND day > CURRENT_DATE - 14
         GROUP BY entity_id
        """,
        source_id,
    )
    best: tuple[int, float] | None = None
    for row in rows:
        if row["last7"] == 0:
            continue
        prev = row["prev7"] or 0
        growth = ((row["last7"] - prev) / prev) if prev else float(row["last7"])
        if best is None or growth > best[1]:
            best = (row["entity_id"], float(growth))
    return best


async def _weekly_series(conn, source_id, entity_id, weeks: int = 12) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT (date_trunc('week', day))::date AS period, SUM(mention_count) AS value
          FROM mention_daily
         WHERE source_id = $1 AND entity_id = $2 AND subreddit = ''
           AND day > CURRENT_DATE - ($3::int * 7)
         GROUP BY 1 ORDER BY 1
        """,
        source_id, entity_id, weeks,
    )
    return [{"period": r["period"].isoformat(), "value": int(r["value"])} for r in rows]


async def _sentiment_focus_ref(conn, source_id) -> dict | None:
    row = await conn.fetchrow(
        """
        SELECT sd.entity_id, e.canonical_name
          FROM sentiment_daily sd
          JOIN entity e ON e.entity_id = sd.entity_id
         WHERE sd.source_id = $1
           AND sd.day = (SELECT max(day) FROM sentiment_daily WHERE source_id = $1)
         ORDER BY sd.sentiment_mean ASC
         LIMIT 1
        """,
        source_id,
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
                "Write a concise newsletter headline and one-sentence dek for a Reddit "
                "trend report. Use ONLY these derived metrics (no raw content): "
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
