"""
Unit tests — Fuzzy Matcher (Fáze 51). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.fuzzy_matcher import (
    FuzzyMatcher,
    Match,
    MatchResult,
    levenshtein,
    ratio,
)


# ── Levenshtein ──────────────────────────────────────────────────────────────────

def test_levenshtein_identical():
    assert levenshtein("cat", "cat") == 0


def test_levenshtein_substitution():
    assert levenshtein("cat", "bat") == 1


def test_levenshtein_insertion():
    assert levenshtein("cat", "cart") == 1


def test_levenshtein_deletion():
    assert levenshtein("cart", "cat") == 1


def test_levenshtein_empty():
    assert levenshtein("", "abc") == 3
    assert levenshtein("abc", "") == 3
    assert levenshtein("", "") == 0


def test_levenshtein_classic():
    assert levenshtein("kitten", "sitting") == 3


# ── Ratio ────────────────────────────────────────────────────────────────────────

def test_ratio_identical():
    assert ratio("hello", "hello") == 1.0


def test_ratio_both_empty():
    assert ratio("", "") == 1.0


def test_ratio_partial():
    # "cat" vs "bat": dist 1, max len 3 → 1 - 1/3 ≈ 0.667
    assert ratio("cat", "bat") == pytest.approx(2 / 3, abs=1e-3)


def test_ratio_disjoint():
    assert ratio("abc", "xyz") == pytest.approx(0.0)


# ── Construction ─────────────────────────────────────────────────────────────────

def test_invalid_threshold_raises():
    with pytest.raises(ValueError):
        FuzzyMatcher(threshold=1.5)


def test_invalid_top_k_raises():
    m = FuzzyMatcher(["a"])
    with pytest.raises(ValueError):
        m.match("a", top_k=0)


# ── Matching ─────────────────────────────────────────────────────────────────────

def test_exact_match_scores_one():
    m = FuzzyMatcher(["apple", "banana", "cherry"])
    r = m.match("apple")
    assert r.best.candidate == "apple"
    assert r.best.score == 1.0


def test_typo_tolerant():
    m = FuzzyMatcher(["banana", "apple", "cherry"], threshold=0.6)
    r = m.match("appel")  # typo of apple
    assert r.best.candidate == "apple"


def test_case_insensitive_default():
    m = FuzzyMatcher(["Apple"])
    r = m.match("apple")
    assert r.best is not None
    assert r.best.score == 1.0


def test_case_sensitive_mode():
    m = FuzzyMatcher(["Apple"], case_sensitive=True, threshold=0.9)
    r = m.match("apple")
    # one substitution (A vs a) → ratio 0.8 < 0.9 → no match
    assert r.best is None


def test_below_threshold_no_match():
    m = FuzzyMatcher(["watermelon"], threshold=0.8)
    r = m.match("car")
    assert r.best is None
    assert r.matches == []


def test_top_k_limits():
    m = FuzzyMatcher(["test", "text", "best", "rest", "tent"], threshold=0.0)
    r = m.match("test", top_k=2)
    assert len(r.matches) == 2


def test_results_sorted_by_score():
    m = FuzzyMatcher(["test", "best", "tasting"], threshold=0.0)
    r = m.match("test")
    scores = [mm.score for mm in r.matches]
    assert scores == sorted(scores, reverse=True)
    assert r.matches[0].candidate == "test"  # exact


def test_per_call_candidates_override():
    m = FuzzyMatcher(["foo"])
    r = m.match("bar", candidates=["bar", "baz"])
    assert r.best.candidate == "bar"


def test_best_match_helper():
    m = FuzzyMatcher(["alpha", "beta"])
    best = m.best_match("alpha")
    assert best.candidate == "alpha"


def test_best_match_none_on_miss():
    m = FuzzyMatcher(["alpha"], threshold=0.9)
    assert m.best_match("zzzzz") is None


def test_empty_candidates():
    m = FuzzyMatcher([])
    r = m.match("anything")
    assert r.best is None


# ── Candidate management ─────────────────────────────────────────────────────────

def test_set_candidates():
    m = FuzzyMatcher()
    m.set_candidates(["one", "two"])
    assert m.list_candidates() == ["one", "two"]


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    m = FuzzyMatcher(["apple"])
    d = m.match("apple").to_dict()
    for key in ("query", "matches", "best"):
        assert key in d
    for key in ("candidate", "score", "distance"):
        assert key in d["matches"][0]


def test_match_to_dict_shape():
    mm = Match("x", 0.9, 1)
    assert mm.to_dict() == {"candidate": "x", "score": 0.9, "distance": 1}


def test_result_best_none_serializes():
    m = FuzzyMatcher(["apple"], threshold=0.99)
    d = m.match("zzzzz").to_dict()
    assert d["best"] is None


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_hits_and_misses():
    m = FuzzyMatcher(["apple"], threshold=0.7)
    m.match("apple")     # hit
    m.match("zzzzz")     # miss
    mm = m.metrics()
    assert mm["total_queries"] == 2
    assert mm["hits"] == 1
    assert mm["misses"] == 1
    assert mm["hit_rate"] == 0.5


def test_metrics_reset():
    m = FuzzyMatcher(["apple"])
    m.match("apple")
    m.reset_metrics()
    mm = m.metrics()
    assert mm["total_queries"] == 0
    assert mm["hits"] == 0


def test_metrics_shape():
    m = FuzzyMatcher(["apple"])
    mm = m.metrics()
    for key in ("total_queries", "hits", "misses", "hit_rate",
                "candidate_count", "threshold"):
        assert key in mm
