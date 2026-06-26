"""
Unit tests — Intent Classifier (Fáze 34). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.intent_classifier import (
    IntentClassifier,
    IntentDefinition,
    IntentResult,
)


# ── Construction ─────────────────────────────────────────────────────────────────

def test_builtins_loaded():
    c = IntentClassifier()
    names = c.list_intents()
    for expected in ("code", "math", "creative", "factual", "summarization", "translation"):
        assert expected in names


def test_no_builtins():
    c = IntentClassifier(load_builtins=False)
    assert c.list_intents() == []


def test_invalid_min_confidence_raises():
    with pytest.raises(ValueError):
        IntentClassifier(min_confidence=1.5)


def test_custom_intents_added():
    custom = IntentDefinition(name="legal", keywords=["contract", "clause"])
    c = IntentClassifier([custom], load_builtins=False)
    assert c.list_intents() == ["legal"]


# ── Classification: built-ins ────────────────────────────────────────────────────

def test_classify_code():
    c = IntentClassifier()
    r = c.classify("I have a bug in my python function, can you debug it?")
    assert r.intent == "code"
    assert r.confidence > 0
    assert r.provider_hint == "claude"


def test_classify_code_with_fence():
    c = IntentClassifier()
    r = c.classify("```\ndef foo():\n    pass\n```")
    assert r.intent == "code"


def test_classify_math():
    c = IntentClassifier()
    r = c.classify("Please calculate the derivative and solve the equation 3*4=12")
    assert r.intent == "math"


def test_classify_creative():
    c = IntentClassifier()
    r = c.classify("Write me a poem about the ocean")
    assert r.intent == "creative"
    assert r.provider_hint == "gemini"


def test_classify_factual():
    c = IntentClassifier()
    r = c.classify("What is the capital of France?")
    assert r.intent == "factual"


def test_classify_summarization():
    c = IntentClassifier()
    r = c.classify("Can you summarize this article and give key points?")
    assert r.intent == "summarization"


def test_classify_translation():
    c = IntentClassifier()
    r = c.classify("Translate this sentence into Spanish")
    assert r.intent == "translation"


# ── Fallback ─────────────────────────────────────────────────────────────────────

def test_no_match_falls_back_to_general():
    c = IntentClassifier()
    r = c.classify("zzzzz qqqq")
    assert r.intent == "general"
    assert r.confidence == 0.0
    assert r.provider_hint is None


def test_empty_query_falls_back():
    c = IntentClassifier()
    r = c.classify("")
    assert r.intent == "general"


def test_min_confidence_threshold_fallback():
    # high threshold → ambiguous query falls back even with a match
    c = IntentClassifier(min_confidence=0.99)
    r = c.classify("what is a function bug")  # matches both code & factual
    # winner confidence below 0.99 → fallback
    assert r.intent == "general"
    assert r.scores  # scores still reported


# ── Scoring details ──────────────────────────────────────────────────────────────

def test_pattern_weighs_more_than_keyword():
    c = IntentClassifier(load_builtins=False)
    c.register(IntentDefinition(name="kwonly", keywords=["alpha"]))
    c.register(IntentDefinition(name="patonly", patterns=[r"alpha"]))
    r = c.classify("alpha")
    # both match "alpha"; pattern weight (2.0) beats keyword (1.0)
    assert r.intent == "patonly"


def test_confidence_is_share_of_total():
    c = IntentClassifier(load_builtins=False)
    c.register(IntentDefinition(name="a", keywords=["foo"]))
    c.register(IntentDefinition(name="b", keywords=["bar"]))
    r = c.classify("foo bar foo")  # a: 2 (foo×2), b: 1 (bar) → conf a = 2/3
    assert r.intent == "a"
    assert r.confidence == pytest.approx(2 / 3, abs=1e-3)


def test_matched_signals_reported():
    c = IntentClassifier(load_builtins=False)
    c.register(IntentDefinition(name="x", keywords=["hello"], patterns=[r"\d+"]))
    r = c.classify("hello 123")
    assert any(s.startswith("kw:hello") for s in r.matched_signals)
    assert any(s.startswith("re:") for s in r.matched_signals)


def test_intent_weight_multiplier():
    c = IntentClassifier(load_builtins=False)
    c.register(IntentDefinition(name="low", keywords=["term"], weight=1.0))
    c.register(IntentDefinition(name="high", keywords=["term"], weight=3.0))
    r = c.classify("term")
    assert r.intent == "high"


# ── Register / unregister ────────────────────────────────────────────────────────

def test_register_then_classify():
    c = IntentClassifier(load_builtins=False)
    c.register(IntentDefinition(name="weather", keywords=["forecast", "temperature"]))
    r = c.classify("what is the forecast today")
    assert r.intent == "weather"


def test_unregister_removes_intent():
    c = IntentClassifier()
    assert c.unregister("code") is True
    assert "code" not in c.list_intents()


def test_unregister_missing_returns_false():
    c = IntentClassifier()
    assert c.unregister("nonexistent") is False


def test_bad_regex_pattern_ignored():
    c = IntentClassifier(load_builtins=False)
    c.register(IntentDefinition(name="broken", keywords=["safe"], patterns=[r"([unclosed"]))
    # should not raise; keyword still matches
    r = c.classify("this is safe")
    assert r.intent == "broken"


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    c = IntentClassifier()
    r = c.classify("write a story")
    d = r.to_dict()
    for key in ("intent", "confidence", "provider_hint", "scores", "matched_signals"):
        assert key in d


def test_definition_to_dict_shape():
    d = IntentDefinition(name="x", keywords=["a"], provider_hint="claude").to_dict()
    for key in ("name", "keywords", "patterns", "provider_hint", "weight"):
        assert key in d


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_counts_by_intent():
    c = IntentClassifier()
    c.classify("write a poem")        # creative
    c.classify("what is python")      # factual or code
    c.classify("zzz")                 # fallback general
    m = c.metrics()
    assert m["total_classifications"] == 3
    assert m["fallbacks"] == 1
    assert sum(m["by_intent"].values()) == 3


def test_metrics_fallback_rate():
    c = IntentClassifier()
    c.classify("zzz")
    c.classify("qqq")
    m = c.metrics()
    assert m["fallback_rate"] == 1.0


def test_metrics_reset():
    c = IntentClassifier()
    c.classify("write a poem")
    c.reset_metrics()
    m = c.metrics()
    assert m["total_classifications"] == 0
    assert m["by_intent"] == {}


def test_metrics_shape():
    c = IntentClassifier()
    m = c.metrics()
    for key in ("total_classifications", "by_intent", "fallbacks",
                "fallback_rate", "intent_count"):
        assert key in m
