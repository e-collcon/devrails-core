"""BR-51..53, Contract v1.3: stub, synced payload, and the validator (BE-3)."""

import copy
import json
from pathlib import Path

import pytest

import config
from config import Settings
from engine import clock
from engine.feed_store import MemoryFeedStore
from engine.fixtures import SCENARIOS, FixtureSource
from engine.payload import STUB_FIELDS, stub_document
from engine.run import run_once
from engine.schema import METRIC_FIELDS, validate_feed

NOW = clock.parse_iso_utc("2026-10-25T19:55:00Z")
EXAMPLE = Path(__file__).resolve().parents[2] / "docs" / "contract" / "v1.3-example-synced.json"


def synced(scenario="normal", now=NOW, init="2026-10-01T07:00:00Z", project="g"):
    s = Settings(gcp_project_id=project, uid="u", project_id=project)
    store = MemoryFeedStore()
    store.create_stub_if_absent("u", project, stub_document(project, clock.parse_iso_utc(init)))
    res = run_once(s, FixtureSource(scenario), store, now=now)
    assert res.exit_code == 0, res
    return res.document


def test_stub_is_exactly_nine_fields_and_valid():
    stub = stub_document("elmscorp-prototype-123", NOW)
    assert tuple(stub) == STUB_FIELDS and len(stub) == 9
    assert stub["status_explanation"] == config.STATE_001_EXPLANATION
    assert stub["guardrail_mode"] == "free_tier" and stub["guardrail_label"] == "Free Tier Watch"
    assert validate_feed(stub) == []


def test_contract_example_is_valid_and_is_what_the_engine_writes():
    """docs/contract/v1.3-example-synced.json is the A.6 example pasted into the contract."""
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert validate_feed(example) == []
    written = synced("risky", now=clock.parse_iso_utc("2026-10-25T13:50:00Z"), project="devrails-poc-target")
    assert written == example


@pytest.mark.parametrize("scenario", [s for s in SCENARIOS if not SCENARIOS[s].fail])
def test_every_fixture_produces_a_valid_document(scenario):
    doc = synced(scenario)
    assert validate_feed(doc) == []
    assert doc["initial_sync_complete"] is True
    assert doc["sync_initialized_at"] == "2026-10-01T07:00:00Z"  # carried over, not regenerated
    assert doc["last_sync_timestamp"] == "2026-10-25T19:55:00Z"
    for m in doc["metrics"].values():
        assert set(m) == METRIC_FIELDS and len(m) == 15
    json.dumps(doc)  # plain JSON types only


def test_six_hour_fields():
    m = synced("normal")["metrics"]["cloud_run_requests"]
    assert m["sparkline_bucket_hours"] == 6
    assert m["sparkline_last_bucket_started_at"] == "2026-10-25T19:00:00Z"
    assert len(m["sparkline_data_points"]) == 27  # Sun 12:55 PT: 6 days x 4 + 3


def _broken(mutate):
    doc = copy.deepcopy(synced("rising"))
    mutate(doc)
    return validate_feed(doc)


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(extra_field=1),
    lambda d: d.pop("status_model"),
    lambda d: d.update(guardrail_mode="Free Tier Watch"),
    lambda d: d.update(monthly_budget_usd=5),
    lambda d: d.update(system_status="Stale"),          # frontend-only value
    lambda d: d.update(system_status="Sync Delayed"),   # frontend-only value
    lambda d: d.update(system_status="Pending"),
    lambda d: d.update(last_sync_timestamp=None),
    lambda d: d.update(last_sync_timestamp="2026-10-25 19:55"),
    lambda d: d["status_model"].update(primary_reason="something_new"),
    lambda d: d["metrics"].pop("cloud_storage_bytes"),
    lambda d: d["metrics"]["cloud_storage_bytes"].update(burn_rate_multiplier=1.2),
    lambda d: d["metrics"]["cloud_run_requests"].update(current_value_7d=5),
    lambda d: d["metrics"]["cloud_run_requests"].pop("projected_hours_to_limit"),
    lambda d: d["metrics"]["cloud_run_requests"].update(projected_hours_to_limit=None),  # elevated needs hours
    lambda d: d["metrics"]["cloud_run_requests"].update(projected_hours_to_limit=-1),
    lambda d: d["metrics"]["cloud_run_requests"].update(window_started_at=None),
    lambda d: d["metrics"]["cloud_storage_bytes"].update(window_started_at="2026-10-01T07:00:00Z"),
    lambda d: d["metrics"]["cloud_run_requests"].update(sparkline_data_points=[1] * 29),
    lambda d: d["metrics"]["cloud_run_requests"].update(sparkline_data_points=[]),
    lambda d: d["metrics"]["cloud_run_requests"].update(sparkline_bucket_hours=24),
    lambda d: d["metrics"]["cloud_run_requests"].pop("sparkline_last_bucket_started_at"),
    lambda d: d["metrics"]["cloud_run_requests"].update(usage_ratio=0.99),
    lambda d: d["metrics"]["cloud_run_requests"].update(velocity_status="insufficient_data"),  # hours must be null
])
def test_validator_rejects_contract_violations(mutate):
    assert _broken(mutate) != []


def test_v12_shape_is_rejected():
    doc = copy.deepcopy(synced("normal"))
    for m in doc["metrics"].values():
        for f in ("projected_hours_to_limit", "sparkline_bucket_hours", "sparkline_last_bucket_started_at"):
            m.pop(f)
    assert validate_feed(doc) != []


def test_stub_rules():
    stub = stub_document("g", NOW)
    assert validate_feed({**stub, "system_status": "Normal"}) != []
    assert validate_feed({**stub, "last_sync_timestamp": "2026-10-25T19:55:00Z"}) != []
    assert validate_feed({**stub, "metrics": {}}) != []
