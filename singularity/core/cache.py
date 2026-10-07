"""
Singularity — Response cache (Fáze 12).

Exact-match (SHA-256) TTL cache with LRU eviction.
Wraps sync POST /task to avoid redundant LLM calls for identical inputs.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field


@dataclass
class _Entry:
    value: dict
    expires_at: float  # monotonic


@dataclass
class _Stats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total else 0.0

    def to_dict(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": self.hit_rate,
        }


class ResponseCache:
    """Async-safe LRU cache keyed by SHA-256 of (task, provider, approved)."""

    def __init__(self, maxsize: int = 1000, default_ttl_s: float = 300.0) -> None:
        self._store: OrderedDict[str, _Entry] = OrderedDict()
        self._maxsize = max(1, maxsize)
        self._default_ttl = default_ttl_s
        self._stats = _Stats()
        self._lock: asyncio.Lock | None = None

    def _lk(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @staticmethod
    def make_key(task: str, force_provider: str = "", approved: bool = False) -> str:
        raw = json.dumps(
            {"task": task, "provider": force_provider, "approved": approved},
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    async def get(self, key: str) -> dict | None:
        async with self._lk():
            entry = self._store.get(key)
            if entry is None:
                self._stats.misses += 1
                return None
            if time.monotonic() > entry.expires_at:
                del self._store[key]
                self._stats.misses += 1
                self._stats.evictions += 1
                return None
            self._store.move_to_end(key)
            self._stats.hits += 1
            return entry.value

    async def set(self, key: str, value: dict, ttl_s: float | None = None) -> None:
        async with self._lk():
            expires_at = time.monotonic() + (ttl_s if ttl_s is not None else self._default_ttl)
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = _Entry(value=value, expires_at=expires_at)
            while len(self._store) > self._maxsize:
                self._store.popitem(last=False)
                self._stats.evictions += 1

    async def invalidate(self, key: str) -> bool:
        async with self._lk():
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def clear(self) -> int:
        async with self._lk():
            n = len(self._store)
            self._store.clear()
            return n

    def stats(self) -> dict:
        return {
            **self._stats.to_dict(),
            "size": len(self._store),
            "maxsize": self._maxsize,
            "default_ttl_s": self._default_ttl,
        }

    def __len__(self) -> int:
        return len(self._store)
