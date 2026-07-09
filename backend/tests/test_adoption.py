from datetime import date

from riivault.collector.adoption import npm_rows, pypi_rows, release_rows, se_rows

TODAY = date(2026, 7, 9)


def test_npm_rows_parses_daily_downloads():
    payload = {
        "downloads": [
            {"day": "2026-07-07", "downloads": 120},
            {"day": "2026-07-08", "downloads": 150},
            {"day": "2026-07-09"},  # missing value -> skipped
        ]
    }
    assert npm_rows(payload) == [
        (date(2026, 7, 7), 120.0),
        (date(2026, 7, 8), 150.0),
    ]


def test_npm_rows_empty_payload():
    assert npm_rows({}) == []


def test_pypi_rows_keeps_only_mirror_free_series():
    payload = {
        "data": [
            {"category": "with_mirrors", "date": "2026-07-08", "downloads": 900},
            {"category": "without_mirrors", "date": "2026-07-08", "downloads": 700},
            {"category": "without_mirrors", "date": "2026-07-09", "downloads": 710},
        ]
    }
    assert pypi_rows(payload) == [
        (date(2026, 7, 8), 700.0),
        (date(2026, 7, 9), 710.0),
    ]


def test_release_rows_counts_per_day_and_skips_drafts():
    payload = [
        {"published_at": "2026-07-01T09:00:00Z"},
        {"published_at": "2026-07-01T18:00:00Z"},
        {"published_at": "2026-07-05T12:00:00Z"},
        {"published_at": "2026-07-05T13:00:00Z", "draft": True},
        {"published_at": None},
    ]
    assert release_rows(payload, TODAY) == [
        (date(2026, 7, 1), 2.0),
        (date(2026, 7, 5), 1.0),
    ]


def test_release_rows_respects_window():
    payload = [
        {"published_at": "2025-01-01T00:00:00Z"},  # far outside 90d window
        {"published_at": "2026-07-01T00:00:00Z"},
    ]
    assert release_rows(payload, TODAY, window_days=90) == [(date(2026, 7, 1), 1.0)]


def test_se_rows_buckets_epochs_by_utc_day():
    items = [
        {"creation_date": 1783490400},  # 2026-07-08T06:00Z
        {"creation_date": 1783533600},  # 2026-07-08T18:00Z
        {"creation_date": 1783566000},  # 2026-07-09T03:00Z
        {},                             # missing epoch -> skipped
    ]
    assert se_rows(items, TODAY) == [
        (date(2026, 7, 8), 2.0),
        (date(2026, 7, 9), 1.0),
    ]


def test_se_rows_truncated_drops_partial_oldest_day():
    items = [
        {"creation_date": 1783490400},  # 2026-07-08 (partial: page cap hit)
        {"creation_date": 1783566000},  # 2026-07-09
    ]
    assert se_rows(items, TODAY, truncated=True) == [(date(2026, 7, 9), 1.0)]
    assert se_rows([], TODAY, truncated=True) == []
