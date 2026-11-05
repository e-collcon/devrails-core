"""BR-04, BR-50..56, BR-23/76: run orchestration, write rules, Sync Failed, provisioning, logs."""

import json
from datetime import timedelta

import pytest

import main
from config import Settings
from engine import clock
from engine.explain import SYNC_FAILED_EXPLANATION
from engine.feed_store import MemoryFeedStore, feed_path
from engine.fixtures import FixtureSource
from engine.payload import stub_document
from engine.run import run_once

NOW = clock.parse_iso_utc("2026-10-25T19:55:00Z")
LATER = clock.parse_iso_utc("2026-10-25T20:05:00Z")
S = Settings(gcp_project_id="target", uid="uid1", project_id="target")
PATH = feed_path("uid1", "target")


def provisioned():
    store = MemoryFeedStore()
    assert store.create_stub_if_absent("uid1", "target", stub_document("target", clock.parse_iso_utc("2026-10-25T19:40:00Z")))
    store.writes.clear()
    return store


def test_feed_path_is_canonical():
    assert PATH == "users/uid1/projects/target/dashboard_feed/current"
    with pytest.raises(ValueError):
        feed_path("a/b", "c")


def test_absent_document_is_never_created_by_the_engine():
    store = MemoryFeedStore()
    res = run_once(S, FixtureSource("normal"), store, now=NOW)
    assert res.exit_code == 2 and store.writes == [] and store.docs == {}


def test_target_mismatch_writes_nothing():
    store = provisioned()
    res = run_once(Settings(gcp_project_id="other", uid="uid1", project_id="target"), FixtureSource("normal"), store, now=NOW)
    assert res.exit_code == 2 and store.writes == []


def test_first_success_flips_flag_and_keeps_sync_initialized_at():
    store = provisioned()
    res = run_once(S, FixtureSource("normal"), store, now=NOW)
    doc = store.docs[PATH]
    assert res.exit_code == 0
    assert [w[0] for w in store.writes] == ["set"]  # exactly one write per run (BR-56)
    assert doc["initial_sync_complete"] is True
    assert doc["sync_initialized_at"] == "2026-10-25T19:40:00Z"
    assert doc["last_sync_timestamp"] == "2026-10-25T19:55:00Z"


def test_failure_before_first_success_writes_nothing():
    store = provisioned()
    before = json.dumps(store.docs, sort_keys=True)
    res = run_once(S, FixtureSource("failing"), store, now=NOW)
    assert res.exit_code == 1 and store.writes == []
    assert json.dumps(store.docs, sort_keys=True) == before


def test_failure_after_success_keeps_last_known_data():
    store = provisioned()
    run_once(S, FixtureSource("risky"), store, now=NOW)
    good = dict(store.docs[PATH])
    store.writes.clear()
    res = run_once(S, FixtureSource("failing"), store, now=LATER)
    doc = store.docs[PATH]
    assert res.exit_code == 1
    assert store.writes == [("update", PATH, {"system_status": "Sync Failed", "status_explanation": SYNC_FAILED_EXPLANATION})]
    for f in ("last_sync_timestamp", "status_model", "metrics", "sync_initialized_at", "initial_sync_complete"):
        assert doc[f] == good[f]


def test_recovery_after_failure_replaces_whole_document():
    store = provisioned()
    run_once(S, FixtureSource("normal"), store, now=NOW)
    run_once(S, FixtureSource("failing"), store, now=LATER)
    res = run_once(S, FixtureSource("elevated"), store, now=LATER)
    assert res.exit_code == 0 and store.docs[PATH]["system_status"] == "Elevated"


def test_schema_failure_is_a_failed_poll(monkeypatch):
    import engine.run as run_mod

    store = provisioned()
    run_once(S, FixtureSource("normal"), store, now=NOW)
    store.writes.clear()
    monkeypatch.setattr(run_mod, "validate_feed", lambda doc, mode=None: ["forced"])
    res = run_once(S, FixtureSource("normal"), store, now=LATER)
    assert res.exit_code == 1 and res.errors == ["forced"]
    assert [w[0] for w in store.writes] == ["update"]


def test_provision_never_overwrites():
    store = provisioned()
    run_once(S, FixtureSource("normal"), store, now=NOW)
    assert store.create_stub_if_absent("uid1", "target", stub_document("target", LATER)) is False
    assert store.docs[PATH]["initial_sync_complete"] is True


def test_logs_are_json_and_never_contain_credentials(monkeypatch, capsys):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/secrets/devrails-poc-sa.json")
    store = provisioned()
    run_once(S, FixtureSource("normal"), store, now=NOW)
    run_once(S, FixtureSource("failing"), store, now=LATER)
    out = capsys.readouterr().out.strip().splitlines()
    recs = [json.loads(line) for line in out]
    assert [r["event"] for r in recs] == ["poll_succeeded", "poll_failed"]
    assert recs[0]["system_status"] == "Normal" and recs[1]["error_class"] == "unavailable"
    joined = "\n".join(out)
    assert "devrails-poc-sa" not in joined and "private_key" not in joined
    assert "metrics" not in recs[0]  # no payload dumps


def test_cli_fixture_dry_run_writes_nothing(capsys):
    code = main.main(["--fixture", "risky", "--now", "2026-10-25T19:55:00Z"])
    out = capsys.readouterr().out
    body = json.loads(out[out.index("{\n"):])
    assert code == 0 and body["would_write"][0]["op"] == "set"
    assert body["would_write"][0]["data"]["system_status"] == "Risky"


def test_cli_live_run_without_config_exits_2(monkeypatch, capsys):
    for k in ("DEVRAILS_GCP_PROJECT_ID", "DEVRAILS_POC_USER_UID", "DEVRAILS_POC_PROJECT_ID"):
        monkeypatch.delenv(k, raising=False)
    assert main.main([]) == 2
    assert "missing_configuration" in capsys.readouterr().out


def test_cli_provision_dry_run(capsys):
    assert main.main(["provision", "--uid", "u1", "--project", "p1", "--dry-run"]) == 0
    out = capsys.readouterr().out
    body = json.loads(out[out.index("{\n"):])
    assert body["would_create"] == "users/u1/projects/p1/dashboard_feed/current"
    assert len(body["data"]) == 9


# --- v1.3 / E's 2026-10-27 decisions ---------------------------------------------------------

def test_no_traffic_is_a_successful_sync_not_sync_failed():
    """N5: a reachable project with no traffic is zero usage."""
    store = MemoryFeedStore()
    store.create_stub_if_absent("uid1", "target", stub_document("target", clock.parse_iso_utc("2026-10-01T07:00:00Z")))
    res = run_once(S, FixtureSource("empty"), store, now=NOW)
    doc = store.docs[PATH]
    assert res.exit_code == 0 and doc["system_status"] == "Normal"
    assert doc["status_model"]["primary_reason"] == "no_recent_activity"
    assert doc["metrics"]["cloud_run_requests"]["current_value"] == 0


def test_a_week_old_feed_is_needed_before_the_no_activity_notice():
    store = MemoryFeedStore()
    store.create_stub_if_absent("uid1", "target", stub_document("target", NOW - timedelta(days=3)))
    run_once(S, FixtureSource("empty"), store, now=NOW)
    assert store.docs[PATH]["status_model"]["primary_reason"] == "all_within_limits"


def test_history_starts_at_sync_initialized_at_by_default():
    store = MemoryFeedStore()
    store.create_stub_if_absent("uid1", "target", stub_document("target", NOW - timedelta(hours=12)))
    run_once(S, FixtureSource("normal"), store, now=NOW)
    m = store.docs[PATH]["metrics"]["cloud_run_requests"]
    assert m["velocity_status"] == "insufficient_data" and m["projected_hours_to_limit"] is None
    assert len(m["sparkline_data_points"]) == 3  # only buckets since collection began


def test_cloud_monitoring_basis_counts_backfilled_history():
    from dataclasses import replace

    store = MemoryFeedStore()
    store.create_stub_if_absent("uid1", "target", stub_document("target", NOW - timedelta(hours=12)))
    run_once(replace(S, history_basis="cloud_monitoring"), FixtureSource("normal"), store, now=NOW)
    m = store.docs[PATH]["metrics"]["cloud_run_requests"]
    assert m["velocity_status"] == "stable" and len(m["sparkline_data_points"]) == 27


def test_cli_refuses_a_live_run_billed_to_the_customer(monkeypatch, capsys):
    monkeypatch.setenv("DEVRAILS_GCP_PROJECT_ID", "devrails-poc-target")
    monkeypatch.setenv("DEVRAILS_POC_USER_UID", "u1")
    monkeypatch.setenv("DEVRAILS_POC_PROJECT_ID", "devrails-poc-target")
    monkeypatch.delenv("DEVRAILS_FIREBASE_PROJECT_ID", raising=False)
    monkeypatch.setenv("DEVRAILS_QUOTA_PROJECT_ID", "devrails-poc-target")
    assert main.main(["--dry-run"]) == 2
    assert "quota_project_refused" in capsys.readouterr().out
    monkeypatch.delenv("DEVRAILS_QUOTA_PROJECT_ID")
    assert main.main(["--dry-run"]) == 2
    assert "quota_project_refused" in capsys.readouterr().out
