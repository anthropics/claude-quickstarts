"""
Unit tests — Pluggable Embedding Provider (Fáze 61). Fully offline.
"""

from __future__ import annotations

import pytest

from core.embeddings import (
    CachingEmbeddingProvider,
    EmbeddingProvider,
    HashingEmbeddingProvider,
    build_embedding_provider,
    cosine_similarity,
    _features,
    _tokens,
)


# ── Helpers ──────────────────────────────────────────────────────────────────────

def test_tokens_lowercase():
    assert _tokens("The Quick Brown") == ["the", "quick", "brown"]


def test_features_includes_bigrams():
    feats = _features("the quick brown", ngram=2)
    assert "the" in feats
    assert "the quick" in feats
    assert "quick brown" in feats


def test_features_unigram_only():
    feats = _features("a b c", ngram=1)
    assert feats == ["a", "b", "c"]


def test_cosine_identical():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_orthogonal():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_mismatched_dims():
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0


def test_cosine_zero_vector():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


# ── HashingEmbeddingProvider ─────────────────────────────────────────────────────

def test_dim_validation():
    with pytest.raises(ValueError):
        HashingEmbeddingProvider(dim=0)


def test_ngram_validation():
    with pytest.raises(ValueError):
        HashingEmbeddingProvider(ngram=0)


def test_embed_dim_matches():
    p = HashingEmbeddingProvider(dim=64)
    v = p.embed("hello world")
    assert len(v) == 64
    assert p.dim == 64


def test_embed_deterministic():
    p = HashingEmbeddingProvider(dim=128)
    assert p.embed("repeatable text") == p.embed("repeatable text")


def test_embed_normalized():
    p = HashingEmbeddingProvider(dim=128)
    v = p.embed("some content here")
    norm = sum(x * x for x in v) ** 0.5
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_embed_empty_is_zero_vector():
    p = HashingEmbeddingProvider(dim=32)
    v = p.embed("")
    assert v == [0.0] * 32


def test_lexical_locality():
    # THE key property: shared words → higher cosine than unrelated text.
    p = HashingEmbeddingProvider(dim=512)
    base = p.embed("the quick brown fox jumps over the lazy dog")
    similar = p.embed("the quick brown fox jumps over the lazy cat")
    unrelated = p.embed("financial markets rallied on strong earnings reports")
    assert cosine_similarity(base, similar) > cosine_similarity(base, unrelated)


def test_identical_text_cosine_one():
    p = HashingEmbeddingProvider(dim=256)
    a = p.embed("machine learning pipeline")
    b = p.embed("machine learning pipeline")
    assert cosine_similarity(a, b) == pytest.approx(1.0, abs=1e-6)


def test_similarity_helper():
    p = HashingEmbeddingProvider(dim=256)
    s = p.similarity("data science", "data science")
    assert s == pytest.approx(1.0, abs=1e-6)


def test_embed_batch():
    p = HashingEmbeddingProvider(dim=64)
    vecs = p.embed_batch(["a", "b", "c"])
    assert len(vecs) == 3
    assert all(len(v) == 64 for v in vecs)


def test_metrics_counts_embeds():
    p = HashingEmbeddingProvider(dim=32)
    p.embed("one")
    p.embed("two")
    m = p.metrics()
    assert m["embeds"] == 2
    assert m["name"] == "hashing"
    assert m["dim"] == 32


# ── CachingEmbeddingProvider ─────────────────────────────────────────────────────

def test_caching_validation():
    with pytest.raises(ValueError):
        CachingEmbeddingProvider(HashingEmbeddingProvider(), max_size=0)


def test_caching_returns_same_vector():
    p = CachingEmbeddingProvider(HashingEmbeddingProvider(dim=64), max_size=10)
    v1 = p.embed("hello")
    v2 = p.embed("hello")
    assert v1 == v2


def test_caching_hit_miss_metrics():
    p = CachingEmbeddingProvider(HashingEmbeddingProvider(dim=64), max_size=10)
    p.embed("x")   # miss
    p.embed("x")   # hit
    p.embed("y")   # miss
    m = p.metrics()
    assert m["hits"] == 1
    assert m["misses"] == 2
    assert m["hit_rate"] == pytest.approx(1 / 3, abs=1e-3)


def test_caching_lru_eviction():
    p = CachingEmbeddingProvider(HashingEmbeddingProvider(dim=32), max_size=2)
    p.embed("a")
    p.embed("b")
    p.embed("c")  # evicts "a"
    assert p.metrics()["cache_size"] == 2


def test_caching_dim_delegates():
    p = CachingEmbeddingProvider(HashingEmbeddingProvider(dim=99))
    assert p.dim == 99


def test_caching_reset_metrics():
    p = CachingEmbeddingProvider(HashingEmbeddingProvider(dim=32))
    p.embed("x")
    p.reset_metrics()
    m = p.metrics()
    assert m["hits"] == 0
    assert m["misses"] == 0


# ── Factory ──────────────────────────────────────────────────────────────────────

def test_build_default_is_cached():
    p = build_embedding_provider()
    assert isinstance(p, CachingEmbeddingProvider)
    assert p.dim == 256


def test_build_no_cache():
    p = build_embedding_provider(cache_size=None)
    assert isinstance(p, HashingEmbeddingProvider)


def test_build_custom_dim():
    p = build_embedding_provider(dim=128, cache_size=None)
    assert p.dim == 128


def test_build_unknown_raises():
    with pytest.raises(ValueError):
        build_embedding_provider("nonexistent")


def test_build_provides_embeddingprovider():
    p = build_embedding_provider()
    assert isinstance(p, EmbeddingProvider)


# ── Integration: drop-in for semantic-cache-style usage ──────────────────────────

def test_usable_as_embed_fn():
    # SemanticCache (Fáze 29) takes embed_fn(text)->list[float]; provider.embed fits.
    p = build_embedding_provider(cache_size=None)
    embed_fn = p.embed
    v = embed_fn("a query string")
    assert isinstance(v, list)
    assert len(v) == p.dim
