"""
Singularity — Async task queue (Fáze 3 + 4 + 5).

Fáze 3: POST /task/async → task_id, GET /task/{id}/status|result
Fáze 4: webhook callback_url, dávkové odeslání
Fáze 5: prioritní fronta (CRITICAL > HIGH > NORMAL > LOW),
         event-based wait() bez busy-pollingu
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from core.graph import SingularityCore

log = structlog.get_logger()


class TaskStatus(str, Enum):
    QUEUED    = "queued"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


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
    status: TaskStatus = TaskStatus.QUEUED
    result: dict | None = None
    error: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None

    # Priority queue comparison — lower priority value = higher urgency
    def __lt__(self, other: QueuedTask) -> bool:
        return self.priority < other.priority


class TaskQueue:
    """
    In-memory prioritní fronta s jedním asyncio workerem.
    V produkci nahradit Celery / arq / Redis Streams.
    """

    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue[tuple[int, str]] = asyncio.PriorityQueue()
        self._tasks: dict[str, QueuedTask] = {}
        self._done_events: dict[str, asyncio.Event] = {}
        self._worker_task: asyncio.Task | None = None
        self._core: SingularityCore | None = None

    def start(self, core: SingularityCore) -> None:
        self._core = core
        self._worker_task = asyncio.create_task(self._worker(), name="task_queue_worker")
        log.info("task_queue_started")

    def stop(self) -> None:
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
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
    ) -> str:
        if isinstance(priority, str):
            priority = TaskPriority[priority.upper()]
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
        )
        self._tasks[task_id] = queued
        self._done_events[task_id] = asyncio.Event()
        await self._queue.put((priority.value, task_id))
        log.info("task_queued", task_id=task_id, user_id=user_id, priority=priority.name)
        return task_id

    def get_status(self, task_id: str) -> dict | None:
        t = self._tasks.get(task_id)
        if t is None:
            return None
        return {
            "task_id": t.task_id,
            "status": t.status,
            "priority": t.priority.name,
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

    async def wait(self, task_id: str, timeout: float = 60.0) -> dict | None:
        """Čeká na dokončení tasku (event-based, bez busy-pollingu). None = timeout/neznámý task."""
        t = self._tasks.get(task_id)
        if t is None:
            return None
        if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
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
        log.info("task_running", task_id=task_id, priority=t.priority.name)

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
            log.info("task_completed", task_id=task_id)
        except Exception as exc:
            t.error = str(exc)
            t.status = TaskStatus.FAILED
            t.completed_at = datetime.now(timezone.utc).isoformat()
            log.error("task_failed", task_id=task_id, error=str(exc))
        finally:
            event = self._done_events.get(task_id)
            if event:
                event.set()

        if t.callback_url:
            await self._fire_webhook(t)

    async def _fire_webhook(self, t: QueuedTask) -> None:
        """Pošle výsledek na callback_url; chyby neblokují systém."""
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
