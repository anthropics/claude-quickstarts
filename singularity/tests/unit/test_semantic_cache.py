"""
Tests for SemanticCache (Fáze 29).
All offline — embed_fn injected as deterministic vector function.
"""
import math
import time
import pytest

from core.semantic_cache import (
    SemanticCache,
    SemanticCacheResult,
    HitType,
    _cosine,
    _normalize,
)


# ── Embed helpers ─────────────────────────────────────────────────────────────

def _unit(v: list[float]) -> list[float]:
    """Normalize a vector to unit length."""
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v] if norm > 0 else v


# Three orthogonal basis vectors + a "near-A" variant
_VEC_A = _unit([1.0, 0.0, 0.0])
_VEC_B = _unit([0.0, 1.0, 0.0])
_VEC_C = _unit([0.0, 0.0, 1.0])
_VEC_NEAR_A = _unit([0.98, 0.2, 0.0])   # cos(A, NEAR_A) ≈ 0.98


def _make_embed(mapping: dict[str, list[float]], default: list[float] | None = None):
    """Return an embed_fn that maps known texts to vectors, unknown → default."""
    _default = default or _VEC_C

    def embed(text: str) -> list[float]:
        norm = " ".join(text.lower().split())
        return mapping.get(norm, _default)

    return embed


def _simple_embed(text: str) -> list[float]:
    """Deterministic embed: maps by first word."""
    w = text.strip().lower().split()[0] if text.strip() else "x"
    mapping = {"hello": _VEC_A, "hi": _VEC_NEAR_A, "bonjour": _VEC_NEAR_A}
    return mapping.get(w, _VEC_C)


def _make_cache(**kwargs) -> SemanticCache:
    return SemanticCache(embed_fn=_simple_embed, threshold=0.95, max_size=10,
                         ttl_s=300.0, **kwargs)


# ── Constructor validation ─────────────────────────────────────────────────────

def test_invalid_threshold_zero_raises():
    with pytest.raises(ValueError, match="threshold"):
        SemanticCache(embed_fn=_simple_embed, threshold=0.0)


def test_invalid_threshold_above_one_raises():
    with pytest.raises(ValueError, match="threshold"):
        SemanticCache(embed_fn=_simple_embed, threshold=1.1)


def test_threshold_exactly_one_is_valid():
    cache = SemanticCache(embed_fn=_simple_embed, threshold=1.0)
    assert cache.threshold == 1.0


def test_invalid_max_size_raises():
    with pytest.raises(ValueError, match="max_size"):
        SemanticCache(embed_fn=_simple_embed, threshold=0.9, max_size=0)


def test_invalid_ttl_raises():
    with pytest.raises(ValueError, match="ttl_s"):
        SemanticCache(embed_fn=_simple_embed, threshold=0.9, ttl_s=0.0)


# ── Cosine helper ─────────────────────────────────────────────────────────────

def test_cosine_identical_vectors():
    v = _unit([3.0, 4.0, 0.0])
    assert abs(_cosine(v, v) - 1.0) < 1e-9


def test_cosine_orthogonal_vectors():
    assert abs(_cosine([1.0, 0.0], [0.0, 1.0])) < 1e-9


def test_cosine_zero_vector_returns_zero():
    assert _cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_cosine_different_lengths_returns_zero():
    assert _cosine([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


def test_cosine_near_vectors():
    score = _cosine(_VEC_A, _VEC_NEAR_A)
    assert score >= 0.95


# ── Normalize helper ──────────────────────────────────────────────────────────

def test_normalize_lowercases():
    assert _normalize("Hello World") == "hello world"


def test_normalize_collapses_whitespace():
    assert _normalize("  foo   bar  ") == "foo bar"


def test_normalize_empty():
    assert _normalize("") == ""


# ── put / get — exact hit ─────────────────────────────────────────────────────

def test_exact_hit_after_put():
    cache = _make_cache()
    cache.put("hello world", "response A")
    result = cache.get("hello world")
    assert result is not None
    assert result.hit_type == HitType.EXACT
    assert result.response == "response A"
    assert result.similarity == 1.0


def test_exact_hit_case_insensitive():
    cache = _make_cache()
    cache.put("Hello World", "answer")
    result = cache.get("hello world")
    assert result is not None
    assert result.hit_type == HitType.EXACT


def test_exact_hit_whitespace_normalized():
    cache = _make_cache()
    cache.put("hello  world", "answer")
    result = cache.get("hello world")
    assert result is not None
    assert result.hit_type == HitType.EXACT


# ── put / get — semantic hit ──────────────────────────────────────────────────

def test_semantic_hit_near_duplicate():
    # "hello" maps to VEC_A; "hi" maps to VEC_NEAR_A — cosine ≈ 0.98 > threshold 0.95
    cache = _make_cache()
    cache.put("hello there", "greet response")
    result = cache.get("hi there")
    assert result is not None
    assert result.hit_type == HitType.SEMANTIC
    assert result.response == "greet response"
    assert 0.95 <= result.similarity <= 1.0


def test_semantic_miss_orthogonal():
    # "bonjour"… wait, bonjour maps to NEAR_A, not VEC_C — use explicit mapping
    embed = _make_embed({"hello world": _VEC_A, "python code": _VEC_C})
    cache = SemanticCache(embed_fn=embed, threshold=0.95, max_size=10, ttl_s=300.0)
    cache.put("hello world", "answer")
    result = cache.get("python code")
    # cosine(A, C) = 0 < 0.95 → miss
    assert result is None


def test_miss_returns_none_empty_cache():
    cache = _make_cache()
    assert cache.get("anything") is None


# ── put — update existing entry ───────────────────────────────────────────────

def test_put_updates_existing_response():
    cache = _make_cache()
    cache.put("hello world", "v1")
    cache.put("hello world", "v2")
    result = cache.get("hello world")
    assert result.response == "v2"
    assert cache.entry_count() == 1


# ── invalidate ────────────────────────────────────────────────────────────────

def test_invalidate_removes_entry():
    cache = _make_cache()
    cache.put("hello world", "answer")
    assert cache.invalidate("hello world") is True
    assert cache.get("hello world") is None


def test_invalidate_missing_returns_false():
    cache = _make_cache()
    assert cache.invalidate("ghost") is False


def test_invalidate_case_insensitive():
    cache = _make_cache()
    cache.put("Hello World", "answer")
    assert cache.invalidate("hello world") is True


# ── clear ─────────────────────────────────────────────────────────────────────

def test_clear_removes_all_entries():
    cache = _make_cache()
    cache.put("hello world", "a")
    cache.put("hi there", "b")
    n = cache.clear()
    assert n == 2
    assert cache.entry_count() == 0


def test_clear_empty_cache_returns_zero():
    cache = _make_cache()
    assert cache.clear() == 0


# ── TTL expiry ────────────────────────────────────────────────────────────────

def test_expired_entry_returns_miss(monkeypatch):
    cache = SemanticCache(embed_fn=_simple_embed, threshold=0.9, max_size=10, ttl_s=1.0)
    cache.put("hello world", "answer")

    # Advance monotonic time past TTL
    original_monotonic = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: original_monotonic() + 2.0)

    result = cache.get("hello world")
    assert result is None


def test_expired_exact_entry_cleaned_up(monkeypatch):
    cache = SemanticCache(embed_fn=_simple_embed, threshold=0.9, max_size=10, ttl_s=1.0)
    cache.put("hello world", "answer")

    original_monotonic = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: original_monotonic() + 2.0)

    cache.get("hello world")
    assert cache.entry_count() == 0


# ── LRU eviction ─────────────────────────────────────────────────────────────

def test_lru_eviction_when_full():
    embed = _make_embed({}, default=_VEC_A)
    cache = SemanticCache(embed_fn=embed, threshold=0.99, max_size=3, ttl_s=300.0)
    cache.put("a", "ra")
    cache.put("b", "rb")
    cache.put("c", "rc")
    assert cache.entry_count() == 3
    # Access "a" to make "b" the LRU
    cache.get("a")
    # Adding "d" should evict "b" (LRU)
    cache.put("d", "rd")
    assert cache.entry_count() == 3
    assert cache.stats()["evictions"] == 1


# ── Stats ─────────────────────────────────────────────────────────────────────

def test_stats_initial_zeros():
    cache = _make_cache()
    s = cache.stats()
    assert s["total_queries"] == 0
    assert s["exact_hits"] == 0
    assert s["semantic_hits"] == 0
    assert s["misses"] == 0
    assert s["hit_rate"] == 0.0


def test_stats_exact_hit_counted():
    cache = _make_cache()
    cache.put("hello world", "a")
    cache.get("hello world")
    s = cache.stats()
    assert s["exact_hits"] == 1
    assert s["total_queries"] == 1
    assert s["hit_rate"] == 1.0


def test_stats_semantic_hit_counted():
    cache = _make_cache()
    cache.put("hello there", "a")
    cache.get("hi there")
    s = cache.stats()
    assert s["semantic_hits"] == 1
    assert s["misses"] == 0


def test_stats_miss_counted():
    embed = _make_embed({"hello world": _VEC_A, "python code": _VEC_C})
    cache = SemanticCache(embed_fn=embed, threshold=0.95, max_size=10, ttl_s=300.0)
    cache.put("hello world", "a")
    cache.get("python code")
    s = cache.stats()
    assert s["misses"] == 1
    assert s["hit_rate"] == 0.0


def test_stats_reset():
    cache = _make_cache()
    cache.put("hello world", "a")
    cache.get("hello world")
    cache.reset_stats()
    s = cache.stats()
    assert s["total_queries"] == 0
    assert s["exact_hits"] == 0
    assert s["entry_count"] == 1  # entries NOT cleared by reset_stats


def test_stats_shape():
    cache = _make_cache()
    s = cache.stats()
    for key in ("total_queries", "exact_hits", "semantic_hits", "misses",
                "evictions", "hit_rate", "semantic_hit_rate",
                "entry_count", "threshold", "max_size", "ttl_s"):
        assert key in s


# ── SemanticCacheResult ───────────────────────────────────────────────────────

def test_result_to_dict_shape():
    cache = _make_cache()
    cache.put("hello world", "answer")
    result = cache.get("hello world")
    assert result is not None
    d = result.to_dict()
    for key in ("hit_type", "response", "similarity", "matched_text", "entry_id"):
        assert key in d


def test_result_entry_id_matches_stored():
    cache = _make_cache()
    eid = cache.put("hello world", "answer")
    result = cache.get("hello world")
    assert result.entry_id == eid


# ── Thread safety smoke test ──────────────────────────────────────────────────

def test_concurrent_puts_do_not_corrupt():
    import threading
    cache = SemanticCache(embed_fn=_simple_embed, threshold=0.9, max_size=100, ttl_s=300.0)
    errors: list[Exception] = []

    def worker(i: int) -> None:
        try:
            for j in range(10):
                cache.put(f"hello {i}-{j}", f"r{i}-{j}")
                cache.get(f"hello {i}-{j}")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert cache.entry_count() <= 100
