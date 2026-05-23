"""Tests for the gateway SessionStore (SQLite)."""

from __future__ import annotations

from adzekit.gateway.session_store import SessionStore


def test_set_get_round_trip(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite")
    assert store.get(42) is None
    store.set(42, "abc-123")
    assert store.get(42) == "abc-123"


def test_set_upserts(tmp_path):
    """Setting a new session_id for an existing chat_id overwrites."""
    store = SessionStore(tmp_path / "s.sqlite")
    store.set(99, "old")
    store.set(99, "new")
    assert store.get(99) == "new"


def test_get_other_chat_does_not_leak(tmp_path):
    store = SessionStore(tmp_path / "s.sqlite")
    store.set(1, "session-one")
    store.set(2, "session-two")
    assert store.get(1) == "session-one"
    assert store.get(2) == "session-two"


def test_clear_removes_session(tmp_path):
    store = SessionStore(tmp_path / "s.sqlite")
    store.set(7, "x")
    assert store.clear(7) is True
    assert store.get(7) is None
    # Second clear returns False (idempotent).
    assert store.clear(7) is False


def test_creates_parent_dirs(tmp_path):
    """SessionStore creates the parent dir if it doesn't exist."""
    db = tmp_path / "deeply" / "nested" / "sessions.sqlite"
    assert not db.parent.exists()
    store = SessionStore(db)
    store.set(1, "x")
    assert db.exists()


def test_persists_across_instances(tmp_path):
    """Round-trip through a fresh SessionStore instance (mimics daemon restart)."""
    db = tmp_path / "s.sqlite"
    s1 = SessionStore(db)
    s1.set(5, "persistent")
    s1.close()
    s2 = SessionStore(db)
    assert s2.get(5) == "persistent"


def test_context_manager(tmp_path):
    with SessionStore(tmp_path / "s.sqlite") as store:
        store.set(1, "x")
        assert store.get(1) == "x"
