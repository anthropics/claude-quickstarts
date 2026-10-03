"""
Cost & streaming statistics endpoints. Extracted from api/main.py (maintainability refactor).

Routes and behaviour are identical to the originals.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.state import _anomaly_detector, _cost_estimator, _percentile_tracker, _sampler
from config.settings import settings
from core.anomaly_detector import DetectionMethod

router = APIRouter()

# ── Cost Estimator (Fáze 40) ────────────────────────────────────────────────────

class CostEstimateRequest(BaseModel):
    model: str
    prompt: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    budget: float | None = None


class CostCompareRequest(BaseModel):
    prompt: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    budget: float | None = None
    models: list[str] | None = None


@router.post("/cost/estimate", tags=["Cost"])
async def cost_estimate(req: CostEstimateRequest):
    """Project the USD cost of a request for a given model."""
    try:
        est = _cost_estimator.estimate(
            req.model,
            input_tokens=req.input_tokens,
            output_tokens=req.output_tokens,
            prompt=req.prompt,
            expected_output_tokens=settings.cost_default_output_tokens,
            budget=req.budget,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return est.to_dict()


@router.post("/cost/compare", tags=["Cost"])
async def cost_compare(req: CostCompareRequest):
    """Compare projected cost across models; reports cheapest/most expensive."""
    try:
        result = _cost_estimator.compare(
            input_tokens=req.input_tokens,
            output_tokens=req.output_tokens,
            prompt=req.prompt,
            expected_output_tokens=settings.cost_default_output_tokens,
            budget=req.budget,
            models=req.models,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.to_dict()


@router.get("/cost/models", tags=["Cost"])
async def cost_models():
    """List models with known pricing."""
    return {"models": _cost_estimator.list_models()}


@router.get("/cost/metrics", tags=["Cost"])
async def cost_metrics():
    """Cost estimator metrics: total/avg projected cost."""
    return _cost_estimator.metrics()


# ── Anomaly Detector (Fáze 52) ──────────────────────────────────────────────────

class AnomalyObserveRequest(BaseModel):
    metric: str
    value: float
    method: str | None = None   # z_score | iqr


@router.post("/anomaly/observe", tags=["Anomaly"])
async def anomaly_observe(req: AnomalyObserveRequest):
    """Record a metric value and report whether it is anomalous vs. recent history."""
    method = None
    if req.method is not None:
        try:
            method = DetectionMethod(req.method)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown method: {req.method!r}")
    return _anomaly_detector.observe(req.metric, req.value, method=method).to_dict()


@router.get("/anomaly/metrics", tags=["Anomaly"])
async def anomaly_metrics():
    """Anomaly detector metrics: anomaly rate, tracked metric streams."""
    return _anomaly_detector.metrics()


# ── Reservoir Sampler (Fáze 53) ─────────────────────────────────────────────────

class SamplerAddRequest(BaseModel):
    item: Any


@router.post("/sampler/add", tags=["Sampler"])
async def sampler_add(req: SamplerAddRequest):
    """Offer an item to the reservoir; returns whether it is currently retained."""
    kept = _sampler.add(req.item)
    return {"kept": kept, "seen": _sampler.seen}


@router.get("/sampler/sample", tags=["Sampler"])
async def sampler_sample():
    """Return the current reservoir sample and state."""
    return _sampler.state().to_dict()


@router.post("/sampler/reset", tags=["Sampler"])
async def sampler_reset():
    """Empty the reservoir."""
    _sampler.reset()
    return {"status": "reset"}


@router.get("/sampler/metrics", tags=["Sampler"])
async def sampler_metrics():
    """Reservoir sampler metrics: seen, sample size, replacements, fill ratio."""
    return _sampler.metrics()


# ── Percentile Tracker (Fáze 54) ────────────────────────────────────────────────

class PercentileObserveRequest(BaseModel):
    metric: str
    value: float


@router.post("/percentile/observe", tags=["Percentile"])
async def percentile_observe(req: PercentileObserveRequest):
    """Record a value for a metric's rolling distribution."""
    _percentile_tracker.observe(req.metric, req.value)
    return {"metric": req.metric, "observed": req.value}


@router.get("/percentile/summary", tags=["Percentile"])
async def percentile_summary(metric: str):
    """Return count/min/max/mean + percentiles (p50/p90/p95/p99) for a metric."""
    summary = _percentile_tracker.summary(metric)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"No data for metric {metric!r}")
    return summary.to_dict()


@router.get("/percentile/metrics", tags=["Percentile"])
async def percentile_metrics():
    """Percentile tracker metrics: total observations, tracked metrics."""
    return _percentile_tracker.metrics()
