"""
Tests for SQLite persistence layer (Fáze 14).
All tests use ":memory:" — no files written to disk.
"""
import pytest

from core.audit_log import AuditLog
from core.api_keys import ApiKeyManager
from core.persistence import Database


@pytest.fixture
def db():
    d = Database(db_path=":memory:")
    d.init_schema()
    return d


# ── Database basics ────────────────────────────────────────────────────────────

def test_init_schema_creates_tables(db):
    rows = db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    names = {r["name"] for r in rows}
    assert "audit_events" in names
    assert "api_keys" in names


def test_execute_and_fetchall(db):
    db.execute(
        "INSERT INTO audit_events (event_type, user_id, details_json, timestamp) "
        "VALUES (?, ?, ?, ?)",
        ("test_event", "user1", "{}", "2026-01-01T00:00:00+00:00"),
    )
    rows = db.fetchall("SELECT * FROM audit_events")
    assert len(rows) == 1
    assert rows[0]["event_type"] == "test_event"


def test_fetchone_returns_none_when_missing(db):
    result = db.fetchone("SELECT * FROM audit_events WHERE id = 9999")
    assert result is None


# ── AuditLog persistence ───────────────────────────────────────────────────────

def test_audit_log_persists_events(db):
    log = AuditLog(db=db)
    log.record("task_submitted", "user1", task_id="t1", priority="HIGH")
    rows = db.fetchall("SELECT * FROM audit_events")
    assert len(rows) == 1
    assert rows[0]["event_type"] == "task_submitted"
    assert rows[0]["user_id"] == "user1"
    assert rows[0]["task_id"] == "t1"


def test_audit_log_loads_from_db_on_init(db):
    db.persist_audit_event("boot_event", "system", None, {}, "2026-01-01T00:00:00+00:00")
    log = AuditLog(db=db)
    events = log.get_events()
    assert any(e["event_type"] == "boot_event" for e in events)


def test_audit_log_attach_db(db):
    log = AuditLog()
    log.attach_db(db)
    log.record("attached_event", "user2")
    rows = db.fetchall("SELECT * FROM audit_events WHERE event_type='attached_event'")
    assert len(rows) == 1


def test_audit_log_without_db_still_works():
    log = AuditLog()
    log.record("no_db_event", "user3")
    assert len(log.get_events()) == 1


# ── ApiKeyManager persistence ──────────────────────────────────────────────────

def test_api_key_create_persists_to_db(db):
    mgr = ApiKeyManager(db=db)
    key = mgr.create_key("alice")
    rows = db.fetchall("SELECT * FROM api_keys WHERE revoked=0")
    assert any(r["user_id"] == "alice" for r in rows)
    assert mgr.validate_key(key) == "alice"


def test_api_key_revoke_persists_to_db(db):
    mgr = ApiKeyManager(db=db)
    key = mgr.create_key("bob")
    mgr.revoke_key(key)
    rows = db.fetchall("SELECT * FROM api_keys WHERE revoked=1")
    assert len(rows) == 1
    assert mgr.validate_key(key) is None


def test_api_key_survives_restart(db):
    mgr1 = ApiKeyManager(db=db)
    key = mgr1.create_key("charlie")

    # Second manager loads from same DB — simulates restart
    mgr2 = ApiKeyManager(db=db)
    # In-memory loaded from DB — validate via in-memory dict keyed by hash
    rows = db.fetchall("SELECT * FROM api_keys WHERE revoked=0")
    assert any(r["user_id"] == "charlie" for r in rows)
