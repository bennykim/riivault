"""Statistical emerging-signal detection (volume spikes; no LLM involved).

An entity "spikes" when its recent mention volume sits far above its own
trailing daily baseline. Detection is pure statistics — every published signal
carries the underlying numbers in ``outcome`` so it can be audited (and later
validated via ``signal_outcome`` track records).

Honesty gate: a baseline is only trustworthy where collection has actually
been running for the whole window — freshly onboarded sources look like a
giant "spike" at their own collection start (backfilled history is partial).
Sources younger than ``BASELINE_DAYS`` (per ``collection_run``) are therefore
excluded; until at least one source matures, detection runs empty by design.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from ..config import Settings, get_settings
from ..db import pool_context
from .normalize import baseline_stats

logger = logging.getLogger("riivault.signals")

BASELINE_DAYS = 28
RECENT_DAYS = 3
Z_THRESHOLD = 3.0
MIN_RECENT_MENTIONS = 15
MIN_BASELINE_ACTIVE_DAYS = 14  # baseline must have data on at least this many days
DEDUPE_DAYS = 7                # one spike signal per entity per week at most


def detect_spikes(
    daily_by_entity: dict[int, dict[date, int]],
    today: date,
    baseline_days: int = BASELINE_DAYS,
    recent_days: int = RECENT_DAYS,
    z_threshold: float = Z_THRESHOLD,
    min_recent: int = MIN_RECENT_MENTIONS,
) -> list[dict[str, Any]]:
    """Find entities whose recent volume spikes above their baseline (pure).

    The recent window is ``(today - recent_days, today]``; the baseline is the
    ``baseline_days`` daily counts before it (missing days count as 0, but at
    least ``MIN_BASELINE_ACTIVE_DAYS`` non-zero days are required — an entity
    without an established baseline cannot "spike", it is merely new).

    Returns ``{entity_id, recent, expected, zscore}`` per detection, where the
    z-score compares the recent sum against ``recent_days * mean`` with a
    ``std * sqrt(recent_days)`` denominator (floored like normalize.zscore).
    """
    detections: list[dict[str, Any]] = []
    for entity_id, daily in daily_by_entity.items():
        recent = sum(
            daily.get(today - timedelta(days=offset), 0)
            for offset in range(recent_days)
        )
        if recent < min_recent:
            continue
        baseline = [
            float(daily.get(today - timedelta(days=recent_days + offset), 0))
            for offset in range(baseline_days)
        ]
        if sum(1 for v in baseline if v > 0) < MIN_BASELINE_ACTIVE_DAYS:
            continue
        mean, std = baseline_stats(baseline)
        expected = recent_days * mean
        denom = max(std, mean**0.5, 1.0) * recent_days**0.5
        z = (recent - expected) / denom
        if z < z_threshold:
            continue
        detections.append(
            {
                "entity_id": entity_id,
                "recent": recent,
                "expected": expected,
                "zscore": z,
            }
        )
    return sorted(detections, key=lambda d: d["zscore"], reverse=True)


async def run_detect_signals(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    today = datetime.now(UTC).date()

    async with pool_context(settings) as pool:
        async with pool.acquire() as conn:
            eligible = await conn.fetch(
                """
                SELECT s.source_id, s.name, min(cr.started_at) AS first_run
                  FROM collection_run cr
                  JOIN source s USING (source_id)
                 GROUP BY s.source_id, s.name
                HAVING min(cr.started_at) <= now() - ($1::int * interval '1 day')
                """,
                BASELINE_DAYS,
            )
            eligible_ids = [r["source_id"] for r in eligible]
            if not eligible_ids:
                logger.info(
                    "detect_signals: no source has %sd of collection history yet; "
                    "skipping (by design — young baselines fake spikes)",
                    BASELINE_DAYS,
                )
                return {"signals": 0, "eligible_sources": []}

            rows = await conn.fetch(
                """
                SELECT entity_id, day, SUM(mention_count) AS cnt
                  FROM mention_daily
                 WHERE subreddit = '' AND source_id = ANY($1::int[])
                   AND day > CURRENT_DATE - ($2::int + $3::int)
                 GROUP BY entity_id, day
                """,
                eligible_ids, BASELINE_DAYS, RECENT_DAYS,
            )
            daily_by_entity: dict[int, dict[date, int]] = {}
            for r in rows:
                daily_by_entity.setdefault(r["entity_id"], {})[r["day"]] = int(r["cnt"])

            detections = detect_spikes(daily_by_entity, today)
            inserted = 0
            for det in detections:
                already = await conn.fetchval(
                    """
                    SELECT 1 FROM emerging_signal
                     WHERE entity_id = $1 AND signal_type = 'spike'
                       AND detected_at > $2::date - $3::int
                    """,
                    det["entity_id"], today, DEDUPE_DAYS,
                )
                if already:
                    continue
                name = await conn.fetchval(
                    "SELECT canonical_name FROM entity WHERE entity_id = $1",
                    det["entity_id"],
                )
                outcome = {
                    "entity": name,
                    "description": (
                        f"Mentions {det['zscore']:.1f}σ above the "
                        f"{BASELINE_DAYS}-day baseline ({det['recent']} in "
                        f"{RECENT_DAYS} days vs ~{det['expected']:.0f} expected)."
                    ),
                    "detected_label": f"Detected {today.isoformat()}",
                    "evidence": {
                        "recent": det["recent"],
                        "expected": round(det["expected"], 2),
                        "zscore": round(det["zscore"], 2),
                        "sources": [r["name"] for r in eligible],
                    },
                }
                await conn.execute(
                    """
                    INSERT INTO emerging_signal
                        (entity_id, detected_at, signal_type, strength, outcome)
                    VALUES ($1, $2, 'spike', $3, $4)
                    """,
                    det["entity_id"], today,
                    min(round(det["zscore"] / 6.0, 2), 0.99),
                    outcome,
                )
                inserted += 1

    summary = {
        "signals": inserted,
        "eligible_sources": [r["name"] for r in eligible],
    }
    logger.info("detect_signals complete: %s", summary)
    return summary
