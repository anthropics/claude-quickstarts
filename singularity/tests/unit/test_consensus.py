"""
Unit tests — Self-Consistency Consensus Engine (Fáze 33).

Fully offline. sample_fn returns deterministic sequences so cluster
sizes and confidence are predictable.
"""

from __future__ import annotations

import asyncio
import pytest

from core.consensus import (
    ConsensusEngine,
    ConsensusResult,
    _normalize,
    _similar,
)


def _cycle(*values):
    """sample_fn returning values in round-robin order."""
    state = {"n": 0}

    async def _fn(messages):
        v = values[state["n"] % len(values)]
        state["n"] += 1
        return v
    return _fn


_MSGS = [{"role": "user", "content": "What is 2+2?"}]


# ── Helpers ──────────────────────────────────────────────────────────────────────

def test_normalize_strips_punctuation_and_case():
    assert _normalize("Hello, World!") == "hello world"


def test_normalize_empty():
    assert _normalize("") == ""


def test_similar_identical():
    assert _similar("abc", "abc") == 1.0


def test_similar_both_empty():
    assert _similar("", "") == 1.0


def test_similar_different():
    assert _similar("abc", "xyz") < 0.5


# ── Construction validation ──────────────────────────────────────────────────────

def test_invalid_n_samples_raises():
    with pytest.raises(ValueError):
        ConsensusEngine(n_samples=0)


def test_invalid_similarity_threshold_raises():
    with pytest.raises(ValueError):
        ConsensusEngine(similarity_threshold=0.0)


def test_invalid_agreement_threshold_raises():
    with pytest.raises(ValueError):
        ConsensusEngine(agreement_threshold=1.5)


# ── from_samples (sync) ──────────────────────────────────────────────────────────

def test_unanimous_consensus():
    eng = ConsensusEngine(agreement_threshold=0.5)
    result = eng.from_samples(["4", "4", "4"])
    assert result.answer == "4"
    assert result.confidence == 1.0
    assert result.cluster_count == 1
    assert result.agreement is True


def test_majority_consensus():
    eng = ConsensusEngine(agreement_threshold=0.5)
    result = eng.from_samples(["4", "4", "5"])
    assert result.answer == "4"
    assert result.confidence == pytest.approx(2 / 3, abs=1e-3)
    assert result.cluster_count == 2
    assert result.agreement is True


def test_no_agreement_below_threshold():
    eng = ConsensusEngine(agreement_threshold=0.6)
    result = eng.from_samples(["a", "b", "c"])  # all distinct → conf 1/3
    assert result.confidence == pytest.approx(1 / 3, abs=1e-3)
    assert result.agreement is False


def test_tie_breaks_by_first_appearance():
    eng = ConsensusEngine()
    # two clusters of size 1 each tie → first seen wins
    result = eng.from_samples(["zebra", "apple"])
    assert result.answer == "zebra"


def test_empty_samples():
    eng = ConsensusEngine()
    result = eng.from_samples([])
    assert result.answer == ""
    assert result.confidence == 0.0
    assert result.sample_count == 0
    assert result.agreement is False


# ── Similarity clustering ─────────────────────────────────────────────────────────

def test_similar_answers_cluster_together():
    eng = ConsensusEngine(similarity_threshold=0.8, agreement_threshold=0.5)
    # punctuation/case differences normalize to the same string
    result = eng.from_samples(["The answer is 4.", "the answer is 4", "The Answer Is 4!"])
    assert result.cluster_count == 1
    assert result.confidence == 1.0


def test_exact_threshold_one_no_fuzzy():
    eng = ConsensusEngine(similarity_threshold=1.0)
    # near-but-not-equal normalized strings stay separate
    result = eng.from_samples(["answer is four", "answer is fourrr"])
    assert result.cluster_count == 2


def test_fuzzy_groups_near_duplicates():
    eng = ConsensusEngine(similarity_threshold=0.7, agreement_threshold=0.5)
    result = eng.from_samples([
        "the capital is paris",
        "the capital is paris indeed",
        "berlin",
    ])
    # first two are similar enough to cluster; berlin separate
    assert result.answer.startswith("the capital is paris")
    assert result.confidence == pytest.approx(2 / 3, abs=1e-3)


# ── run (async) ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_draws_n_samples():
    eng = ConsensusEngine(n_samples=4)
    calls = {"n": 0}

    async def _fn(messages):
        calls["n"] += 1
        return "same"

    result = await eng.run(_MSGS, _fn)
    assert calls["n"] == 4
    assert result.sample_count == 4
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_run_majority():
    eng = ConsensusEngine(n_samples=3, agreement_threshold=0.5)
    result = await eng.run(_MSGS, _cycle("4", "4", "5"))
    assert result.answer == "4"
    assert result.agreement is True


@pytest.mark.asyncio
async def test_run_n_samples_override():
    eng = ConsensusEngine(n_samples=2)
    result = await eng.run(_MSGS, _cycle("x"), n_samples=6)
    assert result.sample_count == 6


@pytest.mark.asyncio
async def test_run_invalid_override_raises():
    eng = ConsensusEngine(n_samples=3)
    with pytest.raises(ValueError):
        await eng.run(_MSGS, _cycle("x"), n_samples=0)


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    eng = ConsensusEngine()
    result = eng.from_samples(["a", "a", "b"])
    d = result.to_dict()
    for key in ("answer", "confidence", "sample_count", "cluster_count",
                "clusters", "agreement", "samples"):
        assert key in d


def test_clusters_sorted_by_size():
    eng = ConsensusEngine()
    result = eng.from_samples(["a", "b", "b", "b", "a"])
    # cluster "b" (3) should be first, "a" (2) second
    assert result.clusters[0]["answer"] == "b"
    assert result.clusters[0]["size"] == 3
    assert result.clusters[1]["size"] == 2


def test_cluster_members_are_indices():
    eng = ConsensusEngine()
    result = eng.from_samples(["x", "y", "x"])
    top = result.clusters[0]
    assert top["members"] == [0, 2]


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_initial():
    eng = ConsensusEngine()
    m = eng.metrics()
    assert m["total_runs"] == 0
    assert m["agreement_rate"] == 0.0
    assert m["avg_confidence"] == 0.0


def test_metrics_after_runs():
    eng = ConsensusEngine(agreement_threshold=0.5)
    eng.from_samples(["a", "a", "a"])   # agreement, conf 1.0
    eng.from_samples(["a", "b", "c"])   # no agreement, conf 1/3
    m = eng.metrics()
    assert m["total_runs"] == 2
    assert m["agreements"] == 1
    assert m["agreement_rate"] == 0.5
    assert m["avg_confidence"] == pytest.approx((1.0 + 1 / 3) / 2, abs=1e-3)


def test_metrics_reset():
    eng = ConsensusEngine()
    eng.from_samples(["a", "a"])
    eng.reset_metrics()
    m = eng.metrics()
    assert m["total_runs"] == 0
    assert m["agreements"] == 0


def test_metrics_shape():
    eng = ConsensusEngine()
    m = eng.metrics()
    for key in ("total_runs", "agreements", "agreement_rate", "avg_confidence",
                "n_samples", "similarity_threshold", "agreement_threshold"):
        assert key in m


# ── Thread / concurrency ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_runs():
    eng = ConsensusEngine(n_samples=3)

    async def run_once():
        await eng.run(_MSGS, _cycle("ok", "ok", "ok"))

    await asyncio.gather(*[run_once() for _ in range(10)])
    assert eng.metrics()["total_runs"] == 10
