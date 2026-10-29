"""
Singularity — Request Pipeline (Fáze 30).

Composable pre/post processing chain for LLM requests.
Each PipelineStep can transform messages before provider invocation
and transform the response after. Steps run in registration order.
"""

from __future__ import annotations

import re
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


# ── Exceptions ────────────────────────────────────────────────────────────────

class PipelineAbort(Exception):
    """Raised by a step to halt the pipeline immediately (not an error)."""


class PipelineError(Exception):
    """Raised when a step fails and fail_fast=True on the pipeline."""


# ── Context ───────────────────────────────────────────────────────────────────

@dataclass
class StepContext:
    messages: list[dict]
    response: str | None = None
    provider: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    aborted: bool = False
    abort_reason: str | None = None

    def copy(self) -> "StepContext":
        return StepContext(
            messages=[m.copy() for m in self.messages],
            response=self.response,
            provider=self.provider,
            metadata=dict(self.metadata),
            aborted=self.aborted,
            abort_reason=self.abort_reason,
        )


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    messages: list[dict]
    response: str | None
    provider: str | None
    metadata: dict[str, Any]
    steps_applied: list[str]
    aborted: bool
    abort_reason: str | None
    duration_ms: float

    def to_dict(self) -> dict:
        return {
            "messages": self.messages,
            "response": self.response,
            "provider": self.provider,
            "metadata": self.metadata,
            "steps_applied": self.steps_applied,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
            "duration_ms": self.duration_ms,
        }


# ── Base step ─────────────────────────────────────────────────────────────────

class PipelineStep(ABC):
    """Base class for all pipeline steps."""

    name: str = "unnamed"

    @abstractmethod
    async def process_request(self, ctx: StepContext) -> StepContext:
        """Transform messages before provider invocation."""

    async def process_response(self, ctx: StepContext) -> StepContext:
        """Transform response after provider invocation. Default: pass-through."""
        return ctx


# ── Built-in steps ────────────────────────────────────────────────────────────

class PromptInjectionStep(PipelineStep):
    """Prepend a system-level injection to every message list."""

    name = "prompt_injection"

    def __init__(self, injection: str, role: str = "system") -> None:
        self.injection = injection
        self.role = role

    async def process_request(self, ctx: StepContext) -> StepContext:
        if self.injection:
            ctx.messages = [{"role": self.role, "content": self.injection}] + ctx.messages
        return ctx


class PIIRedactionStep(PipelineStep):
    """Redact common PII patterns (email, phone, SSN) in messages and responses."""

    name = "pii_redaction"

    _EMAIL = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    _PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
    _SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

    def _redact(self, text: str) -> str:
        text = self._EMAIL.sub("[EMAIL]", text)
        text = self._PHONE.sub("[PHONE]", text)
        text = self._SSN.sub("[SSN]", text)
        return text

    async def process_request(self, ctx: StepContext) -> StepContext:
        ctx.messages = [
            {**m, "content": self._redact(m.get("content", "") or "")}
            for m in ctx.messages
        ]
        return ctx

    async def process_response(self, ctx: StepContext) -> StepContext:
        if ctx.response is not None:
            ctx.response = self._redact(ctx.response)
        return ctx


class TruncationStep(PipelineStep):
    """Truncate the response to at most max_chars characters."""

    name = "truncation"

    def __init__(self, max_chars: int = 2000, suffix: str = "…") -> None:
        if max_chars < 1:
            raise ValueError("max_chars must be >= 1")
        self.max_chars = max_chars
        self.suffix = suffix

    async def process_request(self, ctx: StepContext) -> StepContext:
        return ctx

    async def process_response(self, ctx: StepContext) -> StepContext:
        if ctx.response is not None and len(ctx.response) > self.max_chars:
            ctx.response = ctx.response[: self.max_chars] + self.suffix
        return ctx


class TokenCounterStep(PipelineStep):
    """Estimate token counts (words × 1.3) and store in ctx.metadata."""

    name = "token_counter"

    _APPROX_FACTOR = 1.3

    async def process_request(self, ctx: StepContext) -> StepContext:
        total_words = sum(
            len((m.get("content") or "").split()) for m in ctx.messages
        )
        ctx.metadata["estimated_prompt_tokens"] = int(total_words * self._APPROX_FACTOR)
        return ctx

    async def process_response(self, ctx: StepContext) -> StepContext:
        words = len((ctx.response or "").split())
        ctx.metadata["estimated_response_tokens"] = int(words * self._APPROX_FACTOR)
        return ctx


# ── Pipeline ──────────────────────────────────────────────────────────────────

InvokeFn = Callable[[list[dict], str | None], Coroutine[Any, Any, str]]


class RequestPipeline:
    """
    Ordered chain of PipelineSteps applied to every LLM request/response.

    Usage:
        pipeline = RequestPipeline(fail_fast=False)
        pipeline.add_step(PIIRedactionStep())
        pipeline.add_step(TokenCounterStep())
        result = await pipeline.run(messages, invoke_fn=my_llm_call)
    """

    def __init__(
        self,
        steps: list[PipelineStep] | None = None,
        *,
        fail_fast: bool = False,
    ) -> None:
        self._steps: list[PipelineStep] = list(steps or [])
        self.fail_fast = fail_fast
        self._lock = threading.Lock()

        # metrics
        self._step_invocations: dict[str, int] = {}
        self._step_latency_ms: dict[str, float] = {}
        self._total_runs: int = 0
        self._aborted_runs: int = 0

    # ── Step management ───────────────────────────────────────────────────────

    def add_step(self, step: PipelineStep) -> None:
        with self._lock:
            self._steps.append(step)

    def remove_step(self, name: str) -> bool:
        with self._lock:
            before = len(self._steps)
            self._steps = [s for s in self._steps if s.name != name]
            return len(self._steps) < before

    def list_steps(self) -> list[str]:
        with self._lock:
            return [s.name for s in self._steps]

    def clear_steps(self) -> None:
        with self._lock:
            self._steps.clear()

    # ── Run ───────────────────────────────────────────────────────────────────

    async def run(
        self,
        messages: list[dict],
        provider: str | None = None,
        invoke_fn: InvokeFn | None = None,
    ) -> PipelineResult:
        """
        Full pipeline run:
          1. process_request on each step (in order)
          2. call invoke_fn(messages, provider) if provided
          3. process_response on each step (in order)
        """
        t0 = time.monotonic()
        ctx = StepContext(messages=list(messages), provider=provider)
        applied: list[str] = []

        with self._lock:
            steps = list(self._steps)

        # ── Request phase ──
        for step in steps:
            if ctx.aborted:
                break
            step_t0 = time.monotonic()
            try:
                ctx = await step.process_request(ctx)
                applied.append(f"{step.name}:request")
            except PipelineAbort as exc:
                ctx.aborted = True
                ctx.abort_reason = str(exc) or step.name
                break
            except Exception as exc:
                if self.fail_fast:
                    raise PipelineError(f"Step '{step.name}' failed: {exc}") from exc
            finally:
                self._record_step(step.name, time.monotonic() - step_t0)

        # ── Invoke ──
        if not ctx.aborted and invoke_fn is not None:
            ctx.response = await invoke_fn(ctx.messages, ctx.provider)

        # ── Response phase ──
        if not ctx.aborted:
            for step in steps:
                step_t0 = time.monotonic()
                try:
                    ctx = await step.process_response(ctx)
                    applied.append(f"{step.name}:response")
                except PipelineAbort as exc:
                    ctx.aborted = True
                    ctx.abort_reason = str(exc) or step.name
                    break
                except Exception as exc:
                    if self.fail_fast:
                        raise PipelineError(f"Step '{step.name}' failed: {exc}") from exc
                finally:
                    self._record_step(step.name, time.monotonic() - step_t0)

        with self._lock:
            self._total_runs += 1
            if ctx.aborted:
                self._aborted_runs += 1

        return PipelineResult(
            messages=ctx.messages,
            response=ctx.response,
            provider=ctx.provider,
            metadata=ctx.metadata,
            steps_applied=applied,
            aborted=ctx.aborted,
            abort_reason=ctx.abort_reason,
            duration_ms=(time.monotonic() - t0) * 1000,
        )

    # ── Metrics ───────────────────────────────────────────────────────────────

    def _record_step(self, name: str, elapsed_s: float) -> None:
        with self._lock:
            self._step_invocations[name] = self._step_invocations.get(name, 0) + 1
            self._step_latency_ms[name] = (
                self._step_latency_ms.get(name, 0.0) + elapsed_s * 1000
            )

    def metrics(self) -> dict:
        with self._lock:
            per_step = {}
            for name, count in self._step_invocations.items():
                total_ms = self._step_latency_ms.get(name, 0.0)
                per_step[name] = {
                    "invocations": count,
                    "total_ms": round(total_ms, 3),
                    "avg_ms": round(total_ms / count, 3) if count else 0.0,
                }
            return {
                "total_runs": self._total_runs,
                "aborted_runs": self._aborted_runs,
                "step_count": len(self._steps),
                "per_step": per_step,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._step_invocations.clear()
            self._step_latency_ms.clear()
            self._total_runs = 0
            self._aborted_runs = 0
