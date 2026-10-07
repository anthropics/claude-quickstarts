"""
Singularity — Cron-style task scheduler (Fáze 15).

Submits recurring tasks to the async TaskQueue on a configurable interval.
The scheduler runs a single asyncio.Task that ticks every second and fires
any job whose next_run_at has elapsed.

No external dependencies — uses stdlib only.
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from core.task_queue import TaskQueue

log = structlog.get_logger()

_TICK_S = 1.0   # polling interval — sub-second scheduling is not a goal


@dataclass
class ScheduledJob:
    job_id: str
    task: str
    user_id: str
    interval_s: float
    force_provider: str = ""
    priority: str = "NORMAL"
    max_retries: int = 0
    enabled: bool = True
    run_count: int = 0
    last_task_id: str | None = None
    last_run_at: float | None = None    # monotonic
    next_run_at: float = field(default_factory=time.monotonic)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "task": self.task,
            "user_id": self.user_id,
            "interval_s": self.interval_s,
            "force_provider": self.force_provider,
            "priority": self.priority,
            "max_retries": self.max_retries,
            "enabled": self.enabled,
            "run_count": self.run_count,
            "last_task_id": self.last_task_id,
            "created_at": self.created_at,
        }


class TaskScheduler:
    """
    Asyncio-based recurring task scheduler.
    Call start(queue) in the FastAPI lifespan; call stop() on shutdown.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, ScheduledJob] = {}
        self._lock = threading.Lock()
        self._queue: TaskQueue | None = None
        self._worker: asyncio.Task | None = None

    def start(self, queue: TaskQueue) -> None:
        self._queue = queue
        self._worker = asyncio.create_task(self._run(), name="task_scheduler")
        log.info("scheduler_started")

    def stop(self) -> None:
        if self._worker and not self._worker.done():
            self._worker.cancel()
        log.info("scheduler_stopped")

    def add_job(
        self,
        task: str,
        user_id: str,
        interval_s: float,
        force_provider: str = "",
        priority: str = "NORMAL",
        max_retries: int = 0,
    ) -> str:
        if interval_s < 1:
            raise ValueError("interval_s must be >= 1")
        job_id = str(uuid.uuid4())
        job = ScheduledJob(
            job_id=job_id,
            task=task,
            user_id=user_id,
            interval_s=interval_s,
            force_provider=force_provider,
            priority=priority,
            max_retries=max_retries,
            next_run_at=time.monotonic() + interval_s,
        )
        with self._lock:
            self._jobs[job_id] = job
        log.info("scheduler_job_added", job_id=job_id, interval_s=interval_s)
        return job_id

    def remove_job(self, job_id: str) -> bool:
        with self._lock:
            if job_id not in self._jobs:
                return False
            del self._jobs[job_id]
        log.info("scheduler_job_removed", job_id=job_id)
        return True

    def enable_job(self, job_id: str, enabled: bool) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            job.enabled = enabled
        return True

    def get_job(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
        return job.to_dict() if job else None

    def list_jobs(self) -> list[dict]:
        with self._lock:
            jobs = list(self._jobs.values())
        return [j.to_dict() for j in jobs]

    def job_count(self) -> int:
        with self._lock:
            return len(self._jobs)

    async def _run(self) -> None:
        while True:
            try:
                await asyncio.sleep(_TICK_S)
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("scheduler_tick_error", error=str(exc))

    async def _tick(self) -> None:
        if self._queue is None:
            return
        now = time.monotonic()
        with self._lock:
            due = [j for j in self._jobs.values() if j.enabled and j.next_run_at <= now]
        for job in due:
            try:
                task_id = await self._queue.submit(
                    task=job.task,
                    user_id=job.user_id,
                    force_provider=job.force_provider,
                    priority=job.priority,
                    max_retries=job.max_retries,
                )
                with self._lock:
                    job.run_count += 1
                    job.last_task_id = task_id
                    job.last_run_at = now
                    job.next_run_at = now + job.interval_s
                log.info("scheduler_job_fired", job_id=job.job_id, task_id=task_id,
                         run_count=job.run_count)
            except Exception as exc:
                log.error("scheduler_job_error", job_id=job.job_id, error=str(exc))
                with self._lock:
                    job.next_run_at = now + job.interval_s  # still advance to avoid tight loop
