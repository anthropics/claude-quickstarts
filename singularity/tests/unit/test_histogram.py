"""
Unit tests — Percentile Tracker (Fáze 54). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.histogram import (
    DistributionSummary,
    PercentileTracker,
    _fmt,
    _percentile,
)


# ── _percentile helper ───────────────────────────────────────────────────────────

def test_percentile_median_odd():
    assert _percentile([1, 2, 3, 4, 5], 50) == 3


def test_percentile_empty():
    assert _percentile([], 50) == 0.0


def test_percentile_single():
    assert _percentile([7], 99) == 7


def test_percentile_min_max():
    s = [10, 20, 30, 40, 50]
    assert _percentile(s, 0) == 10
    assert _percentile(s, 100) == 50


def test_percentile_interpolated():
    # type-7 p25 of 1..4 → pos 0.75 → 1.75
    assert _percentile([1, 2, 3, 4], 25) == pytest.approx(1.75)


# ── _fmt helper ──────────────────────────────────────────────────────────────────

def test_fmt_integer():
    assert _fmt(99.0) == "99"


def test_fmt_fractional():
    assert _fmt(99.9) == "99.9"


# ── Construction ─────────────────────────────────────────────────────────────────

def test_invalid_window_raises():
    with pytest.raises(ValueError):
        PercentileTracker(window=0)


def test_invalid_percentile_raises():
    with pytest.raises(ValueError):
        PercentileTracker(percentiles=(50.0, 150.0))


# ── Observe & percentile ─────────────────────────────────────────────────────────

def test_percentile_query():
    t = PercentileTracker()
    t.observe_many("lat", [float(i) for i in range(1, 101)])  # 1..100
    p50 = t.percentile("lat", 50)
    assert 50 <= p50 <= 51


def test_percentile_p99_high():
    t = PercentileTracker()
    t.observe_many("lat", [float(i) for i in range(1, 101)])
    p99 = t.percentile("lat", 99)
    assert p99 >= 99


def test_percentile_unknown_metric_none():
    t = PercentileTracker()
    assert t.percentile("nope", 50) is None


def test_percentile_invalid_q_raises():
    t = PercentileTracker()
    t.observe("m", 1.0)
    with pytest.raises(ValueError):
        t.percentile("m", 101)


# ── Summary ──────────────────────────────────────────────────────────────────────

def test_summary_basic():
    t = PercentileTracker()
    t.observe_many("lat", [10.0, 20.0, 30.0, 40.0, 50.0])
    s = t.summary("lat")
    assert s.count == 5
    assert s.min == 10.0
    assert s.max == 50.0
    assert s.mean == 30.0
    assert "p50" in s.percentiles
    assert "p99" in s.percentiles


def test_summary_default_percentile_keys():
    t = PercentileTracker()
    t.observe("m", 1.0)
    s = t.summary("m")
    assert set(s.percentiles.keys()) == {"p50", "p90", "p95", "p99"}


def test_summary_custom_percentiles():
    t = PercentileTracker()
    t.observe_many("m", [float(i) for i in range(100)])
    s = t.summary("m", percentiles=(25.0, 75.0))
    assert set(s.percentiles.keys()) == {"p25", "p75"}


def test_summary_unknown_metric_none():
    t = PercentileTracker()
    assert t.summary("nope") is None


def test_summary_to_dict_shape():
    t = PercentileTracker()
    t.observe("m", 5.0)
    d = t.summary("m").to_dict()
    for key in ("metric", "count", "min", "max", "mean", "percentiles"):
        assert key in d


# ── Window bounding ──────────────────────────────────────────────────────────────

def test_window_bounds_samples():
    t = PercentileTracker(window=10)
    t.observe_many("m", [float(i) for i in range(100)])
    s = t.summary("m")
    assert s.count == 10
    # only last 10 retained → min should be 90
    assert s.min == 90.0


# ── Multiple metrics ─────────────────────────────────────────────────────────────

def test_separate_metrics():
    t = PercentileTracker()
    t.observe("a", 1.0)
    t.observe("b", 2.0)
    t.observe("b", 3.0)
    assert t.summary("a").count == 1
    assert t.summary("b").count == 2


def test_list_metrics():
    t = PercentileTracker()
    t.observe("z", 1.0)
    t.observe("a", 1.0)
    assert t.list_metrics() == ["a", "z"]


def test_reset_metric():
    t = PercentileTracker()
    t.observe("m", 1.0)
    assert t.reset_metric("m") is True
    assert t.summary("m") is None


def test_reset_missing_metric():
    t = PercentileTracker()
    assert t.reset_metric("nope") is False


# ── Tracker metrics ──────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    t = PercentileTracker()
    t.observe_many("a", [1.0, 2.0])
    t.observe("b", 3.0)
    m = t.metrics()
    assert m["total_observations"] == 3
    assert m["tracked_metrics"] == 2


def test_metrics_reset():
    t = PercentileTracker()
    t.observe("m", 1.0)
    t.reset_metrics()
    m = t.metrics()
    assert m["total_observations"] == 0


def test_metrics_shape():
    t = PercentileTracker()
    m = t.metrics()
    for key in ("total_observations", "tracked_metrics", "window", "percentiles"):
        assert key in m
