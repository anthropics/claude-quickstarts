"""
Unit tests — Reservoir + Rate Sampler (Fáze 53). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.sampler import RateSampler, ReservoirSampler, SampleState


# ── Reservoir: construction ──────────────────────────────────────────────────────

def test_invalid_capacity_raises():
    with pytest.raises(ValueError):
        ReservoirSampler(0)


# ── Reservoir: fill phase ────────────────────────────────────────────────────────

def test_fills_directly_under_capacity():
    r = ReservoirSampler(5, seed=1)
    for i in range(3):
        assert r.add(i) is True
    assert r.sample() == [0, 1, 2]
    assert r.seen == 3


def test_exactly_capacity_keeps_all():
    r = ReservoirSampler(3, seed=1)
    r.add_many([1, 2, 3])
    assert sorted(r.sample()) == [1, 2, 3]


def test_never_exceeds_capacity():
    r = ReservoirSampler(10, seed=1)
    r.add_many(list(range(1000)))
    assert len(r.sample()) == 10


def test_seen_counts_all():
    r = ReservoirSampler(5, seed=1)
    r.add_many(list(range(100)))
    assert r.seen == 100


# ── Reservoir: determinism ───────────────────────────────────────────────────────

def test_same_seed_same_sample():
    r1 = ReservoirSampler(5, seed=42)
    r2 = ReservoirSampler(5, seed=42)
    r1.add_many(list(range(100)))
    r2.add_many(list(range(100)))
    assert r1.sample() == r2.sample()


def test_different_seed_likely_different():
    r1 = ReservoirSampler(5, seed=1)
    r2 = ReservoirSampler(5, seed=2)
    r1.add_many(list(range(100)))
    r2.add_many(list(range(100)))
    # extremely unlikely to be identical
    assert r1.sample() != r2.sample()


# ── Reservoir: uniformity (statistical) ──────────────────────────────────────────

def test_approximately_uniform():
    # Over many trials, each item should appear roughly equally often.
    counts = {i: 0 for i in range(10)}
    trials = 2000
    for t in range(trials):
        r = ReservoirSampler(3, seed=t)
        r.add_many(list(range(10)))
        for item in r.sample():
            counts[item] += 1
    # expected per item ≈ trials * 3 / 10 = 600
    for c in counts.values():
        assert 450 < c < 750  # generous bounds, no flakiness


# ── Reservoir: management ────────────────────────────────────────────────────────

def test_reset():
    r = ReservoirSampler(5, seed=1)
    r.add_many([1, 2, 3])
    r.reset()
    assert r.sample() == []
    assert r.seen == 0


def test_add_many_returns_kept_count():
    r = ReservoirSampler(3, seed=1)
    kept = r.add_many([1, 2, 3])  # all fit
    assert kept == 3


# ── Reservoir: state & metrics ───────────────────────────────────────────────────

def test_state_shape():
    r = ReservoirSampler(5, seed=1)
    r.add_many([1, 2])
    d = r.state().to_dict()
    for key in ("capacity", "seen", "sample_size", "items"):
        assert key in d
    assert d["sample_size"] == 2


def test_metrics_shape():
    r = ReservoirSampler(5, seed=1)
    r.add_many(list(range(20)))
    m = r.metrics()
    for key in ("capacity", "seen", "sample_size", "replacements", "fill_ratio"):
        assert key in m
    assert m["fill_ratio"] == 1.0
    assert m["seen"] == 20


def test_metrics_replacements_counted():
    r = ReservoirSampler(2, seed=1)
    r.add_many(list(range(100)))
    m = r.metrics()
    assert m["replacements"] >= 1


# ── RateSampler ──────────────────────────────────────────────────────────────────

def test_rate_invalid_raises():
    with pytest.raises(ValueError):
        RateSampler(1.5)


def test_rate_one_keeps_all():
    s = RateSampler(1.0, seed=1)
    assert all(s.should_sample() for _ in range(50))
    assert s.metrics()["kept"] == 50


def test_rate_zero_keeps_none():
    s = RateSampler(0.0, seed=1)
    assert not any(s.should_sample() for _ in range(50))
    assert s.metrics()["kept"] == 0


def test_rate_half_approximate():
    s = RateSampler(0.5, seed=7)
    for _ in range(1000):
        s.should_sample()
    eff = s.metrics()["effective_rate"]
    assert 0.4 < eff < 0.6


def test_rate_deterministic_with_seed():
    s1 = RateSampler(0.5, seed=3)
    s2 = RateSampler(0.5, seed=3)
    r1 = [s1.should_sample() for _ in range(50)]
    r2 = [s2.should_sample() for _ in range(50)]
    assert r1 == r2


def test_rate_reset():
    s = RateSampler(0.5, seed=1)
    for _ in range(10):
        s.should_sample()
    s.reset()
    m = s.metrics()
    assert m["seen"] == 0
    assert m["kept"] == 0


def test_rate_metrics_shape():
    s = RateSampler(0.5, seed=1)
    m = s.metrics()
    for key in ("rate", "seen", "kept", "effective_rate"):
        assert key in m
