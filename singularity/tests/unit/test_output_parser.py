"""
Unit tests — Structured Output Parser (Fáze 44). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.output_parser import (
    OutputParser,
    ParseResult,
    _find_balanced_span,
    _repair_json,
    _try_json,
)


# ── Helpers ──────────────────────────────────────────────────────────────────────

def test_try_json_valid():
    ok, data = _try_json('{"a": 1}')
    assert ok and data == {"a": 1}


def test_try_json_invalid():
    ok, data = _try_json("not json")
    assert not ok and data is None


def test_repair_trailing_comma():
    assert _repair_json('{"a": 1,}') == '{"a": 1}'


def test_repair_smart_quotes():
    repaired = _repair_json('{“a”: “b”}')
    assert '"a"' in repaired and '"b"' in repaired


def test_repair_single_quotes():
    assert _repair_json("{'a': 'b'}") == '{"a": "b"}'


def test_find_balanced_object():
    assert _find_balanced_span('text {"a": 1} more') == '{"a": 1}'


def test_find_balanced_array():
    assert _find_balanced_span("see [1, 2, 3] here") == "[1, 2, 3]"


def test_find_balanced_nested():
    assert _find_balanced_span('x {"a": {"b": 1}} y') == '{"a": {"b": 1}}'


def test_find_balanced_ignores_braces_in_strings():
    assert _find_balanced_span('{"a": "}"}') == '{"a": "}"}'


def test_find_balanced_none():
    assert _find_balanced_span("no braces here") is None


# ── extract_json ─────────────────────────────────────────────────────────────────

def test_json_raw():
    p = OutputParser()
    r = p.extract_json('{"key": "value"}')
    assert r.success
    assert r.data == {"key": "value"}
    assert r.method == "raw"


def test_json_fenced():
    p = OutputParser()
    text = 'Here is the result:\n```json\n{"x": 1}\n```\nDone.'
    r = p.extract_json(text)
    assert r.success
    assert r.data == {"x": 1}
    assert r.method == "fenced"


def test_json_plain_fence():
    p = OutputParser()
    text = "```\n{\"y\": 2}\n```"
    r = p.extract_json(text)
    assert r.success
    assert r.data == {"y": 2}


def test_json_balanced_span_in_prose():
    p = OutputParser()
    text = 'The answer is {"result": 42} as computed.'
    r = p.extract_json(text)
    assert r.success
    assert r.data == {"result": 42}
    assert r.method == "balanced_span"


def test_json_repair_trailing_comma():
    p = OutputParser()
    r = p.extract_json('{"a": 1, "b": 2,}')
    assert r.success
    assert r.repaired is True
    assert r.data == {"a": 1, "b": 2}


def test_json_array():
    p = OutputParser()
    r = p.extract_json("[1, 2, 3]")
    assert r.success
    assert r.data == [1, 2, 3]


def test_json_failure():
    p = OutputParser()
    r = p.extract_json("there is no json here at all")
    assert not r.success
    assert r.error


def test_json_fenced_preferred_over_span():
    p = OutputParser()
    text = 'prose {"wrong": 1}\n```json\n{"right": 2}\n```'
    r = p.extract_json(text)
    # fenced candidate is tried first
    assert r.data == {"right": 2}


# ── extract_key_values ───────────────────────────────────────────────────────────

def test_key_values_basic():
    p = OutputParser()
    text = "Name: Alice\nAge: 30\nCity: Prague"
    r = p.extract_key_values(text)
    assert r.success
    assert r.data == {"Name": "Alice", "Age": "30", "City": "Prague"}


def test_key_values_equals_sign():
    p = OutputParser()
    r = p.extract_key_values("key = value")
    assert r.data == {"key": "value"}


def test_key_values_with_bullets():
    p = OutputParser()
    text = "- color: red\n- size: large"
    r = p.extract_key_values(text)
    assert r.data == {"color": "red", "size": "large"}


def test_key_values_none():
    p = OutputParser()
    r = p.extract_key_values("just prose without colons")
    assert not r.success
    assert r.data == {}


# ── extract_list ─────────────────────────────────────────────────────────────────

def test_list_dash_bullets():
    p = OutputParser()
    text = "- apple\n- banana\n- cherry"
    r = p.extract_list(text)
    assert r.success
    assert r.data == ["apple", "banana", "cherry"]


def test_list_numbered():
    p = OutputParser()
    text = "1. first\n2. second\n3. third"
    r = p.extract_list(text)
    assert r.data == ["first", "second", "third"]


def test_list_star_and_bullet():
    p = OutputParser()
    text = "* one\n• two"
    r = p.extract_list(text)
    assert r.data == ["one", "two"]


def test_list_none():
    p = OutputParser()
    r = p.extract_list("no list items here")
    assert not r.success
    assert r.data == []


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    p = OutputParser()
    d = p.extract_json('{"a":1}').to_dict()
    for key in ("success", "data", "method", "repaired", "error"):
        assert key in d


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_json_success():
    p = OutputParser()
    p.extract_json('{"a": 1}')
    m = p.metrics()
    assert m["total_parses"] == 1
    assert m["json_successes"] == 1
    assert m["success_rate"] == 1.0


def test_metrics_repair_counted():
    p = OutputParser()
    p.extract_json('{"a": 1,}')
    m = p.metrics()
    assert m["repaired"] == 1
    assert m["repair_rate"] == 1.0


def test_metrics_failure_counted():
    p = OutputParser()
    p.extract_json("nope")
    m = p.metrics()
    assert m["failures"] == 1
    assert m["success_rate"] == 0.0


def test_metrics_reset():
    p = OutputParser()
    p.extract_json('{"a": 1}')
    p.reset_metrics()
    m = p.metrics()
    assert m["total_parses"] == 0
    assert m["json_successes"] == 0


def test_metrics_shape():
    p = OutputParser()
    m = p.metrics()
    for key in ("total_parses", "json_successes", "repaired", "failures",
                "success_rate", "repair_rate"):
        assert key in m
