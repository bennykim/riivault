"""First-pass backfill horizon (collector.reddit.backfill_floor)."""

from datetime import UTC, datetime, timedelta

from riivault.collector.reddit import BACKFILL_MAX_DAYS, backfill_floor

NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def test_cursor_wins_when_present():
    cursor = datetime(2026, 7, 1, tzinfo=UTC)
    assert backfill_floor(cursor, NOW) == cursor


def test_no_cursor_caps_at_horizon():
    assert backfill_floor(None, NOW) == NOW - timedelta(days=BACKFILL_MAX_DAYS)


def test_old_cursor_is_not_capped():
    """An established cursor older than the horizon stays authoritative —
    the cap exists only to bound *first* passes, never to skip a gap."""
    cursor = NOW - timedelta(days=90)
    assert backfill_floor(cursor, NOW) == cursor
