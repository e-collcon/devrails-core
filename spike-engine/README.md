# spike-engine

This is the DevRails PoC backend. Each process run is **one poll**:

1. Read Cloud Run `request_count` and Cloud Storage `total_bytes` from Cloud Monitoring.
2. Classify both against the free tier: thresholds at 75% and 90%, plus pace. Pace means how soon the free tier runs out at the last 24 hours' rate: under 7 × 24 h is Elevated, under 2 × 24 h is Risky.
3. Write `users/{uid}/projects/{projectId}/dashboard_feed/current` (Contract v1.3).

No traffic is zero usage, not a failure. A poll fails only when the project's data can't be reached.

The requirement IDs used below (BR-xx) are defined in `DevRails_Backend-Requirements.md`.

## Run it

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
python -m pytest                                    # offline test suite, about 1 s
python main.py --fixture risky --now 2026-10-25T19:55:00Z   # the whole engine on fixture data; writes nothing
python main.py --dry-run                            # live Cloud Monitoring read; prints the payload, writes nothing
python main.py                                      # live poll + Firestore write (Cloud Run Job)
python main.py provision --uid U --project P        # nine-field stub, only if the document is absent
python main.py validate feed.json                   # Contract v1.3 check
python main.py export-fixtures --out ../web-app/src/fixtures   # regenerate the dashboard fixtures
```

Fixtures: `normal`, `insufficient_history`, `rising`, `elevated`, `risky`, `runs_out_soon`, `empty` (no recent activity), `failing`.

## Configuration (env)

| Variable | Meaning |
|---|---|
| `DEVRAILS_GCP_PROJECT_ID` | Monitored (target) project |
| `DEVRAILS_FIREBASE_PROJECT_ID` | Host project that holds Firestore |
| `DEVRAILS_POC_USER_UID`, `DEVRAILS_POC_PROJECT_ID` | Firestore path segments |
| `DEVRAILS_POLLING_INTERVAL_MINUTES` | `10`. Use `5` only for an approved demo |
| `DEVRAILS_QUOTA_PROJECT_ID` | Project billed for Monitoring reads. Defaults to the host project (BR-74). **Required:** a live run is refused if it is empty or equals the monitored project (BR-16) |
| `DEVRAILS_HISTORY_BASIS` | `devrails_start` (default: history counts from `sync_initialized_at`) or `cloud_monitoring` (count what Monitoring already holds) (D5) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Only when using a key file. Otherwise ADC is used |

## Layout

| File | Role |
|---|---|
| `engine/clock.py` | Pacific billing clock with DST (BR-34) |
| `engine/metrics_config.py` | One entry per metric (BR-12) |
| `engine/monitoring.py` | Cloud Monitoring adapter: 3 calls per poll, at most 1 retry (BR-30–32, 70, 74) |
| `engine/readings.py` | Month-to-date, latest value, sparkline buckets, velocity facts (BR-33, 35, 38) |
| `engine/classify.py` | Thresholds, pace projection (48 h / 168 h), the per-metric level, rollup, precedence, no recent activity (BR-40–46) |
| `engine/explain.py` | `status_explanation` templates (BR-47). Lexie replaces the wording |
| `engine/payload.py` | Stub and synced documents (BR-51, 52) |
| `engine/schema.py` | v1.3 validator, run before every write (BR-53) |
| `engine/feed_store.py` | Firestore create / replace / mark-failed (BR-50–57) |
| `engine/run.py` | One poll: orchestration, exit codes, JSON logs (BR-04, 54, 55, 76) |
| `engine/fixtures.py` | Offline scenarios (BR-37) |

Exit codes:

- `0`: synced.
- `1`: poll failed. Sync Failed is written only if the project had synced before.
- `2`: not provisioned, or misconfigured. Nothing is written.
