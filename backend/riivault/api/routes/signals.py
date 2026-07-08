"""Emerging signals (early-signal ledger). Display strings live in outcome JSONB."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, Query

from ..deps import get_pool

router = APIRouter()

_ORDERS = {
    "recent": "detected_at DESC, signal_id DESC",
    "strength": "strength DESC, detected_at DESC",
}


async def fetch_signals(
    conn: asyncpg.Connection, limit: int = 6, order: str = "recent"
) -> list[dict]:
    order_sql = _ORDERS.get(order, _ORDERS["recent"])
    rows = await conn.fetch(
        f"""
        SELECT signal_id, signal_type, strength, detected_at, outcome
          FROM emerging_signal
         ORDER BY {order_sql}
         LIMIT $1
        """,
        limit,
    )
    items: list[dict] = []
    for r in rows:
        outcome = r["outcome"] or {}
        items.append(
            {
                "signal_id": r["signal_id"],
                "signal_type": r["signal_type"],
                "entity": outcome.get("entity"),
                "description": outcome.get("description"),
                "strength": r["strength"],
                "detected_label": outcome.get("detected_label"),
            }
        )
    return items


@router.get("/signals")
async def get_signals(
    limit: int = Query(6, ge=1, le=50),
    pool: asyncpg.Pool = Depends(get_pool),
):
    async with pool.acquire() as conn:
        items = await fetch_signals(conn, limit, order="recent")
    return {"items": items}
