"""Unit testy — TaskQueue async fronta (Fáze 3)."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.task_queue import TaskQueue, TaskStatus


def _make_queue(fail: bool = False) -> tuple[TaskQueue, MagicMock]:
    core = MagicMock()
    if fail:
        core.run = AsyncMock(side_effect=RuntimeError("provider down"))
    else:
        core.run = AsyncMock(return_value={
            "response": "Odpověď",
            "provider_log": {"plan": "claude"},
            "risk_score": 0.1,
        })
    q = TaskQueue()
    return q, core


@pytest.mark.unit
async def test_submit_returns_task_id():
    q, core = _make_queue()
    q.start(core)
    task_id = await q.submit("Test úkol", user_id="alice")
    assert isinstance(task_id, str) and len(task_id) > 0
    q.stop()


@pytest.mark.unit
async def test_status_queued_immediately():
    q, core = _make_queue()
    # Nespouštíme worker — task zůstane ve frontě
    task_id = str(__import__("uuid").uuid4())
    from core.task_queue import QueuedTask
    q._tasks[task_id] = QueuedTask(
        task_id=task_id, task="x", user_id="u", approved=False, force_provider=""
    )
    status = q.get_status(task_id)
    assert status["status"] == TaskStatus.QUEUED


@pytest.mark.unit
async def test_completed_after_processing(monkeypatch):
    """Worker zpracuje task a přejde do COMPLETED stavu."""
    import asyncio

    q, core = _make_queue()
    q.start(core)
    task_id = await q.submit("Zpracuj", user_id="bob")
    # Počkáme až worker task zpracuje
    for _ in range(50):
        await asyncio.sleep(0.01)
        if q.get_status(task_id)["status"] == TaskStatus.COMPLETED:
            break
    assert q.get_status(task_id)["status"] == TaskStatus.COMPLETED
    result = q.get_result(task_id)
    assert result["result"]["response"] == "Odpověď"
    q.stop()


@pytest.mark.unit
async def test_failed_task_status(monkeypatch):
    """Při výjimce přejde task do FAILED stavu."""
    import asyncio

    q, core = _make_queue(fail=True)
    q.start(core)
    task_id = await q.submit("Selže", user_id="eve")
    for _ in range(50):
        await asyncio.sleep(0.01)
        if q.get_status(task_id)["status"] in (TaskStatus.FAILED, TaskStatus.COMPLETED):
            break
    assert q.get_status(task_id)["status"] == TaskStatus.FAILED
    assert q.get_result(task_id)["error"] is not None
    q.stop()


@pytest.mark.unit
async def test_unknown_task_id_returns_none():
    q = TaskQueue()
    assert q.get_status("neexistuje") is None
    assert q.get_result("neexistuje") is None
