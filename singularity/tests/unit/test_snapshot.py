"""
Unit tests — Snapshot Manager (Fáze 63). Fully offline (InMemoryStateStore).
"""

from __future__ import annotations

import pytest

from core.feature_flags import FeatureFlagManager
from core.snapshot import SnapshotManager
from core.state_store import InMemoryStateStore


def _mgr():
    return SnapshotManager(InMemoryStateStore())


# ── Registration ─────────────────────────────────────────────────────────────────

def test_register_and_list():
    m = _mgr()
    m.register("a", lambda: {}, lambda d: None)
    m.register("b", lambda: {}, lambda d: None)
    assert m.list_components() == ["a", "b"]


def test_register_requires_name():
    m = _mgr()
    with pytest.raises(ValueError):
        m.register("", lambda: {}, lambda d: None)


def test_register_requires_callables():
    m = _mgr()
    with pytest.raises(ValueError):
        m.register("x", "nope", lambda d: None)


def test_unregister():
    m = _mgr()
    m.register("a", lambda: {}, lambda d: None)
    assert m.unregister("a") is True
    assert m.list_components() == []


def test_unregister_missing():
    m = _mgr()
    assert m.unregister("nope") is False


# ── Snapshot / restore round-trip ────────────────────────────────────────────────

def test_snapshot_and_restore_roundtrip():
    state = {"value": 42}
    restored = {}
    m = _mgr()
    m.register("comp", dump=lambda: dict(state), load=lambda d: restored.update(d))
    assert m.snapshot()["comp"] == "ok"
    # mutate live state, then restore from snapshot
    state["value"] = 999
    assert m.restore()["comp"] == "restored"
    assert restored == {"value": 42}


def test_snapshot_specific_component():
    m = _mgr()
    calls = []
    m.register("a", lambda: {"a": 1}, lambda d: calls.append("a"))
    m.register("b", lambda: {"b": 2}, lambda d: calls.append("b"))
    res = m.snapshot("a")
    assert res == {"a": "ok"}
    assert m.has_snapshot("a") is True
    assert m.has_snapshot("b") is False


def test_snapshot_unknown_raises():
    m = _mgr()
    with pytest.raises(KeyError):
        m.snapshot("ghost")


def test_restore_unknown_raises():
    m = _mgr()
    with pytest.raises(KeyError):
        m.restore("ghost")


def test_restore_no_snapshot_skips():
    m = _mgr()
    m.register("comp", lambda: {}, lambda d: None)
    assert m.restore()["comp"] == "no_snapshot"


def test_dump_error_does_not_break_batch():
    m = _mgr()
    def _boom():
        raise RuntimeError("dump failed")
    m.register("bad", _boom, lambda d: None)
    m.register("good", lambda: {"x": 1}, lambda d: None)
    res = m.snapshot()
    assert "error" in res["bad"]
    assert res["good"] == "ok"


def test_load_error_reported():
    m = _mgr()
    m.register("comp", lambda: {"x": 1}, lambda d: (_ for _ in ()).throw(ValueError("bad")))
    m.snapshot()
    res = m.restore()
    assert "error" in res["comp"]


def test_clear():
    m = _mgr()
    m.register("a", lambda: {"a": 1}, lambda d: None)
    m.snapshot()
    assert m.clear() == 1
    assert m.has_snapshot("a") is False


# ── Real integration: FeatureFlagManager survives a "restart" ────────────────────

def test_feature_flags_survive_restart():
    store = InMemoryStateStore()

    # instance 1: configure flags + snapshot
    flags1 = FeatureFlagManager()
    flags1.register("new_ui", enabled=True, rollout=50)
    flags1.set_user_override("new_ui", "vip", True)
    snap1 = SnapshotManager(store)
    snap1.register("feature_flags", flags1.export, flags1.import_flags)
    snap1.snapshot()

    # instance 2 (fresh process): restore from shared store
    flags2 = FeatureFlagManager()
    snap2 = SnapshotManager(store)
    snap2.register("feature_flags", flags2.export, flags2.import_flags)
    snap2.restore()

    f = flags2.get("new_ui")
    assert f is not None
    assert f["enabled"] is True
    assert f["rollout"] == 50
    assert "vip" in f["on_users"]
    # forced-on user is enabled after restore
    assert flags2.is_enabled("new_ui", "vip") is True


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_counts():
    m = _mgr()
    m.register("a", lambda: {"x": 1}, lambda d: None)
    m.snapshot()
    m.restore()
    mm = m.metrics()
    assert mm["components"] == 1
    assert mm["snapshots"] == 1
    assert mm["restores"] == 1
    assert mm["last_snapshot_at"] is not None


def test_metrics_shape():
    m = _mgr()
    mm = m.metrics()
    for key in ("components", "snapshots", "restores", "last_snapshot_at", "namespace"):
        assert key in mm
