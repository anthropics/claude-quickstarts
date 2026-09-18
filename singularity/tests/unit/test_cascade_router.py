"""
Tests for CascadeRouter (Fáze 26).
All offline — mock Draft and Oracle providers, no external dependencies.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from hpc.cascade.cascade_router import (
    CascadeRouter,
    LLMResponse,
    _ConfidenceHeuristic,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_provider(content="OK", confidence=1.0, raise_exc=None):
    """Build a minimal mock async provider."""
    mock = MagicMock()
    if raise_exc:
        mock.ainvoke = AsyncMock(side_effect=raise_exc)
    else:
        resp = LLMResponse(content=content, provider="mock", confidence=confidence)
        mock.ainvoke = AsyncMock(return_value=resp)
    return mock


def _router(draft_conf=1.0, oracle_conf=1.0, threshold=0.7,
            draft_fail=None, oracle_fail=None):
    draft = _make_provider(content="draft answer", confidence=draft_conf, raise_exc=draft_fail)
    oracle = _make_provider(content="oracle answer", confidence=oracle_conf, raise_exc=oracle_fail)
    return CascadeRouter(draft, oracle, confidence_threshold=threshold), draft, oracle


# ── Validation ─────────────────────────────────────────────────────────────────

def test_invalid_threshold_zero():
    with pytest.raises(ValueError, match="confidence_threshold"):
        CascadeRouter(MagicMock(), MagicMock(), confidence_threshold=0.0)


def test_invalid_threshold_above_one():
    with pytest.raises(ValueError, match="confidence_threshold"):
        CascadeRouter(MagicMock(), MagicMock(), confidence_threshold=1.1)


def test_valid_threshold_boundary():
    cr = CascadeRouter(MagicMock(), MagicMock(), confidence_threshold=1.0)
    assert cr.confidence_threshold == 1.0


# ── Routing: Draft serves ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_draft_served_when_confident():
    cr, draft, oracle = _router(draft_conf=0.9, threshold=0.7)
    resp = await cr.route([{"role": "user", "content": "hello"}])
    assert resp.provider == "mock"   # draft provider tag
    assert resp.content == "draft answer"
    draft.ainvoke.assert_called_once()
    oracle.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_draft_served_at_exact_threshold():
    cr, draft, oracle = _router(draft_conf=0.7, threshold=0.7)
    resp = await cr.route([])
    assert resp.content == "draft answer"
    oracle.ainvoke.assert_not_called()


# ── Routing: Oracle escalation ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_oracle_escalated_when_draft_low_confidence():
    cr, draft, oracle = _router(draft_conf=0.5, threshold=0.7)
    resp = await cr.route([])
    assert resp.content == "oracle answer"
    oracle.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_oracle_escalation_metadata():
    cr, _, _ = _router(draft_conf=0.4, threshold=0.7)
    resp = await cr.route([])
    assert resp.metadata.get("escalation_reason") == "low_confidence"
    assert "draft_confidence" in resp.metadata


# ── Routing: Draft failure fallback ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_oracle_fallback_on_draft_exception():
    cr, draft, oracle = _router(draft_fail=RuntimeError("draft crashed"))
    resp = await cr.route([])
    assert resp.content == "oracle answer"
    oracle.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_oracle_fallback_metadata_reason():
    cr, _, _ = _router(draft_fail=RuntimeError("x"))
    resp = await cr.route([])
    assert resp.metadata.get("escalation_reason") == "draft_failed"


# ── Metrics ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_initial():
    cr, _, _ = _router()
    m = cr.metrics()
    assert m["total_requests"] == 0
    assert m["draft_served"] == 0
    assert m["oracle_escalations"] == 0


@pytest.mark.asyncio
async def test_metrics_draft_served():
    cr, _, _ = _router(draft_conf=0.9, threshold=0.5)
    await cr.route([])
    await cr.route([])
    m = cr.metrics()
    assert m["total_requests"] == 2
    assert m["draft_served"] == 2
    assert m["draft_hit_rate"] == 1.0


@pytest.mark.asyncio
async def test_metrics_oracle_escalations():
    cr, _, _ = _router(draft_conf=0.3, threshold=0.7)
    await cr.route([])
    m = cr.metrics()
    assert m["oracle_escalations"] == 1
    assert m["oracle_fallbacks"] == 0


@pytest.mark.asyncio
async def test_metrics_oracle_fallback():
    cr, _, _ = _router(draft_fail=Exception("boom"))
    await cr.route([])
    m = cr.metrics()
    assert m["oracle_fallbacks"] == 1
    assert m["oracle_escalations"] == 0


@pytest.mark.asyncio
async def test_metrics_reset():
    cr, _, _ = _router(draft_conf=0.9, threshold=0.5)
    await cr.route([])
    cr.reset_metrics()
    m = cr.metrics()
    assert m["total_requests"] == 0
    assert m["draft_served"] == 0


# ── Confidence heuristic ───────────────────────────────────────────────────────

def test_heuristic_high_confidence_full_answer():
    score = _ConfidenceHeuristic.score("The answer is definitely 42 because of the laws of physics.")
    assert score >= 0.9


def test_heuristic_low_confidence_hedged():
    score = _ConfidenceHeuristic.score("I'm not sure, it depends on the context.")
    assert score < 0.7


def test_heuristic_short_answer_penalty():
    score = _ConfidenceHeuristic.score("Yes.")
    assert score < 0.7


def test_heuristic_range():
    for text in ["hello world", "I don't know if I'm uncertain about this."]:
        s = _ConfidenceHeuristic.score(text)
        assert 0.0 <= s <= 1.0
