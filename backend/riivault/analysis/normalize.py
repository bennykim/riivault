"""Baseline normalization for mention time-series (pure functions, no DB).

Raw week-over-week growth is misleading on tiny bases (1 -> 10 mentions reads
as "+900%"), so lead selection ranks entities by how far the current week sits
above that entity's own trailing baseline (z-score with a Poisson-style floor)
and requires a minimum absolute volume before an entity can lead at all.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

# An entity must have at least this many mentions in the last 7 days to
# qualify as the week's lead — below this, growth percentages are noise.
MIN_LEAD_MENTIONS = 20

# Trailing baseline: this many 7-day blocks immediately before the
# last7/prev7 comparison windows.
BASELINE_BLOCKS = 11


def window_sum(daily: dict[date, int], end: date, days: int) -> int:
    """Sum of counts in the half-open window ``(end - days, end]``."""
    return sum(
        daily.get(end - timedelta(days=offset), 0) for offset in range(days)
    )


def baseline_stats(values: list[float]) -> tuple[float, float]:
    """Mean and population standard deviation (0.0, 0.0 for empty input)."""
    if not values:
        return 0.0, 0.0
    mean = sum(values) / len(values)
    std = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
    return mean, std


def zscore(value: float, mean: float, std: float) -> float:
    """Standardized deviation with a Poisson-style denominator floor.

    Count data has std ~ sqrt(mean) under the null, so the denominator never
    drops below ``max(sqrt(mean), 1)`` — otherwise sparse, near-constant
    baselines make any small change look like a many-sigma event.
    """
    denom = max(std, mean**0.5, 1.0)
    return (value - mean) / denom


def lead_scores(
    daily_by_entity: dict[int, dict[date, int]],
    today: date,
    min_mentions: int = MIN_LEAD_MENTIONS,
) -> list[dict[str, Any]]:
    """Score entities for weekly-lead selection.

    ``daily_by_entity`` maps entity_id -> {day: mention_count} (missing days
    count as 0). Returns qualified entities (last7 >= ``min_mentions``) sorted
    by baseline z-score descending; when nothing qualifies, falls back to all
    entities with any current volume sorted by last7 (so a young, low-volume
    index still publishes an honest volume lead).

    Each score dict: ``{entity_id, last7, prev7, growth, zscore}`` where
    ``growth`` is None when prev7 == 0 (undefined, not "+inf%").
    """
    scores: list[dict[str, Any]] = []
    for entity_id, daily in daily_by_entity.items():
        last7 = window_sum(daily, today, 7)
        if last7 == 0:
            continue
        prev7 = window_sum(daily, today - timedelta(days=7), 7)
        blocks = [
            float(window_sum(daily, today - timedelta(days=14 + 7 * k), 7))
            for k in range(BASELINE_BLOCKS)
        ]
        mean, std = baseline_stats(blocks)
        scores.append(
            {
                "entity_id": entity_id,
                "last7": last7,
                "prev7": prev7,
                "growth": ((last7 - prev7) / prev7) if prev7 else None,
                "zscore": zscore(float(last7), mean, std),
            }
        )

    qualified = [s for s in scores if s["last7"] >= min_mentions]
    if qualified:
        return sorted(qualified, key=lambda s: s["zscore"], reverse=True)
    return sorted(scores, key=lambda s: s["last7"], reverse=True)
