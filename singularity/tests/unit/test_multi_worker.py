"""
Tests for multi-worker TaskQueue (Fáze 7).
"""
import asyncio

import pytest

from core.task_queue import TaskQueue, TaskStatus


class _FakeCore:
    """Fake SingularityCore that records which tasks it processed."""

    def __init__(self, delay: float = 0.0):
        self._delay = delay
        self.processed: list[str] = []

    async def run(self, task: str, user_id: str, session_id: str, **_kwargs):
        await asyncio.sleep(self._delay)
        self.processed.append(session_id)
        return {"response": f"ok:{task}", "provider_log": {}, "risk_score": 0.0}


@pytest.fixture()
async def queue():
    q = TaskQueue()
    yield q
    q.stop()


@pytest.mark.asyncio
async def test_multi_worker_all_tasks_complete():
    """All submitted tasks complete when using 3 workers."""
    fake = _FakeCore(delay=0.01)
    q = TaskQueue()
    q.start(fake, num_workers=3)

    ids = [await q.submit(f"task-{i}", user_id="u") for i in range(6)]

    results = await asyncio.gather(*[q.wait(tid, timeout=5.0) for tid in ids])
    q.stop()

    assert all(r is not None for r in results)
    assert all(r["status"] == TaskStatus.COMPLETED for r in results)


@pytest.mark.asyncio
async def test_multi_worker_concurrent_processing():
    """With N workers and N slow tasks, total time < N * task_time (true parallelism)."""
    WORKERS = 3
    TASKS = 3
    TASK_DELAY = 0.15

    fake = _FakeCore(delay=TASK_DELAY)
    q = TaskQueue()
    q.start(fake, num_workers=WORKERS)

    import time
    t0 = time.monotonic()
    ids = [await q.submit(f"slow-{i}", user_id="u") for i in range(TASKS)]
    await asyncio.gather(*[q.wait(tid, timeout=5.0) for tid in ids])
    elapsed = time.monotonic() - t0
    q.stop()

    # Serial would take TASKS * TASK_DELAY; parallel should be much less
    assert elapsed < TASKS * TASK_DELAY * 0.9, f"Took {elapsed:.2f}s — may not be parallel"


@pytest.mark.asyncio
async def test_single_worker_is_default():
    """start() with default num_workers=1 still processes all tasks."""
    fake = _FakeCore()
    q = TaskQueue()
    q.start(fake)  # num_workers defaults to 1

    ids = [await q.submit(f"t{i}", user_id="u") for i in range(3)]
    results = await asyncio.gather(*[q.wait(tid, timeout=5.0) for tid in ids])
    q.stop()

    assert all(r is not None for r in results)
