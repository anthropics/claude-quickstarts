"""Shared type aliases for orchestrator phase wiring."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable

from claude_code_sdk import ClaudeSDKClient

PhaseRunner = Callable[[Path, str, str, str, ClaudeSDKClient | None], Awaitable[str]]
ClientFactory = Callable[[Path, str, str], Any]
