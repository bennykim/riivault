"""Incremental Reddit submission collection via asyncpraw.

Per subreddit we read ``subreddit.new(limit=100)`` and keep only submissions
newer than the stored ``collect_cursor.last_created_utc``. Authors are stored as
a SHA-256 hash only; raw rows expire 48h after fetch.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import asyncpg

from ..config import Settings
from .ratelimit import TokenBucket

logger = logging.getLogger("riivault.reddit")

RAW_TTL_HOURS = 48


def author_hash(author_name: str | None) -> str | None:
    """SHA-256 of the author name (de-identified); None if author is unavailable."""
    if not author_name:
        return None
    return hashlib.sha256(author_name.encode("utf-8")).hexdigest()


@dataclass
class CollectResult:
    subreddit: str
    api_calls: int = 0
    items_ingested: int = 0
    rate_limited: bool = False


async def _get_cursor(conn: asyncpg.Connection, subreddit: str) -> datetime | None:
    row = await conn.fetchrow(
        "SELECT last_created_utc FROM collect_cursor WHERE subreddit = $1", subreddit
    )
    return row["last_created_utc"] if row else None


async def _set_cursor(
    conn: asyncpg.Connection,
    subreddit: str,
    last_fullname: str | None,
    last_created_utc: datetime,
) -> None:
    await conn.execute(
        """
        INSERT INTO collect_cursor (subreddit, last_fullname, last_created_utc, updated_at)
        VALUES ($1, $2, $3, now())
        ON CONFLICT (subreddit) DO UPDATE
            SET last_fullname = EXCLUDED.last_fullname,
                last_created_utc = EXCLUDED.last_created_utc,
                updated_at = now()
        """,
        subreddit,
        last_fullname,
        last_created_utc,
    )


async def collect_subreddit(
    reddit,
    conn: asyncpg.Connection,
    bucket: TokenBucket,
    subreddit_name: str,
    limit: int = 100,
) -> CollectResult:
    result = CollectResult(subreddit=subreddit_name)
    last_seen = await _get_cursor(conn, subreddit_name)
    newest_created = last_seen
    newest_fullname: str | None = None
    rows: list[tuple] = []

    await bucket.acquire()
    result.api_calls += 1
    subreddit = await reddit.subreddit(subreddit_name)
    try:
        async for submission in subreddit.new(limit=limit):
            created = datetime.fromtimestamp(submission.created_utc, tz=UTC)
            if last_seen is not None and created <= last_seen:
                continue
            author = getattr(submission, "author", None)
            author_name = getattr(author, "name", None) if author else None
            rows.append(
                (
                    submission.fullname,
                    subreddit_name,
                    author_hash(author_name),
                    submission.title,
                    getattr(submission, "selftext", None),
                    submission.score,
                    submission.upvote_ratio,
                    submission.num_comments,
                    getattr(submission, "link_flair_text", None),
                    created,
                )
            )
            if newest_created is None or created > newest_created:
                newest_created = created
                newest_fullname = submission.fullname
    except Exception as exc:  # noqa: BLE001 - persist partial progress on any error
        logger.warning("collect %s failed: %s", subreddit_name, exc)
        result.rate_limited = "429" in str(exc) or "rate" in str(exc).lower()

    if rows:
        await conn.executemany(
            """
            INSERT INTO raw_submission
                (reddit_id, subreddit, author_hash, title, selftext, score,
                 upvote_ratio, num_comments, flair, created_utc, fetched_at, expires_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10, now(),
                    now() + interval '48 hours')
            ON CONFLICT (reddit_id) DO NOTHING
            """,
            rows,
        )
        result.items_ingested = len(rows)
    if newest_created is not None and newest_created != last_seen:
        await _set_cursor(conn, subreddit_name, newest_fullname, newest_created)
    return result


# Reddit requires <platform>:<app ID>:<version> (by /u/<username>). Enforced
# rather than merely documented: a malformed UA is a policy violation, so the
# client refuses to be built instead of issuing non-compliant requests.
USER_AGENT_RE = re.compile(
    r"^[\w.-]+:[\w.-]+:v?[\w.-]+ \(by /u/[\w-]{3,20}\)$"
)


def validate_user_agent(user_agent: str) -> str:
    """Return the UA unchanged, or raise ValueError if it violates the format."""
    if not USER_AGENT_RE.match(user_agent or ""):
        raise ValueError(
            "REDDIT_USER_AGENT must match '<platform>:<app ID>:<version> "
            f"(by /u/<username>)'; got {user_agent!r}"
        )
    return user_agent


async def build_reddit(settings: Settings):
    """Construct an asyncpraw Reddit client, pinned read-only.

    ``read_only=True`` is set explicitly so no code path can post, vote, or
    otherwise write, independent of which credentials are supplied.
    """
    import asyncpraw

    client = asyncpraw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=validate_user_agent(settings.reddit_user_agent),
    )
    client.read_only = True
    return client
