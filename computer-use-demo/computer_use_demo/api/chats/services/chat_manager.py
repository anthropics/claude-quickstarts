"""Tracks running per-chat turn tasks and enforces per-chat serialisation."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass

from computer_use_demo.api.chats.services.agent_runner import AgentRunner
from computer_use_demo.api.chats.services.event_bus import EventBus

logger = logging.getLogger(__name__)


class TurnAlreadyRunning(RuntimeError):
    pass


@dataclass
class _Active:
    task: asyncio.Task
    lock: asyncio.Lock


class ChatManager:
    def __init__(self, *, bus: EventBus, runner: AgentRunner) -> None:
        self._bus = bus
        self._runner = runner
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._active: dict[str, _Active] = {}
        self._registry_lock = asyncio.Lock()

    async def start_turn(
        self,
        *,
        chat_id: str,
        api_key: str,
        base_url: str | None = None,
        user_content: str,
    ) -> asyncio.Task:
        lock = self._locks[chat_id]
        async with self._registry_lock:
            existing = self._active.get(chat_id)
            if existing is not None and not existing.task.done():
                raise TurnAlreadyRunning(
                    f"chat {chat_id} already has a turn in progress"
                )
            task = asyncio.create_task(
                self._runner.run_turn(
                    chat_id=chat_id,
                    api_key=api_key,
                    base_url=base_url,
                    user_content=user_content,
                )
            )
            self._active[chat_id] = _Active(task=task, lock=lock)

        def _done(t: asyncio.Task) -> None:
            # Clear registry entry; swallow cancellation so it doesn't warn.
            asyncio.create_task(self._clear(chat_id, t))

        task.add_done_callback(_done)
        return task

    async def _clear(self, chat_id: str, task: asyncio.Task) -> None:
        async with self._registry_lock:
            current = self._active.get(chat_id)
            if current is not None and current.task is task:
                self._active.pop(chat_id, None)

    def is_running(self, chat_id: str) -> bool:
        active = self._active.get(chat_id)
        return active is not None and not active.task.done()

    async def cancel(self, chat_id: str) -> bool:
        async with self._registry_lock:
            active = self._active.get(chat_id)
        if active is None or active.task.done():
            return False
        active.task.cancel()
        try:
            await active.task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        return True

    async def shutdown_all(self, *, timeout: float = 5.0) -> None:
        async with self._registry_lock:
            tasks = [a.task for a in self._active.values() if not a.task.done()]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.wait(tasks, timeout=timeout)
        async with self._registry_lock:
            self._active.clear()
