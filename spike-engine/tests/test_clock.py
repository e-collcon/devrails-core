"""BE-1 / BR-34: Pacific billing clock, including DST month and day boundaries."""

from datetime import timedelta

import pytest

from engine import clock

P = clock.parse_iso_utc


def test_iso_round_trip():
    assert clock.iso_utc(P("2026-10-25T13:50:07Z")) == "2026-10-25T13:50:07Z"


def test_parse_rejects_offsets_and_naive():
    with pytest.raises(ValueError):
        clock.parse_iso_utc("2026-10-25T13:50:00+07:00")
    with pytest.raises(ValueError):
        clock.parse_iso_utc(None)


def test_month_start_pdt_and_pst():
    assert clock.iso_utc(clock.month_start(P("2026-10-25T13:50:00Z"))) == "2026-10-01T07:00:00Z"  # PDT
    assert clock.iso_utc(clock.month_start(P("2026-12-15T12:00:00Z"))) == "2026-12-01T08:00:00Z"  # PST


def test_month_boundary_follows_pacific_not_utc():
    # 2026-11-01T06:59Z is still Oct 31, 23:59 PDT -> October window.
    assert clock.iso_utc(clock.month_start(P("2026-11-01T06:59:00Z"))) == "2026-10-01T07:00:00Z"
    # One minute later it is Nov 1, 00:00 PDT -> November window.
    assert clock.iso_utc(clock.month_start(P("2026-11-01T07:00:00Z"))) == "2026-11-01T07:00:00Z"


def test_dst_end_day_is_25_hours_and_first_bucket_is_7():
    # DST ends 2026-11-01 02:00 PDT -> 01:00 PST.
    nov1, nov2 = clock.day_starts(P("2026-11-02T20:00:00Z"), 2)
    assert nov2 - nov1 == timedelta(hours=25)
    b = clock.bucket_starts(P("2026-11-01T22:00:00Z"), 6, 4)  # Nov 1 14:00 PST
    assert [clock.iso_utc(x) for x in b] == [
        "2026-11-01T01:00:00Z",  # Oct 31 18:00 PDT
        "2026-11-01T07:00:00Z",  # Nov 1 00:00 PDT
        "2026-11-01T14:00:00Z",  # Nov 1 06:00 PST
        "2026-11-01T20:00:00Z",  # Nov 1 12:00 PST
    ]
    assert b[2] - b[1] == timedelta(hours=7)


def test_dst_start_day_is_23_hours():
    # DST starts 2027-03-14 02:00 PST -> 03:00 PDT.
    d13, d14, d15 = clock.day_starts(P("2027-03-15T20:00:00Z"), 3)
    assert d14 - d13 == timedelta(hours=24)
    assert d15 - d14 == timedelta(hours=23)
    first, second = clock.bucket_starts(P("2027-03-14T14:00:00Z"), 6, 2)  # 07:00 PDT
    assert second - first == timedelta(hours=5)


def test_bucket_starts_cross_days_oldest_first():
    b = clock.bucket_starts(P("2026-10-25T19:55:00Z"), 6, 28)  # Sun 12:55 PDT
    assert len(b) == 28
    assert clock.iso_utc(b[-1]) == "2026-10-25T19:00:00Z"  # 12:00 PDT bucket
    assert clock.iso_utc(b[0]) == "2026-10-19T01:00:00Z"   # Sun 18, 18:00 PDT (27 buckets back)
    assert all(x < y for x, y in zip(b, b[1:]))


def test_next_bucket_start_handles_day_rollover():
    s = P("2026-10-25T01:00:00Z")  # Oct 24 18:00 PDT
    assert clock.iso_utc(clock.next_bucket_start(s, 6)) == "2026-10-25T07:00:00Z"
