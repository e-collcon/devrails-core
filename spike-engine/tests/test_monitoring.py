"""BR-30..32, BR-70, BR-74: Monitoring adapter against a fake client returning real monitoring_v3 types."""

from datetime import timedelta

import pytest
from google.api_core import exceptions as gexc
from google.cloud import monitoring_v3

from engine import clock
from engine.metrics_config import CLOUD_RUN_REQUESTS as RUN, CLOUD_STORAGE_BYTES as STO
from engine.monitoring import MetricFetchError, MonitoringSource

NOW = clock.parse_iso_utc("2026-10-25T19:55:30Z")


def series(points):
    """points: list of (end_time, value, kind)"""
    ts = monitoring_v3.TimeSeries()
    for end, value, kind in points:
        p = monitoring_v3.Point(interval=monitoring_v3.TimeInterval(end_time=end),
                                value=monitoring_v3.TypedValue(**{kind: value}))
        ts.points.append(p)
    return ts


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def list_time_series(self, request, retry=None, timeout=None):
        assert retry is None, "the adapter must own retries (BR-70)"
        assert timeout and timeout > 0
        self.requests.append(request)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def src(client, **kw):
    kw.setdefault("quota_project_id", "devrails-core-dev")
    return MonitoringSource("target-proj", client=client, sleep=lambda s: None, **kw)


def test_cloud_run_hourly_plus_partial_hour_queries():
    hour = clock.floor_hour(NOW)
    hourly = series([(hour - timedelta(hours=k), 100, "int64_value") for k in range(3, 0, -1)])
    minutes = series([(hour + timedelta(minutes=m), 2, "int64_value") for m in range(1, 56)])
    c = FakeClient([[hourly], [minutes]])
    pts = src(c).fetch_points(RUN, NOW)

    first, second = c.requests
    assert first.name == "projects/target-proj"
    assert first.filter == 'metric.type="run.googleapis.com/request_count" AND resource.type="cloud_run_revision"'
    assert first.aggregation.per_series_aligner == monitoring_v3.Aggregation.Aligner.ALIGN_DELTA
    assert first.aggregation.cross_series_reducer == monitoring_v3.Aggregation.Reducer.REDUCE_SUM
    assert first.aggregation.alignment_period.total_seconds() == 3600
    assert clock.iso_utc(first.interval.start_time) == "2026-10-01T07:00:00Z"  # month start (lookback)
    assert clock.iso_utc(first.interval.end_time) == clock.iso_utc(hour)
    assert second.aggregation.alignment_period.total_seconds() == 60

    assert [clock.iso_utc(p.at) for p in pts[:3]] == [clock.iso_utc(hour - timedelta(hours=k)) for k in (4, 3, 2)]
    assert pts[-1].at == hour and pts[-1].value == 110  # 55 minutes x 2
    assert sum(p.value for p in pts) == 410


def test_storage_query_uses_next_older_and_reads_doubles():
    pts_in = [(NOW - timedelta(hours=k), 1.5e9 + k, "double_value") for k in range(5, -1, -1)]
    c = FakeClient([[series(pts_in)]])
    pts = src(c).fetch_points(STO, NOW)
    req = c.requests[0]
    assert req.filter == 'metric.type="storage.googleapis.com/storage/total_bytes" AND resource.type="gcs_bucket"'
    assert req.aggregation.per_series_aligner == monitoring_v3.Aggregation.Aligner.ALIGN_NEXT_OLDER
    assert pts[-1].value == 1.5e9 and len(pts) == 6


def test_empty_result_is_zero_usage_not_an_error():
    c = FakeClient([[], []])
    assert src(c).fetch_points(RUN, NOW) == []


def test_transient_error_is_retried_exactly_once():
    c = FakeClient([gexc.ServiceUnavailable("x"), [series([])], []])
    s = src(c)
    s.fetch_points(RUN, NOW)
    assert s.calls == 3  # failed + retried hourly call, then the partial-hour call


def test_transient_error_twice_fails_cleanly():
    c = FakeClient([gexc.ServiceUnavailable("x"), gexc.DeadlineExceeded("y")])
    with pytest.raises(MetricFetchError) as e:
        src(c).fetch_points(RUN, NOW)
    assert e.value.kind == "unavailable" and e.value.metric_key == "cloud_run_requests"


@pytest.mark.parametrize("exc,kind", [
    (gexc.PermissionDenied("no"), "permission_denied"),
    (gexc.NotFound("no"), "not_found"),
    (gexc.InvalidArgument("bad"), "invalid_query"),
    (gexc.Unauthenticated("who"), "unauthenticated"),
])
def test_permanent_errors_are_not_retried(exc, kind):
    c = FakeClient([exc])
    s = src(c)
    with pytest.raises(MetricFetchError) as e:
        s.fetch_points(STO, NOW)
    assert e.value.kind == kind and s.calls == 1


def test_max_attempts_is_capped_at_two():
    s = src(FakeClient([]), max_attempts=10)
    assert s.max_attempts == 2


def test_quota_project_is_passed_to_the_real_client(monkeypatch):
    seen = {}

    class Spy:
        def __init__(self, client_options=None):
            seen["quota"] = client_options.quota_project_id if client_options else None

    monkeypatch.setattr(monitoring_v3, "MetricServiceClient", Spy)
    MonitoringSource("t", quota_project_id="devrails-core-dev").client
    assert seen["quota"] == "devrails-core-dev"


@pytest.mark.parametrize("quota", ["", "target-proj"])
def test_reads_are_never_billed_to_the_customer(quota):
    """E, 2026-10-27: no quota project, or the customer's own project, is refused."""
    with pytest.raises(ValueError):
        MonitoringSource("target-proj", quota_project_id=quota, client=FakeClient([]))
