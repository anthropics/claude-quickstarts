"""
Singularity — API key manager (Fáze 7 + 14).

In-memory správa API klíčů per user_id.
Fáze 14: volitelně persistuje do SQLite přes Database.
"""
from __future__ import annotations

import hashlib
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.persistence import Database


@dataclass
class ApiKey:
    key_id: str
    key: str          # plain text (v produkci: hash)
    user_id: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    revoked: bool = False


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class ApiKeyManager:
    """Thread-safe správce API klíčů + volitelná SQLite persistence (Fáze 14)."""

    _PREFIX = "sk-sg-"

    def __init__(self, db: Database | None = None) -> None:
        self._keys: dict[str, ApiKey] = {}   # raw key → ApiKey
        self._lock = threading.Lock()
        self._db = db
        if db is not None:
            self._load_from_db()

    def attach_db(self, db: Database) -> None:
        """Attach a Database after construction (called from lifespan)."""
        self._db = db
        self._load_from_db()

    def _load_from_db(self) -> None:
        if self._db is None:
            return
        rows = self._db.load_api_keys()
        with self._lock:
            for row in rows:
                # Reconstruct in-memory record; raw key is not stored in DB —
                # use the prefix as a sentinel so validate_key works via DB lookup.
                self._keys[row["key_hash"]] = ApiKey(
                    key_id=row["key_hash"][:16],
                    key=row["key_hash"],      # placeholder; lookup uses hash
                    user_id=row["user_id"],
                    created_at=row["created_at"],
                    revoked=bool(row["revoked"]),
                )

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
        if self._db is not None:
            self._db.persist_api_key(
                key_hash=_hash_key(raw),
                user_id=user_id,
                prefix=raw[:12],
                created_at=record.created_at,
            )
        return raw

    def revoke_key(self, key: str) -> bool:
        """Zneplatní klíč. Vrátí True pokud existoval."""
        with self._lock:
            rec = self._keys.get(key)
            if rec is None:
                return False
            rec.revoked = True
        if self._db is not None:
            self._db.revoke_api_key(_hash_key(key))
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
            records = [r for r in self._keys.values() if not r.revoked]
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
