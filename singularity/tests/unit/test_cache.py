"""
Tests for ResponseCache (Fáze 12).
"""
import asyncio
import time

import pytest

from core.cache import ResponseCache


@pytest.fixture
def cache():
    return ResponseCache(maxsize=5, default_ttl_s=60.0)


async def test_cache_miss_returns_none(cache):
    result = await cache.get("nonexistent")
    assert result is None
    assert cache.stats()["misses"] == 1


async def test_cache_set_and_get(cache):
    key = ResponseCache.make_key("hello world")
    await cache.set(key, {"response": "hi", "eval_scores": {}, "provider_log": {}})
    result = await cache.get(key)
    assert result is not None
    assert result["response"] == "hi"
    assert cache.stats()["hits"] == 1


async def test_cache_ttl_expiry(cache):
    key = "ttl-test"
    await cache.set(key, {"x": 1}, ttl_s=0.05)
    assert await cache.get(key) is not None
    await asyncio.sleep(0.1)
    result = await cache.get(key)
    assert result is None
    assert cache.stats()["evictions"] >= 1


async def test_cache_lru_eviction(cache):
    # Fill to maxsize (5), then add one more — oldest should be evicted
    for i in range(5):
        await cache.set(f"k{i}", {"v": i})
    assert len(cache) == 5
    await cache.set("k5", {"v": 5})
    assert len(cache) == 5
    assert cache.stats()["evictions"] >= 1


async def test_cache_invalidate(cache):
    key = ResponseCache.make_key("task", "claude", False)
    await cache.set(key, {"response": "r"})
    removed = await cache.invalidate(key)
    assert removed is True
    assert await cache.get(key) is None


async def test_cache_invalidate_missing_key(cache):
    removed = await cache.invalidate("no-such-key")
    assert removed is False


async def test_cache_clear(cache):
    for i in range(3):
        await cache.set(f"k{i}", {"v": i})
    cleared = await cache.clear()
    assert cleared == 3
    assert len(cache) == 0


async def test_make_key_is_deterministic():
    k1 = ResponseCache.make_key("task A", "claude", True)
    k2 = ResponseCache.make_key("task A", "claude", True)
    assert k1 == k2


async def test_make_key_differs_by_provider():
    k1 = ResponseCache.make_key("task", "claude")
    k2 = ResponseCache.make_key("task", "gemini")
    assert k1 != k2


async def test_hit_rate_calculation(cache):
    key = ResponseCache.make_key("q")
    await cache.get(key)          # miss
    await cache.set(key, {"r": 1})
    await cache.get(key)          # hit
    await cache.get(key)          # hit
    stats = cache.stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert abs(stats["hit_rate"] - 2 / 3) < 0.001
