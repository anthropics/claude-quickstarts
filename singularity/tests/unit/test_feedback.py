"""
Tests for FeedbackStore (Fáze 17).
All offline — uses Database(":memory:") for persistence tests.
"""
import pytest

from core.feedback import FeedbackStore
from core.persistence import Database


@pytest.fixture
def store():
    return FeedbackStore()


@pytest.fixture
def db():
    d = Database(db_path=":memory:")
    d.init_schema()
    return d


# ── Basic record / retrieve ────────────────────────────────────────────────────

def test_record_returns_feedback_id(store):
    fid = store.record("task-1", "sess-1", "user1", rating=4)
    assert fid is not None
    assert len(fid) == 36  # UUID


def test_get_feedback_returns_dict(store):
    fid = store.record("task-1", "sess-1", "user1", rating=5, thumbs="up", comment="Great!")
    fb = store.get_feedback(fid)
    assert fb is not None
    assert fb["rating"] == 5
    assert fb["thumbs"] == "up"
    assert fb["comment"] == "Great!"
    assert fb["task_id"] == "task-1"


def test_get_feedback_missing_returns_none(store):
    assert store.get_feedback("no-such-id") is None


def test_get_by_task_filters_correctly(store):
    store.record("task-A", "s1", "u1", rating=3)
    store.record("task-A", "s2", "u2", rating=4)
    store.record("task-B", "s3", "u3", rating=5)
    results = store.get_by_task("task-A")
    assert len(results) == 2
    assert all(r["task_id"] == "task-A" for r in results)


def test_get_by_task_empty_when_no_match(store):
    assert store.get_by_task("nonexistent") == []


# ── Validation ────────────────────────────────────────────────────────────────

def test_rating_out_of_range_raises(store):
    with pytest.raises(ValueError):
        store.record("t", "s", "u", rating=0)
    with pytest.raises(ValueError):
        store.record("t", "s", "u", rating=6)


def test_invalid_thumbs_raises(store):
    with pytest.raises(ValueError):
        store.record("t", "s", "u", rating=3, thumbs="meh")


# ── Stats ─────────────────────────────────────────────────────────────────────

def test_stats_empty_store(store):
    stats = store.get_stats()
    assert stats["total"] == 0
    assert stats["avg_rating"] is None
    assert stats["thumbs_up_pct"] is None


def test_stats_with_entries(store):
    store.record("t1", "s", "u", rating=4, thumbs="up")
    store.record("t2", "s", "u", rating=2, thumbs="down")
    store.record("t3", "s", "u", rating=5, thumbs="up")
    stats = store.get_stats()
    assert stats["total"] == 3
    assert stats["avg_rating"] == pytest.approx(11 / 3, rel=1e-2)
    assert stats["thumbs_up"] == 2
    assert stats["thumbs_down"] == 1
    assert stats["thumbs_up_pct"] == pytest.approx(66.7, abs=0.1)


def test_count_matches_records(store):
    for i in range(5):
        store.record(f"task-{i}", "s", "u", rating=3)
    assert store.count() == 5


# ── Persistence ───────────────────────────────────────────────────────────────

def test_persist_to_db(db):
    store = FeedbackStore(db=db)
    store.record("task-db", "sess-db", "user-db", rating=5, thumbs="up")
    rows = db.fetchall("SELECT * FROM feedback")
    assert len(rows) == 1
    assert rows[0]["task_id"] == "task-db"
    assert rows[0]["rating"] == 5


def test_load_from_db_on_init(db):
    db.persist_feedback("fb-1", "task-x", "sess-x", "user-x", 4, "up", "nice", "2026-01-01T00:00:00+00:00")
    store = FeedbackStore(db=db)
    assert store.count() == 1
    fb = store.get_feedback("fb-1")
    assert fb is not None
    assert fb["rating"] == 4


def test_attach_db_persists_subsequent_records(db):
    store = FeedbackStore()
    store.attach_db(db)
    store.record("task-attach", "sess", "user", rating=2, thumbs="down")
    rows = db.fetchall("SELECT * FROM feedback")
    assert len(rows) == 1
    assert rows[0]["thumbs"] == "down"
