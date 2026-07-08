"""Rising pain points / feature requests from the VoC ledger."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, Query

from ..deps import get_pool

router = APIRouter()


async def fetch_pain_points(
    conn: asyncpg.Connection, days: int = 7, limit: int = 10
) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT fr_id, kind, normalized_text AS text, occurrences, momentum
          FROM feature_request
         WHERE last_seen >= CURRENT_DATE - $1::int
         ORDER BY momentum DESC NULLS LAST, occurrences DESC
         LIMIT $2
        """,
        days, limit,
    )
    return [
        {
            "fr_id": r["fr_id"],
            "rank": rank,
            "text": r["text"],
            "kind": r["kind"],
            "occurrences": r["occurrences"],
            "momentum_pct": round((r["momentum"] or 0.0) * 100, 1),
        }
        for rank, r in enumerate(rows, start=1)
    ]


@router.get("/pain-points")
async def get_pain_points(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(10, ge=1, le=100),
    pool: asyncpg.Pool = Depends(get_pool),
):
    async with pool.acquire() as conn:
        items = await fetch_pain_points(conn, days, limit)
    return {"items": items}
