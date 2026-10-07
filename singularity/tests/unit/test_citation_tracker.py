"""
Unit tests — Citation Tracker (Fáze 35). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.citation_tracker import (
    CitationReport,
    CitationTracker,
    Source,
    _jaccard,
    _split_sentences,
    _tokens,
)


# ── Helpers ──────────────────────────────────────────────────────────────────────

def test_tokens_drops_stopwords():
    assert _tokens("the cat is on a mat") == {"cat", "mat"}


def test_tokens_lowercases():
    assert "paris" in _tokens("PARIS is great")


def test_tokens_empty():
    assert _tokens("") == set()


def test_split_sentences_basic():
    s = _split_sentences("Hello world. How are you? I am fine!")
    assert s == ["Hello world.", "How are you?", "I am fine!"]


def test_split_sentences_empty():
    assert _split_sentences("") == []


def test_jaccard_identical():
    assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint():
    assert _jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_empty():
    assert _jaccard(set(), {"a"}) == 0.0


def test_jaccard_partial():
    # {a,b,c} vs {b,c,d}: inter 2, union 4 → 0.5
    assert _jaccard({"a", "b", "c"}, {"b", "c", "d"}) == 0.5


# ── Construction ─────────────────────────────────────────────────────────────────

def test_invalid_threshold_raises():
    with pytest.raises(ValueError):
        CitationTracker(threshold=0.0)


def test_invalid_max_citations_raises():
    with pytest.raises(ValueError):
        CitationTracker(max_citations=0)


# ── Basic grounding ──────────────────────────────────────────────────────────────

def test_supported_sentence_gets_citation():
    tracker = CitationTracker(threshold=0.2)
    sources = [{"source_id": "doc1", "text": "The capital of France is Paris."}]
    report = tracker.track("The capital of France is Paris.", sources)
    assert report.total_sentences == 1
    assert report.supported_sentences == 1
    assert report.sentences[0].supported is True
    assert report.sentences[0].citations[0]["source_id"] == "doc1"


def test_unsupported_sentence_flagged():
    tracker = CitationTracker(threshold=0.3)
    sources = [{"source_id": "doc1", "text": "The capital of France is Paris."}]
    report = tracker.track("Quantum entanglement links distant particles.", sources)
    assert report.unsupported_sentences == 1
    assert report.sentences[0].supported is False
    assert report.sentences[0].citations == []


def test_mixed_grounding_score():
    tracker = CitationTracker(threshold=0.25)
    sources = [{"source_id": "doc1", "text": "Photosynthesis converts sunlight into energy in plants."}]
    response = "Photosynthesis converts sunlight into energy in plants. Dolphins are mammals living in oceans."
    report = tracker.track(response, sources)
    assert report.total_sentences == 2
    assert report.supported_sentences == 1
    assert report.grounding_score == 0.5


def test_used_sources_collected():
    tracker = CitationTracker(threshold=0.2)
    sources = [
        {"source_id": "a", "text": "Cats are small domesticated felines kept as pets."},
        {"source_id": "b", "text": "Dogs are loyal domesticated canines kept as pets."},
    ]
    response = "Cats are small domesticated felines. Dogs are loyal domesticated canines."
    report = tracker.track(response, sources)
    assert set(report.used_sources) == {"a", "b"}


# ── Multiple citations & ranking ─────────────────────────────────────────────────

def test_max_citations_limits_count():
    tracker = CitationTracker(threshold=0.05, max_citations=2)
    sources = [
        {"source_id": "s1", "text": "alpha beta gamma delta"},
        {"source_id": "s2", "text": "alpha beta gamma epsilon"},
        {"source_id": "s3", "text": "alpha beta zeta eta"},
    ]
    report = tracker.track("alpha beta gamma delta epsilon", sources)
    assert len(report.sentences[0].citations) <= 2


def test_citations_sorted_by_score_desc():
    tracker = CitationTracker(threshold=0.05, max_citations=3)
    sources = [
        {"source_id": "low", "text": "alpha something unrelated entirely"},
        {"source_id": "high", "text": "alpha beta gamma delta"},
    ]
    report = tracker.track("alpha beta gamma delta", sources)
    cits = report.sentences[0].citations
    assert cits[0]["source_id"] == "high"
    assert cits[0]["score"] >= cits[-1]["score"]


def test_best_score_recorded_when_unsupported():
    tracker = CitationTracker(threshold=0.9)
    sources = [{"source_id": "d", "text": "alpha beta gamma"}]
    report = tracker.track("alpha beta delta epsilon", sources)
    # not supported at 0.9, but best_score reflects actual overlap > 0
    assert report.sentences[0].supported is False
    assert report.sentences[0].best_score > 0.0


# ── Source normalization ─────────────────────────────────────────────────────────

def test_source_dataclass_input():
    tracker = CitationTracker(threshold=0.2)
    report = tracker.track(
        "Paris is the capital.",
        [Source(source_id="x", text="Paris is the capital of France.")],
    )
    assert report.sentences[0].citations[0]["source_id"] == "x"


def test_source_dict_id_alias():
    tracker = CitationTracker(threshold=0.2)
    report = tracker.track(
        "Paris is the capital.",
        [{"id": "aliased", "text": "Paris is the capital of France."}],
    )
    assert report.sentences[0].citations[0]["source_id"] == "aliased"


def test_source_plain_string():
    tracker = CitationTracker(threshold=0.2)
    report = tracker.track("Paris is the capital.", ["Paris is the capital of France."])
    assert report.sentences[0].supported is True
    assert report.sentences[0].citations[0]["source_id"] == "src0"


# ── Edge cases ──────────────────────────────────────────────────────────────────

def test_empty_response():
    tracker = CitationTracker()
    report = tracker.track("", [{"source_id": "d", "text": "anything"}])
    assert report.total_sentences == 0
    assert report.grounding_score == 0.0


def test_no_sources_all_unsupported():
    tracker = CitationTracker()
    report = tracker.track("Some claim here. Another claim.", [])
    assert report.supported_sentences == 0
    assert report.unsupported_sentences == 2


# ── Report shape ─────────────────────────────────────────────────────────────────

def test_report_to_dict_shape():
    tracker = CitationTracker(threshold=0.2)
    report = tracker.track("Paris is the capital.",
                           [{"source_id": "d", "text": "Paris is the capital of France."}])
    d = report.to_dict()
    for key in ("sentences", "total_sentences", "supported_sentences",
                "unsupported_sentences", "grounding_score", "used_sources"):
        assert key in d
    for key in ("sentence", "supported", "best_score", "citations"):
        assert key in d["sentences"][0]


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    tracker = CitationTracker(threshold=0.2)
    src = [{"source_id": "d", "text": "Paris is the capital of France."}]
    tracker.track("Paris is the capital. Unrelated nonsense words here.", src)
    m = tracker.metrics()
    assert m["total_reports"] == 1
    assert m["total_sentences"] == 2
    assert m["total_supported"] >= 1
    assert 0.0 <= m["overall_grounding"] <= 1.0


def test_metrics_reset():
    tracker = CitationTracker(threshold=0.2)
    tracker.track("Paris is the capital.",
                  [{"source_id": "d", "text": "Paris is the capital of France."}])
    tracker.reset_metrics()
    m = tracker.metrics()
    assert m["total_reports"] == 0
    assert m["total_sentences"] == 0


def test_metrics_shape():
    tracker = CitationTracker()
    m = tracker.metrics()
    for key in ("total_reports", "total_sentences", "total_supported",
                "overall_grounding", "threshold", "max_citations"):
        assert key in m
