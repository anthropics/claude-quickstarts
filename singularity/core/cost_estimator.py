"""
Singularity — Cost Estimator (Fáze 40).

Pre-flight cost projection across LLM models. Given prompt text (or token
counts) the estimator computes the expected USD cost per model from a pricing
table, compares models, and finds the cheapest option that satisfies a
budget. Complements the BudgetManager (which tracks *actual* spend) by
projecting cost *before* a call to inform model selection.

Prices are USD per 1,000,000 tokens (input / output). Dependency-free and
deterministic; the pricing table is editable at runtime.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


_APPROX_FACTOR = 1.3  # words → tokens heuristic


def estimate_tokens(text: str) -> int:
    """Word-count × 1.3 heuristic (matches other Singularity modules)."""
    return int(len((text or "").split()) * _APPROX_FACTOR)


# ── Pricing ─────────────────────────────────────────────────────────────────────

@dataclass
class ModelPricing:
    model: str
    input_per_1m: float    # USD per 1M input tokens
    output_per_1m: float   # USD per 1M output tokens

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "input_per_1m": self.input_per_1m,
            "output_per_1m": self.output_per_1m,
        }


def _default_pricing() -> dict[str, ModelPricing]:
    # Representative USD/1M token rates for offline estimation.
    return {
        "claude-sonnet-4-6": ModelPricing("claude-sonnet-4-6", 3.0, 15.0),
        "claude-opus-4-8": ModelPricing("claude-opus-4-8", 15.0, 75.0),
        "claude-haiku-4-5": ModelPricing("claude-haiku-4-5", 0.8, 4.0),
        "gemini-2.0-flash": ModelPricing("gemini-2.0-flash", 0.1, 0.4),
    }


# ── Results ─────────────────────────────────────────────────────────────────────

@dataclass
class CostEstimate:
    model: str
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    within_budget: bool | None = None

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "input_cost": self.input_cost,
            "output_cost": self.output_cost,
            "total_cost": self.total_cost,
            "within_budget": self.within_budget,
        }


@dataclass
class ComparisonResult:
    estimates: list[CostEstimate] = field(default_factory=list)
    cheapest: str | None = None
    most_expensive: str | None = None

    def to_dict(self) -> dict:
        return {
            "estimates": [e.to_dict() for e in self.estimates],
            "cheapest": self.cheapest,
            "most_expensive": self.most_expensive,
        }


# ── Estimator ───────────────────────────────────────────────────────────────────

class CostEstimator:
    """Project request cost per model and compare across the pricing table."""

    def __init__(self, pricing: dict[str, ModelPricing] | None = None) -> None:
        self._pricing: dict[str, ModelPricing] = pricing or _default_pricing()
        self._lock = threading.Lock()

        # metrics
        self._total_estimates = 0
        self._total_projected_cost = 0.0

    # ── Pricing management ────────────────────────────────────────────────────────

    def set_pricing(self, model: str, input_per_1m: float, output_per_1m: float) -> None:
        if input_per_1m < 0 or output_per_1m < 0:
            raise ValueError("prices must be >= 0")
        with self._lock:
            self._pricing[model] = ModelPricing(model, input_per_1m, output_per_1m)

    def remove_pricing(self, model: str) -> bool:
        with self._lock:
            return self._pricing.pop(model, None) is not None

    def list_models(self) -> list[str]:
        with self._lock:
            return sorted(self._pricing)

    # ── Estimation ────────────────────────────────────────────────────────────────

    def estimate(
        self,
        model: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        prompt: str | None = None,
        expected_output_tokens: int = 500,
        budget: float | None = None,
    ) -> CostEstimate:
        with self._lock:
            pricing = self._pricing.get(model)
        if pricing is None:
            raise ValueError(f"Unknown model: {model!r}")

        in_tok = input_tokens if input_tokens is not None else (
            estimate_tokens(prompt) if prompt is not None else 0
        )
        out_tok = output_tokens if output_tokens is not None else expected_output_tokens
        if in_tok < 0 or out_tok < 0:
            raise ValueError("token counts must be >= 0")

        in_cost = in_tok / 1_000_000 * pricing.input_per_1m
        out_cost = out_tok / 1_000_000 * pricing.output_per_1m
        total = round(in_cost + out_cost, 8)

        within = None if budget is None else total <= budget
        self._record(total)
        return CostEstimate(
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            input_cost=round(in_cost, 8),
            output_cost=round(out_cost, 8),
            total_cost=total,
            within_budget=within,
        )

    def compare(
        self,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        prompt: str | None = None,
        expected_output_tokens: int = 500,
        budget: float | None = None,
        models: list[str] | None = None,
    ) -> ComparisonResult:
        with self._lock:
            candidates = models or list(self._pricing)
        estimates = [
            self.estimate(
                m,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                prompt=prompt,
                expected_output_tokens=expected_output_tokens,
                budget=budget,
            )
            for m in candidates
        ]
        estimates.sort(key=lambda e: (e.total_cost, e.model))
        cheapest = estimates[0].model if estimates else None
        most_expensive = estimates[-1].model if estimates else None
        return ComparisonResult(
            estimates=estimates,
            cheapest=cheapest,
            most_expensive=most_expensive,
        )

    def cheapest_within_budget(
        self,
        budget: float,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        prompt: str | None = None,
        expected_output_tokens: int = 500,
        models: list[str] | None = None,
    ) -> str | None:
        """Return the cheapest model whose projected cost fits the budget."""
        comparison = self.compare(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            prompt=prompt,
            expected_output_tokens=expected_output_tokens,
            budget=budget,
            models=models,
        )
        for est in comparison.estimates:  # already cost-sorted ascending
            if est.total_cost <= budget:
                return est.model
        return None

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, cost: float) -> None:
        with self._lock:
            self._total_estimates += 1
            self._total_projected_cost += cost

    def metrics(self) -> dict:
        with self._lock:
            n = self._total_estimates
            return {
                "total_estimates": n,
                "total_projected_cost": round(self._total_projected_cost, 8),
                "avg_projected_cost": round(self._total_projected_cost / n, 8)
                if n else 0.0,
                "model_count": len(self._pricing),
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_estimates = 0
            self._total_projected_cost = 0.0
