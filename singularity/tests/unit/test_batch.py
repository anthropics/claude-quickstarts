"""
Tests for BatchProcessor (Fáze 22).
All offline — TaskQueue mocked with AsyncMock.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.batch import BatchProcessor


@pytest.fixture
def proc():
    return BatchProcessor()


def _tasks(n=2):
    return [{"task": f"task-{i}", "user_id": f"u{i}"} for i in range(n)]


def _mock_queue(statuses: list[str]) -> MagicMock:
    """
    Build a mock queue whose submit() returns sequential UUIDs and
    get_status() cycles through the provided statuses list on successive calls.
    """
    ids = [f"tid-{i}" for i in range(len(statuses))]
    submit_results = iter(ids)

    status_map = {ids[i]: statuses[i] for i in range(len(statuses))}

    q = MagicMock()
    q.submit = AsyncMock(side_effect=lambda **kw: next(submit_results))  # type: ignore[arg-type]
    q.get_status = MagicMock(
        side_effect=lambda tid: {"status": status_map.get(tid, "completed"), "response": "ok"}
    )
    return q


# ── Submit ────────────────────────────────────────────────────────────────────

def test_submit_returns_uuid(proc):
    bid = proc.submit(_tasks())
    assert bid is not None and len(bid) == 36


def test_submit_empty_raises(proc):
    with pytest.raises(ValueError, match="empty"):
        proc.submit([])


def test_submit_missing_task_field_raises(proc):
    with pytest.raises(ValueError, match="task"):
        proc.submit([{"user_id": "u1"}])


def test_submit_missing_user_id_raises(proc):
    with pytest.raises(ValueError, match="user_id"):
        proc.submit([{"task": "do x"}])


def test_batch_count(proc):
    proc.submit(_tasks(1))
    proc.submit(_tasks(1))
    assert proc.batch_count() == 2


# ── Retrieval ─────────────────────────────────────────────────────────────────

def test_get_batch_returns_dict(proc):
    bid = proc.submit(_tasks(3))
    b = proc.get_batch(bid)
    assert b["batch_id"] == bid
    assert b["total"] == 3
    assert b["status"] == "pending"


def test_get_batch_missing_returns_none(proc):
    assert proc.get_batch("ghost") is None


def test_list_batches(proc):
    proc.submit(_tasks(1))
    proc.submit(_tasks(2))
    assert len(proc.list_batches()) == 2


# ── Cancel ────────────────────────────────────────────────────────────────────

def test_cancel_pending_batch(proc):
    bid = proc.submit(_tasks())
    assert proc.cancel(bid) is True
    assert proc.get_batch(bid)["status"] == "cancelled"


def test_cancel_missing_returns_false(proc):
    assert proc.cancel("ghost") is False


# ── Run batch ─────────────────────────────────────────────────────────────────

async def test_run_batch_all_completed(proc):
    bid = proc.submit(_tasks(2))
    q = _mock_queue(["completed", "completed"])
    result = await proc.run_batch(bid, q)
    assert result["status"] == "completed"
    assert result["completed"] == 2
    assert result["failed"] == 0


async def test_run_batch_one_failed(proc):
    bid = proc.submit(_tasks(2))
    q = _mock_queue(["completed", "failed"])
    result = await proc.run_batch(bid, q)
    assert result["status"] == "failed"
    assert result["completed"] == 1
    assert result["failed"] == 1


async def test_run_batch_sets_started_and_completed_at(proc):
    bid = proc.submit(_tasks(1))
    q = _mock_queue(["completed"])
    result = await proc.run_batch(bid, q)
    assert result["started_at"] is not None
    assert result["completed_at"] is not None


async def test_run_batch_missing_raises_key_error(proc):
    q = MagicMock()
    with pytest.raises(KeyError):
        await proc.run_batch("ghost", q)


async def test_run_batch_already_running_raises(proc):
    bid = proc.submit(_tasks(1))
    q = _mock_queue(["completed"])
    await proc.run_batch(bid, q)
    with pytest.raises(RuntimeError, match="cannot be run"):
        await proc.run_batch(bid, q)


async def test_run_batch_cancelled_raises(proc):
    bid = proc.submit(_tasks(1))
    proc.cancel(bid)
    q = MagicMock()
    with pytest.raises(RuntimeError, match="cannot be run"):
        await proc.run_batch(bid, q)


async def test_run_batch_dlq_counts_as_failed(proc):
    bid = proc.submit(_tasks(2))
    q = _mock_queue(["completed", "dlq"])
    result = await proc.run_batch(bid, q)
    assert result["failed"] == 1
    assert result["status"] == "failed"


async def test_run_batch_task_ids_filled_in(proc):
    bid = proc.submit(_tasks(2))
    q = _mock_queue(["completed", "completed"])
    result = await proc.run_batch(bid, q)
    task_ids = [t["task_id"] for t in result["tasks"]]
    assert task_ids == ["tid-0", "tid-1"]
