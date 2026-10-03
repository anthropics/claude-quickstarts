"""
Unit tests — Readability Analyzer (Fáze 47). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.readability import (
    ReadabilityAnalyzer,
    ReadabilityResult,
    count_syllables,
    _count_sentences,
    _words,
)


# ── Syllable counting ────────────────────────────────────────────────────────────

def test_syllables_simple():
    assert count_syllables("cat") == 1


def test_syllables_two():
    assert count_syllables("table") == 2  # "le" exception kept


def test_syllables_silent_e():
    assert count_syllables("make") == 1   # trailing silent e dropped


def test_syllables_multi():
    assert count_syllables("beautiful") >= 3


def test_syllables_empty():
    assert count_syllables("") == 0


def test_syllables_min_one():
    # a word with no standard vowels still counts as >= 1
    assert count_syllables("rhythm") >= 1


# ── Helpers ──────────────────────────────────────────────────────────────────────

def test_count_sentences():
    assert _count_sentences("One. Two! Three?") == 3


def test_count_sentences_min_one():
    assert _count_sentences("no terminal punctuation") == 1


def test_words_extraction():
    assert _words("Hello, world! 123") == ["Hello", "world"]


# ── Analysis ─────────────────────────────────────────────────────────────────────

def test_empty_text():
    a = ReadabilityAnalyzer()
    r = a.analyze("")
    assert r.word_count == 0
    assert r.reading_level == "unknown"


def test_simple_text_easy():
    a = ReadabilityAnalyzer()
    r = a.analyze("The cat sat. The dog ran. We had fun.")
    # short words + short sentences → high ease
    assert r.flesch_reading_ease > 70
    assert r.reading_level in ("very_easy", "easy")


def test_complex_text_harder():
    a = ReadabilityAnalyzer()
    simple = a.analyze("The cat sat on the mat and ate.")
    complex_ = a.analyze(
        "Constitutional jurisprudence necessitates comprehensive interpretation "
        "of legislative intentions alongside precedential considerations."
    )
    assert complex_.flesch_reading_ease < simple.flesch_reading_ease
    assert complex_.flesch_kincaid_grade > simple.flesch_kincaid_grade


def test_counts_reported():
    a = ReadabilityAnalyzer()
    r = a.analyze("The cat sat on the mat.")
    assert r.word_count == 6
    assert r.sentence_count == 1
    assert r.syllable_count >= 6


def test_averages_computed():
    a = ReadabilityAnalyzer()
    r = a.analyze("One two three. Four five six.")
    assert r.avg_words_per_sentence == pytest.approx(3.0)
    assert r.avg_syllables_per_word > 0


def test_reading_level_buckets():
    a = ReadabilityAnalyzer()
    # very easy
    r = a.analyze("I am a cat. I am a dog. I am here.")
    assert r.reading_level in ("very_easy", "easy")


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    a = ReadabilityAnalyzer()
    d = a.analyze("The cat sat on the mat.").to_dict()
    for key in ("flesch_reading_ease", "flesch_kincaid_grade", "word_count",
                "sentence_count", "syllable_count", "avg_words_per_sentence",
                "avg_syllables_per_word", "reading_level"):
        assert key in d


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    a = ReadabilityAnalyzer()
    a.analyze("The cat sat on the mat.")
    a.analyze("Dogs run fast in the park.")
    m = a.metrics()
    assert m["total_analyses"] == 2
    assert m["avg_reading_ease"] != 0.0


def test_metrics_reset():
    a = ReadabilityAnalyzer()
    a.analyze("Some text here today.")
    a.reset_metrics()
    m = a.metrics()
    assert m["total_analyses"] == 0
    assert m["avg_reading_ease"] == 0.0


def test_metrics_shape():
    a = ReadabilityAnalyzer()
    m = a.metrics()
    for key in ("total_analyses", "avg_reading_ease", "avg_grade_level"):
        assert key in m
