"""WebSocket endpoint for the chat event stream."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from computer_use_demo.api.chats.repo import ChatRepo, EventRepo
from computer_use_demo.api.db import session_scope

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chats"])


@router.websocket("/api/chats/{chat_id}/ws")
async def chat_stream(
    websocket: WebSocket,
    chat_id: str,
    since_seq: int = Query(default=0, ge=0),
) -> None:
    bus = websocket.app.state.bus
    async with session_scope() as db:
        row = await ChatRepo(db).get(chat_id)
        if row is None:
            await websocket.close(code=4404)
            return
        events_repo = EventRepo(db)
        # Seed the in-memory seq counter from DB so new events keep monotonicity.
        current_max = await events_repo.max_seq(chat_id)
        await bus.set_seq_floor(chat_id, current_max)
        replay = await events_repo.list_since(chat_id, since_seq)

    await websocket.accept()

    queue = bus.subscribe(chat_id)
    try:
        for event in replay:
            payload = {
                "v": 1,
                "chat_id": chat_id,
                "turn_id": event.turn_id,
                "seq": event.seq,
                "ts": event.created_at.isoformat(),
                "type": event.type,
                "data": event.data_json,
            }
            await websocket.send_text(json.dumps(payload))

        recv_task = asyncio.create_task(_drain_client(websocket))
        try:
            while True:
                get_task = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait(
                    {recv_task, get_task}, return_when=asyncio.FIRST_COMPLETED
                )
                if get_task in done:
                    envelope = get_task.result()
                    await websocket.send_text(json.dumps(envelope))
                else:
                    get_task.cancel()
                if recv_task in done:
                    # Client closed
                    break
        finally:
            recv_task.cancel()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws failure for chat %s", chat_id)
    finally:
        bus.unsubscribe(chat_id, queue)


async def _drain_client(websocket: WebSocket) -> None:
    """Accept client-sent frames (ignoring contents except ping→pong)."""
    try:
        while True:
            msg = await websocket.receive_text()
            try:
                obj = json.loads(msg)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        return
