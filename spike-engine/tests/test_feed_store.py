"""BR-51/52/54: FirestoreFeedStore issues exactly create / set / update on the canonical path."""

from google.api_core.exceptions import AlreadyExists

from engine.feed_store import FirestoreFeedStore


class FakeSnap:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data)


class FakeRef:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def get(self):
        return FakeSnap(self.db.data.get(self.path))

    def create(self, doc):
        self.db.calls.append(("create", self.path))
        if self.path in self.db.data:
            raise AlreadyExists("exists")
        self.db.data[self.path] = dict(doc)

    def set(self, doc):
        self.db.calls.append(("set", self.path))
        self.db.data[self.path] = dict(doc)

    def update(self, fields):
        self.db.calls.append(("update", self.path, tuple(sorted(fields))))
        self.db.data[self.path].update(fields)


class FakeDb:
    def __init__(self):
        self.data, self.calls = {}, []

    def document(self, path):
        return FakeRef(self, path)


def test_firestore_store_operations():
    db = FakeDb()
    store = FirestoreFeedStore("host", client=db)
    path = "users/u/projects/p/dashboard_feed/current"
    assert store.get("u", "p") is None
    assert store.create_stub_if_absent("u", "p", {"a": 1}) is True
    assert store.create_stub_if_absent("u", "p", {"a": 2}) is False
    assert store.get("u", "p") == {"a": 1}
    store.replace_synced("u", "p", {"b": 2})
    store.mark_sync_failed("u", "p", "x")
    assert db.calls == [("create", path), ("create", path), ("set", path),
                        ("update", path, ("status_explanation", "system_status"))]
    assert db.data[path] == {"b": 2, "system_status": "Sync Failed", "status_explanation": "x"}
