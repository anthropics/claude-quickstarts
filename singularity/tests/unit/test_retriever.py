"""
Unit tests — BM25 Retriever (Fáze 37). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.retriever import BM25Retriever, RetrievalHit, _tokenize


# ── Tokenizer ────────────────────────────────────────────────────────────────────

def test_tokenize_lowercases_and_filters_stopwords():
    assert _tokenize("The Quick Brown Fox") == ["quick", "brown", "fox"]


def test_tokenize_empty():
    assert _tokenize("") == []


def test_tokenize_numbers_kept():
    assert "42" in _tokenize("answer is 42")


# ── Construction ─────────────────────────────────────────────────────────────────

def test_invalid_k1_raises():
    with pytest.raises(ValueError):
        BM25Retriever(k1=-1)


def test_invalid_b_raises():
    with pytest.raises(ValueError):
        BM25Retriever(b=1.5)


# ── Indexing ─────────────────────────────────────────────────────────────────────

def test_add_increases_size():
    r = BM25Retriever()
    r.add("d1", "hello world")
    assert r.size == 1


def test_add_many():
    r = BM25Retriever()
    n = r.add_many([
        {"doc_id": "a", "text": "alpha"},
        {"id": "b", "text": "beta"},
        {"text": "gamma"},
    ])
    assert n == 3
    assert r.size == 3


def test_add_duplicate_id_replaces():
    r = BM25Retriever()
    r.add("d1", "old text here")
    r.add("d1", "new text here")
    assert r.size == 1
    hits = r.search("new")
    assert hits[0].text == "new text here"


def test_remove():
    r = BM25Retriever()
    r.add("d1", "removable content")
    assert r.remove("d1") is True
    assert r.size == 0


def test_remove_missing_returns_false():
    r = BM25Retriever()
    assert r.remove("nope") is False


def test_clear():
    r = BM25Retriever()
    r.add_many([{"doc_id": str(i), "text": f"doc {i}"} for i in range(3)])
    assert r.clear() == 3
    assert r.size == 0


# ── Search basics ────────────────────────────────────────────────────────────────

def test_search_empty_index():
    r = BM25Retriever()
    assert r.search("anything") == []


def test_search_empty_query():
    r = BM25Retriever()
    r.add("d1", "some content")
    assert r.search("") == []


def test_search_invalid_top_k_raises():
    r = BM25Retriever()
    r.add("d1", "content")
    with pytest.raises(ValueError):
        r.search("content", top_k=0)


def test_search_returns_relevant_doc():
    r = BM25Retriever()
    r.add("cats", "Cats are independent feline pets that purr.")
    r.add("dogs", "Dogs are loyal canine companions that bark.")
    hits = r.search("feline purr")
    assert hits[0].doc_id == "cats"


def test_search_ranks_by_relevance():
    r = BM25Retriever()
    r.add("d1", "python python python programming language")
    r.add("d2", "python is mentioned once here")
    r.add("d3", "no mention of the topic at all")
    hits = r.search("python")
    assert hits[0].doc_id == "d1"  # higher term frequency
    ids = [h.doc_id for h in hits]
    assert "d3" not in ids  # no overlap → excluded


def test_search_top_k_limits():
    r = BM25Retriever()
    for i in range(10):
        r.add(f"d{i}", "shared keyword apple")
    hits = r.search("apple", top_k=3)
    assert len(hits) == 3


def test_search_ranks_sequential():
    r = BM25Retriever()
    r.add("d1", "apple banana cherry")
    r.add("d2", "apple banana")
    r.add("d3", "apple")
    hits = r.search("apple banana cherry")
    ranks = [h.rank for h in hits]
    assert ranks == list(range(len(hits)))


def test_search_no_overlap_returns_empty():
    r = BM25Retriever()
    r.add("d1", "completely different subject matter")
    assert r.search("xyz qqq zzz") == []


# ── Length normalization (b parameter) ───────────────────────────────────────────

def test_shorter_doc_scores_higher_with_normalization():
    # Same term count, but one doc padded with irrelevant words.
    r = BM25Retriever(b=0.75)
    r.add("short", "lion")
    r.add("long", "lion " + "padding word here extra " * 20)
    hits = r.search("lion")
    assert hits[0].doc_id == "short"


# ── Metadata ─────────────────────────────────────────────────────────────────────

def test_metadata_returned_in_hits():
    r = BM25Retriever()
    r.add("d1", "metadata test content", metadata={"source": "wiki", "page": 7})
    hits = r.search("content")
    assert hits[0].metadata == {"source": "wiki", "page": 7}


# ── Hit shape ────────────────────────────────────────────────────────────────────

def test_hit_to_dict_shape():
    r = BM25Retriever()
    r.add("d1", "shape test content")
    hit = r.search("content")[0]
    d = hit.to_dict()
    for key in ("doc_id", "text", "score", "rank", "metadata"):
        assert key in d


def test_scores_are_positive():
    r = BM25Retriever()
    r.add("d1", "relevant matching terms")
    hits = r.search("relevant matching")
    assert all(h.score > 0 for h in hits)


# ── IDF behavior ─────────────────────────────────────────────────────────────────

def test_rare_term_outweighs_common_term():
    r = BM25Retriever()
    # "common" appears in all docs; "unicorn" only in d3
    r.add("d1", "common word filler")
    r.add("d2", "common word filler")
    r.add("d3", "common unicorn filler")
    hits = r.search("common unicorn")
    assert hits[0].doc_id == "d3"  # rare term boosts d3


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_after_indexing_and_search():
    r = BM25Retriever()
    r.add("d1", "alpha beta")
    r.add("d2", "beta gamma")
    r.search("beta")
    m = r.metrics()
    assert m["indexed_documents"] == 2
    assert m["vocabulary_size"] == 3  # alpha, beta, gamma
    assert m["total_searches"] == 1
    assert m["total_hits_returned"] == 2


def test_metrics_avg_hits():
    r = BM25Retriever()
    r.add("d1", "apple")
    r.search("apple")
    r.search("apple")
    m = r.metrics()
    assert m["avg_hits_per_search"] == 1.0


def test_metrics_vocabulary_shrinks_on_remove():
    r = BM25Retriever()
    r.add("d1", "uniqueword shared")
    r.add("d2", "shared")
    r.remove("d1")
    m = r.metrics()
    # "uniqueword" gone, "shared" remains
    assert m["vocabulary_size"] == 1


def test_metrics_reset():
    r = BM25Retriever()
    r.add("d1", "content")
    r.search("content")
    r.reset_metrics()
    m = r.metrics()
    assert m["total_searches"] == 0
    assert m["total_hits_returned"] == 0
    # index itself not cleared by metric reset
    assert m["indexed_documents"] == 1


def test_metrics_shape():
    r = BM25Retriever()
    m = r.metrics()
    for key in ("indexed_documents", "vocabulary_size", "total_searches",
                "total_hits_returned", "avg_hits_per_search", "k1", "b"):
        assert key in m
