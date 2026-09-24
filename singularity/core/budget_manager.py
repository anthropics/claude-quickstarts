"""
Singularity — Per-user cost budget manager (Fáze 4).

Umožňuje nastavit limit USD per user_id a blokovat úkoly, které by ho přesáhly.
V produkci synchronizovat s perzistentním úložištěm (DB).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class BudgetRecord:
    user_id: str
    limit_usd: float | None = None       # None = neomezeno
    spent_usd: float = 0.0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class BudgetManager:
    """Thread-safe správce limitů nákladů per user_id."""

    def __init__(self) -> None:
        self._records: dict[str, BudgetRecord] = {}
        self._lock = threading.Lock()

    def set_budget(self, user_id: str, limit_usd: float) -> None:
        """Nastaví nebo aktualizuje limit. limit_usd=0 odebere omezení."""
        with self._lock:
            rec = self._records.setdefault(user_id, BudgetRecord(user_id=user_id))
            rec.limit_usd = limit_usd if limit_usd > 0 else None
            rec.updated_at = datetime.now(timezone.utc).isoformat()

    def reset_spent(self, user_id: str) -> None:
        """Vynuluje utracené náklady (např. na začátku nového období)."""
        with self._lock:
            if user_id in self._records:
                self._records[user_id].spent_usd = 0.0
                self._records[user_id].updated_at = datetime.now(timezone.utc).isoformat()

    def record_spend(self, user_id: str, amount: float) -> None:
        with self._lock:
            rec = self._records.setdefault(user_id, BudgetRecord(user_id=user_id))
            rec.spent_usd = round(rec.spent_usd + amount, 6)
            rec.updated_at = datetime.now(timezone.utc).isoformat()

    def is_allowed(self, user_id: str, estimated_cost: float = 0.0) -> bool:
        """False pokud má uživatel limit a přidání estimated_cost by ho přesáhlo."""
        with self._lock:
            rec = self._records.get(user_id)
        if rec is None or rec.limit_usd is None:
            return True
        return rec.spent_usd + estimated_cost <= rec.limit_usd

    def get_status(self, user_id: str) -> dict:
        with self._lock:
            rec = self._records.get(user_id)
        if rec is None:
            return {
                "user_id": user_id,
                "limit_usd": None,
                "spent_usd": 0.0,
                "remaining_usd": None,
                "over_budget": False,
            }
        remaining = None if rec.limit_usd is None else max(0.0, rec.limit_usd - rec.spent_usd)
        return {
            "user_id": user_id,
            "limit_usd": rec.limit_usd,
            "spent_usd": rec.spent_usd,
            "remaining_usd": remaining,
            "over_budget": (rec.limit_usd is not None and rec.spent_usd >= rec.limit_usd),
            "updated_at": rec.updated_at,
        }

    def list_users(self) -> list[str]:
        with self._lock:
            return list(self._records.keys())
