"""Compliance purge: 48h TTL expiry + Reddit deletion honoring.

(1) Delete raw rows past ``expires_at`` (no logging needed).
(2) For rows still present whose title/selftext/body is ``[deleted]``/``[removed]``:
    delete the raw row, record ``deletion_log`` (action ``purged_raw``), and NULL any
    ``feature_request.example_ref`` that points at that reddit_id. When a ref is
    invalidated the single log row's action becomes ``purged_raw+invalidated_ref``
    (kept as one row since ``reddit_id`` is the deletion_log PK).
"""

from __future__ import annotations

import logging

from ..config import Settings, get_settings
from ..db import pool_context

logger = logging.getLogger("riivault.purge")

DELETED_MARKERS = ["[deleted]", "[removed]"]


def _rowcount(status: str) -> int:
    try:
        return int(status.split()[-1])
    except (ValueError, IndexError, AttributeError):
        return 0


def _short(reddit_id: str) -> str:
    return reddit_id.split("_", 1)[-1]


async def run_purge(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    async with pool_context(settings) as pool:
        async with pool.acquire() as conn:
            # (1) TTL expiry — silent.
            expired_sub = _rowcount(
                await conn.execute("DELETE FROM raw_submission WHERE expires_at < now()")
            )
            expired_com = _rowcount(
                await conn.execute("DELETE FROM raw_comment WHERE expires_at < now()")
            )
            expired_gh = _rowcount(
                await conn.execute("DELETE FROM raw_gh_issue WHERE expires_at < now()")
            )
            expired_ph = _rowcount(
                await conn.execute("DELETE FROM raw_ph_post WHERE expires_at < now()")
            )

            # (2) deletion detection among still-present rows.
            deleted_subs = await conn.fetch(
                """
                SELECT reddit_id FROM raw_submission
                 WHERE title = ANY($1::text[]) OR selftext = ANY($1::text[])
                """,
                DELETED_MARKERS,
            )
            deleted_coms = await conn.fetch(
                "SELECT reddit_id FROM raw_comment WHERE body = ANY($1::text[])",
                DELETED_MARKERS,
            )

            purged = 0
            invalidated = 0
            async with conn.transaction():
                for row in deleted_subs:
                    invalidated += await _purge_deleted(conn, "raw_submission", row["reddit_id"])
                    purged += 1
                for row in deleted_coms:
                    invalidated += await _purge_deleted(conn, "raw_comment", row["reddit_id"])
                    purged += 1

    summary = {
        "expired_submissions": expired_sub,
        "expired_comments": expired_com,
        "expired_gh_issues": expired_gh,
        "expired_ph_posts": expired_ph,
        "deleted_purged": purged,
        "refs_invalidated": invalidated,
    }
    logger.info("purge complete: %s", summary)
    return summary


async def _purge_deleted(conn, table: str, reddit_id: str) -> int:
    short = _short(reddit_id)
    refs = await conn.fetchval(
        "SELECT count(*) FROM feature_request WHERE example_ref LIKE '%' || $1 || '%'",
        short,
    )
    action = "purged_raw"
    if refs:
        await conn.execute(
            "UPDATE feature_request SET example_ref = NULL WHERE example_ref LIKE '%' || $1 || '%'",
            short,
        )
        action = "purged_raw+invalidated_ref"

    # table is an internal constant, never user input.
    await conn.execute(f"DELETE FROM {table} WHERE reddit_id = $1", reddit_id)
    await conn.execute(
        """
        INSERT INTO deletion_log (reddit_id, detected_at, action)
        VALUES ($1, now(), $2)
        ON CONFLICT (reddit_id) DO UPDATE
            SET detected_at = now(), action = EXCLUDED.action
        """,
        reddit_id, action,
    )
    return int(refs or 0)
