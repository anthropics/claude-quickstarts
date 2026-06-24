"""
Singularity — Async task queue (Fáze 3).

Umožňuje odeslat úkol asynchronně a sledovat jeho stav:
  POST /task/async  → vrátí task_id okamžitě
  GET  /task/{id}/status → QUEUED | RUNNING | COMPLETED | FAILED
  GET  /task/{id}/result → výsledek po dokončení
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


@dataclass
class QueuedTask:
    task_id: str
    task: str
    user_id: str
    approved: bool
    force_provider: str
    session_context: str = ""
    status: TaskStatus = TaskStatus.QUEUED
    result: dict | None = None
    error: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None


class TaskQueue:
    """
    Jednoduchá in-memory fronta s jedním workerem.
    V produkci nahradit Celery / arq / Redis Streams.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._tasks: dict[str, QueuedTask] = {}
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
    ) -> str:
        task_id = str(uuid.uuid4())
        queued = QueuedTask(
            task_id=task_id,
            task=task,
            user_id=user_id,
            approved=approved,
            force_provider=force_provider,
            session_context=session_context,
        )
        self._tasks[task_id] = queued
        await self._queue.put(task_id)
        log.info("task_queued", task_id=task_id, user_id=user_id)
        return task_id

    def get_status(self, task_id: str) -> dict | None:
        t = self._tasks.get(task_id)
        if t is None:
            return None
        return {
            "task_id": t.task_id,
            "status": t.status,
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

    def queue_size(self) -> int:
        return self._queue.qsize()

    async def _worker(self) -> None:
        while True:
            try:
                task_id = await self._queue.get()
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
        log.info("task_running", task_id=task_id)

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
