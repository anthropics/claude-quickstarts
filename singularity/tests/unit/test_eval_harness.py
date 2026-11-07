"""
Unit tests — Eval Harness (Fáze 67). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.eval_harness import (
    EvalHarness,
    contains,
    exact_match,
    jaccard,
    numeric_close,
)


# ── Scorers ──────────────────────────────────────────────────────────────────────

def test_exact_match():
    assert exact_match("a", "a") == 1.0
    assert exact_match("a", "b") == 0.0


def test_contains():
    assert contains("cat", "the cat sat") == 1.0
    assert contains("dog", "the cat sat") == 0.0


def test_jaccard():
    assert jaccard("the quick fox", "the quick fox") == 1.0
    assert jaccard("a b c", "b c d") == 0.5
    assert jaccard("", "") == 1.0
    assert jaccard("x", "") == 0.0


def test_numeric_close():
    s = numeric_close(tolerance=0.1)
    assert s(1.0, 1.05) == 1.0
    assert s(1.0, 2.0) == 0.0
    assert s("nan-ish", "x") == 0.0


# ── Case management ──────────────────────────────────────────────────────────────

def test_add_case():
    h = EvalHarness()
    h.add_case("c1", input="q", expected="a")
    assert h.case_count == 1


def test_add_case_requires_name():
    h = EvalHarness()
    with pytest.raises(ValueError):
        h.add_case("", input="q", expected="a")


def test_add_cases_bulk():
    h = EvalHarness()
    n = h.add_cases([
        {"name": "a", "input": 1, "expected": 1},
        {"name": "b", "input": 2, "expected": 2, "tag": "x"},
    ])
    assert n == 2
    assert h.case_count == 2


def test_clear_cases():
    h = EvalHarness()
    h.add_case("c", input=1, expected=1)
    h.clear_cases()
    assert h.case_count == 0


# ── Run / gate ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_pass_gate_passes():
    h = EvalHarness()
    h.add_case("echo1", input="x", expected="x")
    h.add_case("echo2", input="y", expected="y")
    report = await h.run(lambda inp: inp, threshold=0.8)
    assert report.total == 2
    assert report.passed == 2
    assert report.mean_score == 1.0
    assert report.gate_passed is True


@pytest.mark.asyncio
async def test_gate_fails_below_threshold():
    h = EvalHarness()
    h.add_case("ok", input="x", expected="x")
    h.add_case("bad", input="x", expected="different")
    # predictor echoes input → "ok" passes, "bad" fails → mean 0.5 < 0.8
    report = await h.run(lambda inp: inp, threshold=0.8)
    assert report.mean_score == 0.5
    assert report.gate_passed is False
    assert report.failed == 1


@pytest.mark.asyncio
async def test_partial_credit_scorer():
    h = EvalHarness()
    h.add_case("c", input="q", expected="the quick brown fox")
    # actual shares 2/4 tokens → jaccard 0.5; pass_score default 1.0 → not passed
    report = await h.run(lambda inp: "the quick", scorer=jaccard,
                         threshold=0.4, pass_score=1.0)
    assert 0.0 < report.mean_score < 1.0
    assert report.gate_passed is True  # mean >= 0.4


@pytest.mark.asyncio
async def test_async_predict_fn():
    h = EvalHarness()
    h.add_case("c", input=21, expected=42)

    async def _double(x):
        return x * 2

    report = await h.run(_double)
    assert report.passed == 1


@pytest.mark.asyncio
async def test_predict_exception_is_failure():
    h = EvalHarness()
    h.add_case("boom", input="x", expected="x")

    def _boom(_):
        raise RuntimeError("model down")

    report = await h.run(_boom, threshold=0.5)
    assert report.passed == 0
    assert report.gate_passed is False
    assert "model down" in report.cases[0].error


@pytest.mark.asyncio
async def test_pass_score_threshold_per_case():
    h = EvalHarness()
    h.add_case("c", input="q", expected="alpha beta gamma")
    # jaccard 2/3 ≈ 0.667; pass_score 0.6 → passes
    report = await h.run(lambda inp: "alpha beta", scorer=jaccard,
                         threshold=0.5, pass_score=0.6)
    assert report.passed == 1


@pytest.mark.asyncio
async def test_invalid_threshold_raises():
    h = EvalHarness()
    with pytest.raises(ValueError):
        await h.run(lambda x: x, threshold=1.5)


@pytest.mark.asyncio
async def test_empty_harness_gate_false():
    h = EvalHarness()
    report = await h.run(lambda x: x, threshold=0.8)
    assert report.total == 0
    assert report.gate_passed is False


# ── Report shape ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_to_dict_shape():
    h = EvalHarness()
    h.add_case("c", input="x", expected="x")
    d = (await h.run(lambda x: x)).to_dict()
    for key in ("total", "passed", "failed", "mean_score", "pass_rate",
                "threshold", "gate_passed", "cases"):
        assert key in d
    for key in ("name", "score", "passed", "actual", "error"):
        assert key in d["cases"][0]


# ── Metrics ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_track_gate_failures():
    h = EvalHarness()
    h.add_case("bad", input="x", expected="y")
    await h.run(lambda x: x, threshold=0.8)  # fails
    m = h.metrics()
    assert m["runs"] == 1
    assert m["gate_failures"] == 1
    assert m["cases"] == 1


def test_metrics_shape():
    h = EvalHarness()
    m = h.metrics()
    for key in ("cases", "runs", "gate_failures"):
        assert key in m
