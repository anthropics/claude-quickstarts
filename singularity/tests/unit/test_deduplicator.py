"""
Unit tests — Deduplicator (Fáze 48). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.deduplicator import (
    Deduplicator,
    DuplicateCheck,
    hamming,
    simhash,
)


# ── Hash helpers ─────────────────────────────────────────────────────────────────

def test_simhash_deterministic():
    assert simhash("the quick brown fox") == simhash("the quick brown fox")


def test_simhash_empty_is_zero():
    assert simhash("") == 0


def test_simhash_similar_closer_than_different():
    base = simhash("the quick brown fox jumps over the lazy dog")
    similar = simhash("the quick brown fox jumps over the lazy cat")
    different = simhash("cooking recipes italian pasta tomato sauce today")
    # a one-word edit must be markedly closer than an unrelated text
    assert hamming(base, similar) < hamming(base, different)


def test_simhash_different_texts_far():
    a = simhash("machine learning artificial intelligence neural networks")
    b = simhash("cooking recipes italian pasta tomato sauce")
    assert hamming(a, b) > 10


def test_hamming_identical_zero():
    assert hamming(123, 123) == 0


def test_hamming_known():
    assert hamming(0b1010, 0b0001) == 3


# ── Construction ─────────────────────────────────────────────────────────────────

def test_invalid_threshold_raises():
    with pytest.raises(ValueError):
        Deduplicator(threshold=65)


def test_invalid_shingle_k_raises():
    with pytest.raises(ValueError):
        Deduplicator(shingle_k=0)


# ── Exact duplicates ─────────────────────────────────────────────────────────────

def test_exact_duplicate_detected():
    d = Deduplicator()
    d.add("hello world this is a test")
    _, check = d.add("hello world this is a test")
    assert check.is_duplicate
    assert check.duplicate_type == "exact"
    assert check.distance == 0


def test_exact_duplicate_case_whitespace_insensitive():
    d = Deduplicator()
    d.add("Hello   World")
    _, check = d.add("hello world")
    assert check.is_duplicate
    assert check.duplicate_type == "exact"


def test_first_occurrence_not_duplicate():
    d = Deduplicator()
    _, check = d.add("unique content here")
    assert not check.is_duplicate
    assert check.duplicate_type == "none"


# ── Near duplicates ──────────────────────────────────────────────────────────────

def test_near_duplicate_detected():
    d = Deduplicator(threshold=8)
    d.add("the quick brown fox jumps over the lazy dog today")
    _, check = d.add("the quick brown fox jumps over the lazy dog now")
    assert check.is_duplicate
    assert check.duplicate_type == "near"
    assert check.distance is not None and check.distance <= 8


def test_distinct_texts_not_near():
    d = Deduplicator(threshold=3)
    d.add("machine learning models and neural network training")
    _, check = d.add("the weather is sunny and warm in the afternoon")
    assert not check.is_duplicate


def test_threshold_zero_only_exact():
    d = Deduplicator(threshold=0)
    d.add("the quick brown fox runs")
    _, check = d.add("the quick brown fox walks")
    # different content, distance > 0 → with threshold 0, not a near-dup
    assert check.duplicate_type in ("none", "exact")
    assert not (check.duplicate_type == "near")


# ── check (no add) ───────────────────────────────────────────────────────────────

def test_check_does_not_add():
    d = Deduplicator()
    d.check("some text")
    assert d.size == 0


def test_check_finds_existing():
    d = Deduplicator()
    d.add("registered text content")
    check = d.check("registered text content")
    assert check.is_duplicate


# ── add registers ────────────────────────────────────────────────────────────────

def test_add_increases_size():
    d = Deduplicator()
    d.add("first unique text")
    d.add("second different text entirely")
    assert d.size == 2


def test_add_duplicate_does_not_grow():
    d = Deduplicator()
    d.add("same content")
    d.add("same content")
    assert d.size == 1


def test_add_returns_existing_id_on_dup():
    d = Deduplicator()
    id1, _ = d.add("content alpha", entry_id="A")
    id2, check = d.add("content alpha", entry_id="B")
    assert id2 == "A"  # returns original id


# ── deduplicate list ─────────────────────────────────────────────────────────────

def test_deduplicate_list():
    d = Deduplicator()
    texts = [
        "apple banana cherry",
        "apple banana cherry",     # exact dup
        "completely different fruit set here mango",
    ]
    result = d.deduplicate(texts)
    assert result["input_count"] == 3
    assert result["unique_count"] == 2
    assert result["duplicate_count"] == 1


def test_deduplicate_all_unique():
    d = Deduplicator(threshold=3)
    texts = ["alpha one two", "beta three four", "gamma five six"]
    result = d.deduplicate(texts)
    assert result["unique_count"] == 3
    assert result["duplicate_count"] == 0


# ── clear ────────────────────────────────────────────────────────────────────────

def test_clear():
    d = Deduplicator()
    d.add("a b c d")
    d.add("e f g h")
    assert d.clear() == 2
    assert d.size == 0


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_check_to_dict_shape():
    d = Deduplicator()
    check = d.check("text")
    dd = check.to_dict()
    for key in ("is_duplicate", "duplicate_type", "matched_id", "distance"):
        assert key in dd


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    d = Deduplicator()
    d.add("hello world test")
    d.add("hello world test")          # exact
    d.add("entirely separate phrase x")
    m = d.metrics()
    assert m["total_checks"] == 3
    assert m["exact_duplicates"] == 1
    assert m["unique"] == 2


def test_metrics_dup_rate():
    d = Deduplicator()
    d.add("repeat me")
    d.add("repeat me")
    m = d.metrics()
    assert m["dup_rate"] == 0.5


def test_metrics_reset():
    d = Deduplicator()
    d.add("x y z content")
    d.reset_metrics()
    m = d.metrics()
    assert m["total_checks"] == 0
    assert m["unique"] == 0
    # index itself is not cleared by metric reset
    assert m["indexed"] == 1


def test_metrics_shape():
    d = Deduplicator()
    m = d.metrics()
    for key in ("total_checks", "exact_duplicates", "near_duplicates",
                "unique", "dup_rate", "indexed", "threshold", "shingle_k"):
        assert key in m
