"""Tracked entities + per-entity metric series (derived tables only)."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import get_pool

router = APIRouter()


async def fetch_tracked(conn: asyncpg.Connection) -> list[dict]:
    """Tracked entities with 7d-vs-prior-7d change and a 7-day daily spark.

    Mentions are combined across all sources: the per-day counts are summed
    (subreddit='' overall rows) before the spark/window aggregates, so an entity
    seen on both Reddit and Hacker News on a given day contributes one merged
    daily value.
    """
    rows = await conn.fetch(
        """
        WITH daily AS (
            SELECT entity_id, day, SUM(mention_count) AS cnt
              FROM mention_daily
             WHERE subreddit = '' AND day > CURRENT_DATE - 14
             GROUP BY entity_id, day
        )
        SELECT e.entity_id, e.type, e.canonical_name AS name,
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
        """
    )
    items: list[dict] = []
    for r in rows:
        last7, prev7 = r["last7"], r["prev7"]
        change_pct = round((last7 - prev7) / prev7 * 100, 1) if prev7 else None
        items.append(
            {
                "entity_id": r["entity_id"],
                "type": r["type"],
                "name": r["name"],
                "context": r["context"],
                "change_pct": change_pct,
                "spark": [int(v) for v in (r["spark"] or [])],
            }
        )
    return items


@router.get("/entities")
async def get_entities(
    tracked: bool = Query(False),
    pool: asyncpg.Pool = Depends(get_pool),
):
    async with pool.acquire() as conn:
        items = await fetch_tracked(conn)
    return {"items": items}


@router.get("/entities/{entity_id}/series")
async def get_entity_series(
    entity_id: int,
    metric: str = Query("mentions"),
    days: int = Query(90, ge=1, le=365),
    pool: asyncpg.Pool = Depends(get_pool),
):
    metric = "sentiment" if metric == "sentiment" else "mentions"
    async with pool.acquire() as conn:
        source_id = await conn.fetchval(
            "SELECT source_id FROM source WHERE name = 'reddit'"
        )
        if not await conn.fetchval(
            "SELECT 1 FROM entity WHERE entity_id = $1", entity_id
        ):
            raise HTTPException(status_code=404, detail="entity not found")
        if metric == "sentiment":
            rows = await conn.fetch(
                """
                SELECT day, sentiment_mean AS value
                  FROM sentiment_daily
                 WHERE entity_id = $1 AND source_id = $2
                   AND day > CURRENT_DATE - $3::int
                 ORDER BY day
                """,
                entity_id, source_id, days,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT day, mention_count AS value
                  FROM mention_daily
                 WHERE entity_id = $1 AND source_id = $2 AND subreddit = ''
                   AND day > CURRENT_DATE - $3::int
                 ORDER BY day
                """,
                entity_id, source_id, days,
            )

    series = []
    for r in rows:
        value = r["value"]
        if value is None:
            continue
        series.append(
            {
                "period": r["day"].isoformat(),
                "value": round(float(value), 3) if metric == "sentiment" else int(value),
            }
        )
    return {"entity_id": entity_id, "metric": metric, "series": series}
