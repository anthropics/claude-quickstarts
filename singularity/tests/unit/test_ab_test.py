"""
Tests for ABTestManager (Fáze 19).
All offline — no external dependencies.
"""
import pytest
from unittest.mock import patch

from core.ab_test import ABTestManager, VariantMetrics


@pytest.fixture
def mgr():
    return ABTestManager()


def _make_exp(mgr, name="test", control="claude", treatment="gemini", split=0.5) -> str:
    return mgr.create_experiment(name, control, treatment, split)


# ── Creation ──────────────────────────────────────────────────────────────────

def test_create_returns_id(mgr):
    eid = _make_exp(mgr)
    assert eid is not None and len(eid) == 36


def test_invalid_traffic_split_raises(mgr):
    with pytest.raises(ValueError):
        mgr.create_experiment("x", "claude", "gemini", traffic_split=1.5)
    with pytest.raises(ValueError):
        mgr.create_experiment("x", "claude", "gemini", traffic_split=-0.1)


def test_same_providers_raises(mgr):
    with pytest.raises(ValueError):
        mgr.create_experiment("x", "claude", "claude")


def test_experiment_count(mgr):
    _make_exp(mgr, "a")
    _make_exp(mgr, "b")
    assert mgr.experiment_count() == 2


# ── Retrieval ─────────────────────────────────────────────────────────────────

def test_get_experiment_returns_dict(mgr):
    eid = _make_exp(mgr, "my-exp", split=0.3)
    exp = mgr.get_experiment(eid)
    assert exp["name"] == "my-exp"
    assert exp["traffic_split"] == 0.3
    assert exp["status"] == "active"


def test_get_missing_returns_none(mgr):
    assert mgr.get_experiment("ghost") is None


def test_list_experiments(mgr):
    _make_exp(mgr, "alpha")
    _make_exp(mgr, "beta")
    names = {e["name"] for e in mgr.list_experiments()}
    assert names == {"alpha", "beta"}


# ── Update ────────────────────────────────────────────────────────────────────

def test_update_status_to_paused(mgr):
    eid = _make_exp(mgr)
    assert mgr.update_experiment(eid, status="paused") is True
    assert mgr.get_experiment(eid)["status"] == "paused"


def test_update_invalid_status_raises(mgr):
    eid = _make_exp(mgr)
    with pytest.raises(ValueError):
        mgr.update_experiment(eid, status="unknown")


def test_update_traffic_split(mgr):
    eid = _make_exp(mgr)
    mgr.update_experiment(eid, traffic_split=0.8)
    assert mgr.get_experiment(eid)["traffic_split"] == 0.8


def test_update_missing_returns_false(mgr):
    assert mgr.update_experiment("ghost", status="paused") is False


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_experiment(mgr):
    eid = _make_exp(mgr)
    assert mgr.delete_experiment(eid) is True
    assert mgr.get_experiment(eid) is None


def test_delete_missing_returns_false(mgr):
    assert mgr.delete_experiment("ghost") is False


# ── Variant assignment ────────────────────────────────────────────────────────

def test_assign_returns_one_of_two_providers(mgr):
    eid = _make_exp(mgr, control="claude", treatment="gemini", split=0.5)
    provider = mgr.assign_variant(eid)
    assert provider in ("claude", "gemini")


def test_assign_split_0_always_control(mgr):
    eid = _make_exp(mgr, control="claude", treatment="gemini", split=0.0)
    for _ in range(20):
        assert mgr.assign_variant(eid) == "claude"


def test_assign_split_1_always_treatment(mgr):
    eid = _make_exp(mgr, control="claude", treatment="gemini", split=1.0)
    for _ in range(20):
        assert mgr.assign_variant(eid) == "gemini"


def test_assign_paused_raises(mgr):
    eid = _make_exp(mgr)
    mgr.update_experiment(eid, status="paused")
    with pytest.raises(RuntimeError, match="not active"):
        mgr.assign_variant(eid)


def test_assign_missing_raises(mgr):
    with pytest.raises(KeyError):
        mgr.assign_variant("ghost")


# ── Outcome recording ─────────────────────────────────────────────────────────

def test_record_control_outcome(mgr):
    eid = _make_exp(mgr, control="claude", treatment="gemini")
    mgr.record_outcome(eid, "claude", success=True, latency_ms=200.0)
    exp = mgr.get_experiment(eid)
    assert exp["control"]["requests"] == 1
    assert exp["control"]["successes"] == 1
    assert exp["control"]["avg_latency_ms"] == 200.0


def test_record_treatment_outcome(mgr):
    eid = _make_exp(mgr, control="claude", treatment="gemini")
    mgr.record_outcome(eid, "gemini", success=False, latency_ms=500.0)
    exp = mgr.get_experiment(eid)
    assert exp["treatment"]["requests"] == 1
    assert exp["treatment"]["failures"] == 1


def test_record_with_rating(mgr):
    eid = _make_exp(mgr)
    mgr.record_outcome(eid, "claude", success=True, rating=4.5)
    exp = mgr.get_experiment(eid)
    assert exp["control"]["avg_rating"] == 4.5


def test_record_unknown_provider_returns_false(mgr):
    eid = _make_exp(mgr, control="claude", treatment="gemini")
    assert mgr.record_outcome(eid, "ollama", success=True) is False


def test_record_missing_experiment_returns_false(mgr):
    assert mgr.record_outcome("ghost", "claude", success=True) is False


# ── VariantMetrics ────────────────────────────────────────────────────────────

def test_metrics_success_rate_zero_requests():
    m = VariantMetrics()
    assert m.success_rate is None
    assert m.avg_latency_ms is None
    assert m.avg_rating is None


def test_metrics_success_rate_computed():
    m = VariantMetrics()
    m.record(True, 100.0)
    m.record(False, 200.0)
    assert m.success_rate == pytest.approx(0.5)
    assert m.avg_latency_ms == pytest.approx(150.0)
