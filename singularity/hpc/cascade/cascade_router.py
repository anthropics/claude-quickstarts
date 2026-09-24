"""
Singularity — LLM Cascade Router (Fáze 26).

Two-stage routing pattern:
  1. Try a fast/cheap Draft model first.
  2. If confidence < threshold, escalate to the Oracle (stronger/slower) model.

Designed to reduce ~45-60 % of calls to the Oracle model, cutting cost and
latency for simpler queries while maintaining quality on hard ones.

Integrates as strategy "cascade" in core/router.py via CascadeRouter.route().
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

log = structlog.get_logger()


@dataclass
class LLMResponse:
    """Unified response from any LLM provider."""
    content: str
    provider: str
    confidence: float = 1.0          # 0.0–1.0; Draft fills this from heuristic
    latency_ms: float = 0.0
    tokens_used: int = 0
    metadata: dict = field(default_factory=dict)


class _ConfidenceHeuristic:
    """
    Simple heuristic: estimate confidence from response length and hedging phrases.
    Replace with a proper classifier (DistilBERT / reward model) in production.
    """
    _HEDGE_PHRASES = (
        "i'm not sure", "i am not sure", "i don't know", "i do not know",
        "uncertain", "unsure", "cannot determine", "can't determine",
        "it depends", "not enough information", "unclear",
    )

    @classmethod
    def score(cls, text: str) -> float:
        lower = text.lower()
        # Penalise hedging language
        hedge_count = sum(1 for ph in cls._HEDGE_PHRASES if ph in lower)
        base = max(0.0, 1.0 - hedge_count * 0.25)
        # Very short answers → lower confidence (likely incomplete)
        if len(text.strip()) < 50:
            base *= 0.6
        return round(min(1.0, base), 4)


class CascadeRouter:
    """
    Draft → Oracle cascade.

    Both providers must be callable objects with an async `ainvoke(messages)` method
    returning an LLMResponse (or at minimum an object with `.content`).
    """

    def __init__(
        self,
        draft_provider: Any,
        oracle_provider: Any,
        confidence_threshold: float = 0.7,
    ) -> None:
        if not (0.0 < confidence_threshold <= 1.0):
            raise ValueError("confidence_threshold must be in (0, 1]")
        self.draft_provider = draft_provider
        self.oracle_provider = oracle_provider
        self.confidence_threshold = confidence_threshold

        # Telemetry counters
        self._total_requests = 0
        self._draft_served = 0
        self._oracle_escalations = 0
        self._oracle_fallbacks = 0    # oracle used because draft failed

    # ── Main API ─────────────────────────────────────────────────────────────

    async def route(self, messages: list[dict]) -> LLMResponse:
        """
        Route messages through Draft first, escalate to Oracle if needed.
        Falls back to Oracle if Draft raises an exception.
        """
        self._total_requests += 1
        t0 = time.monotonic()

        # 1. Try Draft
        draft_resp: LLMResponse | None = None
        try:
            raw = await self.draft_provider.ainvoke(messages)
            draft_resp = self._to_response(raw, "draft")
            if not hasattr(raw, "confidence"):
                draft_resp.confidence = _ConfidenceHeuristic.score(draft_resp.content)
        except Exception as exc:
            log.warning("cascade_draft_failed", error=str(exc))

        # 2. Decide: serve Draft or escalate
        if draft_resp is not None and draft_resp.confidence >= self.confidence_threshold:
            draft_resp.latency_ms = (time.monotonic() - t0) * 1000
            self._draft_served += 1
            log.info("cascade_draft_served",
                     confidence=draft_resp.confidence,
                     latency_ms=round(draft_resp.latency_ms, 1))
            return draft_resp

        # 3. Escalate to Oracle
        reason = "low_confidence" if draft_resp is not None else "draft_failed"
        if draft_resp is None:
            self._oracle_fallbacks += 1
        else:
            self._oracle_escalations += 1

        log.info("cascade_oracle_escalation",
                 reason=reason,
                 draft_confidence=draft_resp.confidence if draft_resp else None)

        oracle_raw = await self.oracle_provider.ainvoke(messages)
        oracle_resp = self._to_response(oracle_raw, "oracle")
        oracle_resp.latency_ms = (time.monotonic() - t0) * 1000
        oracle_resp.metadata["escalation_reason"] = reason
        if draft_resp is not None:
            oracle_resp.metadata["draft_confidence"] = draft_resp.confidence
        return oracle_resp

    # ── Metrics ───────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        """Return current routing statistics."""
        total = self._total_requests or 1  # avoid ZeroDivisionError
        return {
            "total_requests": self._total_requests,
            "draft_served": self._draft_served,
            "oracle_escalations": self._oracle_escalations,
            "oracle_fallbacks": self._oracle_fallbacks,
            "draft_hit_rate": round(self._draft_served / total, 4),
            "oracle_rate": round((self._oracle_escalations + self._oracle_fallbacks) / total, 4),
            "confidence_threshold": self.confidence_threshold,
            "snapshot_at": datetime.now(timezone.utc).isoformat(),
        }

    def reset_metrics(self) -> None:
        self._total_requests = 0
        self._draft_served = 0
        self._oracle_escalations = 0
        self._oracle_fallbacks = 0

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _to_response(raw: Any, provider_tag: str) -> LLMResponse:
        if isinstance(raw, LLMResponse):
            return raw
        # Coerce from AbstractLLMProvider response objects
        content = getattr(raw, "content", str(raw))
        confidence = getattr(raw, "confidence", 1.0)
        tokens = getattr(raw, "tokens_used", 0)
        return LLMResponse(
            content=content,
            provider=provider_tag,
            confidence=confidence,
            tokens_used=tokens,
        )
