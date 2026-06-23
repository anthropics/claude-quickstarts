"""
Singularity — Session store (Fáze 1).

Udržuje historii konverzací a kumulativní náklady per user_id.
V produkci nahradit Redis / PostgreSQL.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

# USD/1k tokenů per provider (shodné s provider metadata)
_COST_PER_1K: dict[str, float] = {
    "claude": 0.003,
    "gemini": 0.0005,
}
_DEFAULT_COST_PER_1K = 0.003


def estimate_cost(response: str, provider_log: dict[str, str]) -> float:
    """Odhadne náklady z délky odpovědi a použitých providerů."""
    tokens = len(response) / 4.0          # přibližně 4 znaky = 1 token
    providers = list(provider_log.values())
    if not providers:
        rate = _DEFAULT_COST_PER_1K
    else:
        # průměr přes všechny provider kroky
        rate = sum(_COST_PER_1K.get(p, _DEFAULT_COST_PER_1K) for p in providers) / len(providers)
    return round(tokens * rate / 1000, 6)


@dataclass
class ConversationTurn:
    task: str
    response: str
    provider_log: dict
    risk_score: float
    cost_usd: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Session:
    user_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    total_cost_usd: float = 0.0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def add_turn(self, turn: ConversationTurn) -> None:
        self.turns.append(turn)
        self.total_cost_usd = round(self.total_cost_usd + turn.cost_usd, 6)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "created_at": self.created_at,
            "total_cost_usd": self.total_cost_usd,
            "turn_count": len(self.turns),
            "turns": [
                {
                    "task": t.task,
                    "response": t.response,
                    "provider_log": t.provider_log,
                    "risk_score": t.risk_score,
                    "cost_usd": t.cost_usd,
                    "timestamp": t.timestamp,
                }
                for t in self.turns
            ],
        }


class SessionStore:
    """Thread-safe in-memory store pro konverzační session."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def get_or_create(self, user_id: str) -> Session:
        with self._lock:
            if user_id not in self._sessions:
                self._sessions[user_id] = Session(user_id=user_id)
            return self._sessions[user_id]

    def add_turn(self, user_id: str, turn: ConversationTurn) -> None:
        with self._lock:
            session = self._sessions.setdefault(user_id, Session(user_id=user_id))
            session.add_turn(turn)

    def get_history(self, user_id: str) -> dict:
        with self._lock:
            session = self._sessions.get(user_id)
        if session is None:
            return {
                "user_id": user_id,
                "created_at": None,
                "total_cost_usd": 0.0,
                "turn_count": 0,
                "turns": [],
            }
        return session.to_dict()

    def list_users(self) -> list[str]:
        with self._lock:
            return list(self._sessions.keys())
