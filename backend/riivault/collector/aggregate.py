"""Idempotent daily aggregation of raw_* into derived tables.

For every day that currently has raw data (raw is <=48h TTL), the day's rows in
``mention_daily`` / ``sentiment_daily`` are DELETEd and recomputed from scratch,
so re-running is safe. Entity matching happens here (submission = title+selftext,
comment = body). VoC extraction runs only when an Anthropic key is configured.

``aggregate_mentions`` / ``aggregate_sentiments`` are pure functions so the
aggregation math is unit-testable without a database.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from typing import Any

from ..config import Settings, get_settings
from ..db import pool_context
from ..entities import load_matcher
from ..nlp.sentiment import sentiment_compound
from ..nlp.voc import classify_documents

logger = logging.getLogger("riivault.aggregate")

SENTIMENT_THRESHOLD = 0.05
VOC_TOP_N = 100


# --------------------------------------------------------------------------- #
# Pure calculation functions (unit-testable, no DB)                           #
# --------------------------------------------------------------------------- #
def aggregate_mentions(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate per-mention events into ``mention_daily`` rows.

    Each event: ``{day, entity_id, subreddit, author_hash, score, upvote_ratio,
    num_comments}``. Emits one row per (day, entity, subreddit) *and* an overall
    (day, entity, subreddit='') row spanning all subreddits.
    """
    acc: dict[tuple, dict[str, Any]] = {}

    def bump(key: tuple, ev: dict[str, Any]) -> None:
        stats = acc.setdefault(
            key,
            {"mention_count": 0, "authors": set(), "score_sum": 0,
             "upvote_ratios": [], "comment_sum": 0},
        )
        stats["mention_count"] += 1
        if ev.get("author_hash"):
            stats["authors"].add(ev["author_hash"])
        stats["score_sum"] += ev.get("score") or 0
        if ev.get("upvote_ratio") is not None:
            stats["upvote_ratios"].append(ev["upvote_ratio"])
        stats["comment_sum"] += ev.get("num_comments") or 0

    for ev in events:
        day = ev["day"]
        eid = ev["entity_id"]
        sub = ev.get("subreddit") or ""
        bump((day, eid, sub), ev)
        if sub != "":
            bump((day, eid, ""), ev)

    rows: list[dict[str, Any]] = []
    for (day, eid, sub), stats in acc.items():
        ratios = stats["upvote_ratios"]
        rows.append(
            {
                "day": day,
                "entity_id": eid,
                "subreddit": sub,
                "mention_count": stats["mention_count"],
                "unique_authors": len(stats["authors"]),
                "score_sum": stats["score_sum"],
                "upvote_ratio_avg": (sum(ratios) / len(ratios)) if ratios else None,
                "comment_sum": stats["comment_sum"],
            }
        )
    return rows


def aggregate_sentiments(
    events: Iterable[dict[str, Any]], threshold: float = SENTIMENT_THRESHOLD
) -> list[dict[str, Any]]:
    """Aggregate per-mention sentiment events into ``sentiment_daily`` rows.

    Each event: ``{day, entity_id, compound}``. pos/neg/neu use a +/-threshold band.
    ``sentiment_std`` is the population standard deviation.
    """
    buckets: dict[tuple, list[float]] = defaultdict(list)
    for ev in events:
        buckets[(ev["day"], ev["entity_id"])].append(float(ev["compound"]))

    rows: list[dict[str, Any]] = []
    for (day, eid), vals in buckets.items():
        n = len(vals)
        mean = sum(vals) / n
        std = (sum((v - mean) ** 2 for v in vals) / n) ** 0.5
        pos = sum(1 for v in vals if v >= threshold)
        neg = sum(1 for v in vals if v <= -threshold)
        neu = n - pos - neg
        rows.append(
            {
                "day": day,
                "entity_id": eid,
                "sentiment_mean": mean,
                "sentiment_std": std,
                "pos_ratio": pos / n,
                "neg_ratio": neg / n,
                "neu_ratio": neu / n,
                "sample_size": n,
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# DB orchestration                                                            #
# --------------------------------------------------------------------------- #
async def run_aggregate(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    async with pool_context(settings) as pool:
        async with pool.acquire() as conn:
            source_id = await conn.fetchval(
                "SELECT source_id FROM source WHERE name = 'reddit'"
            )
            matcher = await load_matcher(conn)
            submissions = await conn.fetch(
                """
                SELECT reddit_id, subreddit, author_hash, title, selftext,
                       score, upvote_ratio, num_comments, created_utc
                  FROM raw_submission
                """
            )
            comments = await conn.fetch(
                """
                SELECT reddit_id, subreddit, author_hash, body, score, created_utc
                  FROM raw_comment
                """
            )

            mention_events: list[dict[str, Any]] = []
            sentiment_events: list[dict[str, Any]] = []
            voc_candidates: list[dict[str, Any]] = []
            affected_days: set[date] = set()

            for row in submissions:
                day = row["created_utc"].date()
                affected_days.add(day)
                text = f"{row['title'] or ''} {row['selftext'] or ''}".strip()
                entity_ids = matcher.match(text)
                if not entity_ids:
                    continue
                compound = sentiment_compound(text)
                for eid in entity_ids:
                    mention_events.append(
                        {
                            "day": day, "entity_id": eid, "subreddit": row["subreddit"],
                            "author_hash": row["author_hash"], "score": row["score"],
                            "upvote_ratio": row["upvote_ratio"],
                            "num_comments": row["num_comments"],
                        }
                    )
                    sentiment_events.append(
                        {"day": day, "entity_id": eid, "compound": compound}
                    )
                voc_candidates.append(
                    {"day": day, "score": row["score"] or 0, "text": text,
                     "reddit_id": row["reddit_id"], "entity_ids": entity_ids}
                )

            for row in comments:
                day = row["created_utc"].date()
                affected_days.add(day)
                text = row["body"] or ""
                entity_ids = matcher.match(text)
                if not entity_ids:
                    continue
                compound = sentiment_compound(text)
                for eid in entity_ids:
                    mention_events.append(
                        {
                            "day": day, "entity_id": eid, "subreddit": row["subreddit"],
                            "author_hash": row["author_hash"], "score": row["score"],
                            "upvote_ratio": None, "num_comments": 0,
                        }
                    )
                    sentiment_events.append(
                        {"day": day, "entity_id": eid, "compound": compound}
                    )
                voc_candidates.append(
                    {"day": day, "score": row["score"] or 0, "text": text,
                     "reddit_id": row["reddit_id"], "entity_ids": entity_ids}
                )

            mention_rows = aggregate_mentions(mention_events)
            sentiment_rows = aggregate_sentiments(sentiment_events)

            async with conn.transaction():
                for day in affected_days:
                    await conn.execute(
                        "DELETE FROM mention_daily WHERE day = $1 AND source_id = $2",
                        day, source_id,
                    )
                    await conn.execute(
                        "DELETE FROM sentiment_daily WHERE day = $1 AND source_id = $2",
                        day, source_id,
                    )
                if mention_rows:
                    await conn.executemany(
                        """
                        INSERT INTO mention_daily
                            (day, entity_id, source_id, subreddit, mention_count,
                             unique_authors, score_sum, upvote_ratio_avg, comment_sum)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                        """,
                        [
                            (m["day"], m["entity_id"], source_id, m["subreddit"],
                             m["mention_count"], m["unique_authors"], m["score_sum"],
                             m["upvote_ratio_avg"], m["comment_sum"])
                            for m in mention_rows
                        ],
                    )
                if sentiment_rows:
                    await conn.executemany(
                        """
                        INSERT INTO sentiment_daily
                            (day, entity_id, source_id, sentiment_mean, sentiment_std,
                             pos_ratio, neg_ratio, neu_ratio, sample_size)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                        """,
                        [
                            (s["day"], s["entity_id"], source_id, s["sentiment_mean"],
                             s["sentiment_std"], s["pos_ratio"], s["neg_ratio"],
                             s["neu_ratio"], s["sample_size"])
                            for s in sentiment_rows
                        ],
                    )

            if settings.voc_enabled:
                await _run_voc(conn, settings, voc_candidates)
            else:
                logger.info("VoC step skipped (no ANTHROPIC_API_KEY)")

    summary = {
        "days": len(affected_days),
        "mention_rows": len(mention_rows),
        "sentiment_rows": len(sentiment_rows),
    }
    logger.info("aggregate complete: %s", summary)
    return summary


async def run_aggregate_hn(settings: Settings | None = None) -> dict:
    """Idempotent daily aggregation of ``raw_hn_item`` into the derived tables.

    Mirrors ``run_aggregate`` for the Hacker News source: it reads all raw HN
    items, matches entities on title+body, and reuses the pure ``aggregate_mentions``
    / ``aggregate_sentiments`` functions. HN has no subreddit concept, so every
    mention event uses ``subreddit=''`` (overall only). Affected days are DELETEd
    for ``source_id=hackernews`` then re-INSERTed, so re-running is safe.

    VoC/topic extraction is intentionally deferred for HN (the Reddit VoC path is
    Reddit-permalink specific).
    """
    settings = settings or get_settings()
    async with pool_context(settings) as pool:
        async with pool.acquire() as conn:
            source_id = await conn.fetchval(
                "SELECT source_id FROM source WHERE name = 'hackernews'"
            )
            matcher = await load_matcher(conn)
            items = await conn.fetch(
                """
                SELECT hn_id, kind, author_hash, title, body,
                       points, num_comments, created_utc
                  FROM raw_hn_item
                """
            )

            mention_events: list[dict[str, Any]] = []
            sentiment_events: list[dict[str, Any]] = []
            affected_days: set[date] = set()

            for row in items:
                day = row["created_utc"].date()
                affected_days.add(day)
                text = f"{row['title'] or ''} {row['body'] or ''}".strip()
                entity_ids = matcher.match(text)
                if not entity_ids:
                    continue
                compound = sentiment_compound(text)
                for eid in entity_ids:
                    mention_events.append(
                        {
                            "day": day, "entity_id": eid, "subreddit": "",
                            "author_hash": row["author_hash"], "score": row["points"],
                            "upvote_ratio": None,
                            "num_comments": row["num_comments"] or 0,
                        }
                    )
                    sentiment_events.append(
                        {"day": day, "entity_id": eid, "compound": compound}
                    )

            mention_rows = aggregate_mentions(mention_events)
            sentiment_rows = aggregate_sentiments(sentiment_events)

            async with conn.transaction():
                for day in affected_days:
                    await conn.execute(
                        "DELETE FROM mention_daily WHERE day = $1 AND source_id = $2",
                        day, source_id,
                    )
                    await conn.execute(
                        "DELETE FROM sentiment_daily WHERE day = $1 AND source_id = $2",
                        day, source_id,
                    )
                if mention_rows:
                    await conn.executemany(
                        """
                        INSERT INTO mention_daily
                            (day, entity_id, source_id, subreddit, mention_count,
                             unique_authors, score_sum, upvote_ratio_avg, comment_sum)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                        """,
                        [
                            (m["day"], m["entity_id"], source_id, m["subreddit"],
                             m["mention_count"], m["unique_authors"], m["score_sum"],
                             m["upvote_ratio_avg"], m["comment_sum"])
                            for m in mention_rows
                        ],
                    )
                if sentiment_rows:
                    await conn.executemany(
                        """
                        INSERT INTO sentiment_daily
                            (day, entity_id, source_id, sentiment_mean, sentiment_std,
                             pos_ratio, neg_ratio, neu_ratio, sample_size)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                        """,
                        [
                            (s["day"], s["entity_id"], source_id, s["sentiment_mean"],
                             s["sentiment_std"], s["pos_ratio"], s["neg_ratio"],
                             s["neu_ratio"], s["sample_size"])
                            for s in sentiment_rows
                        ],
                    )

    summary = {
        "days": len(affected_days),
        "mention_rows": len(mention_rows),
        "sentiment_rows": len(sentiment_rows),
    }
    logger.info("aggregate_hn complete: %s", summary)
    return summary


async def _run_voc(conn, settings: Settings, candidates: list[dict[str, Any]]) -> None:
    if not candidates:
        return
    top = sorted(candidates, key=lambda c: c["score"], reverse=True)[:VOC_TOP_N]
    records = await classify_documents([c["text"][:1000] for c in top], settings)
    if not records:
        return

    today = date.today()
    name_rows = await conn.fetch("SELECT entity_id, canonical_name FROM entity")
    name_to_id = {r["canonical_name"].lower(): r["entity_id"] for r in name_rows}
    daily_volume: dict[tuple, int] = defaultdict(int)

    for rec in records:
        idx = rec.get("index")
        if not isinstance(idx, int) or not (0 <= idx < len(top)):
            continue
        cand = top[idx]
        entity_id = None
        if rec.get("entity_name"):
            entity_id = name_to_id.get(rec["entity_name"].lower())
        if entity_id is None:
            entity_id = next(iter(cand["entity_ids"]))
        norm = rec["normalized_text"]
        permalink = _permalink(cand["reddit_id"])
        fr_id = await _upsert_feature_request(
            conn, entity_id, rec["kind"], norm, permalink, today
        )
        daily_volume[(fr_id, entity_id, norm)] += 1

    # topic_daily is intentionally reused to hold per-day FR volume as a
    # time-series (differs from the schema comment's "topic cluster" use).
    for (fr_id, entity_id, label), volume in daily_volume.items():
        await conn.execute(
            """
            INSERT INTO topic_daily (day, topic_id, entity_id, label, volume)
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (day, topic_id) DO UPDATE
                SET volume = topic_daily.volume + EXCLUDED.volume,
                    label = EXCLUDED.label,
                    entity_id = EXCLUDED.entity_id
            """,
            today, fr_id, entity_id, label, volume,
        )
    await _recompute_fr_momentum(conn)


def _permalink(reddit_id: str) -> str:
    short = reddit_id.split("_", 1)[-1]
    return f"https://www.reddit.com/comments/{short}"


async def _upsert_feature_request(
    conn, entity_id: int, kind: str, norm: str, permalink: str, today: date
) -> int:
    row = await conn.fetchrow(
        """
        SELECT fr_id FROM feature_request
         WHERE entity_id = $1 AND lower(normalized_text) = lower($2)
        """,
        entity_id, norm,
    )
    if row:
        await conn.execute(
            """
            UPDATE feature_request
               SET occurrences = occurrences + 1,
                   last_seen = $2,
                   example_ref = COALESCE($3, example_ref)
             WHERE fr_id = $1
            """,
            row["fr_id"], today, permalink,
        )
        return row["fr_id"]
    return await conn.fetchval(
        """
        INSERT INTO feature_request
            (entity_id, kind, normalized_text, first_seen, last_seen, occurrences, example_ref)
        VALUES ($1, $2, $3, $4, $4, 1, $5)
        RETURNING fr_id
        """,
        entity_id, kind, norm, today, permalink,
    )


async def _recompute_fr_momentum(conn) -> None:
    # momentum = sum(volume last 7d) / max(sum(volume prev 7d), 1) - 1
    await conn.execute(
        """
        UPDATE feature_request fr
           SET momentum = sub.momentum
          FROM (
            SELECT topic_id AS fr_id,
                   (COALESCE(SUM(volume) FILTER (WHERE day > CURRENT_DATE - 7), 0)::real
                    / GREATEST(
                        COALESCE(SUM(volume) FILTER (
                            WHERE day <= CURRENT_DATE - 7 AND day > CURRENT_DATE - 14), 0),
                        1)) - 1 AS momentum
              FROM topic_daily
             WHERE day > CURRENT_DATE - 14
             GROUP BY topic_id
          ) sub
         WHERE fr.fr_id = sub.fr_id
        """
    )
