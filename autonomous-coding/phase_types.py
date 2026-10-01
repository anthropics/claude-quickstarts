"""Shared type aliases for orchestrator phase wiring."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable

PhaseRunner = Callable[[Path, str, str, str, Any | None], Awaitable[str]]
ClientFactory = Callable[[Path, str, str], Any]
