"""
spike-engine — main.py
DevRails PoC | PRD-001 | Backend Requirements BR-04, BR-37, BR-51

One process run = one poll cycle (Cloud Scheduler → Cloud Run Job).

  python main.py                         poll the configured project, write the feed
  python main.py --dry-run               poll, print the sanitized payload, write nothing
  python main.py --fixture risky         run the whole engine on built-in fixture data
  python main.py provision --uid U --project P [--gcp-project G]
                                         create the nine-field stub if absent (never overwrites)
  python main.py validate FILE.json      check a feed document against Contract v1.3
  python main.py export-fixtures --out DIR
                                         write engine-generated dashboard fixtures for the web-app

Canonical Firestore path: users/{uid}/projects/{projectId}/dashboard_feed/current
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _load_dotenv() -> None:
    """Local development only: load spike-engine/.env (git-ignored) if present."""
    env_file = HERE / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
        except ImportError:
            return
        load_dotenv(env_file, override=False)


def _settings(args):
    import config

    s = config.load_settings()
    if getattr(args, "fixture", None):
        from dataclasses import replace

        s = replace(s, gcp_project_id=s.gcp_project_id or "devrails-fixture-target",
                    uid=s.uid or "fixture-uid", project_id=s.project_id or "devrails-fixture-target")
    return s


def cmd_run(args) -> int:
    from engine import clock
    from engine.feed_store import DryRunStore, FirestoreFeedStore
    from engine.payload import stub_document
    from engine.run import log, run_once

    settings = _settings(args)
    now = clock.parse_iso_utc(args.now) if args.now else datetime.now(clock.UTC)

    if args.fixture:
        from engine.fixtures import FixtureSource

        source = FixtureSource(args.fixture)
        hours = source.s.history_hours or 30 * 24
        stub = stub_document(settings.gcp_project_id, now - timedelta(hours=hours))
        store = DryRunStore(seed=stub)  # fixtures never touch Firestore
    else:
        missing = settings.missing_for_live_run()
        if missing:
            log("ERROR", "missing_configuration", missing=missing)
            return 2
        problem = settings.quota_problem()
        if problem:
            log("ERROR", "quota_project_refused", reason=problem)
            return 2
        from engine.monitoring import MonitoringSource

        source = MonitoringSource(
            settings.gcp_project_id,
            quota_project_id=settings.quota_project_id,
            timeout_seconds=settings.api_timeout_seconds,
            max_attempts=settings.api_max_attempts,
            backoff_seconds=settings.api_retry_backoff_seconds,
        )
        live = FirestoreFeedStore(settings.firebase_project_id) if settings.firebase_project_id else None
        if args.dry_run:
            store = DryRunStore(inner=live, seed=None if live else stub_document(settings.gcp_project_id, now))
        elif live is None:
            log("ERROR", "missing_configuration", missing=["DEVRAILS_FIREBASE_PROJECT_ID"])
            return 2
        else:
            store = live

    result = run_once(settings, source, store, now=now)
    if args.dry_run or args.fixture:
        print(json.dumps({"exit_code": result.exit_code, "outcome": result.outcome,
                          "would_write": [{"op": op, "path": path, "data": data} for op, path, data in store.writes],
                          "errors": result.errors}, indent=2, ensure_ascii=False))
    return result.exit_code


def cmd_provision(args) -> int:
    from engine import clock
    from engine.feed_store import DryRunStore, FirestoreFeedStore, feed_path
    from engine.payload import stub_document
    from engine.run import log
    from engine.schema import validate_feed

    settings = _settings(args)
    gcp_project = args.gcp_project or args.project
    stub = stub_document(gcp_project, datetime.now(clock.UTC))
    errors = validate_feed(stub)
    if errors:
        log("ERROR", "stub_invalid", errors=errors)
        return 1
    if args.dry_run:
        store = DryRunStore()
    else:
        if not settings.firebase_project_id:
            log("ERROR", "missing_configuration", missing=["DEVRAILS_FIREBASE_PROJECT_ID"])
            return 2
        store = FirestoreFeedStore(settings.firebase_project_id)
    created = store.create_stub_if_absent(args.uid, args.project, stub)
    log("INFO" if created else "WARNING", "provision", path_project=args.project,
        gcp_project=gcp_project, created=created, dry_run=bool(args.dry_run),
        note=None if created else "feed already exists; left untouched")
    if args.dry_run:
        print(json.dumps({"would_create": feed_path(args.uid, args.project), "data": stub}, indent=2, ensure_ascii=False))
    return 0


def cmd_validate(args) -> int:
    from engine.schema import validate_feed

    doc = json.loads(Path(args.file).read_text(encoding="utf-8"))
    errors = validate_feed(doc)
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


def cmd_export_fixtures(args) -> int:
    from engine.web_fixtures import export_web_fixtures

    path = export_web_fixtures(Path(args.out))
    print(json.dumps({"written": str(path)}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="spike-engine", description="DevRails spike-engine (one poll per run)")
    sub = p.add_subparsers(dest="command")

    run = sub.add_parser("run", help="poll once (default)")
    run.add_argument("--dry-run", action="store_true", help="print the payload, write nothing")
    run.add_argument("--fixture", metavar="STATE", help="use built-in fixture data instead of Cloud Monitoring")
    run.add_argument("--now", metavar="ISO_UTC", help="override the clock, e.g. 2026-10-25T19:55:00Z")
    run.set_defaults(func=cmd_run)

    prov = sub.add_parser("provision", help="create the nine-field stub if absent")
    prov.add_argument("--uid", required=True)
    prov.add_argument("--project", required=True, help="projectId in the Firestore path")
    prov.add_argument("--gcp-project", help="monitored GCP project id (defaults to --project)")
    prov.add_argument("--dry-run", action="store_true")
    prov.set_defaults(func=cmd_provision)

    val = sub.add_parser("validate", help="validate a feed JSON file")
    val.add_argument("file")
    val.set_defaults(func=cmd_validate)

    exp = sub.add_parser("export-fixtures", help="write web-app dashboard fixtures")
    exp.add_argument("--out", required=True)
    exp.set_defaults(func=cmd_export_fixtures)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in {"run", "provision", "validate", "export-fixtures", "-h", "--help"}:
        argv.insert(0, "run")
    _load_dotenv()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
