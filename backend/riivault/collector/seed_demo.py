"""Demo data seeding (dev/verification only).

Populates the derived tables + weekly_issue with values that mirror the
design mock (``design/index.html``). Live-query anchored data (mention_daily,
sentiment_daily) is placed relative to ``date.today()`` so the API's
``CURRENT_DATE``-based queries return the intended change_pct / sparks whenever
seeding runs. Everything is idempotent (targeted deletes + upserts).

Approximate values are intentional — fidelity to the design's headline numbers
matters more than exactness.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from ..config import Settings, get_settings
from ..db import pool_context

logger = logging.getLogger("riivault.seed")

# 7 entities: 5 tracked products + 2 topics (lead + sentiment focus).
ENTITIES = [
    {"type": "product", "name": "Cursor",
     "aliases": ["Cursor", "Cursor AI", "cursor.sh"],
     "metadata": {"tracked": True, "context": "r/programming"}},
    {"type": "product", "name": "Notion AI",
     "aliases": ["Notion AI", "Notion"],
     "metadata": {"tracked": True, "context": "r/productivity"}},
    {"type": "product", "name": "Zapier",
     "aliases": ["Zapier"],
     "metadata": {"tracked": True, "context": "r/nocode"}},
    {"type": "product", "name": "Supabase",
     "aliases": ["Supabase"],
     "metadata": {"tracked": True, "context": "r/webdev"}},
    {"type": "product", "name": "Framer",
     "aliases": ["Framer"],
     "metadata": {"tracked": True, "context": "r/web_design"}},
    {"type": "topic", "name": "AI wrapper",
     "aliases": ["AI wrapper", "AI wrappers", "AI-wrapper", "GPT wrapper"],
     "metadata": {"tracked": False, "context": "r/SaaS"}},
    {"type": "topic", "name": "AI note-takers",
     "aliases": ["AI note-taker", "AI note-takers", "AI notetaker", "AI note taker"],
     "metadata": {"tracked": False, "context": "r/productivity"}},
]

# (prev-7-days, last-7-days) daily mention counts -> exact change_pct in the design.
TRACKED_COUNTS = {
    "Cursor":    ([7, 7, 7, 7, 7, 7, 8], [7, 8, 9, 11, 12, 14, 15]),    # +52%
    "Notion AI": ([15, 15, 14, 14, 14, 14, 14], [15, 14, 13, 12, 11, 11, 10]),  # -14%
    "Zapier":    ([15, 14, 14, 14, 14, 15, 14], [15, 14, 14, 13, 13, 13, 12]),  # -6%
    "Supabase":  ([15, 14, 14, 14, 14, 15, 14], [15, 16, 17, 18, 20, 21, 22]),  # +29%
    "Framer":    ([15, 14, 14, 14, 14, 15, 14], [14, 15, 15, 16, 16, 17, 18]),  # +11%
}

# feature_request ledger rows: (entity, kind, normalized_text, occurrences, momentum)
FEATURE_REQUESTS = [
    ("Zapier", "pain_point", "Per-seat pricing punishes small teams", 214, 0.61),
    ("Notion AI", "pain_point", '"AI features feel bolted-on, not useful"', 188, 0.47),
    ("Notion AI", "switch_intent", "Leaving Notion for something faster on mobile", 141, 0.38),
    ("Supabase", "feature_request", "Wants offline-first / local export before trusting a tool", 97, 0.22),
    ("Supabase", "pain_point", "Onboarding assumes you already know the jargon", 84, 0.15),
    ("Zapier", "feature_request", "Asking for usage-based pricing instead of tiers", 76, 0.09),
]

# emerging_signal rows: (signal_type, strength, outcome, detected_days_ago)
EMERGING_SIGNALS = [
    ("spike", 0.86, {
        "entity": '"Local-first" SaaS',
        "description": "Mentions up 4.2× in three weeks across dev communities. "
                       "Driven by data-ownership and offline anxiety, not a single launch.",
        "detected_label": "Detected wk25",
    }, 14),
    ("new_topic", 0.71, {
        "entity": 'Agent "handoff" UX',
        "description": "A vocabulary forming around multi-agent handoffs and trust "
                       "boundaries — no incumbent owns the term yet. Green-field naming window.",
        "detected_label": "Detected wk26",
    }, 7),
    ("sentiment_flip", 0.64, {
        "entity": "No-code AI builders",
        "description": 'Flipped from net-positive to net-negative as "vibe-coded" apps '
                       "hit maintenance reality. Complaints center on debugging opacity.",
        "detected_label": "Detected wk27",
    }, 1),
]

LEAD_SERIES = [
    ("2026-04-13", 34), ("2026-04-20", 38), ("2026-04-27", 37), ("2026-05-04", 45),
    ("2026-05-11", 60), ("2026-05-18", 54), ("2026-05-25", 70), ("2026-06-01", 82),
    ("2026-06-08", 94), ("2026-06-15", 114), ("2026-06-22", 142), ("2026-06-29", 168),
]

HEADLINE = "The AI-wrapper honeymoon is ending — churn complaints tripled in six weeks"
DEK = (
    "Across founder communities, the story flipped from “look what I shipped” to "
    "“why is everyone leaving.” Threads about thin GPT wrappers now skew toward "
    "retention, pricing fatigue, and “this is just a prompt” — the first sustained "
    "negative turn riivault has logged for the category since tracking began."
)


async def seed_demo(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    today = date.today()

    async with pool_context(settings) as pool:
        async with pool.acquire() as conn:
            source_id = await conn.fetchval(
                "SELECT source_id FROM source WHERE name = 'reddit'"
            )
            async with conn.transaction():
                ids = await _seed_entities(conn)
                await _seed_mentions(conn, ids, source_id, today)
                await _seed_sentiment(conn, ids["AI note-takers"], source_id, today)
                await _seed_feature_requests(conn, ids, today)
                await _seed_emerging(conn, today)
                await _seed_weekly_issue(conn, ids)

    summary = {"entities": len(ENTITIES), "feature_requests": len(FEATURE_REQUESTS),
               "emerging_signals": len(EMERGING_SIGNALS), "week_start": "2026-06-29"}
    logger.info("seed_demo complete: %s", summary)
    return summary


async def _seed_entities(conn) -> dict[str, int]:
    for e in ENTITIES:
        await conn.execute(
            """
            INSERT INTO entity (type, canonical_name, aliases, metadata)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (type, canonical_name) DO UPDATE
                SET aliases = EXCLUDED.aliases, metadata = EXCLUDED.metadata
            """,
            e["type"], e["name"], e["aliases"], e["metadata"],
        )
    rows = await conn.fetch("SELECT entity_id, canonical_name FROM entity")
    return {r["canonical_name"]: r["entity_id"] for r in rows}


async def _seed_mentions(conn, ids: dict[str, int], source_id: int, today: date) -> None:
    rows: list[tuple] = []
    for name, (prev7, last7) in TRACKED_COUNTS.items():
        eid = ids[name]
        counts = prev7 + last7  # 14 daily values, oldest .. today
        for i, c in enumerate(counts):
            day = today - timedelta(days=13 - i)
            rows.append((day, eid, source_id, "", c, max(1, int(c * 0.8)),
                         c * 15, 0.9, c * 4))

    # Lead topic "AI wrapper": 90 days of rising daily mentions (feeds series API).
    wid = ids["AI wrapper"]
    for i in range(90):
        day = today - timedelta(days=89 - i)
        c = round(3 + 21 * (i / 89))
        rows.append((day, wid, source_id, "", c, max(1, int(c * 0.8)),
                     c * 18, 0.88, c * 6))

    await conn.execute(
        "DELETE FROM mention_daily WHERE entity_id = ANY($1::bigint[]) AND source_id = $2",
        list(ids.values()), source_id,
    )
    await conn.executemany(
        """
        INSERT INTO mention_daily
            (day, entity_id, source_id, subreddit, mention_count, unique_authors,
             score_sum, upvote_ratio_avg, comment_sum)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        """,
        rows,
    )


async def _seed_sentiment(conn, entity_id: int, source_id: int, today: date) -> None:
    rows: list[tuple] = []
    for i in range(90):
        day = today - timedelta(days=89 - i)
        # linear decline from +0.22 (90d ago) to -0.31 (today)
        v = round(0.22 + (-0.31 - 0.22) * (i / 89), 3)
        if v >= 0.05:
            pos, neg, neu = 0.6, 0.1, 0.3
        elif v <= -0.05:
            pos, neg, neu = 0.1, 0.6, 0.3
        else:
            pos, neg, neu = 0.3, 0.3, 0.4
        rows.append((day, entity_id, source_id, v, 0.2, pos, neg, neu, 40))

    await conn.execute(
        "DELETE FROM sentiment_daily WHERE entity_id = $1 AND source_id = $2",
        entity_id, source_id,
    )
    await conn.executemany(
        """
        INSERT INTO sentiment_daily
            (day, entity_id, source_id, sentiment_mean, sentiment_std,
             pos_ratio, neg_ratio, neu_ratio, sample_size)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        """,
        rows,
    )


async def _seed_feature_requests(conn, ids: dict[str, int], today: date) -> None:
    texts = [fr[2] for fr in FEATURE_REQUESTS]
    await conn.execute("DELETE FROM topic_daily WHERE label = ANY($1::text[])", texts)
    await conn.execute(
        "DELETE FROM feature_request WHERE normalized_text = ANY($1::text[])", texts
    )

    # topic_daily reused as per-day FR volume time-series (rising curve). The
    # authoritative momentum for the API is stored on feature_request.momentum.
    vol_prev, vol_last = [3, 3, 4, 4, 4, 5, 5], [6, 7, 7, 8, 9, 10, 11]
    topic_rows: list[tuple] = []
    for entity_name, kind, text, occ, momentum in FEATURE_REQUESTS:
        eid = ids[entity_name]
        fr_id = await conn.fetchval(
            """
            INSERT INTO feature_request
                (entity_id, kind, normalized_text, first_seen, last_seen,
                 occurrences, momentum, example_ref)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NULL)
            RETURNING fr_id
            """,
            eid, kind, text, today - timedelta(days=45), today, occ, momentum,
        )
        for i, vol in enumerate(vol_prev + vol_last):
            day = today - timedelta(days=13 - i)
            topic_rows.append((day, fr_id, eid, text, vol, momentum))

    await conn.executemany(
        """
        INSERT INTO topic_daily (day, topic_id, entity_id, label, volume, momentum)
        VALUES ($1,$2,$3,$4,$5,$6)
        """,
        topic_rows,
    )


async def _seed_emerging(conn, today: date) -> None:
    names = [sig[2]["entity"] for sig in EMERGING_SIGNALS]
    await conn.execute(
        "DELETE FROM emerging_signal WHERE outcome->>'entity' = ANY($1::text[])", names
    )
    for signal_type, strength, outcome, days_ago in EMERGING_SIGNALS:
        await conn.execute(
            """
            INSERT INTO emerging_signal
                (entity_id, detected_at, signal_type, strength, validated, outcome)
            VALUES (NULL, $1, $2, $3, TRUE, $4)
            """,
            today - timedelta(days=days_ago), signal_type, strength, outcome,
        )


async def _seed_weekly_issue(conn, ids: dict[str, int]) -> None:
    payload = {
        "niche": "SaaS",
        "communities": 34,
        "generated_at": "2026-07-03T09:00:00Z",
        "lead": {
            "eyebrow": "Lead signal · momentum +38%",
            "momentum_pct": 38.0,
            "threads": 1240,
            "comments": 8900,
            "window_weeks": 12,
            "subreddits": ["r/SaaS", "r/indiehackers", "r/microsaas"],
            "chart_title": 'Mention Index — "AI wrapper" churn',
            "delta_label": "+40% w/w",
            "delta_value": 168,
            "series": [{"period": p, "value": v} for p, v in LEAD_SERIES],
        },
        "sentiment_focus": {"entity_id": ids["AI note-takers"], "label": '"AI note-takers"'},
        "migration": {
            "origin": "r/Notion",
            "n": 141,
            "title": "where r/Notion posters go",
            "destinations": [
                {"name": "r/Obsidian", "share": 0.41},
                {"name": "r/logseq", "share": 0.23},
                {"name": "r/AppFlowy", "share": 0.17},
                {"name": "r/Anytype", "share": 0.12},
                {"name": "stayed", "share": 0.07},
            ],
        },
    }
    await conn.execute(
        """
        INSERT INTO weekly_issue
            (issue_no, week_start, week_end, headline, dek, lead_entity_id, payload, published_at)
        VALUES (27, DATE '2026-06-29', DATE '2026-07-05', $1, $2, $3, $4,
                TIMESTAMPTZ '2026-07-03 09:00:00+00')
        ON CONFLICT (week_start) DO UPDATE
            SET week_end = EXCLUDED.week_end, headline = EXCLUDED.headline,
                dek = EXCLUDED.dek, lead_entity_id = EXCLUDED.lead_entity_id,
                payload = EXCLUDED.payload, published_at = EXCLUDED.published_at
        """,
        HEADLINE, DEK, ids["AI wrapper"], payload,
    )
    # Keep the SERIAL ahead of the explicit issue_no=27 so real publishes don't collide.
    await conn.execute(
        """
        SELECT setval(pg_get_serial_sequence('weekly_issue', 'issue_no'),
                      GREATEST((SELECT max(issue_no) FROM weekly_issue), 1))
        """
    )
