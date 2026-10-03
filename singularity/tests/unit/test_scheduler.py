"""
Tests for TaskScheduler (Fáze 15).
All tests are offline — TaskQueue is replaced by a lightweight mock.
"""
import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.scheduler import TaskScheduler


@pytest.fixture
def mock_queue():
    q = MagicMock()
    q.submit = AsyncMock(return_value="task-123")
    return q


@pytest.fixture
def sched():
    return TaskScheduler()


def test_add_job_returns_job_id(sched):
    job_id = sched.add_job("test task", "user1", interval_s=60)
    assert job_id is not None
    assert len(job_id) == 36  # UUID


def test_add_job_invalid_interval(sched):
    with pytest.raises(ValueError):
        sched.add_job("task", "user1", interval_s=0.5)


def test_list_jobs_empty(sched):
    assert sched.list_jobs() == []


def test_list_jobs_contains_added_job(sched):
    sched.add_job("task A", "alice", interval_s=30)
    jobs = sched.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["task"] == "task A"
    assert jobs[0]["user_id"] == "alice"
    assert jobs[0]["interval_s"] == 30


def test_remove_job_returns_true(sched):
    job_id = sched.add_job("task", "user1", interval_s=10)
    assert sched.remove_job(job_id) is True
    assert sched.job_count() == 0


def test_remove_nonexistent_job_returns_false(sched):
    assert sched.remove_job("no-such-id") is False


def test_get_job_returns_dict(sched):
    job_id = sched.add_job("task B", "bob", interval_s=120, priority="HIGH")
    job = sched.get_job(job_id)
    assert job is not None
    assert job["priority"] == "HIGH"
    assert job["run_count"] == 0


def test_get_job_missing_returns_none(sched):
    assert sched.get_job("missing") is None


def test_enable_disable_job(sched):
    job_id = sched.add_job("task", "u1", interval_s=60)
    assert sched.enable_job(job_id, False) is True
    job = sched.get_job(job_id)
    assert job["enabled"] is False
    sched.enable_job(job_id, True)
    assert sched.get_job(job_id)["enabled"] is True


async def test_tick_fires_due_job(sched, mock_queue):
    sched._queue = mock_queue
    job_id = sched.add_job("recurring task", "user1", interval_s=100)
    # Force next_run_at to be in the past
    with sched._lock:
        sched._jobs[job_id].next_run_at = time.monotonic() - 1

    await sched._tick()

    mock_queue.submit.assert_awaited_once()
    call_kwargs = mock_queue.submit.call_args.kwargs
    assert call_kwargs["task"] == "recurring task"
    assert call_kwargs["user_id"] == "user1"

    job = sched.get_job(job_id)
    assert job["run_count"] == 1
    assert job["last_task_id"] == "task-123"


async def test_tick_skips_future_job(sched, mock_queue):
    sched._queue = mock_queue
    job_id = sched.add_job("future task", "user2", interval_s=9999)
    # next_run_at is far in the future by default

    await sched._tick()

    mock_queue.submit.assert_not_awaited()
    assert sched.get_job(job_id)["run_count"] == 0


async def test_tick_skips_disabled_job(sched, mock_queue):
    sched._queue = mock_queue
    job_id = sched.add_job("disabled", "user3", interval_s=1)
    with sched._lock:
        sched._jobs[job_id].next_run_at = time.monotonic() - 1
    sched.enable_job(job_id, False)

    await sched._tick()

    mock_queue.submit.assert_not_awaited()
