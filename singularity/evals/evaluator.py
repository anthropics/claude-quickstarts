"""
Singularity — OmegaEvaluator (port z Omega).

Kritická oprava: DeepEval crash bez OPENAI_API_KEY → lazy init + heuristický
degraded mode. Bez klíče běží čistě heuristická evaluace (nikdy nespadne).
"""
from __future__ import annotations

import os

import structlog

log = structlog.get_logger()

_OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()


class OmegaEvaluator:
    def __init__(self) -> None:
        self._deepeval_available = False
        if _OPENAI_KEY:
            try:
                import deepeval  # noqa: F401

                self._deepeval_available = True
                log.info("evaluator_mode", mode="deepeval")
            except Exception:
                pass
        if not self._deepeval_available:
            log.info("evaluator_mode", mode="heuristic")

    def evaluate_response(self, task: str, response: str) -> dict:
        if self._deepeval_available:
            return self._deepeval_evaluate(task, response)
        return self._heuristic_evaluate(task, response)

    def _heuristic_evaluate(self, task: str, response: str) -> dict:
        words = len(response.split())
        task_words = set(task.lower().split())
        resp_words = set(response.lower().split())
        overlap = len(task_words & resp_words) / max(len(task_words), 1)
        return {
            "relevance": round(min(overlap * 2, 1.0), 2),
            "length_ok": words > 10,
            "word_count": words,
            "mode": "heuristic",
        }

    def _deepeval_evaluate(self, task: str, response: str) -> dict:
        try:
            from deepeval.metrics import AnswerRelevancyMetric
            from deepeval.test_case import LLMTestCase

            metric = AnswerRelevancyMetric(threshold=0.5)
            tc = LLMTestCase(input=task, actual_output=response)
            metric.measure(tc)
            return {"relevance": metric.score, "mode": "deepeval"}
        except Exception as exc:
            log.warning("deepeval_eval_failed", error=str(exc))
            return self._heuristic_evaluate(task, response)
