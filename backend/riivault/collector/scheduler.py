"""APScheduler jobs: collect+aggregate 2h, purge 1h, publish Tue 09:00 UTC,
subreddit snapshot once daily. Each run's collection observability lands in
``collection_run`` (recorded inside ``collect_once``).
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..config import Settings, get_settings
from ..db import pool_context
from .aggregate import run_aggregate, run_aggregate_hn
from .hackernews import collect_once_hn
from .pipeline import collect_once
from .publish import publish_issue
from .purge import run_purge
from .reddit import build_reddit

logger = logging.getLogger("riivault.scheduler")


async def collect_and_aggregate(settings: Settings) -> None:
    # Each source is isolated so one failing does not skip the other.
    try:
        await collect_once(settings)
        await run_aggregate(settings)
    except Exception as exc:  # noqa: BLE001
        logger.warning("reddit collect/aggregate failed: %s", exc)
    if settings.hn_enabled:
        try:
            await collect_once_hn(settings)
            await run_aggregate_hn(settings)
        except Exception as exc:  # noqa: BLE001
            logger.warning("hackernews collect/aggregate failed: %s", exc)


async def snapshot_subreddits(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    reddit = await build_reddit(settings)
    rows: list[tuple] = []
    try:
        for name in settings.subreddits:
            try:
                subreddit = await reddit.subreddit(name)
                await subreddit.load()
                rows.append(
                    (
                        name,
                        getattr(subreddit, "subscribers", None),
                        getattr(subreddit, "active_user_count", None),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("subreddit snapshot %s failed: %s", name, exc)
    finally:
        await reddit.close()

    if rows:
        async with pool_context(settings) as pool:
            async with pool.acquire() as conn:
                await conn.executemany(
                    """
                    INSERT INTO subreddit_snapshot (day, subreddit, subscribers, active_users)
                    VALUES (CURRENT_DATE, $1, $2, $3)
                    ON CONFLICT (day, subreddit) DO UPDATE
                        SET subscribers = EXCLUDED.subscribers,
                            active_users = EXCLUDED.active_users
                    """,
                    rows,
                )
    return len(rows)


def build_scheduler(settings: Settings | None = None) -> AsyncIOScheduler:
    settings = settings or get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        collect_and_aggregate, IntervalTrigger(hours=2), args=[settings],
        id="collect_aggregate", max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        run_purge, IntervalTrigger(hours=1), args=[settings],
        id="purge", max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        publish_issue, CronTrigger(day_of_week="tue", hour=9, minute=0), args=[settings],
        id="publish", max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        snapshot_subreddits, CronTrigger(hour=6, minute=0), args=[settings],
        id="subreddit_snapshot", max_instances=1, coalesce=True,
    )
    return scheduler


async def run_scheduler(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    scheduler = build_scheduler(settings)
    scheduler.start()
    logger.info(
        "scheduler started: collect+aggregate/2h, purge/1h, publish Tue 09:00 UTC, snapshot/daily"
    )
    try:
        await asyncio.Event().wait()  # run until cancelled
    finally:
        scheduler.shutdown()
