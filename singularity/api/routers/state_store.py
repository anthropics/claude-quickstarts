"""
Distributed State Store endpoints (Fáze 62, v2.0). Extracted from api/main.py.

Routes and behaviour are identical to the originals. (Named state_store to
avoid confusion with api/state.py, which holds the shared singletons.)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.state import state_store

router = APIRouter(tags=["State"])


class StateSetRequest(BaseModel):
    value: Any
    ttl_s: float | None = None


@router.put("/state/{namespace}/{key}")
async def state_set(namespace: str, key: str, req: StateSetRequest):
    """Store a JSON value under namespace:key, optionally with a TTL."""
    try:
        state_store.set(namespace, key, req.value, ttl_s=req.ttl_s)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok", "namespace": namespace, "key": key}


@router.get("/state/{namespace}/{key}")
async def state_get(namespace: str, key: str):
    """Fetch a value; 404 if absent or expired."""
    val = state_store.get(namespace, key)
    if val is None and not state_store.exists(namespace, key):
        raise HTTPException(status_code=404, detail="not found")
    return {"namespace": namespace, "key": key, "value": val}


@router.delete("/state/{namespace}/{key}")
async def state_delete(namespace: str, key: str):
    """Delete a value; 404 if absent."""
    if not state_store.delete(namespace, key):
        raise HTTPException(status_code=404, detail="not found")
    return {"status": "deleted", "namespace": namespace, "key": key}


@router.get("/state/metrics")
async def state_metrics():
    """State store metrics (backend, key count, hit rate)."""
    return state_store.metrics()


@router.get("/state/{namespace}")
async def state_keys(namespace: str):
    """List live keys within a namespace."""
    return {"namespace": namespace, "keys": state_store.keys(namespace)}
