"""
Request Coalescer endpoints (Fáze 66, v2.0 #6). Extracted from api/main.py.

Routes and behaviour are identical to the originals.
"""

from __future__ import annotations

from fastapi import APIRouter

from api.state import coalescer

router = APIRouter(tags=["Coalescer"])


@router.get("/coalesce/metrics")
async def coalesce_metrics():
    """Request coalescer metrics: calls, executions, coalesce rate."""
    return coalescer.metrics()
