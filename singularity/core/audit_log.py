"""
Singularity — Append-only strukturovaný audit log (Fáze 6).

Zaznamenává klíčové události: odeslání úkolu, dokončení, selhání,
retry, přechod do DLQ, změny budgetu a rate-limitů.
V produkci nahradit perzistentním logem (DB / SIEM).
"""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

_MAX_EVENTS = 1_000  # in-memory ring buffer


@dataclass
class AuditEvent:
    event_type: str
    user_id: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    task_id: str | None = None
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "details": self.details,
        }


class AuditLog:
    """Thread-safe ring buffer pro audit události."""

    def __init__(self, max_events: int = _MAX_EVENTS) -> None:
        self._events: deque[AuditEvent] = deque(maxlen=max_events)
        self._lock = threading.Lock()

    def record(
        self,
        event_type: str,
        user_id: str,
        task_id: str | None = None,
        **details,
    ) -> None:
        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            task_id=task_id,
            details=details,
        )
        with self._lock:
            self._events.append(event)

    def get_events(
        self,
        limit: int = 100,
        event_type: str | None = None,
        user_id: str | None = None,
    ) -> list[dict]:
        with self._lock:
            events = list(self._events)
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        return [e.to_dict() for e in events[-limit:]]

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)
