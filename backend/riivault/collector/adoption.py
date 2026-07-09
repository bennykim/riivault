"""Adoption-metric collection: GitHub stars/releases + npm/PyPI downloads.

Complements discourse mentions ("what people say") with adoption time-series
("what people use"). Unlike the content collectors these endpoints return
public *numeric* stats only — no user content, no author — so rows go straight
into the permanent ``adoption_daily`` derived table (no raw 48h buffer):
``(day, entity_id, source_id, metric, value)`` upserts are idempotent.

Per entity mapping (``entity.metadata`` keys):
- ``repo``   -> source ``github``: ``stars_total`` snapshot (today) and
  ``releases`` count per publish day (last ``RELEASE_WINDOW_DAYS``)
- ``npm``    -> source ``npm``:  ``downloads`` per day (registry range API)
- ``pypi``   -> source ``pypi``: ``downloads`` per day (pypistats, mirrors excluded)
- ``se_tag`` -> source ``stackexchange``: new ``questions`` per day for the
  Stack Overflow tag (technical-interest proxy, last ``SE_WINDOW_DAYS``)

All endpoints are free and unauthenticated; the GitHub calls reuse the
optional ``GH_API_TOKEN`` for the higher rate limit.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

import asyncpg
import httpx

from ..config import Settings, get_settings
from ..db import pool_context
from .github import GH_API_URL, gh_headers
from .ratelimit import TokenBucket

logger = logging.getLogger("riivault.adoption")

NPM_RANGE_URL = "https://api.npmjs.org/downloads/range/last-month"
PYPISTATS_URL = "https://pypistats.org/api/packages"
SE_QUESTIONS_URL = "https://api.stackexchange.com/2.3/questions"
SE_SITE = "stackoverflow"
RELEASE_WINDOW_DAYS = 90
SE_WINDOW_DAYS = 30
SE_PAGE_SIZE = 100
SE_PAGES_MAX = 3


# --------------------------------------------------------------------------- #
# Pure response -> (day, value) parsers (unit-testable, no network)           #
# --------------------------------------------------------------------------- #
def npm_rows(payload: dict[str, Any]) -> list[tuple[date, float]]:
    """``{"downloads": [{"day": "2026-06-09", "downloads": 123}, ...]}``."""
    rows: list[tuple[date, float]] = []
    for point in payload.get("downloads") or []:
        day = point.get("day")
        value = point.get("downloads")
        if day is None or value is None:
            continue
        rows.append((date.fromisoformat(day), float(value)))
    return rows


def pypi_rows(payload: dict[str, Any]) -> list[tuple[date, float]]:
    """pypistats ``overall`` data, keeping the mirror-free series only."""
    rows: list[tuple[date, float]] = []
    for point in payload.get("data") or []:
        if point.get("category") != "without_mirrors":
            continue
        day = point.get("date")
        value = point.get("downloads")
        if day is None or value is None:
            continue
        rows.append((date.fromisoformat(day), float(value)))
    return rows


def release_rows(
    payload: list[dict[str, Any]], today: date, window_days: int = RELEASE_WINDOW_DAYS
) -> list[tuple[date, float]]:
    """Count published (non-draft) releases per day within the window."""
    counts: dict[date, float] = {}
    for release in payload or []:
        published = release.get("published_at")
        if not published or release.get("draft"):
            continue
        day = datetime.fromisoformat(published).date()
        if day < today - timedelta(days=window_days):
            continue
        counts[day] = counts.get(day, 0.0) + 1.0
    return sorted(counts.items())


def se_rows(
    items: list[dict[str, Any]],
    today: date,
    window_days: int = SE_WINDOW_DAYS,
    truncated: bool = False,
) -> list[tuple[date, float]]:
    """Count questions per UTC day from ``creation_date`` epochs.

    When the fetch was ``truncated`` (page cap hit before the window edge),
    the oldest collected day is dropped: it is only partially covered and an
    upsert would overwrite an earlier, complete count with an undercount.
    """
    counts: dict[date, float] = {}
    for item in items or []:
        epoch = item.get("creation_date")
        if epoch is None:
            continue
        day = datetime.fromtimestamp(int(epoch), tz=UTC).date()
        if day < today - timedelta(days=window_days):
            continue
        counts[day] = counts.get(day, 0.0) + 1.0
    if truncated and counts:
        del counts[min(counts)]
    return sorted(counts.items())


# --------------------------------------------------------------------------- #
# DB orchestration                                                            #
# --------------------------------------------------------------------------- #
async def _upsert(
    conn: asyncpg.Connection,
    entity_id: int,
    source_id: int,
    metric: str,
    rows: list[tuple[date, float]],
) -> int:
    if not rows:
        return 0
    await conn.executemany(
        """
        INSERT INTO adoption_daily (day, entity_id, source_id, metric, value)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (day, entity_id, source_id, metric)
            DO UPDATE SET value = EXCLUDED.value
        """,
        [(day, entity_id, source_id, metric, value) for day, value in rows],
    )
    return len(rows)


async def collect_once_adoption(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    today = datetime.now(UTC).date()
    totals = {"api_calls": 0, "rows": 0, "errors": 0}
    bucket = TokenBucket(settings.gh_rpm)

    async with pool_context(settings) as pool:
        async with pool.acquire() as conn:
            source_ids = {
                r["name"]: r["source_id"]
                for r in await conn.fetch("SELECT source_id, name FROM source")
            }
            mappings = await conn.fetch(
                """
                SELECT entity_id, metadata->>'repo' AS repo,
                       metadata->>'npm' AS npm, metadata->>'pypi' AS pypi,
                       metadata->>'se_tag' AS se_tag
                  FROM entity
                 WHERE metadata->>'repo' IS NOT NULL
                    OR metadata->>'npm' IS NOT NULL
                    OR metadata->>'pypi' IS NOT NULL
                    OR metadata->>'se_tag' IS NOT NULL
                 ORDER BY entity_id
                """
            )
            if not mappings:
                logger.info("adoption skipped (no entity repo/npm/pypi mappings)")
                return totals

            # follow_redirects: renamed repos answer 301 to their new home
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                for m in mappings:
                    eid = m["entity_id"]
                    if m["repo"]:
                        await _collect_github(
                            client, conn, bucket, settings, eid, m["repo"],
                            source_ids["github"], today, totals,
                        )
                    if m["npm"]:
                        await _collect_json(
                            client, conn, bucket, totals,
                            f"{NPM_RANGE_URL}/{m['npm']}",
                            eid, source_ids["npm"], "downloads", npm_rows,
                        )
                    if m["pypi"]:
                        await _collect_json(
                            client, conn, bucket, totals,
                            f"{PYPISTATS_URL}/{m['pypi']}/overall",
                            eid, source_ids["pypi"], "downloads", pypi_rows,
                        )
                    if m["se_tag"]:
                        await _collect_stackexchange(
                            client, conn, bucket, eid, m["se_tag"],
                            source_ids["stackexchange"], today, totals,
                        )

    logger.info("collect_once_adoption complete: %s", totals)
    return totals


async def _collect_github(
    client, conn, bucket, settings, entity_id, repo, source_id, today, totals
) -> None:
    try:
        await bucket.acquire()
        totals["api_calls"] += 1
        resp = await client.get(f"{GH_API_URL}/repos/{repo}", headers=gh_headers(settings))
        resp.raise_for_status()
        stars = resp.json().get("stargazers_count")
        if stars is not None:
            totals["rows"] += await _upsert(
                conn, entity_id, source_id, "stars_total", [(today, float(stars))]
            )

        await bucket.acquire()
        totals["api_calls"] += 1
        resp = await client.get(
            f"{GH_API_URL}/repos/{repo}/releases",
            params={"per_page": 100},
            headers=gh_headers(settings),
        )
        resp.raise_for_status()
        totals["rows"] += await _upsert(
            conn, entity_id, source_id, "releases", release_rows(resp.json(), today)
        )
    except Exception as exc:  # noqa: BLE001 - one bad repo must not stop the pass
        logger.warning("adoption github %s failed: %s", repo, exc)
        totals["errors"] += 1


async def _collect_stackexchange(
    client, conn, bucket, entity_id, tag, source_id, today, totals
) -> None:
    """New-question counts for a tag, newest-first within the window.

    Unkeyed quota is 300 req/day per IP, so pages are capped; when the cap
    cuts the window short the partially-covered day is dropped (see se_rows).
    """
    fromdate = int(
        datetime.combine(
            today - timedelta(days=SE_WINDOW_DAYS), datetime.min.time(), tzinfo=UTC
        ).timestamp()
    )
    items: list[dict[str, Any]] = []
    truncated = False
    try:
        for page in range(1, SE_PAGES_MAX + 1):
            await bucket.acquire()
            totals["api_calls"] += 1
            resp = await client.get(
                SE_QUESTIONS_URL,
                params={
                    "tagged": tag, "site": SE_SITE, "order": "desc",
                    "sort": "creation", "fromdate": fromdate,
                    "pagesize": SE_PAGE_SIZE, "page": page,
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            items.extend(payload.get("items") or [])
            if not payload.get("has_more"):
                break
            if page == SE_PAGES_MAX:
                truncated = True
        totals["rows"] += await _upsert(
            conn, entity_id, source_id, "questions",
            se_rows(items, today, truncated=truncated),
        )
    except Exception as exc:  # noqa: BLE001 - one bad tag must not stop the pass
        logger.warning("adoption stackexchange %s failed: %s", tag, exc)
        totals["errors"] += 1


async def _collect_json(
    client, conn, bucket, totals, url, entity_id, source_id, metric, parser
) -> None:
    try:
        await bucket.acquire()
        totals["api_calls"] += 1
        resp = await client.get(url)
        resp.raise_for_status()
        totals["rows"] += await _upsert(
            conn, entity_id, source_id, metric, parser(resp.json())
        )
    except Exception as exc:  # noqa: BLE001 - one bad package must not stop the pass
        logger.warning("adoption %s failed: %s", url, exc)
        totals["errors"] += 1
