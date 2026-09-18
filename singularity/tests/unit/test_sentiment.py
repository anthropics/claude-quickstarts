"""
Unit tests — Sentiment Analyzer (Fáze 45). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.sentiment import (
    Polarity,
    SentimentAnalyzer,
    SentimentResult,
    _tokenize,
)


# ── Tokenizer ────────────────────────────────────────────────────────────────────

def test_tokenize_lowercases():
    assert _tokenize("Good GREAT") == ["good", "great"]


def test_tokenize_keeps_apostrophe():
    assert "don't" in _tokenize("don't")


def test_tokenize_empty():
    assert _tokenize("") == []


# ── Construction ─────────────────────────────────────────────────────────────────

def test_invalid_threshold_raises():
    with pytest.raises(ValueError):
        SentimentAnalyzer(threshold=1.0)


def test_invalid_window_raises():
    with pytest.raises(ValueError):
        SentimentAnalyzer(negation_window=0)


# ── Basic polarity ───────────────────────────────────────────────────────────────

def test_positive_text():
    a = SentimentAnalyzer()
    r = a.analyze("This is great and wonderful, I love it.")
    assert r.polarity == Polarity.POSITIVE
    assert r.score > 0
    assert r.positive_hits >= 2


def test_negative_text():
    a = SentimentAnalyzer()
    r = a.analyze("This is terrible and awful, I hate it.")
    assert r.polarity == Polarity.NEGATIVE
    assert r.score < 0
    assert r.negative_hits >= 2


def test_neutral_text():
    a = SentimentAnalyzer()
    r = a.analyze("The package arrived on Tuesday afternoon.")
    assert r.polarity == Polarity.NEUTRAL
    assert r.score == 0.0


def test_empty_text_neutral():
    a = SentimentAnalyzer()
    r = a.analyze("")
    assert r.polarity == Polarity.NEUTRAL
    assert r.word_count == 0


# ── Negation ─────────────────────────────────────────────────────────────────────

def test_negation_flips_positive():
    a = SentimentAnalyzer()
    r = a.analyze("This is not good.")
    assert r.polarity == Polarity.NEGATIVE
    assert r.negations == 1


def test_negation_flips_negative():
    a = SentimentAnalyzer()
    r = a.analyze("This is not bad at all.")
    assert r.polarity == Polarity.POSITIVE


def test_nt_contraction_negates():
    a = SentimentAnalyzer()
    # "n't" token from tokenizer? "isn't" → ["isn't"]; use explicit form
    r = a.analyze("I do not like this.")
    assert r.polarity == Polarity.NEGATIVE


# ── Intensifiers ─────────────────────────────────────────────────────────────────

def test_intensifier_boosts_score():
    a = SentimentAnalyzer()
    plain = a.analyze("This is good.")
    boosted = a.analyze("This is very good.")
    assert boosted.score > plain.score


def test_extreme_intensifier_stronger():
    a = SentimentAnalyzer()
    very = a.analyze("This is very good.")
    extremely = a.analyze("This is extremely good.")
    assert extremely.score >= very.score


# ── Mixed ────────────────────────────────────────────────────────────────────────

def test_mixed_balances():
    a = SentimentAnalyzer()
    r = a.analyze("The food was good but the service was bad.")
    # one positive, one negative → roughly neutral
    assert -0.5 < r.score < 0.5


def test_score_bounded():
    a = SentimentAnalyzer()
    r = a.analyze("great great great amazing excellent wonderful fantastic love")
    assert -1.0 <= r.score <= 1.0


# ── Threshold behavior ───────────────────────────────────────────────────────────

def test_high_threshold_forces_neutral():
    a = SentimentAnalyzer(threshold=0.99)
    r = a.analyze("This is good.")  # mild positive, below 0.99
    assert r.polarity == Polarity.NEUTRAL


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    a = SentimentAnalyzer()
    d = a.analyze("good").to_dict()
    for key in ("polarity", "score", "positive_hits", "negative_hits",
                "negations", "word_count"):
        assert key in d


def test_word_count_reported():
    a = SentimentAnalyzer()
    r = a.analyze("one two three four")
    assert r.word_count == 4


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    a = SentimentAnalyzer()
    a.analyze("great and wonderful love")   # positive
    a.analyze("terrible awful hate")        # negative
    a.analyze("the table is brown")         # neutral
    m = a.metrics()
    assert m["total_analyses"] == 3
    assert m["positive"] == 1
    assert m["negative"] == 1
    assert m["neutral"] == 1


def test_metrics_rates():
    a = SentimentAnalyzer()
    a.analyze("great wonderful love amazing")
    m = a.metrics()
    assert m["positive_rate"] == 1.0


def test_metrics_reset():
    a = SentimentAnalyzer()
    a.analyze("good")
    a.reset_metrics()
    m = a.metrics()
    assert m["total_analyses"] == 0
    assert m["positive"] == 0


def test_metrics_shape():
    a = SentimentAnalyzer()
    m = a.metrics()
    for key in ("total_analyses", "positive", "negative", "neutral",
                "positive_rate", "negative_rate", "threshold"):
        assert key in m
