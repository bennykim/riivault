"""asyncpg connection pool helpers (direct SQL, no ORM).

A JSONB codec is registered on every connection so ``payload``/``outcome``
columns round-trip as native Python ``dict``/``list`` values.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

from .config import Settings, get_settings


async def _init_connection(conn: asyncpg.Connection) -> None:
    for typename in ("jsonb", "json"):
        await conn.set_type_codec(
            typename,
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )


async def create_pool(
    settings: Settings | None = None, **kwargs: Any
) -> asyncpg.Pool:
    settings = settings or get_settings()
    return await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=kwargs.pop("min_size", 1),
        max_size=kwargs.pop("max_size", 10),
        init=_init_connection,
        **kwargs,
    )


@asynccontextmanager
async def pool_context(
    settings: Settings | None = None,
) -> AsyncIterator[asyncpg.Pool]:
    """Create a pool, yield it, and close it on exit (for CLI one-shot jobs)."""
    pool = await create_pool(settings)
    try:
        yield pool
    finally:
        await pool.close()
