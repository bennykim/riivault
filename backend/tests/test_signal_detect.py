from datetime import date, timedelta

from riivault.analysis.signals import detect_spikes

TODAY = date(2026, 7, 10)


def series(base_per_day: int, recent_per_day: int, baseline_days: int = 28) -> dict[date, int]:
    d = {TODAY - timedelta(days=ago): recent_per_day for ago in range(3)}
    for ago in range(3, 3 + baseline_days):
        d[TODAY - timedelta(days=ago)] = base_per_day
    return d


def test_detects_clear_spike_with_evidence():
    detections = detect_spikes({1: series(base_per_day=5, recent_per_day=20)}, TODAY)
    assert len(detections) == 1
    det = detections[0]
    assert det["entity_id"] == 1
    assert det["recent"] == 60
    assert det["expected"] == 15.0
    assert det["zscore"] > 3.0


def test_steady_volume_is_not_a_spike():
    assert detect_spikes({1: series(base_per_day=10, recent_per_day=11)}, TODAY) == []


def test_low_recent_volume_is_ignored():
    # Big relative jump but under MIN_RECENT_MENTIONS.
    assert detect_spikes({1: series(base_per_day=1, recent_per_day=4)}, TODAY) == []


def test_no_established_baseline_means_new_not_spiking():
    # Only 5 active baseline days (< MIN_BASELINE_ACTIVE_DAYS): a young entity
    # is "new", not "spiking" — collection-start artifacts must not fire.
    d = {TODAY - timedelta(days=ago): 20 for ago in range(3)}
    for ago in range(3, 8):
        d[TODAY - timedelta(days=ago)] = 5
    assert detect_spikes({1: d}, TODAY) == []


def test_detections_sorted_by_zscore():
    detections = detect_spikes(
        {
            1: series(base_per_day=5, recent_per_day=15),
            2: series(base_per_day=5, recent_per_day=40),
        },
        TODAY,
    )
    assert [d["entity_id"] for d in detections] == [2, 1]
