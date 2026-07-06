"""
Unit tests — Distributed State Store (Fáze 62). Fully offline.

InMemoryStateStore is exercised directly; RedisStateStore is exercised via an
injected fake client (no real Redis).
"""

from __future__ import annotations

import time
import pytest

from core.state_store import (
    InMemoryStateStore,
    RedisStateStore,
    StateStore,
    build_state_store,
)


# ── In-memory: basic CRUD ────────────────────────────────────────────────────────

def test_set_get():
    s = InMemoryStateStore()
    s.set("ns", "k", {"a": 1})
    assert s.get("ns", "k") == {"a": 1}


def test_get_missing_none():
    s = InMemoryStateStore()
    assert s.get("ns", "nope") is None


def test_namespaces_isolated():
    s = InMemoryStateStore()
    s.set("a", "k", 1)
    s.set("b", "k", 2)
    assert s.get("a", "k") == 1
    assert s.get("b", "k") == 2


def test_delete():
    s = InMemoryStateStore()
    s.set("ns", "k", 1)
    assert s.delete("ns", "k") is True
    assert s.get("ns", "k") is None


def test_delete_missing():
    s = InMemoryStateStore()
    assert s.delete("ns", "nope") is False


def test_exists():
    s = InMemoryStateStore()
    s.set("ns", "k", 1)
    assert s.exists("ns", "k") is True
    assert s.exists("ns", "other") is False


def test_overwrite():
    s = InMemoryStateStore()
    s.set("ns", "k", 1)
    s.set("ns", "k", 2)
    assert s.get("ns", "k") == 2


# ── keys ─────────────────────────────────────────────────────────────────────────

def test_keys_lists_namespace_only():
    s = InMemoryStateStore()
    s.set("ns", "b", 1)
    s.set("ns", "a", 1)
    s.set("other", "z", 1)
    assert s.keys("ns") == ["a", "b"]


def test_keys_empty():
    s = InMemoryStateStore()
    assert s.keys("ns") == []


# ── incr ─────────────────────────────────────────────────────────────────────────

def test_incr_from_zero():
    s = InMemoryStateStore()
    assert s.incr("ns", "count") == 1
    assert s.incr("ns", "count") == 2


def test_incr_amount():
    s = InMemoryStateStore()
    assert s.incr("ns", "count", 5) == 5


def test_incr_on_non_int_raises():
    s = InMemoryStateStore()
    s.set("ns", "k", "string")
    with pytest.raises(ValueError):
        s.incr("ns", "k")


# ── TTL ──────────────────────────────────────────────────────────────────────────

def test_ttl_expiry(monkeypatch):
    s = InMemoryStateStore()
    clock = {"t": 1000.0}
    monkeypatch.setattr("core.state_store.time.monotonic", lambda: clock["t"])
    s.set("ns", "k", 1, ttl_s=10)
    assert s.get("ns", "k") == 1
    clock["t"] = 1011.0  # past ttl
    assert s.get("ns", "k") is None


def test_ttl_invalid_raises():
    s = InMemoryStateStore()
    with pytest.raises(ValueError):
        s.set("ns", "k", 1, ttl_s=0)


def test_expired_key_not_in_keys(monkeypatch):
    s = InMemoryStateStore()
    clock = {"t": 0.0}
    monkeypatch.setattr("core.state_store.time.monotonic", lambda: clock["t"])
    s.set("ns", "k", 1, ttl_s=5)
    clock["t"] = 10.0
    assert s.keys("ns") == []


def test_exists_respects_ttl(monkeypatch):
    s = InMemoryStateStore()
    clock = {"t": 0.0}
    monkeypatch.setattr("core.state_store.time.monotonic", lambda: clock["t"])
    s.set("ns", "k", 1, ttl_s=5)
    clock["t"] = 10.0
    assert s.exists("ns", "k") is False


def test_incr_preserves_ttl(monkeypatch):
    s = InMemoryStateStore()
    clock = {"t": 0.0}
    monkeypatch.setattr("core.state_store.time.monotonic", lambda: clock["t"])
    s.set("ns", "c", 1, ttl_s=10)
    s.incr("ns", "c")  # -> 2, ttl preserved
    clock["t"] = 11.0
    assert s.get("ns", "c") is None


# ── clear ────────────────────────────────────────────────────────────────────────

def test_clear_namespace():
    s = InMemoryStateStore()
    s.set("a", "k1", 1)
    s.set("a", "k2", 1)
    s.set("b", "k", 1)
    assert s.clear("a") == 2
    assert s.get("a", "k1") is None
    assert s.get("b", "k") == 1


def test_clear_all():
    s = InMemoryStateStore()
    s.set("a", "k", 1)
    s.set("b", "k", 1)
    assert s.clear() == 2
    assert s.keys("a") == []


# ── metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_hit_miss():
    s = InMemoryStateStore()
    s.set("ns", "k", 1)
    s.get("ns", "k")      # hit
    s.get("ns", "nope")   # miss
    m = s.metrics()
    assert m["backend"] == "memory"
    assert m["gets"] == 2
    assert m["hits"] == 1
    assert m["hit_rate"] == 0.5
    assert m["keys"] == 1
    assert m["sets"] == 1


def test_metrics_shape():
    s = InMemoryStateStore()
    m = s.metrics()
    for key in ("backend", "keys", "gets", "hits", "sets", "hit_rate"):
        assert key in m


# ── Factory ──────────────────────────────────────────────────────────────────────

def test_build_memory():
    s = build_state_store("memory")
    assert isinstance(s, InMemoryStateStore)
    assert isinstance(s, StateStore)


def test_build_unknown_raises():
    with pytest.raises(ValueError):
        build_state_store("cassandra")


# ── Redis backend via fake client ────────────────────────────────────────────────

class _FakeRedis:
    """Minimal in-memory stand-in for the redis client surface used."""

    def __init__(self):
        self.store: dict[str, str] = {}

    def get(self, k):
        return self.store.get(k)

    def set(self, k, v, ex=None):
        self.store[k] = v
        return True

    def delete(self, *keys):
        n = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                n += 1
        return n

    def exists(self, k):
        return 1 if k in self.store else 0

    def keys(self, pattern):
        import fnmatch
        return [k for k in self.store if fnmatch.fnmatch(k, pattern)]

    def incrby(self, k, amount):
        cur = int(self.store.get(k, "0"))
        cur += amount
        self.store[k] = str(cur)
        return cur


def test_redis_backend_crud():
    s = RedisStateStore(client=_FakeRedis())
    s.set("ns", "k", {"x": 1})
    assert s.get("ns", "k") == {"x": 1}
    assert s.exists("ns", "k") is True
    assert s.delete("ns", "k") is True
    assert s.get("ns", "k") is None


def test_redis_backend_keys_and_clear():
    s = RedisStateStore(client=_FakeRedis())
    s.set("ns", "a", 1)
    s.set("ns", "b", 1)
    s.set("other", "c", 1)
    assert s.keys("ns") == ["a", "b"]
    assert s.clear("ns") == 2
    assert s.keys("ns") == []
    assert s.keys("other") == ["c"]


def test_redis_backend_incr():
    s = RedisStateStore(client=_FakeRedis())
    assert s.incr("ns", "c") == 1
    assert s.incr("ns", "c", 4) == 5


def test_redis_backend_ttl_invalid():
    s = RedisStateStore(client=_FakeRedis())
    with pytest.raises(ValueError):
        s.set("ns", "k", 1, ttl_s=0)


def test_redis_metrics_shape():
    s = RedisStateStore(client=_FakeRedis())
    m = s.metrics()
    assert m["backend"] == "redis"
    assert "url" in m


def test_build_redis_with_client():
    s = build_state_store("redis", client=_FakeRedis())
    assert isinstance(s, RedisStateStore)
