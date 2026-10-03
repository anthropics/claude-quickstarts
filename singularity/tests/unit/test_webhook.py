"""Unit testy — webhook callback po dokončení async tasku (Fáze 4)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.task_queue import QueuedTask, TaskQueue, TaskStatus


def _make_queue(fail: bool = False) -> tuple[TaskQueue, MagicMock]:
    core = MagicMock()
    if fail:
        core.run = AsyncMock(side_effect=RuntimeError("provider down"))
    else:
        core.run = AsyncMock(return_value={
            "response": "OK",
            "provider_log": {"plan": "claude"},
            "risk_score": 0.0,
        })
    q = TaskQueue()
    return q, core


@pytest.mark.unit
async def test_webhook_fired_on_completion():
    """Webhook se spustí po úspěšném dokončení tasku."""
    import asyncio

    q, core = _make_queue()
    q.start(core)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        task_id = await q.submit("Test", user_id="alice", callback_url="http://example.com/cb")
        for _ in range(50):
            await asyncio.sleep(0.01)
            if q.get_status(task_id)["status"] == TaskStatus.COMPLETED:
                break

        assert q.get_status(task_id)["status"] == TaskStatus.COMPLETED
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://example.com/cb"
        payload = call_args[1]["json"]
        assert payload["task_id"] == task_id
        assert payload["status"] == TaskStatus.COMPLETED

    q.stop()


@pytest.mark.unit
async def test_webhook_fired_on_failure():
    """Webhook se spustí i při selhání tasku."""
    import asyncio

    q, core = _make_queue(fail=True)
    q.start(core)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        task_id = await q.submit("Fail", user_id="bob", callback_url="http://example.com/cb")
        for _ in range(50):
            await asyncio.sleep(0.01)
            if q.get_status(task_id)["status"] in (TaskStatus.FAILED, TaskStatus.COMPLETED):
                break

        assert q.get_status(task_id)["status"] == TaskStatus.FAILED
        mock_client.post.assert_called_once()
        payload = mock_client.post.call_args[1]["json"]
        assert payload["status"] == TaskStatus.FAILED
        assert payload["error"] is not None

    q.stop()


@pytest.mark.unit
async def test_no_webhook_without_callback_url():
    """Pokud není callback_url, webhook se nespustí."""
    import asyncio

    q, core = _make_queue()
    q.start(core)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        task_id = await q.submit("NoWebhook", user_id="carol")
        for _ in range(50):
            await asyncio.sleep(0.01)
            if q.get_status(task_id)["status"] == TaskStatus.COMPLETED:
                break

        assert q.get_status(task_id)["status"] == TaskStatus.COMPLETED
        mock_client_cls.assert_not_called()

    q.stop()
