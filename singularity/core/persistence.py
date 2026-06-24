"""
Singularity — SQLite persistence layer (Fáze 14).

Thread-safe synchronous wrapper around stdlib sqlite3.
Used by AuditLog and ApiKeyManager for durable storage that survives restarts.
Pass db_path=":memory:" in tests for a zero-cost in-process database.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path


_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type   TEXT    NOT NULL,
    user_id      TEXT    NOT NULL,
    task_id      TEXT,
    details_json TEXT,
    timestamp    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    key_hash   TEXT    PRIMARY KEY,
    user_id    TEXT    NOT NULL,
    prefix     TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    revoked    INTEGER NOT NULL DEFAULT 0
);
"""


class Database:
    """
    Thin sqlite3 wrapper with a per-instance threading.Lock for write safety.
    All public methods are synchronous and safe to call from asyncio handlers
    (short, non-blocking operations only).
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()

    def init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            cursor = self._conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        with self._lock:
            cursor = self._conn.execute(sql, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ── Audit helpers ──────────────────────────────────────────────────────────

    def persist_audit_event(
        self,
        event_type: str,
        user_id: str,
        task_id: str | None,
        details: dict,
        timestamp: str,
    ) -> None:
        self.execute(
            "INSERT INTO audit_events (event_type, user_id, task_id, details_json, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_type, user_id, task_id, json.dumps(details), timestamp),
        )

    def load_audit_events(self, limit: int = 1000) -> list[dict]:
        rows = self.fetchall(
            "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?", (limit,)
        )
        for row in rows:
            row["details"] = json.loads(row.pop("details_json") or "{}")
        return list(reversed(rows))

    # ── API key helpers ────────────────────────────────────────────────────────

    def persist_api_key(
        self, key_hash: str, user_id: str, prefix: str, created_at: str
    ) -> None:
        self.execute(
            "INSERT OR IGNORE INTO api_keys (key_hash, user_id, prefix, created_at) "
            "VALUES (?, ?, ?, ?)",
            (key_hash, user_id, prefix, created_at),
        )

    def revoke_api_key(self, key_hash: str) -> bool:
        before = self.fetchone(
            "SELECT revoked FROM api_keys WHERE key_hash = ?", (key_hash,)
        )
        if before is None or before["revoked"]:
            return False
        self.execute(
            "UPDATE api_keys SET revoked = 1 WHERE key_hash = ?", (key_hash,)
        )
        return True

    def load_api_keys(self) -> list[dict]:
        return self.fetchall("SELECT * FROM api_keys WHERE revoked = 0")
