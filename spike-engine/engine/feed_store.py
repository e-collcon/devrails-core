"""
Firestore feed store — BR-50..57 (TASK-019, 021, 061, 068, 072, 125, 129).

Path: users/{uid}/projects/{projectId}/dashboard_feed/current [CONTRACT A.1].
Only the spike-engine and operator tooling write here, through the Firebase
Admin SDK (which bypasses Security Rules; clients can never write).

Three write operations, nothing else:
  create_stub_if_absent  provisioning; never overwrites (atomic create)
  replace_synced         full-document replace after a successful poll
  mark_sync_failed       updates only system_status + status_explanation

MemoryFeedStore and DryRunStore implement the same interface for tests,
`--dry-run` and fixtures.
"""

from __future__ import annotations

import copy
from typing import Protocol


def feed_path(uid: str, project_id: str) -> str:
    if not uid or not project_id or "/" in uid or "/" in project_id:
        raise ValueError("uid and project_id must be non-empty and contain no '/'")
    return f"users/{uid}/projects/{project_id}/dashboard_feed/current"


class FeedStore(Protocol):
    def get(self, uid: str, project_id: str) -> dict | None: ...
    def create_stub_if_absent(self, uid: str, project_id: str, stub: dict) -> bool: ...
    def replace_synced(self, uid: str, project_id: str, doc: dict) -> None: ...
    def mark_sync_failed(self, uid: str, project_id: str, explanation: str) -> None: ...


class MemoryFeedStore:
    """In-memory store with the same semantics. `writes` records every write for tests."""

    def __init__(self, docs: dict[str, dict] | None = None):
        self.docs: dict[str, dict] = copy.deepcopy(docs) if docs else {}
        self.writes: list[tuple[str, str, dict]] = []

    def get(self, uid, project_id):
        doc = self.docs.get(feed_path(uid, project_id))
        return copy.deepcopy(doc) if doc is not None else None

    def create_stub_if_absent(self, uid, project_id, stub):
        path = feed_path(uid, project_id)
        if path in self.docs:
            return False
        self.docs[path] = copy.deepcopy(stub)
        self.writes.append(("create", path, copy.deepcopy(stub)))
        return True

    def replace_synced(self, uid, project_id, doc):
        path = feed_path(uid, project_id)
        self.docs[path] = copy.deepcopy(doc)
        self.writes.append(("set", path, copy.deepcopy(doc)))

    def mark_sync_failed(self, uid, project_id, explanation):
        path = feed_path(uid, project_id)
        fields = {"system_status": "Sync Failed", "status_explanation": explanation}
        self.docs[path].update(fields)
        self.writes.append(("update", path, fields))


class DryRunStore:
    """Reads from `inner` (or a seeded stub), records writes, performs none."""

    def __init__(self, inner: FeedStore | None = None, seed: dict | None = None):
        self.inner = inner
        self.seed = seed
        self.writes: list[tuple[str, str, dict]] = []

    def get(self, uid, project_id):
        if self.inner is not None:
            return self.inner.get(uid, project_id)
        return copy.deepcopy(self.seed)

    def create_stub_if_absent(self, uid, project_id, stub):
        self.writes.append(("create", feed_path(uid, project_id), copy.deepcopy(stub)))
        return True

    def replace_synced(self, uid, project_id, doc):
        self.writes.append(("set", feed_path(uid, project_id), copy.deepcopy(doc)))

    def mark_sync_failed(self, uid, project_id, explanation):
        self.writes.append(("update", feed_path(uid, project_id),
                            {"system_status": "Sync Failed", "status_explanation": explanation}))


class FirestoreFeedStore:
    """Firebase Admin SDK implementation. Uses Application Default Credentials of the
    runtime service account in the host project (BR-25); no key is read here."""

    def __init__(self, firebase_project_id: str, client=None):
        if client is None:
            import firebase_admin
            from firebase_admin import firestore

            try:
                app = firebase_admin.get_app("devrails-spike-engine")
            except ValueError:
                options = {"projectId": firebase_project_id} if firebase_project_id else None
                app = firebase_admin.initialize_app(options=options, name="devrails-spike-engine")
            client = firestore.client(app)
        self._db = client

    def _ref(self, uid, project_id):
        return self._db.document(feed_path(uid, project_id))

    def get(self, uid, project_id):
        snap = self._ref(uid, project_id).get()
        return snap.to_dict() if snap.exists else None

    def create_stub_if_absent(self, uid, project_id, stub):
        from google.api_core.exceptions import AlreadyExists, Conflict

        try:
            self._ref(uid, project_id).create(stub)  # fails if the document exists
            return True
        except (AlreadyExists, Conflict):
            return False

    def replace_synced(self, uid, project_id, doc):
        self._ref(uid, project_id).set(doc)  # full replace: no stray fields survive (BR-52)

    def mark_sync_failed(self, uid, project_id, explanation):
        self._ref(uid, project_id).update(
            {"system_status": "Sync Failed", "status_explanation": explanation}
        )
