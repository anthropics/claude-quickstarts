"""
Unit tests — Language Detector (Fáze 43). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.language_detector import (
    LanguageDetector,
    LanguageResult,
    _tokenize,
)


# ── Tokenizer ────────────────────────────────────────────────────────────────────

def test_tokenize_lowercases():
    assert _tokenize("Hello World") == ["hello", "world"]


def test_tokenize_strips_digits_punct():
    assert _tokenize("abc, 123 def!") == ["abc", "def"]


def test_tokenize_unicode_letters():
    # accented letters preserved
    toks = _tokenize("že příliš")
    assert "že" in toks and "příliš" in toks


# ── Construction ─────────────────────────────────────────────────────────────────

def test_invalid_min_confidence_raises():
    with pytest.raises(ValueError):
        LanguageDetector(min_confidence=2.0)


def test_default_languages_present():
    d = LanguageDetector()
    langs = d.list_languages()
    for lang in ("en", "cs", "de", "fr", "es"):
        assert lang in langs


# ── Detection: built-in languages ────────────────────────────────────────────────

def test_detect_english():
    d = LanguageDetector()
    r = d.detect("The cat is on the table and that is what we have to do.")
    assert r.language == "en"
    assert r.confidence > 0


def test_detect_czech():
    d = LanguageDetector()
    r = d.detect("To je velmi důležité a já se na to dívám podle toho co vím.")
    assert r.language == "cs"


def test_detect_german():
    d = LanguageDetector()
    r = d.detect("Der Hund und die Katze sind in dem Haus mit der Familie.")
    assert r.language == "de"


def test_detect_french():
    d = LanguageDetector()
    r = d.detect("Le chat est sur la table et il ne veut pas se lever pour nous.")
    assert r.language == "fr"


def test_detect_spanish():
    d = LanguageDetector()
    r = d.detect("El gato que está en la casa y los perros no son para mí pero sí.")
    assert r.language == "es"


# ── Fallback ─────────────────────────────────────────────────────────────────────

def test_empty_text_unknown():
    d = LanguageDetector()
    r = d.detect("")
    assert r.language == "unknown"
    assert r.confidence == 0.0


def test_no_stopword_hits_unknown():
    d = LanguageDetector()
    r = d.detect("xyzzy qwerty zzzz")
    assert r.language == "unknown"
    assert r.word_count == 3


def test_min_confidence_high_forces_unknown():
    d = LanguageDetector(min_confidence=1.0)
    # mixed text won't reach 1.0 confidence
    r = d.detect("the der le la el")  # one stopword from several languages
    assert r.language == "unknown"
    assert r.scores  # scores still reported


# ── Scores & fields ──────────────────────────────────────────────────────────────

def test_scores_sum_to_one_when_hits():
    d = LanguageDetector()
    r = d.detect("the cat is on the table")
    assert r.scores
    assert sum(r.scores.values()) == pytest.approx(1.0, abs=1e-3)


def test_matched_stopwords_reported():
    d = LanguageDetector()
    r = d.detect("the the the cat")
    assert r.matched_stopwords >= 3
    assert r.word_count == 4


# ── Custom profile ───────────────────────────────────────────────────────────────

def test_register_custom_profile():
    d = LanguageDetector(profiles={}, min_confidence=0.0)
    d.register_profile("xx", ["foo", "bar", "baz"])
    r = d.detect("foo bar something foo")
    assert r.language == "xx"


def test_register_overrides_existing():
    d = LanguageDetector()
    d.register_profile("en", ["customword"])
    r = d.detect("customword customword")
    assert r.language == "en"


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    d = LanguageDetector()
    r = d.detect("the cat")
    dd = r.to_dict()
    for key in ("language", "confidence", "scores", "word_count", "matched_stopwords"):
        assert key in dd


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    d = LanguageDetector()
    d.detect("the cat is on the table")  # en
    d.detect("xyzzy qwerty")             # unknown
    m = d.metrics()
    assert m["total_detections"] == 2
    assert m["unknowns"] == 1
    assert m["unknown_rate"] == 0.5
    assert m["by_language"].get("en", 0) == 1


def test_metrics_reset():
    d = LanguageDetector()
    d.detect("the cat is here")
    d.reset_metrics()
    m = d.metrics()
    assert m["total_detections"] == 0
    assert m["by_language"] == {}


def test_metrics_shape():
    d = LanguageDetector()
    m = d.metrics()
    for key in ("total_detections", "by_language", "unknowns",
                "unknown_rate", "language_count"):
        assert key in m
