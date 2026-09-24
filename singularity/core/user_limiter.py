"""
Singularity — Per-user rate limiter (Fáze 5).

Sliding-window counter per user_id (okno 60 s).
Thread-safe; nezávislý na aiolimiter (který je per-provider).
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class _UserRecord:
    user_id: str
    rpm_limit: int | None = None
    _timestamps: deque[float] = field(default_factory=deque)


_WINDOW = 60.0  # sekund


class UserRateLimiter:
    """Sleduje počet požadavků per user_id v posledních 60 s."""

    def __init__(self) -> None:
        self._records: dict[str, _UserRecord] = {}
        self._lock = threading.Lock()

    def set_limit(self, user_id: str, rpm: int) -> None:
        """Nastaví limit. rpm=0 odebere omezení."""
        with self._lock:
            rec = self._records.setdefault(user_id, _UserRecord(user_id=user_id))
            rec.rpm_limit = rpm if rpm > 0 else None

    def check_and_record(self, user_id: str) -> bool:
        """Vrátí True a zaznamená požadavek; False pokud je překročen limit."""
        now = time.monotonic()
        with self._lock:
            rec = self._records.setdefault(user_id, _UserRecord(user_id=user_id))
            self._prune(rec, now)
            if rec.rpm_limit is not None and len(rec._timestamps) >= rec.rpm_limit:
                return False
            rec._timestamps.append(now)
            return True

    def get_status(self, user_id: str) -> dict:
        now = time.monotonic()
        with self._lock:
            rec = self._records.get(user_id)
        if rec is None:
            return {
                "user_id": user_id,
                "rpm_limit": None,
                "requests_last_minute": 0,
                "limited": False,
            }
        self._prune(rec, now)
        count = len(rec._timestamps)
        return {
            "user_id": user_id,
            "rpm_limit": rec.rpm_limit,
            "requests_last_minute": count,
            "limited": rec.rpm_limit is not None and count >= rec.rpm_limit,
        }

    def reset(self, user_id: str) -> None:
        """Resetuje counter a odebere limit."""
        with self._lock:
            if user_id in self._records:
                self._records[user_id]._timestamps.clear()
                self._records[user_id].rpm_limit = None

    def list_users(self) -> list[str]:
        with self._lock:
            return list(self._records.keys())

    @staticmethod
    def _prune(rec: _UserRecord, now: float) -> None:
        cutoff = now - _WINDOW
        while rec._timestamps and rec._timestamps[0] < cutoff:
            rec._timestamps.popleft()
