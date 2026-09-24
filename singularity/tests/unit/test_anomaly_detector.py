"""
Unit tests — Anomaly Detector (Fáze 52). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.anomaly_detector import (
    AnomalyDetector,
    AnomalyResult,
    DetectionMethod,
    _mean,
    _quantile,
    _stdev,
)


# ── Stats helpers ────────────────────────────────────────────────────────────────

def test_mean():
    assert _mean([1, 2, 3, 4]) == 2.5


def test_mean_empty():
    assert _mean([]) == 0.0


def test_stdev_known():
    xs = [2, 4, 4, 4, 5, 5, 7, 9]
    # sample stdev of this set ≈ 2.138
    assert _stdev(xs, _mean(xs)) == pytest.approx(2.138, abs=1e-2)


def test_stdev_single():
    assert _stdev([5], 5) == 0.0


def test_quantile_median():
    assert _quantile([1, 2, 3, 4, 5], 0.5) == 3


def test_quantile_interpolation():
    assert _quantile([1, 2, 3, 4], 0.25) == pytest.approx(1.75)


# ── Construction ─────────────────────────────────────────────────────────────────

def test_invalid_window_raises():
    with pytest.raises(ValueError):
        AnomalyDetector(window=1)


def test_invalid_min_samples_raises():
    with pytest.raises(ValueError):
        AnomalyDetector(min_samples=1)


def test_invalid_z_threshold_raises():
    with pytest.raises(ValueError):
        AnomalyDetector(z_threshold=0)


def test_invalid_iqr_k_raises():
    with pytest.raises(ValueError):
        AnomalyDetector(iqr_k=0)


# ── Warm-up ──────────────────────────────────────────────────────────────────────

def test_warming_up_no_anomaly():
    d = AnomalyDetector(min_samples=5)
    for i in range(3):
        r = d.observe("lat", 100.0)
        assert r.warming_up is True
        assert r.is_anomaly is False


# ── Z-score detection ────────────────────────────────────────────────────────────

def test_zscore_detects_spike():
    d = AnomalyDetector(method=DetectionMethod.Z_SCORE, min_samples=5, z_threshold=3.0)
    for _ in range(20):
        d.observe("lat", 100.0 + (_ % 3))  # ~100, low variance
    r = d.observe("lat", 100000.0)         # huge spike
    assert r.is_anomaly is True
    assert r.direction == "high"
    assert r.score > 3.0


def test_zscore_normal_value_ok():
    d = AnomalyDetector(min_samples=5, z_threshold=3.0)
    for v in [10, 11, 9, 10, 12, 8, 10, 11]:
        d.observe("m", float(v))
    r = d.observe("m", 10.5)
    assert r.is_anomaly is False


def test_zscore_flat_history_differs():
    d = AnomalyDetector(min_samples=3, z_threshold=3.0)
    for _ in range(5):
        d.observe("flat", 50.0)
    r = d.observe("flat", 51.0)
    # stdev 0, value differs → anomaly
    assert r.is_anomaly is True


def test_zscore_low_direction():
    d = AnomalyDetector(min_samples=5, z_threshold=2.0)
    for v in [100, 101, 99, 100, 102, 98, 100]:
        d.observe("m", float(v))
    r = d.observe("m", 0.0)
    assert r.is_anomaly is True
    assert r.direction == "low"


# ── IQR detection ────────────────────────────────────────────────────────────────

def test_iqr_detects_outlier():
    d = AnomalyDetector(method=DetectionMethod.IQR, min_samples=5, iqr_k=1.5)
    for v in [10, 12, 11, 13, 10, 12, 11, 14, 10, 12]:
        d.observe("m", float(v))
    r = d.observe("m", 1000.0)
    assert r.is_anomaly is True
    assert r.direction == "high"


def test_iqr_normal_value_ok():
    d = AnomalyDetector(method=DetectionMethod.IQR, min_samples=5)
    for v in [10, 12, 11, 13, 10, 12, 11, 14]:
        d.observe("m", float(v))
    r = d.observe("m", 12.0)
    assert r.is_anomaly is False


def test_iqr_method_override_per_call():
    d = AnomalyDetector(method=DetectionMethod.Z_SCORE, min_samples=5)
    for v in [10, 12, 11, 13, 10, 12, 11, 14]:
        d.observe("m", float(v))
    r = d.observe("m", 1000.0, method=DetectionMethod.IQR)
    assert r.method == "iqr"
    assert r.is_anomaly is True


# ── Window / streams ─────────────────────────────────────────────────────────────

def test_window_bounded():
    d = AnomalyDetector(window=5, min_samples=2)
    for i in range(10):
        d.observe("m", float(i))
    assert d.stream_size("m") == 5


def test_separate_streams():
    d = AnomalyDetector(min_samples=2)
    d.observe("a", 1.0)
    d.observe("b", 2.0)
    d.observe("b", 3.0)
    assert d.stream_size("a") == 1
    assert d.stream_size("b") == 2


def test_reset_stream():
    d = AnomalyDetector(min_samples=2)
    d.observe("a", 1.0)
    assert d.reset_stream("a") is True
    assert d.stream_size("a") == 0


def test_reset_missing_stream():
    d = AnomalyDetector()
    assert d.reset_stream("nope") is False


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    d = AnomalyDetector(min_samples=2)
    d.observe("m", 1.0)
    r = d.observe("m", 2.0)
    dd = r.to_dict()
    for key in ("metric", "value", "is_anomaly", "method", "score",
                "direction", "window_size", "warming_up"):
        assert key in dd


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    d = AnomalyDetector(min_samples=3, z_threshold=3.0)
    for _ in range(10):
        d.observe("m", 100.0)
    d.observe("m", 100000.0)  # anomaly
    m = d.metrics()
    assert m["total_observations"] == 11
    assert m["anomalies"] >= 1
    assert m["tracked_metrics"] == 1


def test_metrics_reset():
    d = AnomalyDetector(min_samples=2)
    d.observe("m", 1.0)
    d.reset_metrics()
    m = d.metrics()
    assert m["total_observations"] == 0
    assert m["anomalies"] == 0


def test_metrics_shape():
    d = AnomalyDetector()
    m = d.metrics()
    for key in ("total_observations", "anomalies", "anomaly_rate",
                "tracked_metrics", "method", "window"):
        assert key in m
