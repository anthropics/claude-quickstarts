"""
In-memory session state manager.

Each session gets:
- run_lock: asyncio.Lock — prevents concurrent sampling_loop runs
- active_task: asyncio.Task — the currently running loop (None if idle)
- sse_queues: fan-out list of asyncio.Queue — one per connected SSE client

All SSE events are delivered via put_nowait() so callbacks (which run
synchronously inside the asyncio event loop) never need to await.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SessionState:
    session_id: str
    run_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    active_task: asyncio.Task | None = None
    sse_queues: list[asyncio.Queue] = field(default_factory=list)
    last_active: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SessionManager:
    """Singleton managing all in-memory session state."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._registry_lock = asyncio.Lock()

    async def get_or_create(self, session_id: str) -> SessionState:
        async with self._registry_lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionState(session_id=session_id)
            return self._sessions[session_id]

    def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    async def remove(self, session_id: str) -> None:
        async with self._registry_lock:
            state = self._sessions.pop(session_id, None)
        if state and state.active_task and not state.active_task.done():
            state.active_task.cancel()
            try:
                await state.active_task
            except (asyncio.CancelledError, Exception):
                pass

    def is_running(self, session_id: str) -> bool:
        state = self._sessions.get(session_id)
        return bool(state and state.active_task and not state.active_task.done())

    async def cancel_run(self, session_id: str) -> bool:
        """Cancel the active task. Returns True if one was cancelled."""
        state = self._sessions.get(session_id)
        if state and state.active_task and not state.active_task.done():
            state.active_task.cancel()
            try:
                await state.active_task
            except (asyncio.CancelledError, Exception):
                pass
            state.active_task = None
            return True
        return False

    # ------------------------------------------------------------------
    # SSE fan-out
    # ------------------------------------------------------------------

    async def subscribe(self, session_id: str) -> asyncio.Queue:
        """Create and register a new SSE queue for this session."""
        state = await self.get_or_create(session_id)
        q: asyncio.Queue = asyncio.Queue(maxsize=512)
        state.sse_queues.append(q)
        return q

    def unsubscribe(self, session_id: str, q: asyncio.Queue) -> None:
        state = self._sessions.get(session_id)
        if state and q in state.sse_queues:
            state.sse_queues.remove(q)

    def broadcast_sync(self, session_id: str, payload: dict) -> None:
        """
        Synchronous broadcast — safe to call from non-async callbacks
        that run inside the asyncio event loop thread.
        Puts a JSON string onto every registered SSE queue.
        """
        state = self._sessions.get(session_id)
        if not state:
            return
        data = json.dumps(payload)
        dead: list[asyncio.Queue] = []
        for q in state.sse_queues:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            try:
                state.sse_queues.remove(q)
            except ValueError:
                pass

    def signal_done(self, session_id: str) -> None:
        """Send None sentinel to all SSE queues to close streams."""
        state = self._sessions.get(session_id)
        if not state:
            return
        for q in state.sse_queues:
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass


# Module-level singleton
session_manager = SessionManager()
