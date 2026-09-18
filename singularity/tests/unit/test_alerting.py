"""
Tests for AlertManager (Fáze 20).
All offline — HTTP callbacks mocked via httpx patch.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.alerting import AlertManager, AlertCondition


@pytest.fixture
def mgr():
    return AlertManager()


def _add(mgr, condition="budget_exceeded", threshold=10.0, url="https://example.com/cb"):
    return mgr.create_alert("test-alert", condition, threshold, url)


# ── Creation ──────────────────────────────────────────────────────────────────

def test_create_returns_id(mgr):
    aid = _add(mgr)
    assert aid is not None and len(aid) == 36


def test_create_unknown_condition_raises(mgr):
    with pytest.raises(ValueError, match="Unknown condition"):
        mgr.create_alert("x", "bogus_condition", 1.0, "https://cb")


def test_create_empty_url_raises(mgr):
    with pytest.raises(ValueError, match="callback_url"):
        mgr.create_alert("x", "budget_exceeded", 1.0, "")


def test_alert_count(mgr):
    _add(mgr)
    _add(mgr)
    assert mgr.alert_count() == 2


# ── Retrieval ─────────────────────────────────────────────────────────────────

def test_get_alert_returns_dict(mgr):
    aid = _add(mgr, threshold=5.0)
    a = mgr.get_alert(aid)
    assert a["threshold"] == 5.0
    assert a["status"] == "active"
    assert a["fire_count"] == 0


def test_get_missing_returns_none(mgr):
    assert mgr.get_alert("ghost") is None


def test_list_alerts(mgr):
    _add(mgr, condition="budget_exceeded")
    _add(mgr, condition="latency_high")
    conditions = {a["condition"] for a in mgr.list_alerts()}
    assert "budget_exceeded" in conditions
    assert "latency_high" in conditions


# ── Status management ─────────────────────────────────────────────────────────

def test_mute_alert(mgr):
    aid = _add(mgr)
    assert mgr.set_status(aid, "muted") is True
    assert mgr.get_alert(aid)["status"] == "muted"


def test_unmute_alert(mgr):
    aid = _add(mgr)
    mgr.set_status(aid, "muted")
    mgr.set_status(aid, "active")
    assert mgr.get_alert(aid)["status"] == "active"


def test_set_status_invalid_raises(mgr):
    aid = _add(mgr)
    with pytest.raises(ValueError):
        mgr.set_status(aid, "disabled")


def test_set_status_missing_returns_false(mgr):
    assert mgr.set_status("ghost", "muted") is False


# ── Deletion ──────────────────────────────────────────────────────────────────

def test_delete_alert(mgr):
    aid = _add(mgr)
    assert mgr.delete_alert(aid) is True
    assert mgr.get_alert(aid) is None


def test_delete_missing_returns_false(mgr):
    assert mgr.delete_alert("ghost") is False


# ── Evaluate ─────────────────────────────────────────────────────────────────

async def test_evaluate_fires_when_at_threshold(mgr):
    aid = _add(mgr, threshold=10.0)
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        fired = await mgr.evaluate("budget_exceeded", 10.0)

    assert aid in fired
    assert mgr.get_alert(aid)["fire_count"] == 1
    assert mgr.get_alert(aid)["last_fired_at"] is not None


async def test_evaluate_does_not_fire_below_threshold(mgr):
    _add(mgr, threshold=10.0)
    fired = await mgr.evaluate("budget_exceeded", 9.99)
    assert fired == []


async def test_evaluate_skips_muted_alert(mgr):
    aid = _add(mgr, threshold=5.0)
    mgr.set_status(aid, "muted")
    fired = await mgr.evaluate("budget_exceeded", 100.0)
    assert fired == []


async def test_evaluate_unknown_condition_returns_empty(mgr):
    fired = await mgr.evaluate("nonexistent_condition", 999.0)
    assert fired == []


async def test_evaluate_feedback_rating_fires_when_low(mgr):
    aid = mgr.create_alert("low-rating", "feedback_rating_low", 2.5, "https://cb")
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=MagicMock())
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        fired_low = await mgr.evaluate("feedback_rating_low", 2.0)   # below → fires
        fired_high = await mgr.evaluate("feedback_rating_low", 3.0)  # above → no fire

    assert aid in fired_low
    assert fired_high == []


async def test_evaluate_multiple_matching_alerts(mgr):
    aid1 = _add(mgr, threshold=5.0, url="https://a.com")
    aid2 = _add(mgr, threshold=8.0, url="https://b.com")
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=MagicMock())
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        fired = await mgr.evaluate("budget_exceeded", 9.0)

    assert aid1 in fired
    assert aid2 in fired
    assert mock_client.post.await_count == 2


async def test_callback_failure_does_not_raise(mgr):
    aid = _add(mgr, threshold=1.0)
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("network error"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        # Should not raise even if callback fails
        fired = await mgr.evaluate("budget_exceeded", 5.0)

    assert aid in fired   # fire_count still incremented before HTTP attempt
