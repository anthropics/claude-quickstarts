"""Unit testy — prioritní TaskQueue (Fáze 5)."""
import asyncio

import pytest

from core.task_queue import QueuedTask, TaskPriority, TaskQueue, TaskStatus


def _make_queue(fail: bool = False):
    from unittest.mock import AsyncMock, MagicMock
    core = MagicMock()
    if fail:
        core.run = AsyncMock(side_effect=RuntimeError("err"))
    else:
        core.run = AsyncMock(return_value={"response": "OK", "provider_log": {}, "risk_score": 0.0})
    q = TaskQueue()
    return q, core


@pytest.mark.unit
def test_task_priority_ordering():
    """CRITICAL < HIGH < NORMAL < LOW (nižší číslo = vyšší priorita)."""
    assert TaskPriority.CRITICAL < TaskPriority.HIGH
    assert TaskPriority.HIGH < TaskPriority.NORMAL
    assert TaskPriority.NORMAL < TaskPriority.LOW


@pytest.mark.unit
async def test_submit_with_priority_stored():
    q, core = _make_queue()
    q.start(core)
    task_id = await q.submit("hi", user_id="alice", priority=TaskPriority.HIGH)
    status = q.get_status(task_id)
    assert status["priority"] == "HIGH"
    q.stop()


@pytest.mark.unit
async def test_submit_priority_as_string():
    q, core = _make_queue()
    q.start(core)
    task_id = await q.submit("hi", user_id="bob", priority="critical")
    status = q.get_status(task_id)
    assert status["priority"] == "CRITICAL"
    q.stop()


@pytest.mark.unit
async def test_wait_returns_result_on_completion():
    """wait() vrátí výsledek bez busy-pollingu."""
    q, core = _make_queue()
    q.start(core)
    task_id = await q.submit("task", user_id="carol")
    result = await asyncio.wait_for(q.wait(task_id, timeout=5.0), timeout=6.0)
    assert result is not None
    assert result["status"] == TaskStatus.COMPLETED
    q.stop()


@pytest.mark.unit
async def test_wait_timeout_returns_none():
    """wait() vrátí None pokud task nedoběhne v čase."""
    q = TaskQueue()
    # Worker nespuštěn → task zůstane ve frontě
    task_id = str(__import__("uuid").uuid4())
    q._tasks[task_id] = QueuedTask(
        task_id=task_id, task="x", user_id="u", approved=False, force_provider=""
    )
    import asyncio as _asyncio
    q._done_events[task_id] = _asyncio.Event()
    result = await q.wait(task_id, timeout=0.05)
    assert result is None
