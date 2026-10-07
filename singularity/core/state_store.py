"""
Singularity — Distributed State Store (Fáze 62, v2.0 #2).

A backend-agnostic key/value abstraction so state that is today per-process
(caches, feature flags, SLO windows, rate limits, webhook subscriptions) can
move to shared storage for multi-instance deployments — without changing the
callers.

  - InMemoryStateStore:  dict-backed, thread-safe, lazy-TTL. The default;
                         behaviour-identical to a single process today and the
                         backend used in tests.
  - RedisStateStore:     lazily imports ``redis`` and wraps a client so the
                         same API is served from shared storage. Not exercised
                         offline — the abstraction is what unlocks the swap.

Values are JSON-serialized so any backend stores homogeneous strings.
Keys are namespaced (``namespace:key``) to keep subsystems isolated.
Dependency-free core.
"""

from __future__ import annotations

import json
import threading
import time
from abc import ABC, abstractmethod
from typing import Any


class StateStore(ABC):
    """Namespaced key/value store with optional per-key TTL."""

    @abstractmethod
    def get(self, namespace: str, key: str) -> Any | None: ...

    @abstractmethod
    def set(self, namespace: str, key: str, value: Any, *, ttl_s: float | None = None) -> None: ...

    @abstractmethod
    def delete(self, namespace: str, key: str) -> bool: ...

    @abstractmethod
    def exists(self, namespace: str, key: str) -> bool: ...

    @abstractmethod
    def keys(self, namespace: str) -> list[str]: ...

    @abstractmethod
    def incr(self, namespace: str, key: str, amount: int = 1) -> int: ...

    @abstractmethod
    def clear(self, namespace: str | None = None) -> int: ...

    @abstractmethod
    def metrics(self) -> dict: ...


# ── In-memory backend ────────────────────────────────────────────────────────────

class InMemoryStateStore(StateStore):
    """Thread-safe dict backend with lazy TTL expiry."""

    def __init__(self) -> None:
        # full_key -> (json_value, expires_at | None)
        self._data: dict[str, tuple[str, float | None]] = {}
        self._lock = threading.Lock()
        self._gets = 0
        self._hits = 0
        self._sets = 0

    @staticmethod
    def _fk(namespace: str, key: str) -> str:
        return f"{namespace}:{key}"

    def _expired(self, entry: tuple[str, float | None]) -> bool:
        _, exp = entry
        return exp is not None and time.monotonic() > exp

    def get(self, namespace: str, key: str) -> Any | None:
        fk = self._fk(namespace, key)
        with self._lock:
            self._gets += 1
            entry = self._data.get(fk)
            if entry is None:
                return None
            if self._expired(entry):
                del self._data[fk]
                return None
            self._hits += 1
            return json.loads(entry[0])

    def set(self, namespace: str, key: str, value: Any, *, ttl_s: float | None = None) -> None:
        if ttl_s is not None and ttl_s <= 0:
            raise ValueError("ttl_s must be > 0")
        fk = self._fk(namespace, key)
        exp = (time.monotonic() + ttl_s) if ttl_s else None
        payload = json.dumps(value)
        with self._lock:
            self._data[fk] = (payload, exp)
            self._sets += 1

    def delete(self, namespace: str, key: str) -> bool:
        fk = self._fk(namespace, key)
        with self._lock:
            return self._data.pop(fk, None) is not None

    def exists(self, namespace: str, key: str) -> bool:
        fk = self._fk(namespace, key)
        with self._lock:
            entry = self._data.get(fk)
            if entry is None:
                return False
            if self._expired(entry):
                del self._data[fk]
                return False
            return True

    def keys(self, namespace: str) -> list[str]:
        prefix = f"{namespace}:"
        with self._lock:
            out = []
            for fk in list(self._data):
                if not fk.startswith(prefix):
                    continue
                if self._expired(self._data[fk]):
                    del self._data[fk]
                    continue
                out.append(fk[len(prefix):])
            return sorted(out)

    def incr(self, namespace: str, key: str, amount: int = 1) -> int:
        fk = self._fk(namespace, key)
        with self._lock:
            entry = self._data.get(fk)
            current = 0
            if entry is not None and not self._expired(entry):
                val = json.loads(entry[0])
                if not isinstance(val, int):
                    raise ValueError(f"value at {fk!r} is not an integer")
                current = val
            new = current + amount
            # preserve existing expiry if present
            exp = entry[1] if (entry is not None and not self._expired(entry)) else None
            self._data[fk] = (json.dumps(new), exp)
            return new

    def clear(self, namespace: str | None = None) -> int:
        with self._lock:
            if namespace is None:
                n = len(self._data)
                self._data.clear()
                return n
            prefix = f"{namespace}:"
            to_del = [fk for fk in self._data if fk.startswith(prefix)]
            for fk in to_del:
                del self._data[fk]
            return len(to_del)

    def metrics(self) -> dict:
        with self._lock:
            # count live (non-expired) keys
            live = sum(1 for e in self._data.values() if not self._expired(e))
            return {
                "backend": "memory",
                "keys": live,
                "gets": self._gets,
                "hits": self._hits,
                "sets": self._sets,
                "hit_rate": round(self._hits / self._gets, 4) if self._gets else 0.0,
            }


# ── Redis backend (lazy) ─────────────────────────────────────────────────────────

class RedisStateStore(StateStore):
    """
    Redis-backed store. Lazily imports ``redis``; the client is injectable so
    the class can be unit-constructed with a fake in tests, but production wires
    a real ``redis.Redis``. Values are JSON strings; TTL uses Redis EX.
    """

    def __init__(self, *, url: str = "redis://localhost:6379/0", client: Any = None) -> None:
        self.url = url
        if client is not None:
            self._client = client
        else:
            import redis  # lazy — only needed when actually using Redis
            self._client = redis.Redis.from_url(url, decode_responses=True)

    @staticmethod
    def _fk(namespace: str, key: str) -> str:
        return f"{namespace}:{key}"

    def get(self, namespace: str, key: str) -> Any | None:
        raw = self._client.get(self._fk(namespace, key))
        return json.loads(raw) if raw is not None else None

    def set(self, namespace: str, key: str, value: Any, *, ttl_s: float | None = None) -> None:
        if ttl_s is not None and ttl_s <= 0:
            raise ValueError("ttl_s must be > 0")
        ex = int(ttl_s) if ttl_s else None
        self._client.set(self._fk(namespace, key), json.dumps(value), ex=ex)

    def delete(self, namespace: str, key: str) -> bool:
        return bool(self._client.delete(self._fk(namespace, key)))

    def exists(self, namespace: str, key: str) -> bool:
        return bool(self._client.exists(self._fk(namespace, key)))

    def keys(self, namespace: str) -> list[str]:
        prefix = f"{namespace}:"
        return sorted(k[len(prefix):] for k in self._client.keys(f"{prefix}*"))

    def incr(self, namespace: str, key: str, amount: int = 1) -> int:
        return int(self._client.incrby(self._fk(namespace, key), amount))

    def clear(self, namespace: str | None = None) -> int:
        pattern = "*" if namespace is None else f"{namespace}:*"
        keys = self._client.keys(pattern)
        return int(self._client.delete(*keys)) if keys else 0

    def metrics(self) -> dict:
        return {"backend": "redis", "url": self.url}


# ── Factory ──────────────────────────────────────────────────────────────────────

def build_state_store(backend: str = "memory", *, redis_url: str = "redis://localhost:6379/0",
                      client: Any = None) -> StateStore:
    if backend in ("memory", "inmemory", "local"):
        return InMemoryStateStore()
    if backend == "redis":
        return RedisStateStore(url=redis_url, client=client)
    raise ValueError(f"Unknown state store backend: {backend!r}")
