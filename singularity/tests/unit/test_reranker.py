"""
Unit tests — Hybrid Reranker (Fáze 38). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.reranker import (
    FusedResult,
    FusionMethod,
    HybridReranker,
    RankedItem,
    _coerce,
    _minmax_normalize,
)


# ── Helpers ──────────────────────────────────────────────────────────────────────

def test_coerce_from_dict():
    item = _coerce({"doc_id": "d1", "score": 0.5, "text": "hi"})
    assert item.doc_id == "d1"
    assert item.score == 0.5
    assert item.text == "hi"


def test_coerce_id_alias():
    assert _coerce({"id": "x", "score": 1.0}).doc_id == "x"


def test_coerce_from_string():
    assert _coerce("abc").doc_id == "abc"


def test_coerce_passthrough_rankeditem():
    ri = RankedItem(doc_id="d", score=2.0)
    assert _coerce(ri) is ri


def test_minmax_normalize_basic():
    assert _minmax_normalize([0.0, 5.0, 10.0]) == [0.0, 0.5, 1.0]


def test_minmax_all_equal():
    assert _minmax_normalize([3.0, 3.0, 3.0]) == [1.0, 1.0, 1.0]


def test_minmax_empty():
    assert _minmax_normalize([]) == []


# ── Construction ─────────────────────────────────────────────────────────────────

def test_invalid_rrf_k_raises():
    with pytest.raises(ValueError):
        HybridReranker(rrf_k=0)


# ── RRF fusion ───────────────────────────────────────────────────────────────────

def test_rrf_single_list_preserves_order():
    r = HybridReranker()
    fused = r.fuse([["a", "b", "c"]])
    assert [f.doc_id for f in fused] == ["a", "b", "c"]
    assert fused[0].rank == 0


def test_rrf_consensus_doc_wins():
    r = HybridReranker(rrf_k=60)
    # "x" is top in both lists → highest combined RRF
    list1 = ["x", "y", "z"]
    list2 = ["x", "z", "y"]
    fused = r.fuse([list1, list2])
    assert fused[0].doc_id == "x"


def test_rrf_doc_in_both_beats_doc_in_one():
    r = HybridReranker(rrf_k=60)
    # "shared" is rank1 in both; "solo" is rank0 in one only
    list1 = ["solo", "shared"]
    list2 = ["other", "shared"]
    fused = r.fuse([list1, list2])
    # shared appears twice (2/(61)) vs solo once (1/60); shared wins
    assert fused[0].doc_id == "shared"


def test_rrf_sources_tracked():
    r = HybridReranker()
    fused = r.fuse([["a"], ["a"]])
    a = next(f for f in fused if f.doc_id == "a")
    assert set(a.sources) == {"list0", "list1"}


def test_rrf_weights_applied():
    r = HybridReranker(rrf_k=60)
    # boost list2 heavily so its top doc beats list1's top
    fused = r.fuse([["a", "b"], ["b", "a"]], weights=[0.1, 5.0])
    assert fused[0].doc_id == "b"


# ── Weighted-score fusion ────────────────────────────────────────────────────────

def test_weighted_score_uses_magnitude():
    r = HybridReranker()
    list1 = [{"doc_id": "a", "score": 10.0}, {"doc_id": "b", "score": 1.0}]
    fused = r.fuse([list1], method=FusionMethod.WEIGHTED_SCORE)
    assert fused[0].doc_id == "a"


def test_weighted_score_normalizes_across_scales():
    r = HybridReranker()
    # list1 scores 0-100, list2 scores 0-1; normalization makes them comparable
    list1 = [{"doc_id": "a", "score": 100.0}, {"doc_id": "b", "score": 0.0}]
    list2 = [{"doc_id": "b", "score": 1.0}, {"doc_id": "a", "score": 0.0}]
    fused = r.fuse([list1, list2], method=FusionMethod.WEIGHTED_SCORE)
    # a: norm 1.0 + 0.0 = 1.0; b: norm 0.0 + 1.0 = 1.0 → tie, doc_id break
    scores = {f.doc_id: f.fused_score for f in fused}
    assert scores["a"] == pytest.approx(scores["b"])


def test_weighted_score_weights():
    r = HybridReranker()
    list1 = [{"doc_id": "a", "score": 1.0}, {"doc_id": "b", "score": 0.0}]
    list2 = [{"doc_id": "b", "score": 1.0}, {"doc_id": "a", "score": 0.0}]
    fused = r.fuse([list1, list2], method=FusionMethod.WEIGHTED_SCORE, weights=[3.0, 1.0])
    # a weighted higher
    assert fused[0].doc_id == "a"


# ── Validation ───────────────────────────────────────────────────────────────────

def test_weights_length_mismatch_raises():
    r = HybridReranker()
    with pytest.raises(ValueError):
        r.fuse([["a"], ["b"]], weights=[1.0])


def test_empty_lists():
    r = HybridReranker()
    assert r.fuse([]) == []


def test_all_empty_lists():
    r = HybridReranker()
    assert r.fuse([[], []]) == []


# ── top_k ────────────────────────────────────────────────────────────────────────

def test_top_k_limits_output():
    r = HybridReranker()
    fused = r.fuse([["a", "b", "c", "d", "e"]], top_k=2)
    assert len(fused) == 2


# ── Ranks & metadata ─────────────────────────────────────────────────────────────

def test_ranks_sequential():
    r = HybridReranker()
    fused = r.fuse([["a", "b", "c"]])
    assert [f.rank for f in fused] == [0, 1, 2]


def test_text_and_metadata_carried():
    r = HybridReranker()
    list1 = [{"doc_id": "a", "score": 1.0, "text": "hello", "metadata": {"k": 1}}]
    fused = r.fuse([list1], method=FusionMethod.WEIGHTED_SCORE)
    assert fused[0].text == "hello"
    assert fused[0].metadata == {"k": 1}


def test_text_filled_from_later_list_if_missing():
    r = HybridReranker()
    list1 = [{"doc_id": "a", "score": 1.0}]               # no text
    list2 = [{"doc_id": "a", "score": 1.0, "text": "found"}]
    fused = r.fuse([list1, list2])
    assert fused[0].text == "found"


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    r = HybridReranker()
    fused = r.fuse([["a"]])
    d = fused[0].to_dict()
    for key in ("doc_id", "fused_score", "rank", "sources", "text", "metadata"):
        assert key in d


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    r = HybridReranker()
    r.fuse([["a", "b"], ["b", "c"]])
    m = r.metrics()
    assert m["total_fusions"] == 1
    assert m["total_input_items"] == 4
    assert m["total_output_items"] == 3  # a, b, c


def test_metrics_avg_output():
    r = HybridReranker()
    r.fuse([["a", "b"]])
    r.fuse([["c", "d"]])
    m = r.metrics()
    assert m["avg_output_size"] == 2.0


def test_metrics_reset():
    r = HybridReranker()
    r.fuse([["a"]])
    r.reset_metrics()
    m = r.metrics()
    assert m["total_fusions"] == 0
    assert m["total_input_items"] == 0


def test_metrics_shape():
    r = HybridReranker()
    m = r.metrics()
    for key in ("total_fusions", "total_input_items", "total_output_items",
                "avg_output_size", "rrf_k", "default_method"):
        assert key in m
