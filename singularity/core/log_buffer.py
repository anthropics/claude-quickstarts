"""
Singularity — In-memory log buffer (Fáze 10).

Works as a structlog processor: captures a copy of each event_dict
into a thread-safe ring buffer before the renderer sees it.
"""
from __future__ import annotations

import threading
from collections import deque
from typing import Any


class LogBuffer:
    """Thread-safe ring buffer that doubles as a structlog processor."""

    def __init__(self, maxlen: int = 500) -> None:
        self._events: deque[dict] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def __call__(self, logger: Any, method: str, event_dict: dict) -> dict:
        with self._lock:
            self._events.append({**event_dict, "_level": method})
        return event_dict  # pass through unchanged

    def get_recent(
        self,
        limit: int = 50,
        level: str | None = None,
    ) -> list[dict]:
        with self._lock:
            events = list(self._events)
        if level:
            events = [e for e in events if e.get("_level") == level.lower()]
        return events[-limit:]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def __len__(self) -> int:
        return len(self._events)
