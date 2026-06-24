"""
Singularity — API key manager (Fáze 7).

In-memory správa API klíčů per user_id.
V produkci ukládat do DB s bcrypt hashováním.
"""
from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ApiKey:
    key_id: str
    key: str          # plain text (v produkci: hash)
    user_id: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    revoked: bool = False


class ApiKeyManager:
    """Thread-safe správce API klíčů."""

    _PREFIX = "sk-sg-"

    def __init__(self) -> None:
        self._keys: dict[str, ApiKey] = {}   # key → ApiKey
        self._lock = threading.Lock()

    def create_key(self, user_id: str) -> str:
        """Vygeneruje a uloží nový klíč; vrátí raw hodnotu."""
        raw = self._PREFIX + secrets.token_urlsafe(32)
        record = ApiKey(
            key_id=secrets.token_hex(8),
            key=raw,
            user_id=user_id,
        )
        with self._lock:
            self._keys[raw] = record
        return raw

    def revoke_key(self, key: str) -> bool:
        """Zneplatní klíč. Vrátí True pokud existoval."""
        with self._lock:
            rec = self._keys.get(key)
            if rec is None:
                return False
            rec.revoked = True
        return True

    def validate_key(self, key: str) -> str | None:
        """Vrátí user_id pro platný klíč; None pokud neexistuje nebo je revoked."""
        with self._lock:
            rec = self._keys.get(key)
        if rec is None or rec.revoked:
            return None
        return rec.user_id

    def list_keys(self, user_id: str | None = None) -> list[dict]:
        with self._lock:
            records = list(self._keys.values())
        if user_id:
            records = [r for r in records if r.user_id == user_id]
        return [
            {
                "key_id": r.key_id,
                "user_id": r.user_id,
                "created_at": r.created_at,
                "revoked": r.revoked,
                "key_prefix": r.key[:12] + "...",
            }
            for r in records
        ]

    def delete_user_keys(self, user_id: str) -> int:
        """Smaže všechny klíče uživatele. Vrátí počet."""
        with self._lock:
            to_delete = [k for k, v in self._keys.items() if v.user_id == user_id]
            for k in to_delete:
                del self._keys[k]
        return len(to_delete)
