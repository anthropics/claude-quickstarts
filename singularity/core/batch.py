"""
Singularity — Batch Task Processor (Fáze 22).

Groups multiple task submissions into a single BatchJob. After calling
submit() to register the batch, run_batch() enqueues all tasks to the
provided TaskQueue and polls until every task reaches a terminal state.
"""
from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

log = structlog.get_logger()

_VALID_STATUSES = frozenset({"pending", "running", "completed", "failed", "cancelled"})
_TERMINAL = frozenset({"completed", "failed", "dlq"})
_POLL_INTERVAL = 0.2   # seconds between queue status polls
_DEFAULT_TIMEOUT = 300.0


@dataclass
class BatchTask:
    task: str
    user_id: str
    force_provider: str = ""
    priority: str = "NORMAL"
    # filled in after run_batch() enqueues
    task_id: str | None = None
    status: str = "pending"
    response: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task": self.task,
            "user_id": self.user_id,
            "force_provider": self.force_provider,
            "priority": self.priority,
            "status": self.status,
            "response": self.response,
            "error": self.error,
        }


@dataclass
class BatchJob:
    batch_id: str
    tasks: list[BatchTask]
    status: str = "pending"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    started_at: str | None = None
    completed_at: str | None = None

    @property
    def total(self) -> int:
        return len(self.tasks)

    @property
    def completed_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == "completed")

    @property
    def failed_count(self) -> int:
        return sum(1 for t in self.tasks if t.status in ("failed", "dlq"))

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "status": self.status,
            "total": self.total,
            "completed": self.completed_count,
            "failed": self.failed_count,
            "pending": self.total - self.completed_count - self.failed_count,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "tasks": [t.to_dict() for t in self.tasks],
        }


class BatchProcessor:
    """
    Thread-safe manager for batch task submission.

    Usage:
        bid = proc.submit([{"task": "...", "user_id": "u1"}, ...])
        result = await proc.run_batch(bid, task_queue)
    """

    def __init__(self) -> None:
        self._batches: dict[str, BatchJob] = {}
        self._lock = threading.Lock()

    def submit(self, tasks: list[dict[str, Any]]) -> str:
        """Register a batch. Returns batch_id. Does NOT enqueue tasks yet."""
        if not tasks:
            raise ValueError("tasks must not be empty")
        batch_tasks: list[BatchTask] = []
        for t in tasks:
            if not t.get("task"):
                raise ValueError("every task entry must have a non-empty 'task' field")
            if not t.get("user_id"):
                raise ValueError("every task entry must have a non-empty 'user_id' field")
            batch_tasks.append(BatchTask(
                task=t["task"],
                user_id=t["user_id"],
                force_provider=t.get("force_provider", ""),
                priority=t.get("priority", "NORMAL"),
            ))
        batch_id = str(uuid.uuid4())
        with self._lock:
            self._batches[batch_id] = BatchJob(batch_id=batch_id, tasks=batch_tasks)
        log.info("batch_submitted", batch_id=batch_id, task_count=len(batch_tasks))
        return batch_id

    def get_batch(self, batch_id: str) -> dict | None:
        with self._lock:
            b = self._batches.get(batch_id)
        return b.to_dict() if b else None

    def list_batches(self) -> list[dict]:
        with self._lock:
            items = list(self._batches.values())
        return [b.to_dict() for b in items]

    def cancel(self, batch_id: str) -> bool:
        """Cancel a pending batch. Returns False if not found or already running."""
        with self._lock:
            b = self._batches.get(batch_id)
            if b is None:
                return False
            if b.status not in ("pending",):
                return False
            b.status = "cancelled"
        log.info("batch_cancelled", batch_id=batch_id)
        return True

    def batch_count(self) -> int:
        with self._lock:
            return len(self._batches)

    async def run_batch(
        self,
        batch_id: str,
        queue: Any,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> dict:
        """
        Enqueue all tasks in the batch to *queue* and poll until all finish.
        Returns the final batch dict.
        Raises KeyError if batch_id not found; RuntimeError if already running/done.
        """
        with self._lock:
            b = self._batches.get(batch_id)
        if b is None:
            raise KeyError(f"No batch: {batch_id!r}")
        if b.status != "pending":
            raise RuntimeError(
                f"Batch {batch_id!r} cannot be run (status={b.status!r})"
            )

        with self._lock:
            b.status = "running"
            b.started_at = datetime.now(timezone.utc).isoformat()

        # Enqueue every task
        for bt in b.tasks:
            task_id = await queue.submit(
                task=bt.task,
                user_id=bt.user_id,
                force_provider=bt.force_provider,
                priority=bt.priority,
            )
            bt.task_id = task_id

        # Poll until all tasks reach terminal state
        deadline = asyncio.get_event_loop().time() + timeout
        pending = [bt for bt in b.tasks if bt.task_id is not None]

        while pending:
            if asyncio.get_event_loop().time() > deadline:
                for bt in pending:
                    bt.status = "failed"
                    bt.error = "timeout"
                break
            await asyncio.sleep(_POLL_INTERVAL)
            still_pending = []
            for bt in pending:
                info = queue.get_status(bt.task_id)
                if info is None:
                    bt.status = "failed"
                    bt.error = "task not found in queue"
                    continue
                state = info.get("status", "queued")
                if state in _TERMINAL:
                    bt.status = "completed" if state == "completed" else "failed"
                    bt.response = info.get("response", "")
                    bt.error = info.get("error", "")
                else:
                    still_pending.append(bt)
            pending = still_pending

        final_status = "completed" if b.failed_count == 0 else "failed"
        with self._lock:
            b.status = final_status
            b.completed_at = datetime.now(timezone.utc).isoformat()

        log.info("batch_finished", batch_id=batch_id, status=final_status,
                 completed=b.completed_count, failed=b.failed_count)
        return b.to_dict()
