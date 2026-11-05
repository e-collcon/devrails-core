"""
One poll cycle — BR-04, BR-52..58, BR-70, BR-76 (TASK-051, 061, 068, 072). Contract v1.3.

Sync Failed (N5, E 2026-10-27) means DevRails could not establish a link with the
project's data: a Monitoring API error (permission, not found, unauthenticated,
unavailable after one retry, invalid query) or a payload that fails validation.

run_once() never raises for expected failures; it returns a RunResult whose
exit_code main.py hands to the process:
  0  synced document written
  1  poll failed (Sync Failed written if a prior success exists; otherwise nothing)
  2  not provisioned / misconfigured (nothing written)
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from config import Settings
from engine import clock
from engine.classify import classify_metric, rollup
from engine.explain import SYNC_FAILED_EXPLANATION, explain
from engine.feed_store import FeedStore
from engine.metrics_config import METRICS, MetricConfig
from engine.monitoring import MetricFetchError
from engine.payload import synced_document
from engine.readings import Point, build_reading
from engine.schema import validate_feed


class PointSource(Protocol):
    calls: int

    def fetch_points(self, cfg: MetricConfig, now: datetime) -> list[Point]: ...


def log(severity: str, event: str, **fields) -> None:
    """One JSON line per event (Cloud Logging parses `severity`). Never pass secrets or payloads."""
    rec = {"severity": severity, "event": event, "component": "spike-engine", **fields}
    print(json.dumps(rec, separators=(",", ":"), default=str), file=sys.stdout, flush=True)


@dataclass
class RunResult:
    exit_code: int
    outcome: str
    document: dict | None = None
    errors: list[str] = field(default_factory=list)


def run_once(settings: Settings, source: PointSource, store: FeedStore, now: datetime | None = None) -> RunResult:
    started = time.monotonic()
    now = clock.ensure_utc(now) if now else datetime.now(clock.UTC)
    uid, pid = settings.uid, settings.project_id
    ctx = {"project_id": pid, "target_project": settings.gcp_project_id}

    existing = store.get(uid, pid)
    if existing is None:
        log("ERROR", "feed_not_provisioned", **ctx,
            hint="run `python main.py provision` first; the engine never creates the feed itself")
        return RunResult(2, "not_provisioned")
    if existing.get("gcp_project_id") != settings.gcp_project_id:
        # Never write one project's readings under another project's feed.
        log("ERROR", "target_project_mismatch", **ctx, feed_gcp_project=existing.get("gcp_project_id"))
        return RunResult(2, "target_project_mismatch")

    # D5: collected history starts at sync_initialized_at (devrails_start), or covers
    # everything Cloud Monitoring holds (cloud_monitoring).
    collection_start = None
    if settings.history_basis == "devrails_start":
        try:
            collection_start = clock.parse_iso_utc(existing.get("sync_initialized_at"))
        except (TypeError, ValueError):
            log("ERROR", "feed_invalid_sync_initialized_at", **ctx)
            return RunResult(2, "invalid_feed")

    def fail(kind: str, metric: str = "", errors: list[str] | None = None) -> RunResult:
        if existing.get("initial_sync_complete") is True:
            store.mark_sync_failed(uid, pid, SYNC_FAILED_EXPLANATION)  # BR-54: last-known data kept
            wrote = "sync_failed"
        else:
            wrote = "nothing"  # BR-55: frontend shows Sync Delayed after 15 min
        log("WARNING", "poll_failed", **ctx, error_class=kind, metric=metric, wrote=wrote,
            series_calls=getattr(source, "calls", 0), duration_ms=round((time.monotonic() - started) * 1000))
        return RunResult(1, f"failed:{kind}", errors=errors or [])

    readings = []
    for cfg in METRICS:
        try:
            points = source.fetch_points(cfg, now)
        except MetricFetchError as exc:
            return fail(exc.kind, exc.metric_key)  # either metric failing fails the poll (BR-54)
        # A successful read with no series is zero usage, not a failure (N5).
        readings.append(build_reading(cfg, points, now, collection_start))

    statuses = [classify_metric(r, now) for r in readings]
    result = rollup(statuses)
    doc = synced_document(
        existing=existing,
        readings=readings,
        result=result,
        explanation=explain(result),
        now=now,
    )
    errors = validate_feed(doc)
    if errors:  # BR-53: never write an invalid document
        return fail("schema_validation", errors=errors)

    store.replace_synced(uid, pid, doc)
    log("INFO", "poll_succeeded", **ctx,
        system_status=doc["system_status"], primary_reason=doc["status_model"]["primary_reason"],
        first_sync=existing.get("initial_sync_complete") is not True,
        series_calls=getattr(source, "calls", 0), duration_ms=round((time.monotonic() - started) * 1000))
    return RunResult(0, "synced", document=doc)
