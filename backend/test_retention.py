from datetime import datetime, timezone

import pytest

from retention import parse_retention_days, retention_cutoff


@pytest.mark.parametrize("raw,expected", [(None, 0), ("", 0), ("0", 0), (" 30 ", 30), ("3650", 3650)])
def test_retention_days_accepts_disabled_and_bounded_windows(raw, expected):
    assert parse_retention_days(raw) == expected


@pytest.mark.parametrize("raw", ["-1", "3651", "2.5", "weekly"])
def test_retention_days_rejects_unsafe_configuration(raw):
    with pytest.raises(ValueError, match="DAISY_RUN_RETENTION_DAYS"):
        parse_retention_days(raw)


def test_cutoff_is_utc_and_disabled_policy_has_no_cutoff():
    now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    assert retention_cutoff(30, now) == "2026-09-10T12:00:00+00:00"
    assert retention_cutoff(0, now) is None


def test_cutoff_rejects_ambiguous_local_time():
    with pytest.raises(ValueError, match="timezone"):
        retention_cutoff(30, datetime(2026, 10, 10, 12, 0))
