"""
Singularity — Async task queue (Fáze 3 + 4 + 5 + 6).

Fáze 3: POST /task/async → task_id, GET /task/{id}/status|result
Fáze 4: webhook callback_url, dávkové odeslání
Fáze 5: prioritní fronta (CRITICAL > HIGH > NORMAL > LOW), event-based wait()
Fáze 6: retry s exponenciálním backoffem, dead-letter queue (DLQ)
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

import structlog

from core.retry_policy import NO_RETRY, RetryPolicy

if TYPE_CHECKING:
    from core.audit_log import AuditLog
    from core.graph import SingularityCore
    from core.task_events import TaskEventBus

log = structlog.get_logger()


class TaskStatus(str, Enum):
    QUEUED    = "queued"
    RUNNING   = "running"
    RETRYING  = "retrying"   # Fáze 6
    COMPLETED = "completed"
    FAILED    = "failed"
    DLQ       = "dlq"        # Fáze 6: dead-letter


class TaskPriority(int, Enum):
    CRITICAL = 0
    HIGH     = 1
    NORMAL   = 2
    LOW      = 3


@dataclass
class QueuedTask:
    task_id: str
    task: str
    user_id: str
    approved: bool
    force_provider: str
    session_context: str = ""
    callback_url: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    retry_policy: RetryPolicy = field(default_factory=lambda: NO_RETRY)
    attempt: int = 0             # kolikátý pokus právě běží (0-indexed)
    status: TaskStatus = TaskStatus.QUEUED
    result: dict | None = None
    error: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None

    def __lt__(self, other: QueuedTask) -> bool:
        return self.priority < other.priority


class TaskQueue:
    """
    In-memory prioritní fronta s retry + DLQ + multi-worker (Fáze 7).
    V produkci nahradit Celery / arq / Redis Streams.
    """

    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue[tuple[int, str]] = asyncio.PriorityQueue()
        self._tasks: dict[str, QueuedTask] = {}
        self._dlq: dict[str, QueuedTask] = {}
        self._done_events: dict[str, asyncio.Event] = {}
        self._worker_tasks: list[asyncio.Task] = []
        self._core: SingularityCore | None = None
        self._audit: AuditLog | None = None
        self._bus: TaskEventBus | None = None

    def start(
        self,
        core: SingularityCore,
        audit: AuditLog | None = None,
        num_workers: int = 1,
        event_bus: TaskEventBus | None = None,
    ) -> None:
        self._core = core
        self._audit = audit
        self._bus = event_bus
        self._worker_tasks = [
            asyncio.create_task(self._worker(), name=f"task_queue_worker_{i}")
            for i in range(max(1, num_workers))
        ]
        log.info("task_queue_started", num_workers=len(self._worker_tasks))

    def stop(self) -> None:
        for wt in self._worker_tasks:
            if not wt.done():
                wt.cancel()
        self._worker_tasks.clear()
        log.info("task_queue_stopped")

    async def submit(
        self,
        task: str,
        user_id: str,
        approved: bool = False,
        force_provider: str = "",
        session_context: str = "",
        callback_url: str = "",
        priority: TaskPriority | str = TaskPriority.NORMAL,
        max_retries: int = 0,
    ) -> str:
        if isinstance(priority, str):
            priority = TaskPriority[priority.upper()]
        retry_policy = RetryPolicy(max_attempts=max(1, max_retries + 1))
        task_id = str(uuid.uuid4())
        queued = QueuedTask(
            task_id=task_id,
            task=task,
            user_id=user_id,
            approved=approved,
            force_provider=force_provider,
            session_context=session_context,
            callback_url=callback_url,
            priority=priority,
            retry_policy=retry_policy,
        )
        self._tasks[task_id] = queued
        self._done_events[task_id] = asyncio.Event()
        await self._queue.put((priority.value, task_id))
        log.info("task_queued", task_id=task_id, user_id=user_id, priority=priority.name)
        self._audit_record("task_submitted", user_id, task_id,
                           priority=priority.name, max_retries=max_retries)
        return task_id

    async def retry_from_dlq(self, task_id: str) -> bool:
        """Přesune task z DLQ zpět do fronty. Vrátí True pokud úspěch."""
        t = self._dlq.pop(task_id, None)
        if t is None:
            return False
        t.attempt = 0
        t.status = TaskStatus.QUEUED
        t.error = None
        t.completed_at = None
        self._done_events[task_id] = asyncio.Event()
        self._tasks[task_id] = t
        await self._queue.put((t.priority.value, task_id))
        self._audit_record("task_dlq_retried", t.user_id, task_id)
        log.info("task_dlq_retried", task_id=task_id)
        return True

    def get_status(self, task_id: str) -> dict | None:
        t = self._tasks.get(task_id) or self._dlq.get(task_id)
        if t is None:
            return None
        return {
            "task_id": t.task_id,
            "status": t.status,
            "priority": t.priority.name,
            "attempt": t.attempt,
            "max_attempts": t.retry_policy.max_attempts,
            "user_id": t.user_id,
            "created_at": t.created_at,
            "completed_at": t.completed_at,
            "error": t.error,
        }

    def get_result(self, task_id: str) -> dict | None:
        t = self._tasks.get(task_id)
        if t is None:
            return None
        return {
            "task_id": t.task_id,
            "status": t.status,
            "result": t.result,
            "error": t.error,
        }

    def get_dlq(self) -> list[dict]:
        return [self.get_status(tid) for tid in self._dlq]

    async def wait(self, task_id: str, timeout: float = 60.0) -> dict | None:
        """Čeká na dokončení tasku (event-based). None = timeout/neznámý."""
        t = self._tasks.get(task_id)
        if t is None:
            return None
        if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.DLQ):
            return self.get_result(task_id)
        event = self._done_events.get(task_id)
        if event is None:
            return None
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        return self.get_result(task_id)

    def queue_size(self) -> int:
        return self._queue.qsize()

    async def _publish(self, t: QueuedTask) -> None:
        if self._bus is None:
            return
        await self._bus.publish(t.task_id, {
            "task_id": t.task_id,
            "status": t.status,
            "attempt": t.attempt,
            "error": t.error,
            "result": t.result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _worker(self) -> None:
        while True:
            try:
                _priority_val, task_id = await self._queue.get()
                await self._process(task_id)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("task_queue_worker_error", error=str(exc))

    async def _process(self, task_id: str) -> None:
        assert self._core is not None
        t = self._tasks[task_id]
        t.status = TaskStatus.RUNNING
        await self._publish(t)
        log.info("task_running", task_id=task_id, attempt=t.attempt, priority=t.priority.name)

        try:
            result = await self._core.run(
                task=t.task,
                user_id=t.user_id,
                session_id=task_id,
                approved=t.approved,
                force_provider=t.force_provider,
                session_context=t.session_context,
            )
            t.result = result
            t.status = TaskStatus.COMPLETED
            t.completed_at = datetime.now(timezone.utc).isoformat()
            await self._publish(t)
            log.info("task_completed", task_id=task_id, attempt=t.attempt)
            self._audit_record("task_completed", t.user_id, task_id, attempt=t.attempt)

        except Exception as exc:
            t.error = str(exc)
            t.attempt += 1
            if t.attempt < t.retry_policy.max_attempts:
                delay = t.retry_policy.delay_for_attempt(t.attempt)
                t.status = TaskStatus.RETRYING
                await self._publish(t)
                log.warning("task_retrying", task_id=task_id, attempt=t.attempt, delay_s=delay)
                self._audit_record("task_retried", t.user_id, task_id,
                                   attempt=t.attempt, error=str(exc), delay_s=delay)
                await asyncio.sleep(delay)
                t.status = TaskStatus.QUEUED
                await self._queue.put((t.priority.value, task_id))
                return  # don't signal done_event yet
            else:
                t.status = TaskStatus.FAILED
                t.completed_at = datetime.now(timezone.utc).isoformat()
                await self._publish(t)
                log.error("task_failed", task_id=task_id, attempt=t.attempt, error=str(exc))
                self._audit_record("task_failed", t.user_id, task_id,
                                   attempt=t.attempt, error=str(exc))
                if t.retry_policy.max_attempts > 1:
                    t.status = TaskStatus.DLQ
                    self._dlq[task_id] = t
                    del self._tasks[task_id]
                    log.warning("task_moved_to_dlq", task_id=task_id)
                    self._audit_record("task_dlq", t.user_id, task_id, attempts=t.attempt)

        finally:
            if t.status not in (TaskStatus.QUEUED, TaskStatus.RETRYING):
                event = self._done_events.get(task_id)
                if event:
                    event.set()

        if t.callback_url:
            await self._fire_webhook(t)

    async def _fire_webhook(self, t: QueuedTask) -> None:
        try:
            import httpx

            payload = {
                "task_id": t.task_id,
                "status": t.status,
                "result": t.result,
                "error": t.error,
                "completed_at": t.completed_at,
            }
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(t.callback_url, json=payload)
            log.info("webhook_sent", task_id=t.task_id, status_code=resp.status_code)
        except Exception as exc:
            log.warning("webhook_failed", task_id=t.task_id, url=t.callback_url, error=str(exc))

    def _audit_record(self, event_type: str, user_id: str, task_id: str | None = None, **details) -> None:
        if self._audit is not None:
            self._audit.record(event_type, user_id, task_id=task_id, **details)
