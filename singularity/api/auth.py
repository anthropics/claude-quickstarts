"""
Singularity — FastAPI auth dependency (Fáze 7).

Pokud je require_api_key=True, všechny chráněné endpointy
vyžadují header X-API-Key s platným klíčem.
Při require_api_key=False propustí vše (dev mode).
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from config.settings import settings
from core.api_keys import ApiKeyManager

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Sdílená instance — importována z api.main při startu
_manager: ApiKeyManager | None = None


def set_manager(manager: ApiKeyManager) -> None:
    global _manager
    _manager = manager


async def verify_api_key(key: str | None = Security(_api_key_header)) -> str:
    """
    FastAPI dependency — vrátí user_id pro platný klíč.
    Když require_api_key=False, propustí anonymně jako 'anonymous'.
    """
    if not settings.require_api_key:
        return "anonymous"
    if key is None:
        raise HTTPException(status_code=401, detail="X-API-Key header je vyžadován")
    assert _manager is not None
    user_id = _manager.validate_key(key)
    if user_id is None:
        raise HTTPException(status_code=403, detail="Neplatný nebo revokovaný API klíč")
    return user_id
