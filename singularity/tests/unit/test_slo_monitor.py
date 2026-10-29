"""
Unit tests — SLO Monitor (Fáze 58). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.slo_monitor import SLOKind, SLOMonitor, SLOReport, SLOStatus


# ── Registration ─────────────────────────────────────────────────────────────────

def test_register_and_list():
    m = SLOMonitor()
    m.register("api", target=0.99)
    assert m.list_slos() == ["api"]


def test_register_requires_name():
    m = SLOMonitor()
    with pytest.raises(ValueError):
        m.register("", target=0.99)


def test_register_invalid_target():
    m = SLOMonitor()
    with pytest.raises(ValueError):
        m.register("x", target=1.0)
    with pytest.raises(ValueError):
        m.register("x", target=0.0)


def test_register_invalid_window():
    m = SLOMonitor()
    with pytest.raises(ValueError):
        m.register("x", target=0.99, window=0)


def test_latency_requires_threshold():
    m = SLOMonitor()
    with pytest.raises(ValueError):
        m.register("lat", kind=SLOKind.LATENCY, target=0.99)


def test_delete():
    m = SLOMonitor()
    m.register("a", target=0.99)
    assert m.delete("a") is True
    assert m.list_slos() == []


def test_delete_missing():
    m = SLOMonitor()
    assert m.delete("nope") is False


# ── Recording validation ─────────────────────────────────────────────────────────

def test_record_unknown_slo_raises():
    m = SLOMonitor()
    with pytest.raises(KeyError):
        m.record_success("ghost")


def test_record_latency_on_availability_raises():
    m = SLOMonitor()
    m.register("api", kind=SLOKind.AVAILABILITY, target=0.99)
    with pytest.raises(ValueError):
        m.record_latency("api", 10.0)


# ── Availability SLO ─────────────────────────────────────────────────────────────

def test_all_success_healthy():
    m = SLOMonitor()
    m.register("api", target=0.99)
    for _ in range(100):
        m.record_success("api")
    r = m.report("api")
    assert r.sli == 1.0
    assert r.status == SLOStatus.HEALTHY.value
    assert r.budget_remaining == 1.0
    assert r.burn_rate == 0.0


def test_breach_when_below_target():
    m = SLOMonitor()
    m.register("api", target=0.99, window=100)
    # 90 good / 10 bad → SLI 0.90 < 0.99 → breached
    for _ in range(90):
        m.record_success("api")
    for _ in range(10):
        m.record_failure("api")
    r = m.report("api")
    assert r.sli == pytest.approx(0.90)
    assert r.status == SLOStatus.BREACHED.value


def test_error_budget_value():
    m = SLOMonitor()
    m.register("api", target=0.99)
    m.record_success("api")
    r = m.report("api")
    assert r.error_budget == pytest.approx(0.01)


def test_burn_rate_above_one():
    m = SLOMonitor()
    m.register("api", target=0.99, window=100)  # allowed fail 1%
    # 5% observed fail → burn rate 5x
    for _ in range(95):
        m.record_success("api")
    for _ in range(5):
        m.record_failure("api")
    r = m.report("api")
    assert r.burn_rate == pytest.approx(5.0, abs=0.01)


def test_warning_when_budget_low():
    m = SLOMonitor()
    # target 0.90 → allowed fail 10%; produce 8% fail → SLI 0.92 >= target
    # budget remaining = 1 - 0.08/0.10 = 0.20 < 0.25 → WARNING
    m.register("api", target=0.90, window=100)
    for _ in range(92):
        m.record_success("api")
    for _ in range(8):
        m.record_failure("api")
    r = m.report("api")
    assert r.status == SLOStatus.WARNING.value
    assert r.sli >= r.target


def test_empty_slo_healthy():
    m = SLOMonitor()
    m.register("api", target=0.99)
    r = m.report("api")
    assert r.total == 0
    assert r.sli == 1.0
    assert r.status == SLOStatus.HEALTHY.value


def test_window_bounds_events():
    m = SLOMonitor()
    m.register("api", target=0.99, window=10)
    for _ in range(50):
        m.record_success("api")
    r = m.report("api")
    assert r.total == 10


# ── Latency SLO ──────────────────────────────────────────────────────────────────

def test_latency_good_under_threshold():
    m = SLOMonitor()
    m.register("lat", kind=SLOKind.LATENCY, target=0.95, threshold_ms=100.0, window=100)
    for _ in range(100):
        m.record_latency("lat", 50.0)  # all under threshold
    r = m.report("lat")
    assert r.sli == 1.0
    assert r.status == SLOStatus.HEALTHY.value


def test_latency_breach_when_slow():
    m = SLOMonitor()
    m.register("lat", kind=SLOKind.LATENCY, target=0.95, threshold_ms=100.0, window=100)
    for _ in range(80):
        m.record_latency("lat", 50.0)
    for _ in range(20):
        m.record_latency("lat", 500.0)  # over threshold
    r = m.report("lat")
    assert r.sli == pytest.approx(0.80)
    assert r.status == SLOStatus.BREACHED.value


def test_latency_boundary_inclusive():
    m = SLOMonitor()
    m.register("lat", kind=SLOKind.LATENCY, target=0.95, threshold_ms=100.0)
    m.record_latency("lat", 100.0)  # exactly threshold → good
    r = m.report("lat")
    assert r.good == 1


# ── report_all ───────────────────────────────────────────────────────────────────

def test_report_all():
    m = SLOMonitor()
    m.register("a", target=0.99)
    m.register("b", target=0.99)
    m.record_success("a")
    reports = m.report_all()
    assert len(reports) == 2
    names = {r["name"] for r in reports}
    assert names == {"a", "b"}


def test_report_unknown_raises():
    m = SLOMonitor()
    with pytest.raises(KeyError):
        m.report("nope")


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_report_to_dict_shape():
    m = SLOMonitor()
    m.register("api", target=0.99)
    m.record_success("api")
    d = m.report("api").to_dict()
    for key in ("name", "kind", "target", "window", "total", "good", "bad",
                "sli", "error_budget", "budget_remaining", "burn_rate", "status"):
        assert key in d


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_breach_counted():
    m = SLOMonitor()
    m.register("api", target=0.99, window=10)
    for _ in range(10):
        m.record_failure("api")
    m.report("api")  # breached
    assert m.metrics()["breach_observations"] == 1


def test_metrics_reset():
    m = SLOMonitor()
    m.register("api", target=0.99, window=10)
    m.record_failure("api")
    m.report("api")
    m.reset_metrics()
    assert m.metrics()["breach_observations"] == 0


def test_metrics_shape():
    m = SLOMonitor()
    mm = m.metrics()
    for key in ("slos", "breach_observations"):
        assert key in mm
