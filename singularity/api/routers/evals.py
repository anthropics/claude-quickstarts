"""
Eval Harness endpoint (Fáze 67, v2.0 #7). Extracted from api/main.py.

Routes and behaviour are identical to the original.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.eval_harness import EvalHarness, contains, exact_match, jaccard, numeric_close

router = APIRouter(tags=["Evals"])


class EvalScoreRequest(BaseModel):
    cases: list[dict]          # [{name, expected, actual}]
    scorer: str = "exact_match"  # exact_match | contains | jaccard | numeric_close
    threshold: float = 0.8
    pass_score: float = 1.0
    tolerance: float = 0.01    # for numeric_close


_SCORERS = {
    "exact_match": exact_match,
    "contains": contains,
    "jaccard": jaccard,
}


@router.post("/evals/score")
async def evals_score(req: EvalScoreRequest):
    """Score pre-computed expected/actual pairs and return a pass/fail gate.

    A CI regression gate — fail the build when mean score < threshold."""
    if req.scorer == "numeric_close":
        scorer = numeric_close(tolerance=req.tolerance)
    elif req.scorer in _SCORERS:
        scorer = _SCORERS[req.scorer]
    else:
        raise HTTPException(status_code=400, detail=f"unknown scorer {req.scorer!r}")

    harness = EvalHarness()
    actuals: dict[str, Any] = {}
    for i, c in enumerate(req.cases):
        name = c.get("name", f"case{i}")
        harness.add_case(name, input=name, expected=c.get("expected"))
        actuals[name] = c.get("actual")

    try:
        report = await harness.run(
            lambda name: actuals.get(name),
            scorer=scorer, threshold=req.threshold, pass_score=req.pass_score,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return report.to_dict()
