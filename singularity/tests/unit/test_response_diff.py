"""
Unit tests — Response Comparator (Fáze 41). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.response_diff import (
    DiffOp,
    DiffResult,
    DiffSegment,
    ResponseComparator,
    _jaccard,
    _split_sentences,
    _tokens,
)


# ── Helpers ──────────────────────────────────────────────────────────────────────

def test_split_sentences():
    assert _split_sentences("One. Two! Three?") == ["One.", "Two!", "Three?"]


def test_split_sentences_empty():
    assert _split_sentences("") == []


def test_tokens_lowercase():
    assert _tokens("Hello World") == {"hello", "world"}


def test_jaccard_identical():
    assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_both_empty():
    assert _jaccard(set(), set()) == 1.0


def test_jaccard_one_empty():
    assert _jaccard(set(), {"a"}) == 0.0


# ── Identical ────────────────────────────────────────────────────────────────────

def test_identical_texts():
    c = ResponseComparator()
    r = c.compare("Same text here. Second sentence.", "Same text here. Second sentence.")
    assert r.identical is True
    assert r.similarity == 1.0
    assert r.token_jaccard == 1.0
    assert r.added == 0 and r.removed == 0 and r.changed == 0
    assert all(s.op == DiffOp.UNCHANGED for s in r.segments)


# ── Pure addition ────────────────────────────────────────────────────────────────

def test_addition():
    c = ResponseComparator()
    r = c.compare("First sentence.", "First sentence. New second sentence.")
    assert r.added == 1
    assert r.removed == 0
    assert r.unchanged == 1
    added = [s for s in r.segments if s.op == DiffOp.ADDED]
    assert added[0].b_text == "New second sentence."


# ── Pure removal ─────────────────────────────────────────────────────────────────

def test_removal():
    c = ResponseComparator()
    r = c.compare("Keep this. Drop this.", "Keep this.")
    assert r.removed == 1
    assert r.unchanged == 1
    removed = [s for s in r.segments if s.op == DiffOp.REMOVED]
    assert removed[0].a_text == "Drop this."


# ── Change (replace) ─────────────────────────────────────────────────────────────

def test_change():
    c = ResponseComparator()
    r = c.compare("The sky is blue.", "The sky is green.")
    assert r.changed == 1
    changed = [s for s in r.segments if s.op == DiffOp.CHANGED]
    assert changed[0].a_text == "The sky is blue."
    assert changed[0].b_text == "The sky is green."


def test_replace_with_surplus_additions():
    c = ResponseComparator()
    # one sentence replaced by two → 1 changed + 1 added
    r = c.compare("Old line.", "New line one. New line two.")
    assert r.changed == 1
    assert r.added == 1


def test_replace_with_surplus_removals():
    c = ResponseComparator()
    # two sentences replaced by one → 1 changed + 1 removed
    r = c.compare("Old one. Old two.", "Fresh single.")
    assert r.changed == 1
    assert r.removed == 1


# ── Mixed ────────────────────────────────────────────────────────────────────────

def test_mixed_diff():
    c = ResponseComparator()
    a = "Intro stays. This will change. This is removed."
    b = "Intro stays. This has changed. Brand new one."
    r = c.compare(a, b)
    assert r.unchanged >= 1
    # similarity strictly between 0 and 1
    assert 0.0 < r.similarity < 1.0
    assert r.identical is False


# ── Empty inputs ─────────────────────────────────────────────────────────────────

def test_both_empty():
    c = ResponseComparator()
    r = c.compare("", "")
    assert r.identical is True
    assert r.segments == []


def test_a_empty_b_has_content():
    c = ResponseComparator()
    r = c.compare("", "New content here.")
    assert r.added == 1
    assert r.removed == 0


def test_b_empty_a_has_content():
    c = ResponseComparator()
    r = c.compare("Old content here.", "")
    assert r.removed == 1
    assert r.added == 0


# ── token_jaccard ────────────────────────────────────────────────────────────────

def test_token_jaccard_partial():
    c = ResponseComparator()
    r = c.compare("alpha beta gamma.", "beta gamma delta.")
    # tokens: {alpha,beta,gamma} vs {beta,gamma,delta} → 2/4 = 0.5
    assert r.token_jaccard == pytest.approx(0.5)


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    c = ResponseComparator()
    r = c.compare("a.", "b.")
    d = r.to_dict()
    for key in ("segments", "similarity", "token_jaccard", "added", "removed",
                "changed", "unchanged", "identical"):
        assert key in d


def test_segment_to_dict_shape():
    seg = DiffSegment(DiffOp.CHANGED, a_text="x", b_text="y")
    d = seg.to_dict()
    assert d == {"op": "changed", "a_text": "x", "b_text": "y"}


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    c = ResponseComparator()
    c.compare("same.", "same.")       # identical
    c.compare("a.", "b.")             # changed
    m = c.metrics()
    assert m["total_comparisons"] == 2
    assert m["identical_count"] == 1
    assert m["identical_rate"] == 0.5
    assert 0.0 <= m["avg_similarity"] <= 1.0


def test_metrics_reset():
    c = ResponseComparator()
    c.compare("x.", "y.")
    c.reset_metrics()
    m = c.metrics()
    assert m["total_comparisons"] == 0
    assert m["identical_count"] == 0


def test_metrics_shape():
    c = ResponseComparator()
    m = c.metrics()
    for key in ("total_comparisons", "identical_count",
                "avg_similarity", "identical_rate"):
        assert key in m
