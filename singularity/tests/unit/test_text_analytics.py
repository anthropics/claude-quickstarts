"""
Unit tests — Text Analytics Suite (Fáze 50). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.text_analytics import AnalysisReport, TextAnalyticsSuite


_SAMPLE = (
    "The new product is absolutely amazing and I love it. "
    "It costs $50 and launches on 2024-06-15. "
    "Barack Obama praised the machine learning features."
)


# ── Full analysis ────────────────────────────────────────────────────────────────

def test_full_report_has_all_sections():
    s = TextAnalyticsSuite()
    r = s.analyze(_SAMPLE)
    assert set(r.sections) == {"language", "sentiment", "readability",
                               "keywords", "entities", "summary"}
    assert r.language is not None
    assert r.sentiment is not None
    assert r.readability is not None
    assert r.keywords is not None
    assert r.entities is not None
    assert r.summary is not None


def test_char_and_word_counts():
    s = TextAnalyticsSuite()
    r = s.analyze("hello world foo")
    assert r.word_count == 3
    assert r.char_count == len("hello world foo")


# ── Section content sanity ───────────────────────────────────────────────────────

def test_sentiment_positive_detected():
    s = TextAnalyticsSuite()
    r = s.analyze("This is wonderful and great, I love it.")
    assert r.sentiment["polarity"] == "positive"


def test_language_detected_english():
    s = TextAnalyticsSuite()
    r = s.analyze("The cat is on the table and that is what we have here.")
    assert r.language["language"] == "en"


def test_entities_extracted():
    s = TextAnalyticsSuite()
    r = s.analyze("Pay $50 by 2024-06-15.")
    types = {e["type"] for e in r.entities}
    assert "MONEY" in types
    assert "DATE" in types


def test_keywords_present():
    s = TextAnalyticsSuite()
    r = s.analyze("Machine learning models improve with training data and tuning.")
    assert len(r.keywords) > 0


def test_readability_computed():
    s = TextAnalyticsSuite()
    r = s.analyze("The cat sat on the mat. The dog ran fast.")
    assert "flesch_reading_ease" in r.readability


# ── Section toggles ──────────────────────────────────────────────────────────────

def test_disable_sections():
    s = TextAnalyticsSuite()
    r = s.analyze(_SAMPLE, sentiment=False, entities=False, summary=False)
    assert r.sentiment is None
    assert r.entities is None
    assert r.summary is None
    assert r.language is not None
    assert "sentiment" not in r.sections


def test_only_one_section():
    s = TextAnalyticsSuite()
    r = s.analyze(_SAMPLE, language=False, sentiment=True, readability=False,
                  keywords=False, entities=False, summary=False)
    assert r.sections == ["sentiment"]


def test_top_keywords_limit():
    s = TextAnalyticsSuite()
    r = s.analyze(
        "alpha beta. gamma delta. epsilon zeta. eta theta. iota kappa. lam mu.",
        top_keywords=2,
    )
    assert len(r.keywords) <= 2


# ── Empty text ───────────────────────────────────────────────────────────────────

def test_empty_text():
    s = TextAnalyticsSuite()
    r = s.analyze("")
    assert r.char_count == 0
    assert r.word_count == 0
    # summary section present but empty
    assert r.summary["summary"] == ""


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_report_to_dict_shape():
    s = TextAnalyticsSuite()
    d = s.analyze(_SAMPLE).to_dict()
    for key in ("char_count", "word_count", "language", "sentiment",
                "readability", "keywords", "entities", "summary", "sections"):
        assert key in d


# ── Injectable analyzers ─────────────────────────────────────────────────────────

def test_injected_analyzers_used():
    from core.sentiment import SentimentAnalyzer
    custom = SentimentAnalyzer(threshold=0.99)  # very strict
    s = TextAnalyticsSuite(sentiment_analyzer=custom)
    r = s.analyze("This is good.")  # mild → neutral under strict threshold
    assert r.sentiment["polarity"] == "neutral"


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    s = TextAnalyticsSuite()
    s.analyze(_SAMPLE)
    s.analyze(_SAMPLE, sentiment=False)
    m = s.metrics()
    assert m["total_analyses"] == 2
    assert m["section_counts"]["language"] == 2
    assert m["section_counts"]["sentiment"] == 1


def test_metrics_reset():
    s = TextAnalyticsSuite()
    s.analyze(_SAMPLE)
    s.reset_metrics()
    m = s.metrics()
    assert m["total_analyses"] == 0
    assert m["section_counts"] == {}


def test_metrics_shape():
    s = TextAnalyticsSuite()
    m = s.metrics()
    for key in ("total_analyses", "section_counts"):
        assert key in m
