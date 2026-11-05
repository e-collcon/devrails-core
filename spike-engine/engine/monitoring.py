"""
Cloud Monitoring adapter — BR-30..32, BR-36, BR-38, BR-70, BR-74 (TASK-046..050).

The only Google API this engine calls. Read-only: timeSeries.list on the target
project, with the reducer applied server-side so each query returns one series.

Queries per poll (BR-75: about three calls, one series each):
  1. Cloud Run request_count, ALIGN_DELTA + REDUCE_SUM, 1 h alignment, from the
     lookback start to the current UTC hour (hour-aligned, so buckets match
     Pacific hours: PT offsets are whole hours).
  2. Cloud Run request_count for the partial current hour at 1-minute alignment
     (skipped when under 60 s).
  3. Cloud Storage total_bytes, ALIGN_NEXT_OLDER + REDUCE_SUM, 1 h alignment.

Errors become MetricFetchError with a short class name; they never crash the run.
Retries: at most `max_attempts` (2) per call, transient errors only, fixed backoff.
"""

from __future__ import annotations

import time as _time
from datetime import datetime, timedelta
from typing import Callable

from engine import clock
from engine.metrics_config import MetricConfig
from engine.readings import Point, lookback_start

ALIGNMENT_SECONDS = 3600


class MetricFetchError(Exception):
    """A failed Monitoring read. `kind` is safe to log; the message never contains credentials."""

    def __init__(self, kind: str, metric_key: str, detail: str = ""):
        self.kind = kind
        self.metric_key = metric_key
        super().__init__(f"{metric_key}: {kind}" + (f" ({detail})" if detail else ""))


def _error_kind(exc: Exception) -> tuple[str, bool]:
    """Map an exception to (kind, transient)."""
    from google.api_core import exceptions as gexc
    from google.auth import exceptions as auth_exc

    if isinstance(exc, auth_exc.DefaultCredentialsError):
        return "credentials", False
    if isinstance(exc, gexc.PermissionDenied):
        return "permission_denied", False
    if isinstance(exc, gexc.Unauthenticated):
        return "unauthenticated", False
    if isinstance(exc, gexc.NotFound):
        return "not_found", False
    if isinstance(exc, gexc.InvalidArgument):
        return "invalid_query", False
    if isinstance(exc, (gexc.ServiceUnavailable, gexc.DeadlineExceeded, gexc.InternalServerError,
                        gexc.TooManyRequests)):
        return "unavailable", True
    if isinstance(exc, gexc.GoogleAPICallError):
        return "api_error", False
    return "unexpected", False


def _typed_number(typed_value) -> float:
    from google.cloud import monitoring_v3

    pb = monitoring_v3.TypedValue.pb(typed_value)
    kind = pb.WhichOneof("value")
    if kind == "int64_value":
        return float(pb.int64_value)
    if kind == "double_value":
        return float(pb.double_value)
    return 0.0


class MonitoringSource:
    """Reads one target project. `client` is injectable for tests."""

    def __init__(
        self,
        target_project_id: str,
        *,
        quota_project_id: str = "",
        client=None,
        timeout_seconds: float = 20.0,
        max_attempts: int = 2,
        backoff_seconds: float = 2.0,
        sleep: Callable[[float], None] = _time.sleep,
    ):
        if not target_project_id:
            raise ValueError("target_project_id is required")
        # E, 2026-10-27: DevRails' Google activity is never billed to the customer.
        # Every read names the DevRails host project as its quota project.
        if not quota_project_id:
            raise ValueError("quota_project_id (the DevRails host project) is required")
        if quota_project_id == target_project_id:
            raise ValueError("quota_project_id must not be the monitored project")
        self.project_name = f"projects/{target_project_id}"
        self.timeout = timeout_seconds
        self.max_attempts = max(1, min(int(max_attempts), 2))  # BR-70: never more than one retry
        self.backoff = backoff_seconds
        self._sleep = sleep
        self._client = client
        self._quota_project_id = quota_project_id
        self.calls = 0  # time-series list calls made (logged per run, BR-76)

    @property
    def client(self):
        if self._client is None:
            from google.api_core.client_options import ClientOptions
            from google.cloud import monitoring_v3

            # BR-74: bill Monitoring reads to the DevRails host project. [VERIFY LEDGER-09]
            opts = ClientOptions(quota_project_id=self._quota_project_id)
            self._client = monitoring_v3.MetricServiceClient(client_options=opts)
        return self._client

    # -- low level ---------------------------------------------------------

    def _list(self, cfg: MetricConfig, start: datetime, end: datetime, period_s: int, aligner: str):
        from google.cloud import monitoring_v3
        from google.protobuf import duration_pb2, timestamp_pb2

        start_ts, end_ts = timestamp_pb2.Timestamp(), timestamp_pb2.Timestamp()
        start_ts.FromDatetime(start.replace(tzinfo=None))
        end_ts.FromDatetime(end.replace(tzinfo=None))
        request = monitoring_v3.ListTimeSeriesRequest(
            name=self.project_name,
            filter=cfg.monitoring_filter,
            interval=monitoring_v3.TimeInterval(start_time=start_ts, end_time=end_ts),
            aggregation=monitoring_v3.Aggregation(
                alignment_period=duration_pb2.Duration(seconds=period_s),
                per_series_aligner=getattr(monitoring_v3.Aggregation.Aligner, aligner),
                cross_series_reducer=monitoring_v3.Aggregation.Reducer.REDUCE_SUM,
            ),
            view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
        )
        attempt = 0
        while True:
            attempt += 1
            self.calls += 1
            try:
                # retry=None: the bounded loop here is the only retry (BR-70).
                return list(self.client.list_time_series(request=request, retry=None, timeout=self.timeout))
            except Exception as exc:  # noqa: BLE001 — converted to a structured error
                kind, transient = _error_kind(exc)
                if transient and attempt < self.max_attempts:
                    self._sleep(self.backoff)
                    continue
                raise MetricFetchError(kind, cfg.key, type(exc).__name__) from None

    @staticmethod
    def _points(series_list, *, delta: bool, period_s: int) -> list[Point]:
        """Delta points are stamped with their period start (end - period); gauge points with their time."""
        out = []
        for series in series_list:
            for p in series.points:
                end = clock.ensure_utc(p.interval.end_time)
                at = end - timedelta(seconds=period_s) if delta else end
                out.append(Point(at=at, value=_typed_number(p.value)))
        return out

    # -- public ------------------------------------------------------------

    def fetch_points(self, cfg: MetricConfig, now: datetime) -> list[Point]:
        now = clock.ensure_utc(now)
        start = lookback_start(now)
        if cfg.kind == "delta_count":
            hour = clock.floor_hour(now)
            points = self._points(self._list(cfg, start, hour, ALIGNMENT_SECONDS, "ALIGN_DELTA"),
                                  delta=True, period_s=ALIGNMENT_SECONDS)
            if (now - hour).total_seconds() >= 60:
                # Partial current hour at 1-minute alignment: robust to how periods are anchored,
                # still one series. Summed into a single point stamped at the hour start.
                minute = now.replace(second=0, microsecond=0)
                partial = self._points(self._list(cfg, hour, minute, 60, "ALIGN_DELTA"), delta=True, period_s=60)
                if partial:
                    points.append(Point(at=hour, value=sum(p.value for p in partial)))
            return points
        if cfg.kind == "gauge_bytes":
            return self._points(self._list(cfg, start, now, ALIGNMENT_SECONDS, "ALIGN_NEXT_OLDER"),
                                delta=False, period_s=ALIGNMENT_SECONDS)
        raise ValueError(f"unknown metric kind {cfg.kind!r}")
