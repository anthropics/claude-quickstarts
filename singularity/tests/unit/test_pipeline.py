"""
Unit tests — Request Pipeline (Fáze 30).

All tests are fully offline (no LLM calls). invoke_fn is provided as a
simple async lambda returning a fixed string.
"""

from __future__ import annotations

import asyncio
import pytest

from core.pipeline import (
    PIIRedactionStep,
    PipelineAbort,
    PipelineError,
    PipelineResult,
    PipelineStep,
    PromptInjectionStep,
    RequestPipeline,
    StepContext,
    TokenCounterStep,
    TruncationStep,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_MSGS = [{"role": "user", "content": "Hello"}]


async def _invoke(messages, provider):
    return "LLM response"


async def _invoke_echo(messages, provider):
    return messages[-1]["content"]


# ── StepContext ───────────────────────────────────────────────────────────────

def test_step_context_copy_is_independent():
    ctx = StepContext(messages=[{"role": "user", "content": "x"}], metadata={"k": 1})
    c2 = ctx.copy()
    c2.messages[0]["content"] = "y"
    c2.metadata["k"] = 99
    assert ctx.messages[0]["content"] == "x"
    assert ctx.metadata["k"] == 1


def test_step_context_defaults():
    ctx = StepContext(messages=[])
    assert ctx.response is None
    assert ctx.provider is None
    assert ctx.aborted is False
    assert ctx.metadata == {}


# ── PipelineResult ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_result_to_dict_shape():
    pipeline = RequestPipeline()
    result = await pipeline.run(_MSGS, invoke_fn=_invoke)
    d = result.to_dict()
    for key in ("messages", "response", "provider", "metadata",
                "steps_applied", "aborted", "abort_reason", "duration_ms"):
        assert key in d


@pytest.mark.asyncio
async def test_result_duration_ms_positive():
    pipeline = RequestPipeline()
    result = await pipeline.run(_MSGS, invoke_fn=_invoke)
    assert result.duration_ms >= 0


# ── Empty pipeline ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_pipeline_passes_through():
    pipeline = RequestPipeline()
    result = await pipeline.run(_MSGS, invoke_fn=_invoke)
    assert result.response == "LLM response"
    assert result.aborted is False
    assert result.steps_applied == []


@pytest.mark.asyncio
async def test_empty_pipeline_no_invoke():
    pipeline = RequestPipeline()
    result = await pipeline.run(_MSGS)
    assert result.response is None


# ── PromptInjectionStep ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_prompt_injection_prepends_system_message():
    pipeline = RequestPipeline([PromptInjectionStep("Be concise.")])
    result = await pipeline.run(_MSGS, invoke_fn=_invoke)
    assert result.messages[0]["role"] == "system"
    assert result.messages[0]["content"] == "Be concise."
    assert result.messages[1]["role"] == "user"


@pytest.mark.asyncio
async def test_prompt_injection_custom_role():
    step = PromptInjectionStep("Hint.", role="assistant")
    pipeline = RequestPipeline([step])
    result = await pipeline.run(_MSGS, invoke_fn=_invoke)
    assert result.messages[0]["role"] == "assistant"


@pytest.mark.asyncio
async def test_prompt_injection_empty_string_no_prepend():
    pipeline = RequestPipeline([PromptInjectionStep("")])
    result = await pipeline.run(_MSGS, invoke_fn=_invoke)
    assert result.messages == _MSGS


# ── PIIRedactionStep ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pii_redacts_email_in_request():
    msgs = [{"role": "user", "content": "Contact me at user@example.com please"}]
    pipeline = RequestPipeline([PIIRedactionStep()])
    result = await pipeline.run(msgs, invoke_fn=_invoke)
    assert "[EMAIL]" in result.messages[-1]["content"]
    assert "user@example.com" not in result.messages[-1]["content"]


@pytest.mark.asyncio
async def test_pii_redacts_phone_in_request():
    msgs = [{"role": "user", "content": "Call me at 555-867-5309"}]
    pipeline = RequestPipeline([PIIRedactionStep()])
    result = await pipeline.run(msgs, invoke_fn=_invoke)
    assert "[PHONE]" in result.messages[-1]["content"]


@pytest.mark.asyncio
async def test_pii_redacts_ssn_in_request():
    msgs = [{"role": "user", "content": "SSN is 123-45-6789"}]
    pipeline = RequestPipeline([PIIRedactionStep()])
    result = await pipeline.run(msgs, invoke_fn=_invoke)
    assert "[SSN]" in result.messages[-1]["content"]


@pytest.mark.asyncio
async def test_pii_redacts_email_in_response():
    async def _inv(messages, provider):
        return "Reply: contact@corp.io"

    pipeline = RequestPipeline([PIIRedactionStep()])
    result = await pipeline.run(_MSGS, invoke_fn=_inv)
    assert "[EMAIL]" in result.response
    assert "contact@corp.io" not in result.response


@pytest.mark.asyncio
async def test_pii_no_pii_unchanged():
    msgs = [{"role": "user", "content": "Plain message"}]
    pipeline = RequestPipeline([PIIRedactionStep()])
    result = await pipeline.run(msgs, invoke_fn=_invoke)
    assert result.messages[-1]["content"] == "Plain message"


# ── TruncationStep ────────────────────────────────────────────────────────────

def test_truncation_invalid_max_chars_raises():
    with pytest.raises(ValueError):
        TruncationStep(max_chars=0)


@pytest.mark.asyncio
async def test_truncation_cuts_long_response():
    async def _long(_m, _p):
        return "A" * 100

    pipeline = RequestPipeline([TruncationStep(max_chars=10)])
    result = await pipeline.run(_MSGS, invoke_fn=_long)
    assert len(result.response) == 11  # 10 chars + "…"
    assert result.response.endswith("…")


@pytest.mark.asyncio
async def test_truncation_short_response_unchanged():
    pipeline = RequestPipeline([TruncationStep(max_chars=1000)])
    result = await pipeline.run(_MSGS, invoke_fn=_invoke)
    assert result.response == "LLM response"


@pytest.mark.asyncio
async def test_truncation_custom_suffix():
    async def _long(_m, _p):
        return "X" * 20

    pipeline = RequestPipeline([TruncationStep(max_chars=5, suffix="...")])
    result = await pipeline.run(_MSGS, invoke_fn=_long)
    assert result.response == "XXXXX..."


@pytest.mark.asyncio
async def test_truncation_none_response_unchanged():
    pipeline = RequestPipeline([TruncationStep(max_chars=5)])
    result = await pipeline.run(_MSGS)  # no invoke_fn → response=None
    assert result.response is None


# ── TokenCounterStep ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_token_counter_sets_prompt_tokens():
    msgs = [{"role": "user", "content": "one two three"}]
    pipeline = RequestPipeline([TokenCounterStep()])
    result = await pipeline.run(msgs, invoke_fn=_invoke)
    assert result.metadata["estimated_prompt_tokens"] == int(3 * 1.3)


@pytest.mark.asyncio
async def test_token_counter_sets_response_tokens():
    async def _five(_m, _p):
        return "one two three four five"

    pipeline = RequestPipeline([TokenCounterStep()])
    result = await pipeline.run(_MSGS, invoke_fn=_five)
    assert result.metadata["estimated_response_tokens"] == int(5 * 1.3)


@pytest.mark.asyncio
async def test_token_counter_empty_messages():
    pipeline = RequestPipeline([TokenCounterStep()])
    result = await pipeline.run([], invoke_fn=_invoke)
    assert result.metadata["estimated_prompt_tokens"] == 0


# ── Step ordering ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_steps_applied_in_order():
    order: list[str] = []

    class MarkerStep(PipelineStep):
        def __init__(self, label: str):
            self.name = label

        async def process_request(self, ctx):
            order.append(self.name)
            return ctx

    pipeline = RequestPipeline([MarkerStep("a"), MarkerStep("b"), MarkerStep("c")])
    await pipeline.run(_MSGS, invoke_fn=_invoke)
    assert order == ["a", "b", "c"]


# ── Dynamic step management ───────────────────────────────────────────────────

def test_add_and_list_steps():
    pipeline = RequestPipeline()
    pipeline.add_step(PIIRedactionStep())
    pipeline.add_step(TruncationStep())
    assert pipeline.list_steps() == ["pii_redaction", "truncation"]


def test_remove_step_returns_true():
    pipeline = RequestPipeline([PIIRedactionStep()])
    removed = pipeline.remove_step("pii_redaction")
    assert removed is True
    assert pipeline.list_steps() == []


def test_remove_missing_step_returns_false():
    pipeline = RequestPipeline()
    assert pipeline.remove_step("nonexistent") is False


def test_clear_steps():
    pipeline = RequestPipeline([PIIRedactionStep(), TruncationStep()])
    pipeline.clear_steps()
    assert pipeline.list_steps() == []


# ── PipelineAbort ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_abort_in_request_phase_skips_invoke():
    invoked = []

    async def _inv(messages, provider):
        invoked.append(True)
        return "should not reach here"

    class AbortStep(PipelineStep):
        name = "aborter"

        async def process_request(self, ctx):
            raise PipelineAbort("blocked")

    pipeline = RequestPipeline([AbortStep()])
    result = await pipeline.run(_MSGS, invoke_fn=_inv)
    assert result.aborted is True
    assert result.abort_reason == "blocked"
    assert result.response is None
    assert invoked == []


@pytest.mark.asyncio
async def test_abort_in_response_phase():
    class AbortOnResponse(PipelineStep):
        name = "resp_aborter"

        async def process_request(self, ctx):
            return ctx

        async def process_response(self, ctx):
            raise PipelineAbort("output blocked")

    pipeline = RequestPipeline([AbortOnResponse()])
    result = await pipeline.run(_MSGS, invoke_fn=_invoke)
    assert result.aborted is True
    assert "output blocked" in result.abort_reason


# ── fail_fast ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fail_fast_raises_pipeline_error():
    class BrokenStep(PipelineStep):
        name = "broken"

        async def process_request(self, ctx):
            raise RuntimeError("boom")

    pipeline = RequestPipeline([BrokenStep()], fail_fast=True)
    with pytest.raises(PipelineError, match="boom"):
        await pipeline.run(_MSGS, invoke_fn=_invoke)


@pytest.mark.asyncio
async def test_fail_silent_continues_on_error():
    class BrokenStep(PipelineStep):
        name = "broken"

        async def process_request(self, ctx):
            raise RuntimeError("ignored")

    pipeline = RequestPipeline([BrokenStep()], fail_fast=False)
    result = await pipeline.run(_MSGS, invoke_fn=_invoke)
    assert result.response == "LLM response"  # invoke still runs


# ── Metrics ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_initial_zeros():
    pipeline = RequestPipeline()
    m = pipeline.metrics()
    assert m["total_runs"] == 0
    assert m["aborted_runs"] == 0
    assert m["step_count"] == 0


@pytest.mark.asyncio
async def test_metrics_after_run():
    pipeline = RequestPipeline([TokenCounterStep()])
    await pipeline.run(_MSGS, invoke_fn=_invoke)
    m = pipeline.metrics()
    assert m["total_runs"] == 1
    assert "token_counter" in m["per_step"]
    assert m["per_step"]["token_counter"]["invocations"] >= 1


@pytest.mark.asyncio
async def test_metrics_aborted_counted():
    class AbortStep(PipelineStep):
        name = "aborter"

        async def process_request(self, ctx):
            raise PipelineAbort("stop")

    pipeline = RequestPipeline([AbortStep()])
    await pipeline.run(_MSGS, invoke_fn=_invoke)
    m = pipeline.metrics()
    assert m["aborted_runs"] == 1


@pytest.mark.asyncio
async def test_metrics_reset():
    pipeline = RequestPipeline([TokenCounterStep()])
    await pipeline.run(_MSGS, invoke_fn=_invoke)
    pipeline.reset_metrics()
    m = pipeline.metrics()
    assert m["total_runs"] == 0
    assert m["per_step"] == {}


@pytest.mark.asyncio
async def test_metrics_shape():
    pipeline = RequestPipeline([TokenCounterStep()])
    await pipeline.run(_MSGS, invoke_fn=_invoke)
    m = pipeline.metrics()
    for key in ("total_runs", "aborted_runs", "step_count", "per_step"):
        assert key in m


# ── Multi-step integration ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pii_then_token_counter():
    msgs = [{"role": "user", "content": "Email: a@b.com one two three"}]

    async def _echo(messages, _p):
        return messages[-1]["content"]

    pipeline = RequestPipeline([PIIRedactionStep(), TokenCounterStep()])
    result = await pipeline.run(msgs, invoke_fn=_echo)
    # PII redacted in message passed to provider
    assert "a@b.com" not in result.messages[-1]["content"]
    assert "[EMAIL]" in result.messages[-1]["content"]
    # token counter fired
    assert "estimated_prompt_tokens" in result.metadata


@pytest.mark.asyncio
async def test_injection_then_pii_then_truncation():
    msgs = [{"role": "user", "content": "ssn: 111-22-3333"}]
    pipeline = RequestPipeline([
        PromptInjectionStep("System."),
        PIIRedactionStep(),
        TruncationStep(max_chars=5),
    ])

    async def _long(_m, _p):
        return "A" * 50

    result = await pipeline.run(msgs, invoke_fn=_long)
    assert result.messages[0]["content"] == "System."
    assert "[SSN]" in result.messages[1]["content"]
    assert len(result.response) == 6  # 5 + "…"


# ── Thread safety ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_runs_do_not_corrupt_metrics():
    pipeline = RequestPipeline([TokenCounterStep()])

    async def run_once():
        await pipeline.run(_MSGS, invoke_fn=_invoke)

    await asyncio.gather(*[run_once() for _ in range(20)])
    m = pipeline.metrics()
    assert m["total_runs"] == 20
