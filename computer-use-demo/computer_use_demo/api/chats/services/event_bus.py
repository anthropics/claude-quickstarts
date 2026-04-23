"""Per-chat pub/sub for live WebSocket event fan-out.

Seq numbers and persistence are owned elsewhere; this bus only forwards
already-stamped envelopes to in-memory subscribers.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._channels: dict[str, set[asyncio.Queue[Any]]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._seqs: dict[str, int] = {}

    async def set_seq_floor(self, chat_id: str, seq: int) -> None:
        async with self._lock:
            if seq > self._seqs.get(chat_id, 0):
                self._seqs[chat_id] = seq

    async def next_seq(self, chat_id: str) -> int:
        async with self._lock:
            self._seqs[chat_id] = self._seqs.get(chat_id, 0) + 1
            return self._seqs[chat_id]

    def subscribe(self, chat_id: str) -> asyncio.Queue[Any]:
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=1024)
        self._channels[chat_id].add(queue)
        return queue

    def unsubscribe(self, chat_id: str, queue: asyncio.Queue[Any]) -> None:
        self._channels.get(chat_id, set()).discard(queue)

    def publish(self, chat_id: str, envelope: dict[str, Any]) -> None:
        for queue in list(self._channels.get(chat_id, ())):
            try:
                queue.put_nowait(envelope)
            except asyncio.QueueFull:
                # Drop newest for this slow subscriber; they can reconnect with since_seq.
                pass

    def drop(self, chat_id: str) -> None:
        self._channels.pop(chat_id, None)
        self._seqs.pop(chat_id, None)
