"""
Unit tests — Keyword Extractor (Fáze 46). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.keyword_extractor import (
    Keyword,
    KeywordExtractor,
    KeywordResult,
)


# ── Construction ─────────────────────────────────────────────────────────────────

def test_invalid_max_phrase_words_raises():
    with pytest.raises(ValueError):
        KeywordExtractor(max_phrase_words=0)


def test_invalid_min_word_length_raises():
    with pytest.raises(ValueError):
        KeywordExtractor(min_word_length=0)


def test_invalid_top_k_raises():
    e = KeywordExtractor()
    with pytest.raises(ValueError):
        e.extract("some text here", top_k=0)


# ── Empty / trivial ──────────────────────────────────────────────────────────────

def test_empty_text():
    e = KeywordExtractor()
    r = e.extract("")
    assert r.keywords == []
    assert r.candidate_count == 0


def test_all_stopwords():
    e = KeywordExtractor()
    r = e.extract("the and of to in on at")
    assert r.keywords == []


# ── Basic extraction ─────────────────────────────────────────────────────────────

def test_extracts_keyphrase():
    e = KeywordExtractor()
    text = "Machine learning algorithms improve with more training data."
    r = e.extract(text)
    phrases = [k.phrase for k in r.keywords]
    assert any("machine learning" in p for p in phrases)


def test_stopwords_split_phrases():
    e = KeywordExtractor()
    # "the cat" → "cat"; "on the mat" → "mat" (the/on are stopwords)
    r = e.extract("The cat sat on the mat.")
    phrases = [k.phrase for k in r.keywords]
    assert "cat sat" in phrases or "cat" in phrases
    assert "mat" in phrases


def test_punctuation_breaks_phrases():
    e = KeywordExtractor()
    r = e.extract("apples, oranges, bananas")
    phrases = [k.phrase for k in r.keywords]
    assert "apples" in phrases
    assert "oranges" in phrases
    assert "bananas" in phrases


def test_top_k_limits():
    e = KeywordExtractor()
    text = "alpha beta. gamma delta. epsilon zeta. eta theta. iota kappa."
    r = e.extract(text, top_k=2)
    assert len(r.keywords) == 2


def test_keywords_sorted_by_score_desc():
    e = KeywordExtractor()
    text = "data science. data science methods. random unrelated word."
    r = e.extract(text)
    scores = [k.score for k in r.keywords]
    assert scores == sorted(scores, reverse=True)


def test_longer_phrase_scores_higher():
    e = KeywordExtractor()
    # multi-word phrase accumulates more word-scores than a single word
    text = "deep neural network architecture. cat."
    r = e.extract(text)
    top = r.keywords[0]
    assert len(top.phrase.split()) > 1


# ── max_phrase_words ─────────────────────────────────────────────────────────────

def test_max_phrase_words_drops_long():
    e = KeywordExtractor(max_phrase_words=2)
    # "one two three four five" has no stopwords → single 5-word phrase, dropped
    r = e.extract("one two three four five")
    assert r.candidate_count == 0


def test_max_phrase_words_keeps_short():
    e = KeywordExtractor(max_phrase_words=3)
    r = e.extract("quick brown fox")
    assert r.candidate_count == 1


# ── min_word_length ──────────────────────────────────────────────────────────────

def test_min_word_length_filters():
    e = KeywordExtractor(min_word_length=4)
    # "ai is ml" → all short words filtered
    r = e.extract("ai is ml")
    assert r.keywords == []


# ── Custom stopwords ─────────────────────────────────────────────────────────────

def test_custom_stopwords():
    e = KeywordExtractor(stopwords=frozenset({"foo"}))
    # "foo" splits; "the" is NOT a stopword now so stays
    r = e.extract("the bar foo the baz")
    phrases = [k.phrase for k in r.keywords]
    assert any("the bar" in p for p in phrases)


# ── Dedup ────────────────────────────────────────────────────────────────────────

def test_duplicate_phrases_deduped():
    e = KeywordExtractor()
    r = e.extract("neural network. neural network. neural network.")
    phrases = [k.phrase for k in r.keywords]
    assert phrases.count("neural network") == 1


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    e = KeywordExtractor()
    r = e.extract("machine learning models")
    d = r.to_dict()
    for key in ("keywords", "candidate_count", "word_count"):
        assert key in d
    if d["keywords"]:
        for key in ("phrase", "score"):
            assert key in d["keywords"][0]


def test_word_count_reported():
    e = KeywordExtractor()
    r = e.extract("one two three")
    assert r.word_count == 3


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    e = KeywordExtractor()
    e.extract("machine learning models")
    e.extract("data science methods")
    m = e.metrics()
    assert m["total_extractions"] == 2
    assert m["total_keywords"] >= 2


def test_metrics_avg():
    e = KeywordExtractor()
    e.extract("alpha beta gamma")  # one phrase
    m = e.metrics()
    assert m["avg_keywords"] >= 1.0


def test_metrics_reset():
    e = KeywordExtractor()
    e.extract("some keywords here")
    e.reset_metrics()
    m = e.metrics()
    assert m["total_extractions"] == 0
    assert m["total_keywords"] == 0


def test_metrics_shape():
    e = KeywordExtractor()
    m = e.metrics()
    for key in ("total_extractions", "total_keywords", "avg_keywords",
                "max_phrase_words", "min_word_length"):
        assert key in m
