"""Incremental Hacker News collection via the Algolia public search API.

HN has no subreddit concept, so instead of a firehose we search per tracked
entity *term* (canonical_name + aliases, de-duplicated). For each term we page
``search_by_date`` for both stories and comments, keeping only items newer than
the stored ``collect_cursor.last_created_utc`` (key ``hn:story:<term>`` /
``hn:comment:<term>``). Authors are stored as a SHA-256 hash only; raw rows
expire 48h after fetch. The Algolia API needs no key.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import asyncpg
import httpx

from ..config import Settings, get_settings
from ..db import pool_context
from .ratelimit import TokenBucket
from .reddit import CollectResult, author_hash, backfill_floor

logger = logging.getLogger("riivault.hn")

HN_TTL_HOURS = 48
HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"


def _permalink(hn_id: str) -> str:
    return f"https://news.ycombinator.com/item?id={hn_id}"


def _cursor_key(kind: str, term: str) -> str:
    """Namespaced ``collect_cursor`` key so HN reuses the Reddit cursor table."""
    return f"hn:{kind}:{term}"


def parse_hit(hit: dict, kind: str) -> tuple:
    """Map an Algolia hit dict to a ``raw_hn_item`` row tuple (pure, testable).

    Returns ``(hn_id, kind, author_hash, title, body, url, points,
    num_comments, created_utc)``. Stories carry ``story_text`` as body; comments
    carry ``comment_text`` as body with ``title=None``.
    """
    hn_id = str(hit["objectID"])
    if kind == "story":
        title = hit.get("title")
        body = hit.get("story_text")
    else:
        title = None
        body = hit.get("comment_text")
    created_utc = datetime.fromtimestamp(int(hit["created_at_i"]), tz=UTC)
    return (
        hn_id,
        kind,
        author_hash(hit.get("author")),
        title,
        body,
        hit.get("url"),
        hit.get("points"),
        hit.get("num_comments"),
        created_utc,
    )


async def _load_terms(conn: asyncpg.Connection) -> list[str]:
    """Distinct canonical_name + aliases across all entities (source-independent)."""
    rows = await conn.fetch("SELECT canonical_name, aliases FROM entity")
    terms: set[str] = set()
    for row in rows:
        for term in (row["canonical_name"], *(row["aliases"] or [])):
            if term and term.strip():
                terms.add(term.strip())
    return sorted(terms)


async def _get_cursor(conn: asyncpg.Connection, key: str) -> datetime | None:
    row = await conn.fetchrow(
        "SELECT last_created_utc FROM collect_cursor WHERE subreddit = $1", key
    )
    return row["last_created_utc"] if row else None


async def _set_cursor(
    conn: asyncpg.Connection,
    key: str,
    last_hn_id: str | None,
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
        last_hn_id,
        last_created_utc,
    )


async def collect_term(
    client: httpx.AsyncClient,
    conn: asyncpg.Connection,
    bucket: TokenBucket,
    term: str,
    kind: str,
    settings: Settings,
) -> CollectResult:
    key = _cursor_key(kind, term)
    result = CollectResult(subreddit=key)
    last_seen = await _get_cursor(conn, key)
    newest_created = last_seen
    newest_hn_id: str | None = None
    # Cursor when present, else a 30-day horizon — a fresh term must not
    # backfill years of sparse history into the daily series.
    floor = backfill_floor(last_seen)
    since = int(floor.timestamp())
    rows: list[tuple] = []

    try:
        for page in range(settings.hn_max_pages_per_term):
            await bucket.acquire()
            result.api_calls += 1
            resp = await client.get(
                HN_SEARCH_URL,
                params={
                    "tags": kind,
                    "query": term,
                    "hitsPerPage": settings.hn_hits_per_page,
                    "page": page,
                    "numericFilters": f"created_at_i>{since}",
                },
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            if not hits:
                break
            for hit in hits:
                row = parse_hit(hit, kind)
                created = row[-1]
                if created <= floor:
                    continue
                rows.append(row)
                if newest_created is None or created > newest_created:
                    newest_created = created
                    newest_hn_id = row[0]
            if len(hits) < settings.hn_hits_per_page:
                break
    except Exception as exc:  # noqa: BLE001 - persist partial progress on any error
        logger.warning("collect hn %s failed: %s", key, exc)
        result.rate_limited = "429" in str(exc) or "rate" in str(exc).lower()

    if rows:
        await conn.executemany(
            """
            INSERT INTO raw_hn_item
                (hn_id, kind, author_hash, title, body, url, points,
                 num_comments, created_utc, fetched_at, expires_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9, now(),
                    now() + interval '48 hours')
            ON CONFLICT (hn_id) DO NOTHING
            """,
            rows,
        )
        result.items_ingested = len(rows)
    if newest_created is not None and newest_created != last_seen:
        await _set_cursor(conn, key, newest_hn_id, newest_created)
    return result


async def collect_once_hn(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    totals = {"api_calls": 0, "items": 0, "errors": 0, "rate_limited": False}
    if not settings.hn_enabled:
        logger.info("HN collection disabled (hn_enabled=false)")
        return totals

    bucket = TokenBucket(settings.hn_rpm)

    async with pool_context(settings) as pool:
        async with pool.acquire() as conn:
            run_id = await conn.fetchval(
                """
                INSERT INTO collection_run (source_id, started_at)
                VALUES ((SELECT source_id FROM source WHERE name = 'hackernews'), now())
                RETURNING run_id
                """
            )
            terms = await _load_terms(conn)

        async with httpx.AsyncClient(timeout=30.0) as client:
            for term in terms:
                for kind in ("story", "comment"):
                    try:
                        async with pool.acquire() as conn:
                            res = await collect_term(
                                client, conn, bucket, term, kind, settings
                            )
                        totals["api_calls"] += res.api_calls
                        totals["items"] += res.items_ingested
                        totals["rate_limited"] = totals["rate_limited"] or res.rate_limited
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("hn term %s/%s error: %s", kind, term, exc)
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
    logger.info("collect_once_hn complete: %s", totals)
    return totals
