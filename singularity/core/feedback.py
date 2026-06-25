"""
Singularity — Human Feedback Loop (Fáze 17).

Collects per-task feedback (1–5 star rating + thumbs up/down + optional comment)
and exposes aggregate quality stats. Optionally persists to SQLite via Database.
"""
from __future__ import annotations

import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from core.persistence import Database

log = structlog.get_logger()

_RING_SIZE = 1000


@dataclass
class FeedbackEntry:
    feedback_id: str
    task_id: str
    session_id: str
    user_id: str
    rating: int          # 1–5
    thumbs: str          # "up" | "down" | ""
    comment: str
    created_at: str      # ISO 8601 UTC

    def to_dict(self) -> dict:
        return {
            "feedback_id": self.feedback_id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "rating": self.rating,
            "thumbs": self.thumbs,
            "comment": self.comment,
            "created_at": self.created_at,
        }


class FeedbackStore:
    """
    Thread-safe in-memory store for task feedback with optional SQLite persistence.
    Keeps the most recent _RING_SIZE entries in memory (older entries are still in DB).
    """

    def __init__(self, db: Database | None = None) -> None:
        self._entries: dict[str, FeedbackEntry] = {}
        self._ring: deque[str] = deque(maxlen=_RING_SIZE)  # ordered feedback_ids
        self._lock = threading.Lock()
        self._db: Database | None = db
        if db is not None:
            self._load_from_db()

    def attach_db(self, db: Database) -> None:
        """Wire up a Database after construction (mirrors AuditLog.attach_db pattern)."""
        with self._lock:
            self._db = db
        self._load_from_db()

    def _load_from_db(self) -> None:
        if self._db is None:
            return
        rows = self._db.load_feedback(limit=_RING_SIZE)
        with self._lock:
            for row in rows:
                entry = FeedbackEntry(**row)
                self._entries[entry.feedback_id] = entry
                self._ring.append(entry.feedback_id)

    def record(
        self,
        task_id: str,
        session_id: str,
        user_id: str,
        rating: int,
        thumbs: str = "",
        comment: str = "",
    ) -> str:
        if not 1 <= rating <= 5:
            raise ValueError(f"rating must be 1–5, got {rating}")
        if thumbs not in ("up", "down", ""):
            raise ValueError(f"thumbs must be 'up', 'down', or '', got {thumbs!r}")
        feedback_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        entry = FeedbackEntry(
            feedback_id=feedback_id,
            task_id=task_id,
            session_id=session_id,
            user_id=user_id,
            rating=rating,
            thumbs=thumbs,
            comment=comment,
            created_at=created_at,
        )
        with self._lock:
            # Evict oldest if ring is full
            if len(self._ring) == _RING_SIZE:
                oldest = self._ring[0]
                self._entries.pop(oldest, None)
            self._entries[feedback_id] = entry
            self._ring.append(feedback_id)
        if self._db is not None:
            self._db.persist_feedback(
                feedback_id=feedback_id,
                task_id=task_id,
                session_id=session_id,
                user_id=user_id,
                rating=rating,
                thumbs=thumbs,
                comment=comment,
                created_at=created_at,
            )
        log.info("feedback_recorded", feedback_id=feedback_id, task_id=task_id, rating=rating)
        return feedback_id

    def get_feedback(self, feedback_id: str) -> dict | None:
        with self._lock:
            entry = self._entries.get(feedback_id)
        return entry.to_dict() if entry else None

    def get_by_task(self, task_id: str) -> list[dict]:
        with self._lock:
            entries = [e for e in self._entries.values() if e.task_id == task_id]
        return [e.to_dict() for e in entries]

    def get_all(self, limit: int = 100) -> list[dict]:
        with self._lock:
            ids = list(self._ring)[-limit:]
            entries = [self._entries[fid] for fid in ids if fid in self._entries]
        return [e.to_dict() for e in entries]

    def get_stats(self) -> dict:
        with self._lock:
            entries = list(self._entries.values())
        total = len(entries)
        if total == 0:
            return {"total": 0, "avg_rating": None, "thumbs_up": 0, "thumbs_down": 0, "thumbs_up_pct": None}
        avg_rating = sum(e.rating for e in entries) / total
        thumbs_up = sum(1 for e in entries if e.thumbs == "up")
        thumbs_down = sum(1 for e in entries if e.thumbs == "down")
        with_thumbs = thumbs_up + thumbs_down
        return {
            "total": total,
            "avg_rating": round(avg_rating, 2),
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "thumbs_up_pct": round(thumbs_up / with_thumbs * 100, 1) if with_thumbs else None,
        }

    def count(self) -> int:
        with self._lock:
            return len(self._entries)
