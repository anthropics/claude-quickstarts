"""
Unit tests — Feature Flag Manager (Fáze 56). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.feature_flags import FeatureFlagManager, Flag, _bucket


# ── Bucket helper ────────────────────────────────────────────────────────────────

def test_bucket_deterministic():
    assert _bucket("flag", "user1") == _bucket("flag", "user1")


def test_bucket_in_range():
    for u in range(100):
        assert 0 <= _bucket("f", f"user{u}") < 100


def test_bucket_varies_by_user():
    vals = {_bucket("f", f"u{i}") for i in range(50)}
    assert len(vals) > 1  # not all identical


# ── Registration ─────────────────────────────────────────────────────────────────

def test_register_and_get():
    m = FeatureFlagManager()
    m.register("new_ui", enabled=True, description="New UI")
    f = m.get("new_ui")
    assert f["name"] == "new_ui"
    assert f["enabled"] is True


def test_register_requires_name():
    m = FeatureFlagManager()
    with pytest.raises(ValueError):
        m.register("")


def test_register_invalid_rollout():
    m = FeatureFlagManager()
    with pytest.raises(ValueError):
        m.register("x", rollout=150)


def test_get_missing_none():
    m = FeatureFlagManager()
    assert m.get("nope") is None


def test_list_flags():
    m = FeatureFlagManager()
    m.register("a")
    m.register("b")
    assert len(m.list_flags()) == 2


def test_delete():
    m = FeatureFlagManager()
    m.register("a")
    assert m.delete("a") is True
    assert m.get("a") is None


def test_delete_missing():
    m = FeatureFlagManager()
    assert m.delete("nope") is False


# ── Master switch ────────────────────────────────────────────────────────────────

def test_disabled_flag_off():
    m = FeatureFlagManager()
    m.register("f", enabled=False)
    assert m.is_enabled("f", "user1") is False


def test_enabled_full_rollout_on():
    m = FeatureFlagManager()
    m.register("f", enabled=True, rollout=100)
    assert m.is_enabled("f", "anyone") is True


def test_unknown_flag_off():
    m = FeatureFlagManager()
    assert m.is_enabled("ghost", "user1") is False


def test_set_enabled_toggle():
    m = FeatureFlagManager()
    m.register("f", enabled=False, rollout=100)
    m.set_enabled("f", True)
    assert m.is_enabled("f", "u") is True
    m.set_enabled("f", False)
    assert m.is_enabled("f", "u") is False


def test_set_enabled_missing():
    m = FeatureFlagManager()
    assert m.set_enabled("nope", True) is False


# ── Rollout ──────────────────────────────────────────────────────────────────────

def test_rollout_zero_all_off():
    m = FeatureFlagManager()
    m.register("f", enabled=True, rollout=0)
    assert all(not m.is_enabled("f", f"u{i}") for i in range(50))


def test_rollout_full_all_on():
    m = FeatureFlagManager()
    m.register("f", enabled=True, rollout=100)
    assert all(m.is_enabled("f", f"u{i}") for i in range(50))


def test_rollout_partial_approximate():
    m = FeatureFlagManager()
    m.register("f", enabled=True, rollout=50)
    on = sum(1 for i in range(1000) if m.is_enabled("f", f"user{i}"))
    # ~50% with generous bounds
    assert 400 < on < 600


def test_rollout_sticky_per_user():
    m = FeatureFlagManager()
    m.register("f", enabled=True, rollout=50)
    first = m.is_enabled("f", "stable_user")
    for _ in range(10):
        assert m.is_enabled("f", "stable_user") == first


def test_rollout_monotonic_growth():
    # a user enabled at X% stays enabled at higher %
    m = FeatureFlagManager()
    m.register("f", enabled=True, rollout=30)
    enabled_at_30 = {f"u{i}" for i in range(200) if m.is_enabled("f", f"u{i}")}
    m.set_rollout("f", 60)
    enabled_at_60 = {f"u{i}" for i in range(200) if m.is_enabled("f", f"u{i}")}
    assert enabled_at_30 <= enabled_at_60


def test_set_rollout_invalid():
    m = FeatureFlagManager()
    m.register("f")
    with pytest.raises(ValueError):
        m.set_rollout("f", 200)


def test_partial_rollout_no_user_off():
    m = FeatureFlagManager()
    m.register("f", enabled=True, rollout=50)
    # no user supplied → partial rollout can't bucket → off
    assert m.is_enabled("f") is False


# ── User overrides ───────────────────────────────────────────────────────────────

def test_force_on_overrides_disabled():
    m = FeatureFlagManager()
    m.register("f", enabled=False)
    m.set_user_override("f", "vip", True)
    assert m.is_enabled("f", "vip") is True


def test_force_off_overrides_full_rollout():
    m = FeatureFlagManager()
    m.register("f", enabled=True, rollout=100)
    m.set_user_override("f", "banned", False)
    assert m.is_enabled("f", "banned") is False


def test_clear_override():
    m = FeatureFlagManager()
    m.register("f", enabled=True, rollout=100)
    m.set_user_override("f", "u", False)
    assert m.is_enabled("f", "u") is False
    m.set_user_override("f", "u", None)
    assert m.is_enabled("f", "u") is True


def test_override_switches_sides():
    m = FeatureFlagManager()
    m.register("f", enabled=False)
    m.set_user_override("f", "u", True)
    assert m.is_enabled("f", "u") is True
    m.set_user_override("f", "u", False)
    assert m.is_enabled("f", "u") is False


def test_override_missing_flag():
    m = FeatureFlagManager()
    assert m.set_user_override("nope", "u", True) is False


# ── evaluate_all ─────────────────────────────────────────────────────────────────

def test_evaluate_all():
    m = FeatureFlagManager()
    m.register("on", enabled=True, rollout=100)
    m.register("off", enabled=False)
    result = m.evaluate_all("user1")
    assert result == {"on": True, "off": False}


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    m = FeatureFlagManager()
    m.register("f", enabled=True, rollout=100)
    m.is_enabled("f", "a")
    m.is_enabled("f", "b")
    mm = m.metrics()
    assert mm["evaluations"] == 2
    assert mm["enabled_results"] == 2
    assert mm["enabled_rate"] == 1.0


def test_metrics_reset():
    m = FeatureFlagManager()
    m.register("f", enabled=True, rollout=100)
    m.is_enabled("f", "a")
    m.reset_metrics()
    mm = m.metrics()
    assert mm["evaluations"] == 0


def test_metrics_shape():
    m = FeatureFlagManager()
    mm = m.metrics()
    for key in ("flags", "evaluations", "enabled_results", "enabled_rate"):
        assert key in mm


# ── Flag dataclass ───────────────────────────────────────────────────────────────

def test_flag_to_dict_shape():
    d = Flag(name="x", enabled=True, rollout=50, description="d").to_dict()
    for key in ("name", "enabled", "rollout", "on_users", "off_users", "description"):
        assert key in d
