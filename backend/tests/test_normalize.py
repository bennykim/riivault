from datetime import date, timedelta

from riivault.analysis.normalize import (
    baseline_stats,
    lead_scores,
    window_sum,
    zscore,
)

TODAY = date(2026, 7, 10)


def daily(counts_by_days_ago: dict[int, int]) -> dict[date, int]:
    return {TODAY - timedelta(days=ago): n for ago, n in counts_by_days_ago.items()}


def flat_series(per_day: int, days: int = 91) -> dict[date, int]:
    return {TODAY - timedelta(days=ago): per_day for ago in range(days)}


def test_window_sum_half_open_bounds():
    d = daily({0: 5, 6: 2, 7: 9})
    assert window_sum(d, TODAY, 7) == 7  # days 0..6 only; day 7 excluded
    assert window_sum(d, TODAY - timedelta(days=7), 7) == 9  # days 7..13


def test_baseline_stats_and_zscore_floor():
    mean, std = baseline_stats([4.0, 4.0, 4.0])
    assert (mean, std) == (4.0, 0.0)
    # std floored to sqrt(mean)=2, not 0 — a flat sparse baseline must not
    # turn any small change into a many-sigma event.
    assert zscore(8.0, mean, std) == 2.0
    assert baseline_stats([]) == (0.0, 0.0)


def test_micro_base_growth_does_not_beat_volume_lead():
    # Entity 1: 1 -> 10 mentions (+900% raw growth, tiny base).
    # Entity 2: steady ~70/week baseline, current week 123 (+76%).
    series = {
        1: daily({0: 5, 1: 5, 8: 1}),
        2: {**flat_series(10), **daily({i: 18 for i in range(7)})},
    }
    scores = lead_scores(series, TODAY)
    assert [s["entity_id"] for s in scores] == [2]  # entity 1 fails the floor
    top = scores[0]
    assert top["last7"] == 18 * 7
    assert top["growth"] is not None and top["growth"] > 0


def test_growth_is_none_on_zero_prior_week():
    series = {1: daily({i: 4 for i in range(7)})}  # 28 in last7, nothing before
    scores = lead_scores(series, TODAY)
    assert scores[0]["growth"] is None


def test_volume_fallback_when_nothing_qualifies():
    series = {
        1: daily({0: 3, 8: 1}),
        2: daily({0: 7, 8: 2}),
    }
    scores = lead_scores(series, TODAY)  # both below MIN_LEAD_MENTIONS
    assert [s["entity_id"] for s in scores] == [2, 1]  # ranked by last7


def test_zero_current_week_is_excluded():
    series = {1: daily({8: 5})}
    assert lead_scores(series, TODAY) == []
