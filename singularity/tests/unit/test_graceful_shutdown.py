"""
Tests for GracefulShutdown (Fáze 9).
"""
import asyncio

import pytest

from core.graceful_shutdown import GracefulShutdown
from core.task_queue import TaskQueue


class _FakeCore:
    async def run(self, task: str, user_id: str, session_id: str, **_):
        await asyncio.sleep(0.01)
        return {"response": "ok", "provider_log": {}, "risk_score": 0.0}


@pytest.mark.asyncio
async def test_initially_not_draining():
    q = TaskQueue()
    gs = GracefulShutdown(q)
    assert not gs.is_draining()


@pytest.mark.asyncio
async def test_drain_sets_flag():
    q = TaskQueue()
    gs = GracefulShutdown(q, timeout_s=1.0)
    await gs.drain()
    assert gs.is_draining()


@pytest.mark.asyncio
async def test_drain_stops_workers():
    q = TaskQueue()
    q.start(_FakeCore(), num_workers=2)
    assert len(q._worker_tasks) == 2
    gs = GracefulShutdown(q, timeout_s=2.0)
    await gs.drain()
    assert all(wt.done() for wt in q._worker_tasks)


@pytest.mark.asyncio
async def test_drain_is_idempotent():
    q = TaskQueue()
    gs = GracefulShutdown(q, timeout_s=1.0)
    await gs.drain()
    await gs.drain()  # second call should return immediately without error
    assert gs.is_draining()


@pytest.mark.asyncio
async def test_drain_waits_for_submitted_task():
    q = TaskQueue()
    q.start(_FakeCore(), num_workers=1)
    task_id = await q.submit("t1", user_id="u")
    gs = GracefulShutdown(q, timeout_s=5.0)
    await gs.drain()
    from core.task_queue import TaskStatus
    result = q.get_result(task_id)
    assert result is not None
    assert result["status"] == TaskStatus.COMPLETED
