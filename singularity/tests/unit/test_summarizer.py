"""
Unit tests — Extractive Summarizer (Fáze 42). Fully offline, deterministic.
"""

from __future__ import annotations

import math
import pytest

from core.summarizer import (
    ExtractiveSummarizer,
    SummaryResult,
    _content_words,
    _split_sentences,
)


# ── Helpers ──────────────────────────────────────────────────────────────────────

def test_split_sentences():
    assert _split_sentences("One. Two! Three?") == ["One.", "Two!", "Three?"]


def test_split_sentences_empty():
    assert _split_sentences("") == []


def test_content_words_filters_stopwords():
    assert _content_words("the cat and the dog") == ["cat", "dog"]


# ── Construction ─────────────────────────────────────────────────────────────────

def test_invalid_ratio_zero_raises():
    with pytest.raises(ValueError):
        ExtractiveSummarizer(ratio=0.0)


def test_invalid_ratio_above_one_raises():
    with pytest.raises(ValueError):
        ExtractiveSummarizer(ratio=1.5)


def test_invalid_max_sentences_raises():
    with pytest.raises(ValueError):
        ExtractiveSummarizer(max_sentences=0)


# ── Empty input ──────────────────────────────────────────────────────────────────

def test_empty_text():
    s = ExtractiveSummarizer()
    r = s.summarize("")
    assert r.summary == ""
    assert r.original_sentences == 0
    assert r.compression_ratio == 0.0


# ── Basic summarization ──────────────────────────────────────────────────────────

def test_single_sentence_returns_itself():
    s = ExtractiveSummarizer(ratio=0.5)
    r = s.summarize("Only one sentence here.")
    assert r.summary == "Only one sentence here."
    assert r.summary_sentences == 1


def test_ratio_selects_fraction():
    s = ExtractiveSummarizer(ratio=0.5)
    text = "Aaa aaa. Bbb bbb. Ccc ccc. Ddd ddd."  # 4 sentences
    r = s.summarize(text)
    # ceil(0.5*4) = 2
    assert r.summary_sentences == 2


def test_max_sentences_caps():
    s = ExtractiveSummarizer(ratio=1.0, max_sentences=2)
    text = "One here. Two here. Three here. Four here."
    r = s.summarize(text)
    assert r.summary_sentences == 2


def test_selected_indices_in_order():
    s = ExtractiveSummarizer(ratio=0.6)
    text = "First sentence alpha. Second sentence beta. Third sentence gamma."
    r = s.summarize(text)
    assert r.selected_indices == sorted(r.selected_indices)


def test_high_frequency_sentence_selected():
    s = ExtractiveSummarizer(ratio=0.34)  # pick ~1 of 3
    # "machine learning" repeated → that sentence should win
    text = (
        "Machine learning models learn from machine learning data. "
        "The weather today is sunny and warm. "
        "Cats enjoy sleeping in the afternoon."
    )
    r = s.summarize(text)
    assert "machine learning" in r.summary.lower()


# ── Keywords ─────────────────────────────────────────────────────────────────────

def test_keywords_extracted():
    s = ExtractiveSummarizer()
    text = "Python python python is great. Coding coding is fun."
    r = s.summarize(text, top_keywords=2)
    assert "python" in r.keywords


def test_keywords_respect_limit():
    s = ExtractiveSummarizer()
    r = s.summarize("alpha beta gamma delta epsilon zeta.", top_keywords=3)
    assert len(r.keywords) <= 3


# ── Per-call overrides ───────────────────────────────────────────────────────────

def test_ratio_override():
    s = ExtractiveSummarizer(ratio=0.9)
    text = "A one. B two. C three. D four. E five."
    r = s.summarize(text, ratio=0.2)  # ceil(0.2*5)=1
    assert r.summary_sentences == 1


def test_max_sentences_override():
    s = ExtractiveSummarizer(ratio=1.0)
    text = "A one. B two. C three. D four."
    r = s.summarize(text, max_sentences=1)
    assert r.summary_sentences == 1


def test_invalid_ratio_override_raises():
    s = ExtractiveSummarizer()
    with pytest.raises(ValueError):
        s.summarize("Some text here.", ratio=2.0)


# ── Compression ratio ────────────────────────────────────────────────────────────

def test_compression_ratio_computed():
    s = ExtractiveSummarizer(ratio=0.5)
    text = "One. Two. Three. Four."
    r = s.summarize(text)
    assert r.compression_ratio == pytest.approx(r.summary_sentences / 4)


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    s = ExtractiveSummarizer()
    r = s.summarize("Alpha beta. Gamma delta.")
    d = r.to_dict()
    for key in ("summary", "selected_indices", "original_sentences",
                "summary_sentences", "compression_ratio", "keywords"):
        assert key in d


# ── Edge: sentences with only stopwords ──────────────────────────────────────────

def test_all_stopword_sentences():
    s = ExtractiveSummarizer(ratio=0.5)
    # no content words anywhere → still returns at least one sentence
    r = s.summarize("the the the. and and and.")
    assert r.summary_sentences >= 1


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    s = ExtractiveSummarizer(ratio=0.5)
    s.summarize("One. Two. Three. Four.")   # 4 in, 2 out
    m = s.metrics()
    assert m["total_summaries"] == 1
    assert m["total_input_sentences"] == 4
    assert m["total_output_sentences"] == 2


def test_metrics_overall_compression():
    s = ExtractiveSummarizer(ratio=0.5)
    s.summarize("A. B. C. D.")
    m = s.metrics()
    assert 0.0 < m["overall_compression"] <= 1.0


def test_metrics_reset():
    s = ExtractiveSummarizer()
    s.summarize("A. B.")
    s.reset_metrics()
    m = s.metrics()
    assert m["total_summaries"] == 0
    assert m["total_input_sentences"] == 0


def test_metrics_shape():
    s = ExtractiveSummarizer()
    m = s.metrics()
    for key in ("total_summaries", "total_input_sentences",
                "total_output_sentences", "overall_compression",
                "ratio", "max_sentences"):
        assert key in m
