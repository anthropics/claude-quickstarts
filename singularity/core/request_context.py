"""
Singularity — Per-request context propagation (Fáze 8).

Uses contextvars so that request_id / user_id flow through the entire
async call chain without explicit parameter threading.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar

_request_id: ContextVar[str] = ContextVar("request_id", default="")
_user_id: ContextVar[str] = ContextVar("user_id", default="")


def set_request_context(request_id: str = "", user_id: str = "") -> tuple[str, str]:
    """Set context vars for the current request. Returns (request_id, user_id)."""
    rid = request_id or str(uuid.uuid4())
    _request_id.set(rid)
    _user_id.set(user_id)
    return rid, user_id


def clear_request_context() -> None:
    _request_id.set("")
    _user_id.set("")


def get_request_id() -> str:
    return _request_id.get()


def get_user_id() -> str:
    return _user_id.get()
