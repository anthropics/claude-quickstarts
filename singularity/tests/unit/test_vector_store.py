"""
Unit tests — Vector Store / Dense Retriever (Fáze 69). Fully offline.

Uses the deterministic hashing embedding provider (lexical locality), so
semantic ranking is predictable.
"""

from __future__ import annotations

import pytest

from core.vector_store import VectorHit, VectorStore


# ── Indexing ─────────────────────────────────────────────────────────────────────

def test_add_increases_size():
    vs = VectorStore()
    vs.add("d1", "hello world")
    assert vs.size == 1


def test_add_many():
    vs = VectorStore()
    n = vs.add_many([
        {"doc_id": "a", "text": "alpha"},
        {"id": "b", "text": "beta"},
        {"text": "gamma"},
    ])
    assert n == 3
    assert vs.size == 3


def test_add_overwrites_same_id():
    vs = VectorStore()
    vs.add("d1", "first")
    vs.add("d1", "second")
    assert vs.size == 1


def test_remove():
    vs = VectorStore()
    vs.add("d1", "content")
    assert vs.remove("d1") is True
    assert vs.size == 0


def test_remove_missing():
    vs = VectorStore()
    assert vs.remove("nope") is False


def test_clear():
    vs = VectorStore()
    vs.add_many([{"doc_id": str(i), "text": f"doc {i}"} for i in range(3)])
    assert vs.clear() == 3
    assert vs.size == 0


def test_dim_exposed():
    vs = VectorStore()
    assert vs.dim > 0


# ── Search ───────────────────────────────────────────────────────────────────────

def test_search_empty_returns_empty():
    vs = VectorStore()
    assert vs.search("anything") == []


def test_search_invalid_top_k():
    vs = VectorStore()
    vs.add("d", "x")
    with pytest.raises(ValueError):
        vs.search("x", top_k=0)


def test_search_semantic_ranking():
    vs = VectorStore()
    vs.add("animals", "the quick brown fox jumps over the lazy dog")
    vs.add("finance", "quarterly earnings and revenue growth in markets")
    vs.add("cooking", "recipe for pasta with tomato sauce and basil")
    # query overlaps the animals doc's vocabulary → highest cosine
    hits = vs.search("the quick fox and the lazy dog", top_k=1)
    assert hits[0].doc_id == "animals"


def test_search_top_k_limits():
    vs = VectorStore()
    for i in range(10):
        vs.add(f"d{i}", "shared keyword apple content")
    hits = vs.search("apple", top_k=3)
    assert len(hits) == 3


def test_search_ranks_sequential():
    vs = VectorStore()
    vs.add("a", "alpha beta gamma")
    vs.add("b", "alpha beta")
    vs.add("c", "alpha")
    hits = vs.search("alpha beta gamma")
    ranks = [h.rank for h in hits]
    assert ranks == list(range(len(hits)))
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_search_min_score_filters():
    vs = VectorStore()
    vs.add("match", "machine learning neural networks")
    vs.add("nomatch", "gardening tips for tomatoes")
    hits = vs.search("deep learning models", min_score=0.99)
    # nothing reaches 0.99 → filtered
    assert all(h.score >= 0.99 for h in hits)


def test_search_metadata_returned():
    vs = VectorStore()
    vs.add("d1", "content here", metadata={"source": "wiki"})
    hits = vs.search("content")
    assert hits[0].metadata == {"source": "wiki"}


# ── Hit shape ────────────────────────────────────────────────────────────────────

def test_hit_to_dict_shape():
    vs = VectorStore()
    vs.add("d1", "shape test content")
    d = vs.search("content")[0].to_dict()
    for key in ("doc_id", "score", "text", "rank", "metadata"):
        assert key in d


# ── Injected embedder ────────────────────────────────────────────────────────────

def test_injected_embedder_used():
    from core.embeddings import HashingEmbeddingProvider
    vs = VectorStore(embedder=HashingEmbeddingProvider(dim=64))
    vs.add("d", "text")
    assert vs.dim == 64


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics():
    vs = VectorStore()
    vs.add("a", "alpha")
    vs.add("b", "beta")
    vs.search("alpha")
    m = vs.metrics()
    assert m["indexed"] == 2
    assert m["searches"] == 1
    assert m["total_hits"] >= 1
    assert m["dim"] > 0


def test_metrics_shape():
    vs = VectorStore()
    m = vs.metrics()
    for key in ("indexed", "dim", "searches", "total_hits", "avg_hits"):
        assert key in m
