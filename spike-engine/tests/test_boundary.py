"""BR-36 (TASK-052): Cloud Monitoring is the only Google API the engine calls.
BR-01: no web-app coupling. BR-23: credentials never committed."""

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_GOOGLE = {
    "google.cloud.monitoring_v3",   # Cloud Monitoring (read-only)
    "google.api_core",              # errors, client options
    "google.auth",                  # credential errors only
    "google.protobuf",              # Timestamp / Duration
}
ALLOWED_FIREBASE = {"firebase_admin", "firebase_admin.firestore"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


def test_only_cloud_monitoring_and_firestore_are_imported():
    for path in list((ROOT / "engine").glob("*.py")) + [ROOT / "main.py", ROOT / "config.py"]:
        for name in _imports(path):
            if any(a.startswith(name + ".") for a in ALLOWED_GOOGLE):
                continue  # a parent package such as `google.cloud` in `from google.cloud import x`
            if name.startswith("google"):
                assert any(name == a or name.startswith(a + ".") for a in ALLOWED_GOOGLE), (path.name, name)
            if name.startswith("firebase"):
                assert name in ALLOWED_FIREBASE, (path.name, name)
            for banned in ("billing", "budget", "bigquery", "asset", "quotas", "iam", "secretmanager", "requests"):
                assert banned not in name.split("."), (path.name, name)


def test_no_credential_files_are_tracked():
    repo = ROOT.parent
    try:
        tracked = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return
    for line in tracked.splitlines():
        if line.startswith("spike-engine/credentials/"):
            assert line.endswith(".gitkeep"), line
        assert not line.endswith(".env"), line
