"""
Singularity — Eval Harness (Fáze 67, v2.0 #7).

Golden-dataset evaluation with a pass/fail gate for CI regression guarding.
Register labelled cases, run the system-under-test against them with a scoring
function, and get an aggregate report plus a boolean gate (mean score ≥
threshold) that CI can fail on.

Scorers are injectable and a few deterministic built-ins are provided
(exact_match, contains, jaccard, numeric_close) so the harness — and the
regression gate — run fully offline. The system-under-test ``predict_fn`` may
be sync or async.
"""

from __future__ import annotations

import asyncio
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


_WORD = re.compile(r"[a-z0-9]+")


# ── Built-in scorers ─────────────────────────────────────────────────────────────

def exact_match(expected: Any, actual: Any) -> float:
    return 1.0 if expected == actual else 0.0


def contains(expected: Any, actual: Any) -> float:
    return 1.0 if str(expected).lower() in str(actual).lower() else 0.0


def jaccard(expected: Any, actual: Any) -> float:
    a = set(_WORD.findall(str(expected).lower()))
    b = set(_WORD.findall(str(actual).lower()))
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def numeric_close(tolerance: float = 0.01) -> Callable[[Any, Any], float]:
    def _score(expected: Any, actual: Any) -> float:
        try:
            return 1.0 if abs(float(expected) - float(actual)) <= tolerance else 0.0
        except (TypeError, ValueError):
            return 0.0
    return _score


# ── Data structures ─────────────────────────────────────────────────────────────

@dataclass
class EvalCase:
    name: str
    input: Any
    expected: Any
    metadata: dict = field(default_factory=dict)


@dataclass
class CaseResult:
    name: str
    score: float
    passed: bool
    actual: Any = None
    error: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "score": self.score, "passed": self.passed,
                "actual": self.actual, "error": self.error}


@dataclass
class EvalReport:
    total: int
    passed: int
    failed: int
    mean_score: float
    pass_rate: float
    threshold: float
    gate_passed: bool
    cases: list[CaseResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total": self.total, "passed": self.passed, "failed": self.failed,
            "mean_score": self.mean_score, "pass_rate": self.pass_rate,
            "threshold": self.threshold, "gate_passed": self.gate_passed,
            "cases": [c.to_dict() for c in self.cases],
        }


# ── Harness ─────────────────────────────────────────────────────────────────────

Scorer = Callable[[Any, Any], float]
PredictFn = Callable[[Any], Any | Awaitable[Any]]


class EvalHarness:
    """Register golden cases and evaluate a predictor against them."""

    def __init__(self) -> None:
        self._cases: list[EvalCase] = []
        self._lock = threading.Lock()
        self._runs = 0
        self._gate_failures = 0

    # ── Case management ───────────────────────────────────────────────────────────

    def add_case(self, name: str, input: Any, expected: Any, **metadata: Any) -> None:
        if not name:
            raise ValueError("case name is required")
        with self._lock:
            self._cases.append(EvalCase(name=name, input=input, expected=expected,
                                        metadata=metadata))

    def add_cases(self, cases: list[dict]) -> int:
        for c in cases:
            self.add_case(c["name"], c["input"], c["expected"],
                          **{k: v for k, v in c.items()
                             if k not in ("name", "input", "expected")})
        return len(cases)

    def clear_cases(self) -> None:
        with self._lock:
            self._cases.clear()

    @property
    def case_count(self) -> int:
        with self._lock:
            return len(self._cases)

    # ── Run ───────────────────────────────────────────────────────────────────────

    async def run(
        self,
        predict_fn: PredictFn,
        *,
        scorer: Scorer = exact_match,
        threshold: float = 0.8,
        pass_score: float = 1.0,
    ) -> EvalReport:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be in [0.0, 1.0]")
        with self._lock:
            cases = list(self._cases)

        results: list[CaseResult] = []
        for case in cases:
            try:
                actual = predict_fn(case.input)
                if asyncio.iscoroutine(actual):
                    actual = await actual
                score = float(scorer(case.expected, actual))
                results.append(CaseResult(
                    name=case.name, score=round(score, 6),
                    passed=score >= pass_score, actual=actual,
                ))
            except Exception as exc:
                results.append(CaseResult(
                    name=case.name, score=0.0, passed=False,
                    error=f"{type(exc).__name__}: {exc}",
                ))

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        mean = round(sum(r.score for r in results) / total, 6) if total else 0.0
        gate = mean >= threshold if total else False

        with self._lock:
            self._runs += 1
            if not gate:
                self._gate_failures += 1

        return EvalReport(
            total=total, passed=passed, failed=total - passed,
            mean_score=mean, pass_rate=round(passed / total, 6) if total else 0.0,
            threshold=threshold, gate_passed=gate, cases=results,
        )

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        with self._lock:
            return {
                "cases": len(self._cases),
                "runs": self._runs,
                "gate_failures": self._gate_failures,
            }
