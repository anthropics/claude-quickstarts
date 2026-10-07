"""Unit testy — AuditLog append-only ring buffer (Fáze 6)."""
import pytest

from core.audit_log import AuditLog


@pytest.mark.unit
def test_record_and_get_events():
    al = AuditLog()
    al.record("task_submitted", "alice", task_id="t1", priority="NORMAL")
    events = al.get_events()
    assert len(events) == 1
    assert events[0]["event_type"] == "task_submitted"
    assert events[0]["user_id"] == "alice"
    assert events[0]["task_id"] == "t1"
    assert events[0]["details"]["priority"] == "NORMAL"


@pytest.mark.unit
def test_filter_by_event_type():
    al = AuditLog()
    al.record("task_submitted", "alice", task_id="t1")
    al.record("task_completed", "alice", task_id="t1")
    al.record("budget_set", "bob")
    events = al.get_events(event_type="task_submitted")
    assert len(events) == 1
    assert events[0]["event_type"] == "task_submitted"


@pytest.mark.unit
def test_filter_by_user_id():
    al = AuditLog()
    al.record("task_submitted", "alice", task_id="t1")
    al.record("task_submitted", "bob", task_id="t2")
    events = al.get_events(user_id="alice")
    assert all(e["user_id"] == "alice" for e in events)
    assert len(events) == 1


@pytest.mark.unit
def test_ring_buffer_maxlen():
    al = AuditLog(max_events=5)
    for i in range(10):
        al.record("evt", "user", task_id=str(i))
    assert len(al) == 5
    events = al.get_events(limit=10)
    task_ids = [e["task_id"] for e in events]
    assert "0" not in task_ids   # starší přepsány
    assert "9" in task_ids       # nejnovější zachovány


@pytest.mark.unit
def test_limit_parameter():
    al = AuditLog()
    for i in range(20):
        al.record("evt", "user")
    events = al.get_events(limit=5)
    assert len(events) == 5
