"""
Singularity — Secret Manager (Fáze 23).

Stores named secrets (API keys, tokens, credentials) scoped per owner.
Secrets are held in memory only (never logged). Optional TTL expiry.
Thread-safe; no external dependencies.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

log = structlog.get_logger()

_NEVER_EXPIRES = 0.0


@dataclass
class SecretEntry:
    secret_id: str
    name: str
    owner: str
    value: str
    description: str
    tags: list[str]
    expires_at: float   # monotonic timestamp; 0.0 = never
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def is_expired(self) -> bool:
        return self.expires_at != _NEVER_EXPIRES and time.monotonic() > self.expires_at

    def to_dict(self, *, reveal: bool = False) -> dict:
        return {
            "secret_id": self.secret_id,
            "name": self.name,
            "owner": self.owner,
            "value": self.value if reveal else "***",
            "description": self.description,
            "tags": self.tags,
            "expires_at": (
                datetime.fromtimestamp(
                    self.created_at_epoch + (self.expires_at - self._created_mono),
                    tz=timezone.utc,
                ).isoformat()
                if self.expires_at != _NEVER_EXPIRES else None
            ),
            "expired": self.is_expired(),
            "created_at": self.created_at,
        }


class SecretManager:
    """
    Thread-safe in-memory secret store.

    Usage:
        sid = mgr.store("openai-key", "sk-...", owner="alice", ttl_s=3600)
        value = mgr.reveal(sid, owner="alice")
    """

    def __init__(self) -> None:
        self._secrets: dict[str, SecretEntry] = {}
        self._lock = threading.Lock()

    def store(
        self,
        name: str,
        value: str,
        *,
        owner: str,
        description: str = "",
        tags: list[str] | None = None,
        ttl_s: float | None = None,   # seconds until expiry; None = never
    ) -> str:
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        if not value:
            raise ValueError("value must not be empty")
        if not owner or not owner.strip():
            raise ValueError("owner must not be empty")
        expires_at = _NEVER_EXPIRES
        if ttl_s is not None:
            if ttl_s <= 0:
                raise ValueError("ttl_s must be positive")
            expires_at = time.monotonic() + ttl_s

        secret_id = str(uuid.uuid4())
        entry = SecretEntry(
            secret_id=secret_id,
            name=name,
            owner=owner,
            value=value,
            description=description,
            tags=list(tags or []),
            expires_at=expires_at,
        )
        # Store helper attributes for to_dict expiry ISO calculation
        entry._created_mono = time.monotonic()   # type: ignore[attr-defined]
        entry.created_at_epoch = datetime.now(timezone.utc).timestamp()  # type: ignore[attr-defined]

        with self._lock:
            self._secrets[secret_id] = entry
        log.info("secret_stored", secret_id=secret_id, name=name, owner=owner)
        return secret_id

    def reveal(self, secret_id: str, *, owner: str) -> str | None:
        """Return the plaintext value. Returns None if missing, expired, or wrong owner."""
        with self._lock:
            entry = self._secrets.get(secret_id)
        if entry is None:
            return None
        if entry.owner != owner:
            log.warning("secret_access_denied", secret_id=secret_id,
                        expected_owner=entry.owner, actual_owner=owner)
            return None
        if entry.is_expired():
            return None
        return entry.value

    def get(self, secret_id: str, *, owner: str) -> dict | None:
        """Return metadata (value masked). None if missing, expired, or wrong owner."""
        with self._lock:
            entry = self._secrets.get(secret_id)
        if entry is None or entry.owner != owner or entry.is_expired():
            return None
        return entry.to_dict(reveal=False)

    def list_secrets(self, *, owner: str, tag: str | None = None) -> list[dict]:
        """List non-expired secrets belonging to owner, optionally filtered by tag."""
        with self._lock:
            items = [e for e in self._secrets.values()
                     if e.owner == owner and not e.is_expired()]
        if tag is not None:
            items = [e for e in items if tag in e.tags]
        return [e.to_dict(reveal=False) for e in items]

    def delete(self, secret_id: str, *, owner: str) -> bool:
        """Delete a secret. Returns False if not found or wrong owner."""
        with self._lock:
            entry = self._secrets.get(secret_id)
            if entry is None or entry.owner != owner:
                return False
            del self._secrets[secret_id]
        log.info("secret_deleted", secret_id=secret_id, owner=owner)
        return True

    def rotate(self, secret_id: str, new_value: str, *, owner: str) -> bool:
        """Replace the secret value in-place. Returns False on mismatch/expiry."""
        if not new_value:
            raise ValueError("new_value must not be empty")
        with self._lock:
            entry = self._secrets.get(secret_id)
            if entry is None or entry.owner != owner or entry.is_expired():
                return False
            entry.value = new_value
        log.info("secret_rotated", secret_id=secret_id, owner=owner)
        return True

    def purge_expired(self) -> int:
        """Remove all expired secrets. Returns count removed."""
        with self._lock:
            expired = [sid for sid, e in self._secrets.items() if e.is_expired()]
            for sid in expired:
                del self._secrets[sid]
        if expired:
            log.info("secrets_purged", count=len(expired))
        return len(expired)

    def secret_count(self, *, owner: str | None = None) -> int:
        with self._lock:
            if owner is None:
                return len(self._secrets)
            return sum(1 for e in self._secrets.values() if e.owner == owner)
