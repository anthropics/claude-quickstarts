"""
Tests for QuotaManager (Fáze 24).
All offline — no external dependencies.
"""
import pytest

from core.quota_manager import QuotaManager, QuotaWindow


@pytest.fixture
def mgr():
    return QuotaManager()


# ── Validation ────────────────────────────────────────────────────────────────

def test_set_quota_empty_user_raises(mgr):
    with pytest.raises(ValueError, match="user_id"):
        mgr.set_quota("", "requests", 100)


def test_set_quota_invalid_metric_raises(mgr):
    with pytest.raises(ValueError, match="metric"):
        mgr.set_quota("alice", "bananas", 100)


def test_set_quota_zero_limit_raises(mgr):
    with pytest.raises(ValueError, match="limit"):
        mgr.set_quota("alice", "requests", 0)


def test_set_quota_invalid_window_raises(mgr):
    with pytest.raises(ValueError, match="window"):
        mgr.set_quota("alice", "requests", 100, window="weekly")


# ── CRUD ──────────────────────────────────────────────────────────────────────

def test_set_quota_returns_uuid(mgr):
    rid = mgr.set_quota("alice", "requests", 100)
    assert rid is not None and len(rid) == 36


def test_quota_count(mgr):
    mgr.set_quota("alice", "requests", 100)
    mgr.set_quota("alice", "tokens", 5000)
    assert mgr.quota_count() == 2


def test_get_quota_returns_dict(mgr):
    rid = mgr.set_quota("alice", "cost_usd", 10.0, window="monthly")
    r = mgr.get_quota(rid)
    assert r["user_id"] == "alice"
    assert r["metric"] == "cost_usd"
    assert r["limit"] == 10.0
    assert r["window"] == "monthly"


def test_get_quota_missing_returns_none(mgr):
    assert mgr.get_quota("ghost") is None


def test_list_quotas_all(mgr):
    mgr.set_quota("alice", "requests", 10)
    mgr.set_quota("bob", "tokens", 100)
    assert len(mgr.list_quotas()) == 2


def test_list_quotas_by_user(mgr):
    mgr.set_quota("alice", "requests", 10)
    mgr.set_quota("bob", "tokens", 100)
    assert len(mgr.list_quotas(user_id="alice")) == 1


def test_delete_quota(mgr):
    rid = mgr.set_quota("alice", "requests", 10)
    assert mgr.delete_quota(rid) is True
    assert mgr.get_quota(rid) is None


def test_delete_missing_returns_false(mgr):
    assert mgr.delete_quota("ghost") is False


# ── Usage + check ─────────────────────────────────────────────────────────────

def test_no_quota_always_allowed(mgr):
    result = mgr.check_quota("alice", "requests")
    assert result["allowed"] is True
    assert result["rules"] == []


def test_within_quota_allowed(mgr):
    mgr.set_quota("alice", "requests", 10, window="daily")
    mgr.record_usage("alice", requests=5)
    result = mgr.check_quota("alice", "requests")
    assert result["allowed"] is True
    assert result["rules"][0]["used"] == 5.0
    assert result["rules"][0]["remaining"] == 5.0


def test_at_limit_blocked(mgr):
    mgr.set_quota("alice", "requests", 3, window="daily")
    mgr.record_usage("alice", requests=3)
    result = mgr.check_quota("alice", "requests")
    assert result["allowed"] is False


def test_tokens_quota(mgr):
    mgr.set_quota("bob", "tokens", 1000, window="hourly")
    mgr.record_usage("bob", tokens=999)
    r = mgr.check_quota("bob", "tokens")
    assert r["allowed"] is True
    mgr.record_usage("bob", tokens=1)
    r2 = mgr.check_quota("bob", "tokens")
    assert r2["allowed"] is False


def test_cost_quota(mgr):
    mgr.set_quota("carol", "cost_usd", 5.0, window="monthly")
    mgr.record_usage("carol", cost_usd=4.99)
    assert mgr.check_quota("carol", "cost_usd")["allowed"] is True
    mgr.record_usage("carol", cost_usd=0.02)
    assert mgr.check_quota("carol", "cost_usd")["allowed"] is False


def test_multiple_rules_one_exceeded_blocks(mgr):
    mgr.set_quota("alice", "requests", 10, window="hourly")
    mgr.set_quota("alice", "requests", 2, window="daily")
    mgr.record_usage("alice", requests=3)
    result = mgr.check_quota("alice", "requests")
    assert result["allowed"] is False  # daily rule exceeded


def test_usage_summary_structure(mgr):
    mgr.record_usage("alice", requests=5, tokens=200, cost_usd=0.01)
    summary = mgr.get_usage_summary("alice")
    assert summary["daily"]["requests"] == 5.0
    assert summary["daily"]["tokens"] == 200.0
    assert summary["monthly"]["cost_usd"] == pytest.approx(0.01)


def test_usage_accumulates(mgr):
    mgr.record_usage("alice", requests=3)
    mgr.record_usage("alice", requests=7)
    summary = mgr.get_usage_summary("alice")
    assert summary["daily"]["requests"] == 10.0


def test_independent_users(mgr):
    mgr.set_quota("alice", "requests", 5, window="daily")
    mgr.record_usage("alice", requests=5)
    mgr.record_usage("bob", requests=100)
    assert mgr.check_quota("alice", "requests")["allowed"] is False
    assert mgr.check_quota("bob", "requests")["allowed"] is True
