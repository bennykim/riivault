"""Incremental GitHub Issues collection via the REST API (no key required).

Issues and issue comments on a tracked entity's repository are *actual product
feedback* (bug reports, feature requests) rather than discourse mentions, so
they feed the VoC ledger directly. Repos come from ``entity.metadata->>'repo'``
(owner/name). For each repo we page the list endpoints newest-first, keeping
only items created after the stored ``collect_cursor`` (key
``gh:issue:<repo>`` / ``gh:comment:<repo>``) — the same forward-only semantics
as the HN collector, so day-recompute aggregation stays correct. Authors are
stored as a SHA-256 hash only; raw rows expire 48h after fetch.

Unauthenticated requests are limited to 60/hr; setting ``GH_API_TOKEN`` lifts
that to 5000/hr.
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

logger = logging.getLogger("riivault.gh")

GH_API_URL = "https://api.github.com"


def gh_headers(settings: Settings) -> dict[str, str]:
    """Standard REST headers; adds auth only when a token is configured."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.gh_api_token:
        headers["Authorization"] = f"Bearer {settings.gh_api_token}"
    return headers


def _cursor_key(kind: str, repo: str) -> str:
    """Namespaced ``collect_cursor`` key so GitHub reuses the cursor table."""
    return f"gh:{kind}:{repo}"


def _issue_number_from_url(issue_url: str | None) -> int | None:
    """``.../repos/o/r/issues/42`` -> 42 (comments carry no number field)."""
    if not issue_url:
        return None
    tail = issue_url.rstrip("/").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else None


def parse_issue(item: dict, repo: str, kind: str) -> tuple:
    """Map a REST issue/comment dict to a ``raw_gh_issue`` row tuple (pure).

    Returns ``(gh_id, repo, kind, number, author_hash, title, body, state,
    num_comments, url, created_utc)``. Issues carry title/state/comment count;
    comments carry ``body`` only, with ``number`` parsed from ``issue_url``.
    """
    user = item.get("user") or {}
    if kind == "issue":
        number = item["number"]
        gh_id = f"{repo}#{number}"
        title = item.get("title")
        state = item.get("state")
        num_comments = item.get("comments") or 0
    else:
        number = _issue_number_from_url(item.get("issue_url"))
        gh_id = f"{repo}#c{item['id']}"
        title = None
        state = None
        num_comments = 0
    created_utc = datetime.fromisoformat(item["created_at"])
    return (
        gh_id,
        repo,
        kind,
        number,
        author_hash(user.get("login")),
        title,
        item.get("body"),
        state,
        num_comments,
        item.get("html_url"),
        created_utc,
    )


def _list_url(repo: str, kind: str) -> str:
    if kind == "issue":
        return f"{GH_API_URL}/repos/{repo}/issues"
    return f"{GH_API_URL}/repos/{repo}/issues/comments"


async def _load_repos(conn: asyncpg.Connection) -> list[str]:
    """Distinct mapped repos across all entities."""
    rows = await conn.fetch(
        "SELECT DISTINCT metadata->>'repo' AS repo FROM entity"
        " WHERE metadata->>'repo' IS NOT NULL"
    )
    return sorted(r["repo"] for r in rows)


async def _get_cursor(conn: asyncpg.Connection, key: str) -> datetime | None:
    row = await conn.fetchrow(
        "SELECT last_created_utc FROM collect_cursor WHERE subreddit = $1", key
    )
    return row["last_created_utc"] if row else None


async def _set_cursor(
    conn: asyncpg.Connection,
    key: str,
    last_gh_id: str | None,
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
        last_gh_id,
        last_created_utc,
    )


async def collect_repo(
    client: httpx.AsyncClient,
    conn: asyncpg.Connection,
    bucket: TokenBucket,
    repo: str,
    kind: str,
    settings: Settings,
) -> CollectResult:
    key = _cursor_key(kind, repo)
    result = CollectResult(subreddit=key)
    last_seen = await _get_cursor(conn, key)
    newest_created = last_seen
    newest_gh_id: str | None = None
    rows: list[tuple] = []

    try:
        for page in range(1, settings.gh_max_pages_per_repo + 1):
            await bucket.acquire()
            result.api_calls += 1
            resp = await client.get(
                _list_url(repo, kind),
                params={
                    "state": "all",
                    "sort": "created",
                    "direction": "desc",
                    "per_page": settings.gh_per_page,
                    "page": page,
                },
                headers=gh_headers(settings),
            )
            if resp.status_code == 410:  # issues disabled for this repo
                logger.info("collect gh %s: issues disabled, skipping", key)
                return result
            resp.raise_for_status()
            items = resp.json()
            if not items:
                break
            reached_cursor = False
            for item in items:
                if kind == "issue" and "pull_request" in item:
                    continue  # the issues endpoint also lists PRs
                row = parse_issue(item, repo, kind)
                created = row[-1]
                if last_seen is not None and created <= last_seen:
                    reached_cursor = True
                    continue
                rows.append(row)
                if newest_created is None or created > newest_created:
                    newest_created = created
                    newest_gh_id = row[0]
            if reached_cursor or len(items) < settings.gh_per_page:
                break
    except Exception as exc:  # noqa: BLE001 - persist partial progress on any error
        logger.warning("collect gh %s failed: %s", key, exc)
        result.rate_limited = "403" in str(exc) or "rate" in str(exc).lower()

    if rows:
        await conn.executemany(
            """
            INSERT INTO raw_gh_issue
                (gh_id, repo, kind, number, author_hash, title, body, state,
                 num_comments, url, created_utc, fetched_at, expires_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11, now(),
                    now() + interval '48 hours')
            ON CONFLICT (gh_id) DO NOTHING
            """,
            rows,
        )
        result.items_ingested = len(rows)
    if newest_created is not None and newest_created != last_seen:
        await _set_cursor(conn, key, newest_gh_id, newest_created)
    return result


async def collect_once_gh(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    totals = {"api_calls": 0, "items": 0, "errors": 0, "rate_limited": False}
    if not settings.gh_enabled:
        logger.info("GitHub collection disabled (gh_enabled=false)")
        return totals

    bucket = TokenBucket(settings.gh_rpm)

    async with pool_context(settings) as pool:
        async with pool.acquire() as conn:
            repos = await _load_repos(conn)
            if not repos:
                logger.info("GitHub collection skipped (no entity repo mappings)")
                return totals
            run_id = await conn.fetchval(
                """
                INSERT INTO collection_run (source_id, started_at)
                VALUES ((SELECT source_id FROM source WHERE name = 'github'), now())
                RETURNING run_id
                """
            )

        # follow_redirects: renamed repos answer 301 to their new home
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for repo in repos:
                for kind in ("issue", "comment"):
                    try:
                        async with pool.acquire() as conn:
                            res = await collect_repo(
                                client, conn, bucket, repo, kind, settings
                            )
                        totals["api_calls"] += res.api_calls
                        totals["items"] += res.items_ingested
                        totals["rate_limited"] = totals["rate_limited"] or res.rate_limited
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("gh %s/%s error: %s", kind, repo, exc)
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
    logger.info("collect_once_gh complete: %s", totals)
    return totals
