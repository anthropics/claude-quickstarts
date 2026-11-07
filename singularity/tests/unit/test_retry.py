"""Unit testy — retry + dead-letter queue (Fáze 6)."""
import asyncio

import pytest

from core.retry_policy import RetryPolicy
from core.task_queue import TaskPriority, TaskQueue, TaskStatus


def _make_queue(fail_times: int = 0):
    from unittest.mock import AsyncMock, MagicMock
    core = MagicMock()
    call_count = {"n": 0}

    async def _run(**kwargs):
        call_count["n"] += 1
        if call_count["n"] <= fail_times:
            raise RuntimeError(f"simulated failure #{call_count['n']}")
        return {"response": "OK", "provider_log": {}, "risk_score": 0.0}

    core.run = _run
    q = TaskQueue()
    return q, core, call_count


@pytest.mark.unit
def test_retry_policy_delay_increases():
    p = RetryPolicy(max_attempts=5, backoff_base=2.0, jitter=False)
    delays = [p.delay_for_attempt(i) for i in range(1, 5)]
    for i in range(len(delays) - 1):
        assert delays[i] < delays[i + 1]


@pytest.mark.unit
def test_retry_policy_max_backoff_cap():
    p = RetryPolicy(max_attempts=10, backoff_base=2.0, max_backoff=5.0, jitter=False)
    assert p.delay_for_attempt(10) == 5.0


@pytest.mark.unit
async def test_task_succeeds_after_retry():
    """Task selže 1× a pak projde — status = COMPLETED."""
    q, core, calls = _make_queue(fail_times=1)
    # max_attempts=2 → 1 retry
    from core.retry_policy import RetryPolicy
    q.start(core)
    task_id = await q.submit("task", user_id="alice", max_retries=2,
                             backoff_base=0.001, jitter=False)
    result = await asyncio.wait_for(q.wait(task_id, timeout=10.0), timeout=12.0)
    assert result is not None
    assert result["status"] == TaskStatus.COMPLETED
    assert calls["n"] == 2  # 1 selhání + 1 úspěch
    q.stop()


@pytest.mark.unit
async def test_task_moves_to_dlq_after_exhaustion():
    """Task selže víckrát než max_retries → přejde do DLQ."""
    q, core, calls = _make_queue(fail_times=99)
    q.start(core)
    task_id = await q.submit("task", user_id="bob", max_retries=2,
                             backoff_base=0.001, jitter=False)
    # Počkáme na DLQ
    for _ in range(200):
        await asyncio.sleep(0.05)
        dlq = q.get_dlq()
        if any(t["task_id"] == task_id for t in dlq):
            break
    dlq_ids = [t["task_id"] for t in q.get_dlq()]
    assert task_id in dlq_ids
    status = q.get_status(task_id)
    assert status["status"] == TaskStatus.DLQ
    q.stop()


@pytest.mark.unit
async def test_dlq_retry_requeues_task():
    """retry_from_dlq() vrátí task zpět do fronty."""
    q, core, calls = _make_queue(fail_times=99)
    q.start(core)
    task_id = await q.submit("task", user_id="carol", max_retries=1,
                             backoff_base=0.001, jitter=False)
    for _ in range(100):
        await asyncio.sleep(0.05)
        if any(t["task_id"] == task_id for t in q.get_dlq()):
            break
    # Opravíme mock — teď bude úspěšný
    from unittest.mock import AsyncMock
    core.run = AsyncMock(return_value={"response": "fixed", "provider_log": {}, "risk_score": 0.0})
    success = await q.retry_from_dlq(task_id)
    assert success is True
    result = await asyncio.wait_for(q.wait(task_id, timeout=5.0), timeout=6.0)
    assert result is not None
    assert result["status"] == TaskStatus.COMPLETED
    q.stop()
