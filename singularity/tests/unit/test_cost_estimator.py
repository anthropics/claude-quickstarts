"""
Unit tests — Cost Estimator (Fáze 40). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.cost_estimator import (
    ComparisonResult,
    CostEstimate,
    CostEstimator,
    ModelPricing,
    estimate_tokens,
)


def _estimator():
    # Fixed pricing for predictable math (USD per 1M tokens).
    return CostEstimator({
        "cheap": ModelPricing("cheap", 1.0, 2.0),
        "mid": ModelPricing("mid", 5.0, 10.0),
        "pricey": ModelPricing("pricey", 20.0, 40.0),
    })


# ── token helper ─────────────────────────────────────────────────────────────────

def test_estimate_tokens_basic():
    assert estimate_tokens("one two three") == int(3 * 1.3)


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0


# ── Estimation math ──────────────────────────────────────────────────────────────

def test_estimate_explicit_tokens():
    e = _estimator()
    est = e.estimate("cheap", input_tokens=1_000_000, output_tokens=1_000_000)
    # input 1.0 + output 2.0
    assert est.input_cost == pytest.approx(1.0)
    assert est.output_cost == pytest.approx(2.0)
    assert est.total_cost == pytest.approx(3.0)


def test_estimate_from_prompt():
    e = _estimator()
    est = e.estimate("cheap", prompt="word " * 1000, output_tokens=0)
    # 1000 words × 1.3 = 1300 tokens input
    assert est.input_tokens == 1300


def test_estimate_default_output_tokens():
    e = _estimator()
    est = e.estimate("cheap", input_tokens=0)
    assert est.output_tokens == 500  # default expected_output_tokens


def test_estimate_unknown_model_raises():
    e = _estimator()
    with pytest.raises(ValueError):
        e.estimate("nonexistent", input_tokens=10)


def test_estimate_negative_tokens_raises():
    e = _estimator()
    with pytest.raises(ValueError):
        e.estimate("cheap", input_tokens=-5)


# ── Budget flag ──────────────────────────────────────────────────────────────────

def test_within_budget_true():
    e = _estimator()
    est = e.estimate("cheap", input_tokens=1_000_000, output_tokens=0, budget=5.0)
    assert est.within_budget is True


def test_within_budget_false():
    e = _estimator()
    est = e.estimate("pricey", input_tokens=1_000_000, output_tokens=0, budget=5.0)
    assert est.within_budget is False


def test_within_budget_none_when_no_budget():
    e = _estimator()
    est = e.estimate("cheap", input_tokens=10)
    assert est.within_budget is None


# ── Comparison ───────────────────────────────────────────────────────────────────

def test_compare_sorts_ascending():
    e = _estimator()
    result = e.compare(input_tokens=1_000_000, output_tokens=0)
    models = [est.model for est in result.estimates]
    assert models == ["cheap", "mid", "pricey"]
    assert result.cheapest == "cheap"
    assert result.most_expensive == "pricey"


def test_compare_subset_of_models():
    e = _estimator()
    result = e.compare(input_tokens=100, models=["mid", "pricey"])
    assert {est.model for est in result.estimates} == {"mid", "pricey"}
    assert result.cheapest == "mid"


def test_compare_applies_budget_flag():
    e = _estimator()
    result = e.compare(input_tokens=1_000_000, output_tokens=0, budget=2.0)
    by_model = {est.model: est.within_budget for est in result.estimates}
    assert by_model["cheap"] is True       # 1.0 <= 2.0
    assert by_model["pricey"] is False     # 20.0 > 2.0


# ── cheapest_within_budget ───────────────────────────────────────────────────────

def test_cheapest_within_budget_picks_cheapest_fitting():
    e = _estimator()
    # budget 6.0; cheap=1.0, mid=5.0, pricey=20.0 → cheapest fitting = cheap
    model = e.cheapest_within_budget(6.0, input_tokens=1_000_000, output_tokens=0)
    assert model == "cheap"


def test_cheapest_within_budget_none_when_all_too_expensive():
    e = _estimator()
    model = e.cheapest_within_budget(0.5, input_tokens=1_000_000, output_tokens=0)
    assert model is None


def test_cheapest_within_budget_boundary_inclusive():
    e = _estimator()
    # exactly 1.0 for cheap
    model = e.cheapest_within_budget(1.0, input_tokens=1_000_000, output_tokens=0)
    assert model == "cheap"


# ── Pricing management ───────────────────────────────────────────────────────────

def test_set_pricing_adds_model():
    e = _estimator()
    e.set_pricing("custom", 2.0, 3.0)
    assert "custom" in e.list_models()
    est = e.estimate("custom", input_tokens=1_000_000, output_tokens=0)
    assert est.total_cost == pytest.approx(2.0)


def test_set_pricing_negative_raises():
    e = _estimator()
    with pytest.raises(ValueError):
        e.set_pricing("bad", -1.0, 2.0)


def test_remove_pricing():
    e = _estimator()
    assert e.remove_pricing("cheap") is True
    assert "cheap" not in e.list_models()


def test_remove_missing_returns_false():
    e = _estimator()
    assert e.remove_pricing("nope") is False


def test_default_pricing_has_known_models():
    e = CostEstimator()
    models = e.list_models()
    assert "claude-sonnet-4-6" in models
    assert "gemini-2.0-flash" in models


# ── Result shapes ────────────────────────────────────────────────────────────────

def test_estimate_to_dict_shape():
    e = _estimator()
    d = e.estimate("cheap", input_tokens=10).to_dict()
    for key in ("model", "input_tokens", "output_tokens", "input_cost",
                "output_cost", "total_cost", "within_budget"):
        assert key in d


def test_comparison_to_dict_shape():
    e = _estimator()
    d = e.compare(input_tokens=10).to_dict()
    for key in ("estimates", "cheapest", "most_expensive"):
        assert key in d


def test_model_pricing_to_dict():
    d = ModelPricing("m", 1.0, 2.0).to_dict()
    assert d == {"model": "m", "input_per_1m": 1.0, "output_per_1m": 2.0}


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    e = _estimator()
    e.estimate("cheap", input_tokens=1_000_000, output_tokens=0)  # 1.0
    e.estimate("mid", input_tokens=1_000_000, output_tokens=0)    # 5.0
    m = e.metrics()
    assert m["total_estimates"] == 2
    assert m["total_projected_cost"] == pytest.approx(6.0)
    assert m["avg_projected_cost"] == pytest.approx(3.0)


def test_metrics_reset():
    e = _estimator()
    e.estimate("cheap", input_tokens=10)
    e.reset_metrics()
    m = e.metrics()
    assert m["total_estimates"] == 0
    assert m["total_projected_cost"] == 0.0


def test_metrics_shape():
    e = _estimator()
    m = e.metrics()
    for key in ("total_estimates", "total_projected_cost",
                "avg_projected_cost", "model_count"):
        assert key in m
