"""Event dispatching utility for agent lifecycle events."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    USER_INPUT     = "user_input"
    TOOL_CALL      = "tool_call"
    TOOL_RESULT    = "tool_result"
    TOOL_ERROR     = "tool_error"
    AGENT_RESPONSE = "agent_response"
    LOOP_END       = "loop_end"


@dataclass
class AgentEvent:
    type: EventType
    agent_name: str
    payload: dict[str, Any] = field(default_factory=dict)


EventCallback = Callable[[AgentEvent], Awaitable[None]]


class EventDispatcher:
    """Holds callbacks and dispatches AgentEvents to them sequentially."""

    def __init__(self, callbacks: list[EventCallback] | None = None):
        self._callbacks: list[EventCallback] = list(callbacks or [])

    async def emit(self, event: AgentEvent) -> None:
        """Dispatch event to all registered callbacks, swallowing errors."""
        for callback in self._callbacks:
            try:
                await callback(event)
            except Exception as exc:
                logger.error(
                    "Callback %r raised for event %s: %s",
                    callback,
                    event.type,
                    exc,
                )


async def LoggingCallback(event: AgentEvent) -> None:
    """Replicates the legacy verbose=True stdout output."""
    name = event.agent_name
    p = event.payload

    if event.type == EventType.USER_INPUT:
        print(f"\n[{name}] Received: {p.get('input')}")
    elif event.type == EventType.TOOL_CALL:
        params_str = ", ".join(f"{k}={v}" for k, v in p.get("tool_input", {}).items())
        print(f"\n[{name}] Tool call: {p.get('tool_name')}({params_str})")
    elif event.type in (EventType.TOOL_RESULT, EventType.TOOL_ERROR):
        print(f"\n[{name}] Tool result: {p.get('content')}")
    elif event.type == EventType.AGENT_RESPONSE:
        print(f"\n[{name}] Output: {p.get('text')}")
