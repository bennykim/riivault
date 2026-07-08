"""GET /issue/current — composite main-page response.

Combines the latest ``weekly_issue`` row (+ its payload snapshot: lead series,
migration) with live derived-table queries (tracked, pain_points,
sentiment_focus, emerging). Returns 404 when no issue has been published.
Never reads raw_* tables.
"""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_pool
from .entities import fetch_tracked
from .painpoints import fetch_pain_points
from .signals import fetch_signals

router = APIRouter()


@router.get("/issue/current")
async def issue_current(pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as conn:
        issue = await conn.fetchrow(
            """
            SELECT issue_no, week_start, week_end, headline, dek,
                   lead_entity_id, payload, published_at
              FROM weekly_issue
             ORDER BY week_start DESC
             LIMIT 1
            """
        )
        if issue is None:
            raise HTTPException(status_code=404, detail="no published issue")

        payload = issue["payload"] or {}
        tracked = await fetch_tracked(conn)
        pain_points = await fetch_pain_points(conn, days=7, limit=10)
        emerging = await fetch_signals(conn, limit=6, order="strength")
        sentiment_focus = await _sentiment_focus(
            conn, payload.get("sentiment_focus")
        )

    lead = dict(payload.get("lead") or {})
    lead["headline"] = issue["headline"]
    lead["dek"] = issue["dek"]

    generated_at = payload.get("generated_at")
    if generated_at is None and issue["published_at"] is not None:
        generated_at = issue["published_at"].isoformat()

    return {
        "issue_no": issue["issue_no"],
        "week_start": issue["week_start"].isoformat(),
        "week_end": issue["week_end"].isoformat(),
        "generated_at": generated_at,
        "niche": payload.get("niche"),
        "communities": payload.get("communities"),
        "lead": lead,
        "tracked": [
            {k: v for k, v in item.items() if k != "type"} for item in tracked
        ],
        "pain_points": pain_points,
        "sentiment_focus": sentiment_focus,
        "migration": payload.get("migration"),
        "emerging": emerging,
    }


async def _sentiment_focus(conn, focus_ref: dict | None) -> dict | None:
    if not focus_ref:
        return None
    entity_id = focus_ref.get("entity_id")
    label = focus_ref.get("label")
    if entity_id is None:
        return {"label": label, "current": None, "trend": "flat", "series": []}

    # Pool sentiment across all sources per day, weighted by each source's sample_size.
    rows = await conn.fetch(
        """
        SELECT day,
               SUM(sentiment_mean * sample_size) / NULLIF(SUM(sample_size), 0)
                   AS sentiment_mean
          FROM sentiment_daily
         WHERE entity_id = $1
         GROUP BY day
         ORDER BY day
        """,
        entity_id,
    )
    series = [
        {"period": r["day"].isoformat(), "value": round(float(r["sentiment_mean"]), 3)}
        for r in rows
        if r["sentiment_mean"] is not None
    ]
    current = series[-1]["value"] if series else None
    trend = "flat"
    if len(series) >= 2:
        if series[-1]["value"] < series[0]["value"]:
            trend = "falling"
        elif series[-1]["value"] > series[0]["value"]:
            trend = "rising"
    return {"label": label, "current": current, "trend": trend, "series": series}
