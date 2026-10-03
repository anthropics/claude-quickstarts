"""
Singularity — Graceful shutdown (Fáze 9).

Drains in-flight tasks before stopping workers so no work is lost
on SIGTERM / normal uvicorn shutdown.
"""
from __future__ import annotations

import asyncio
import signal

import structlog

from core.task_queue import TaskQueue

log = structlog.get_logger()


class GracefulShutdown:
    def __init__(self, queue: TaskQueue, timeout_s: float = 30.0) -> None:
        self._queue = queue
        self._timeout = timeout_s
        self._draining = False

    def is_draining(self) -> bool:
        return self._draining

    async def drain(self) -> None:
        """Wait for the queue to empty (up to timeout_s), then stop workers."""
        if self._draining:
            return
        self._draining = True
        log.info("graceful_shutdown_started", timeout_s=self._timeout)
        try:
            await asyncio.wait_for(
                self._queue._queue.join(), timeout=self._timeout
            )
            log.info("graceful_shutdown_queue_drained")
        except asyncio.TimeoutError:
            log.warning("graceful_shutdown_timeout", timeout_s=self._timeout)
        finally:
            self._queue.stop()

    def register(self) -> None:
        """Register SIGTERM/SIGINT handlers on the running event loop."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig, lambda: asyncio.ensure_future(self.drain())
            )
        log.info("graceful_shutdown_registered")
