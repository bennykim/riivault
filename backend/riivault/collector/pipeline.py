"""Collection run orchestration: throttle, ingest each subreddit, record run."""

from __future__ import annotations

import logging

from ..config import Settings, get_settings
from ..db import pool_context
from .ratelimit import TokenBucket
from .reddit import build_reddit, collect_subreddit

logger = logging.getLogger("riivault.pipeline")


async def collect_once(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    # No-op cleanly when Reddit credentials are absent (e.g. before API approval),
    # so scheduled/CI runs still proceed to the HN + aggregate steps.
    if not settings.reddit_client_id:
        logger.info("reddit collection skipped (REDDIT_CLIENT_ID not set)")
        return {"api_calls": 0, "items": 0, "errors": 0, "rate_limited": False,
                "skipped": "no_credentials"}
    bucket = TokenBucket(settings.reddit_qpm)
    totals = {"api_calls": 0, "items": 0, "errors": 0, "rate_limited": False}

    async with pool_context(settings) as pool:
        async with pool.acquire() as conn:
            run_id = await conn.fetchval(
                """
                INSERT INTO collection_run (source_id, started_at)
                VALUES ((SELECT source_id FROM source WHERE name = 'reddit'), now())
                RETURNING run_id
                """
            )

        reddit = await build_reddit(settings)
        try:
            for name in settings.subreddits:
                try:
                    async with pool.acquire() as conn:
                        res = await collect_subreddit(reddit, conn, bucket, name)
                    totals["api_calls"] += res.api_calls
                    totals["items"] += res.items_ingested
                    totals["rate_limited"] = totals["rate_limited"] or res.rate_limited
                except Exception as exc:  # noqa: BLE001
                    logger.warning("subreddit %s error: %s", name, exc)
                    totals["errors"] += 1
        finally:
            await reddit.close()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE collection_run
                   SET finished_at = now(), api_calls = $2, items_ingested = $3,
                       errors = $4, rate_limited = $5
                 WHERE run_id = $1
                """,
                run_id,
                totals["api_calls"],
                totals["items"],
                totals["errors"],
                totals["rate_limited"],
            )
    logger.info("collect_once complete: %s", totals)
    return totals
