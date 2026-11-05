"""
Reusable metric config — BR-12 (TASK-045, TASK-047, TASK-048).

Each monitored signal is one MetricConfig entry. Adding a Bucket 1 clone (for
example Cloud Functions, stretch TASK-146..152, behind E's gate) is a new entry
here, not new code.
"""

from __future__ import annotations

from dataclasses import dataclass

import config


@dataclass(frozen=True)
class MetricConfig:
    key: str                # output key under `metrics` [CONTRACT A.4]
    metric_id: str          # Cloud Monitoring metric type [CONTRACT A.7.3]
    resource_type: str      # monitored resource type in the filter
    metric_role: str        # primary_burn_rate_signal | capacity_status_signal
    value_window: str       # month_to_date | latest [CONTRACT A.7.9]
    freshness_profile: str  # near_real_time | daily_or_delayed
    free_tier_limit: int
    kind: str               # "delta_count" (summed) | "gauge_bytes" (latest reading)
    reason_prefix: str      # primary_reason prefix, e.g. "cloud_run"
    display_name: str       # used in explanations only
    unit: str

    @property
    def monitoring_filter(self) -> str:
        return f'metric.type="{self.metric_id}" AND resource.type="{self.resource_type}"'


CLOUD_RUN_REQUESTS = MetricConfig(
    key="cloud_run_requests",
    metric_id="run.googleapis.com/request_count",
    resource_type="cloud_run_revision",
    metric_role="primary_burn_rate_signal",
    value_window="month_to_date",
    freshness_profile="near_real_time",
    free_tier_limit=config.CLOUD_RUN_FREE_REQUESTS_PER_MONTH,
    kind="delta_count",
    reason_prefix="cloud_run",
    display_name="Cloud Run requests",
    unit="requests",
)

CLOUD_STORAGE_BYTES = MetricConfig(
    key="cloud_storage_bytes",
    metric_id="storage.googleapis.com/storage/total_bytes",
    resource_type="gcs_bucket",
    metric_role="capacity_status_signal",
    value_window="latest",
    freshness_profile="daily_or_delayed",
    free_tier_limit=config.CLOUD_STORAGE_FREE_BYTES,
    kind="gauge_bytes",
    reason_prefix="cloud_storage",
    display_name="Cloud Storage",
    unit="bytes",
)

# Order matters: Cloud Run first wins ties in the rollup [PENDING D3 rec].
METRICS: tuple[MetricConfig, ...] = (CLOUD_RUN_REQUESTS, CLOUD_STORAGE_BYTES)
