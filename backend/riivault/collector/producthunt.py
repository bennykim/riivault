"""Incremental Product Hunt launch collection via the GraphQL v2 API.

New launches in the niche's topics (``ph_topics``) are an early-detection
surface: mentions of tracked entities in launch copy ("built on Supabase",
"a Cursor for X") signal ecosystem pull. For each topic we page ``posts``
newest-first, keeping only posts created after the stored ``collect_cursor``
(key ``ph:posts:<topic>``) — the same forward-only semantics as the HN/GitHub
collectors. Makers are stored as a SHA-256 hash only; raw rows expire 48h
after fetch. Requires ``PRODUCTHUNT_TOKEN`` (developer token, sent as Bearer).
"""

from __future__ import annotations

import logging
from datetime import datetime

import asyncpg
import httpx

from ..config import Settings, get_settings
from ..db import pool_context
from .ratelimit import TokenBucket
from .reddit import CollectResult, author_hash

logger = logging.getLogger("riivault.ph")

PH_GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"

_POSTS_QUERY = """
query($topic: String!, $first: Int!, $after: String) {
  posts(topic: $topic, order: NEWEST, first: $first, after: $after) {
    pageInfo { hasNextPage endCursor }
    edges { node {
      id name tagline description url votesCount commentsCount createdAt
      user { username }
    } }
  }
}
"""


def _cursor_key(topic: str) -> str:
    """Namespaced ``collect_cursor`` key so PH reuses the cursor table."""
    return f"ph:posts:{topic}"


def parse_post(node: dict, topic: str) -> tuple:
    """Map a GraphQL post node to a ``raw_ph_post`` row tuple (pure, testable).

    Returns ``(ph_id, topic, author_hash, name, tagline, description, url,
    votes, num_comments, created_utc)``.
    """
    user = node.get("user") or {}
    created_utc = datetime.fromisoformat(node["createdAt"])
    return (
        str(node["id"]),
        topic,
        author_hash(user.get("username")),
        node.get("name"),
        node.get("tagline"),
        node.get("description"),
        node.get("url"),
        node.get("votesCount"),
        node.get("commentsCount"),
        created_utc,
    )


async def _get_cursor(conn: asyncpg.Connection, key: str) -> datetime | None:
    row = await conn.fetchrow(
        "SELECT last_created_utc FROM collect_cursor WHERE subreddit = $1", key
    )
    return row["last_created_utc"] if row else None


async def _set_cursor(
    conn: asyncpg.Connection,
    key: str,
    last_ph_id: str | None,
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
        key,
        last_ph_id,
        last_created_utc,
    )


async def _query(
    client: httpx.AsyncClient, settings: Settings, variables: dict
) -> dict:
    resp = await client.post(
        PH_GRAPHQL_URL,
        json={"query": _POSTS_QUERY, "variables": variables},
        headers={"Authorization": f"Bearer {settings.producthunt_token}"},
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(f"GraphQL errors: {data['errors'][:1]}")
    return data["data"]["posts"]


async def collect_topic(
    client: httpx.AsyncClient,
    conn: asyncpg.Connection,
    bucket: TokenBucket,
    topic: str,
    settings: Settings,
) -> CollectResult:
    key = _cursor_key(topic)
    result = CollectResult(subreddit=key)
    last_seen = await _get_cursor(conn, key)
    newest_created = last_seen
    newest_ph_id: str | None = None
    rows: list[tuple] = []
    after: str | None = None

    try:
        for _page in range(settings.ph_max_pages_per_topic):
            await bucket.acquire()
            result.api_calls += 1
            posts = await _query(
                client, settings,
                {"topic": topic, "first": settings.ph_first, "after": after},
            )
            edges = posts.get("edges") or []
            if not edges:
                break
            reached_cursor = False
            for edge in edges:
                row = parse_post(edge["node"], topic)
                created = row[-1]
                if last_seen is not None and created <= last_seen:
                    reached_cursor = True
                    continue
                rows.append(row)
                if newest_created is None or created > newest_created:
                    newest_created = created
                    newest_ph_id = row[0]
            page_info = posts.get("pageInfo") or {}
            if reached_cursor or not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")
    except Exception as exc:  # noqa: BLE001 - persist partial progress on any error
        logger.warning("collect ph %s failed: %s", key, exc)
        result.rate_limited = "429" in str(exc) or "rate" in str(exc).lower()

    if rows:
        await conn.executemany(
            """
            INSERT INTO raw_ph_post
                (ph_id, topic, author_hash, name, tagline, description, url,
                 votes, num_comments, created_utc, fetched_at, expires_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10, now(),
                    now() + interval '48 hours')
            ON CONFLICT (ph_id) DO NOTHING
            """,
            rows,
        )
        result.items_ingested = len(rows)
    if newest_created is not None and newest_created != last_seen:
        await _set_cursor(conn, key, newest_ph_id, newest_created)
    return result


async def collect_once_ph(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    totals = {"api_calls": 0, "items": 0, "errors": 0, "rate_limited": False}
    if not settings.ph_enabled or not settings.producthunt_token:
        logger.info("Product Hunt collection skipped (disabled or no token)")
        return totals

    bucket = TokenBucket(settings.ph_rpm)

    async with pool_context(settings) as pool:
        async with pool.acquire() as conn:
            run_id = await conn.fetchval(
                """
                INSERT INTO collection_run (source_id, started_at)
                VALUES ((SELECT source_id FROM source WHERE name = 'producthunt'), now())
                RETURNING run_id
                """
            )

        async with httpx.AsyncClient(timeout=30.0) as client:
            for topic in settings.ph_topic_list:
                try:
                    async with pool.acquire() as conn:
                        res = await collect_topic(client, conn, bucket, topic, settings)
                    totals["api_calls"] += res.api_calls
                    totals["items"] += res.items_ingested
                    totals["rate_limited"] = totals["rate_limited"] or res.rate_limited
                except Exception as exc:  # noqa: BLE001
                    logger.warning("ph topic %s error: %s", topic, exc)
                    totals["errors"] += 1

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
    logger.info("collect_once_ph complete: %s", totals)
    return totals
