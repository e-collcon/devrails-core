"""BR-33/35/38, Contract v1.3: value windows, six-hour sparkline, pace facts, zero usage (N5), D5 collection start."""

from datetime import timedelta

from engine import clock
from engine.metrics_config import CLOUD_RUN_REQUESTS as RUN, CLOUD_STORAGE_BYTES as STO
from engine.readings import Point, build_reading, lookback_start, next_month_start, sparkline_buckets

P = clock.parse_iso_utc
NOW = P("2026-10-25T19:55:00Z")  # Sun 25 Oct 12:55 PDT


def hourly(start, end, value=100.0):
    out, t = [], start
    while t < end:
        out.append(Point(t, value))
        t += timedelta(hours=1)
    return out


def test_lookback_is_month_start_or_eight_days_whichever_earlier():
    assert clock.iso_utc(lookback_start(NOW)) == "2026-10-01T07:00:00Z"
    assert clock.iso_utc(lookback_start(P("2026-10-03T12:00:00Z"))) == "2026-09-25T07:00:00Z"


def test_next_month_start_is_pacific():
    assert clock.iso_utc(next_month_start(NOW)) == "2026-11-01T07:00:00Z"   # still PDT at 00:00 Nov 1
    assert clock.iso_utc(next_month_start(P("2026-12-20T00:00:00Z"))) == "2027-01-01T08:00:00Z"


def test_cloud_run_current_value_is_month_to_date_even_before_collection():
    pts = hourly(P("2026-09-28T07:00:00Z"), clock.floor_hour(NOW))
    r = build_reading(RUN, pts, NOW, collection_start=NOW - timedelta(hours=2))
    assert r.current_value == sum(p.value for p in pts if p.at >= P("2026-10-01T07:00:00Z"))  # D2: actual usage
    assert clock.iso_utc(r.window_started_at) == "2026-10-01T07:00:00Z"


def test_storage_current_value_is_latest_reading_never_a_sum():
    pts = [Point(NOW - timedelta(hours=h), 1000 + h) for h in range(48, -1, -1)]
    r = build_reading(STO, pts, NOW)
    assert r.current_value == 1000 and r.window_started_at is None


def test_sparkline_covers_the_same_seven_pacific_days_in_six_hour_buckets():
    b = sparkline_buckets(NOW)
    assert clock.iso_utc(b[0]) == "2026-10-19T07:00:00Z"   # Mon 19 00:00 PT
    assert clock.iso_utc(b[-1]) == "2026-10-25T19:00:00Z"  # Sun 25 12:00 PT, the current bucket
    assert len(b) == 27                                     # 6 days x 4 + 3 of today's buckets
    pts = hourly(P("2026-10-10T07:00:00Z"), NOW)
    r = build_reading(RUN, pts, NOW)
    assert len(r.sparkline) == 27 and r.sparkline[0] == 600 and r.bucket_hours == 6
    assert clock.iso_utc(r.last_bucket_started_at) == "2026-10-25T19:00:00Z"


def test_sparkline_never_padded_before_collection_started():
    pts = hourly(P("2026-10-10T07:00:00Z"), NOW)
    r = build_reading(RUN, pts, NOW, collection_start=NOW - timedelta(hours=30))
    assert 5 <= len(r.sparkline) <= 7
    assert all(v > 0 for v in r.sparkline[:-1])


def test_zero_traffic_is_zero_usage_not_missing_data():
    r = build_reading(RUN, [], NOW, collection_start=NOW - timedelta(days=10))
    assert r.current_value == 0 and len(r.sparkline) == 27 and set(r.sparkline) == {0}
    s = build_reading(STO, [], NOW, collection_start=NOW - timedelta(days=10))
    assert s.current_value == 0 and set(s.sparkline) == {0}
    assert r.velocity.activity == 0 and s.velocity.activity == 0


def test_dst_end_day_buckets_follow_the_wall_clock():
    now = P("2026-11-02T20:00:00Z")  # Mon 2 Nov 12:00 PST
    pts = hourly(P("2026-10-20T07:00:00Z"), clock.floor_hour(now))
    r = build_reading(RUN, pts, now)
    # Nov 1 is 25 h long; its 00:00–06:00 PT bucket holds 7 hours.
    nov1 = [b for b in sparkline_buckets(now) if clock.pacific_date(b).day == 1]
    i = sparkline_buckets(now).index(nov1[0])
    assert r.sparkline[i] == 700 and sum(r.sparkline[i:i + 4]) == 2500


def test_pace_facts_for_cloud_run():
    pts = hourly(P("2026-10-10T07:00:00Z"), NOW)
    v = build_reading(RUN, pts, NOW).velocity
    assert v.last_24h == 2400 and v.pace_per_hour == 100
    assert v.week_total == 168 * 100
    assert clock.iso_utc(v.resets_at) == "2026-11-01T07:00:00Z"


def test_hours_collected_follows_collection_start():
    assert build_reading(RUN, [], NOW, collection_start=NOW - timedelta(hours=12)).velocity.hours_collected == 12
    assert build_reading(RUN, [], NOW, collection_start=None).velocity.hours_collected > 24 * 8


def test_storage_growth_over_24_hours():
    pts = [Point(NOW - timedelta(hours=h), 5000 - h) for h in range(30, -1, -1)]
    v = build_reading(STO, pts, NOW).velocity
    assert v.last_24h == 24 and v.pace_per_hour == 1 and v.resets_at is None


def test_storage_with_no_reading_a_day_ago_grew_from_zero():
    pts = [Point(NOW - timedelta(hours=h), 5000) for h in range(10, -1, -1)]  # first bucket today
    v = build_reading(STO, pts, NOW).velocity
    assert v.last_24h == 5000
