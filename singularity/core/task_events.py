"""
Singularity — Task event bus (Fáze 11).

Asyncio pub/sub: each subscriber gets its own asyncio.Queue so events
are delivered independently with no head-of-line blocking.
Used by GET /task/{id}/stream to push live task-lifecycle events.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict


class TaskEventBus:

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._lock: asyncio.Lock | None = None

    def _lock_(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def publish(self, task_id: str, event: dict) -> None:
        async with self._lock_():
            queues = list(self._subscribers.get(task_id, []))
        for q in queues:
            await q.put(event)

    async def subscribe(self, task_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        async with self._lock_():
            self._subscribers[task_id].append(q)
        return q

    async def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        async with self._lock_():
            subs = self._subscribers.get(task_id, [])
            if queue in subs:
                subs.remove(queue)
            if not subs:
                self._subscribers.pop(task_id, None)

    def subscriber_count(self, task_id: str) -> int:
        return len(self._subscribers.get(task_id, []))
