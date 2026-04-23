"""Liveness probe endpoint."""

from fastapi import APIRouter
from pydantic import BaseModel

from computer_use_demo.settings import API_VERSION


class HealthOut(BaseModel):
    status: str
    version: str


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    return HealthOut(status="ok", version=API_VERSION)
