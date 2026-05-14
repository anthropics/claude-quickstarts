"""
Messages router: send a message, stream SSE events, cancel a run.

The core flow:
  POST /sessions/{id}/messages
    → appends user message to DB
    → launches asyncio.Task(_run_sampling_loop)
    → returns 202 with stream_url

  GET /sessions/{id}/stream
    → subscribes a new asyncio.Queue to the session's fan-out
    → yields SSE-formatted strings until None sentinel or client disconnect

  DELETE /sessions/{id}/run
    → cancels the active task
"""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...loop import APIProvider, sampling_loop
from ...tools.base import ToolResult
from ..crypto import decrypt_api_key
from ..database import AsyncSessionLocal, get_db
from ..models import Message, Session
from ..schemas import SendMessageRequest, SendMessageResponse
from ..session_manager import SessionState, session_manager

router = APIRouter(prefix="/sessions", tags=["messages"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_session_or_404(session_id: str, db: AsyncSession) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


async def _reconstruct_messages(session_id: str, db: AsyncSession) -> list[dict]:
    """Rebuild the BetaMessageParam list from DB rows for sampling_loop."""
    result = await db.execute(
        select(Message)
        .where(
            Message.session_id == session_id,
            Message.display_role.in_(["user", "assistant", "tool"]),
        )
        .order_by(Message.created_at)
    )
    rows = result.scalars().all()
    return [{"role": r.role, "content": r.content_json} for r in rows]


async def _set_session_status(session_id: str, new_status: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(status=new_status, updated_at=datetime.utcnow())
        )
        await db.commit()


async def _persist_new_messages(
    session_id: str,
    updated_messages: list[dict],
    messages_before: int,
) -> None:
    """Persist only the messages sampling_loop appended (the diff)."""
    new_msgs = updated_messages[messages_before:]
    if not new_msgs:
        return
    async with AsyncSessionLocal() as db:
        for msg in new_msgs:
            role = msg["role"]
            content = msg["content"]
            if role == "assistant":
                display_role = "assistant"
            elif role == "user" and isinstance(content, list):
                display_role = "tool"
            else:
                display_role = "user"
            db.add(
                Message(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    role=role,
                    content_json=content,
                    display_role=display_role,
                )
            )
        await db.commit()


# ---------------------------------------------------------------------------
# Core sampling loop task
# ---------------------------------------------------------------------------

async def _run_sampling_loop(
    session_id: str,
    session_snapshot: dict,
    messages_before_count: int,
    state: SessionState,
) -> None:
    """
    Runs as an asyncio.Task. Holds state.run_lock for its entire lifetime.
    Broadcasts SSE events via session_manager.broadcast_sync().
    """
    async with state.run_lock:
        try:
            # Rebuild current message list from DB
            async with AsyncSessionLocal() as db:
                messages = await _reconstruct_messages(session_id, db)

            # ---------------------------------------------------------------
            # Callbacks — called synchronously from within sampling_loop.
            # put_nowait() is safe here (same event loop thread).
            # ---------------------------------------------------------------

            def output_callback(block: dict) -> None:
                block_type = block.get("type")
                if block_type == "text":
                    session_manager.broadcast_sync(session_id, {
                        "event": "text",
                        "session_id": session_id,
                        "timestamp": _now_iso(),
                        "text": block.get("text", ""),
                    })
                elif block_type == "thinking":
                    session_manager.broadcast_sync(session_id, {
                        "event": "thinking",
                        "session_id": session_id,
                        "timestamp": _now_iso(),
                        "thinking": block.get("thinking", ""),
                    })
                elif block_type == "tool_use":
                    session_manager.broadcast_sync(session_id, {
                        "event": "tool_use",
                        "session_id": session_id,
                        "timestamp": _now_iso(),
                        "tool_id": block.get("id", ""),
                        "tool_name": block.get("name", ""),
                        "tool_input": block.get("input", {}),
                    })

            def tool_output_callback(result: ToolResult, tool_use_id: str) -> None:
                session_manager.broadcast_sync(session_id, {
                    "event": "tool_result",
                    "session_id": session_id,
                    "timestamp": _now_iso(),
                    "tool_id": tool_use_id,
                    "output": result.output,
                    "error": result.error,
                    "screenshot_base64": result.base64_image,
                    "system_msg": result.system,
                    "is_error": result.error is not None,
                })

            def api_response_callback(
                request: httpx.Request,
                response: httpx.Response | object | None,
                error: Exception | None,
            ) -> None:
                if error:
                    session_manager.broadcast_sync(session_id, {
                        "event": "api_error",
                        "session_id": session_id,
                        "timestamp": _now_iso(),
                        "error_type": type(error).__name__,
                        "message": str(error),
                    })
                else:
                    # Emit request details
                    try:
                        req_body = json.loads(request.content.decode("utf-8", errors="replace"))
                    except Exception:
                        req_body = None
                    session_manager.broadcast_sync(session_id, {
                        "event": "api_request",
                        "session_id": session_id,
                        "timestamp": _now_iso(),
                        "method": request.method,
                        "url": str(request.url),
                        "body": req_body,
                    })
                    # Emit response details
                    if isinstance(response, httpx.Response):
                        try:
                            resp_body = response.json()
                        except Exception:
                            resp_body = None
                        session_manager.broadcast_sync(session_id, {
                            "event": "api_response",
                            "session_id": session_id,
                            "timestamp": _now_iso(),
                            "status_code": response.status_code,
                            "body": resp_body,
                        })

            # ---------------------------------------------------------------
            # Run the agent loop
            # ---------------------------------------------------------------
            updated_messages = await sampling_loop(
                model=session_snapshot["model"],
                provider=APIProvider(session_snapshot["provider"]),
                system_prompt_suffix=session_snapshot["system_prompt_suffix"],
                messages=messages,
                output_callback=output_callback,
                tool_output_callback=tool_output_callback,
                api_response_callback=api_response_callback,
                api_key=decrypt_api_key(session_snapshot["api_key_encrypted"]),
                only_n_most_recent_images=session_snapshot["only_n_most_recent_images"],
                max_tokens=session_snapshot["max_tokens"],
                tool_version=session_snapshot["tool_version"],
                thinking_budget=session_snapshot["thinking_budget"],
                token_efficient_tools_beta=session_snapshot["token_efficient_tools_beta"],
            )

            await _persist_new_messages(session_id, updated_messages, messages_before_count)
            await _set_session_status(session_id, "idle")

            session_manager.broadcast_sync(session_id, {
                "event": "done",
                "session_id": session_id,
                "timestamp": _now_iso(),
                "total_messages": len(updated_messages),
                "final_status": "completed",
            })

        except asyncio.CancelledError:
            await _set_session_status(session_id, "idle")
            session_manager.broadcast_sync(session_id, {
                "event": "done",
                "session_id": session_id,
                "timestamp": _now_iso(),
                "total_messages": 0,
                "final_status": "cancelled",
            })
            raise  # re-raise so the Task is properly cancelled

        except Exception as exc:
            await _set_session_status(session_id, "error")
            session_manager.broadcast_sync(session_id, {
                "event": "error",
                "session_id": session_id,
                "timestamp": _now_iso(),
                "code": "loop_error",
                "message": str(exc),
            })

        finally:
            state.active_task = None
            session_manager.signal_done(session_id)


# ---------------------------------------------------------------------------
# POST /sessions/{id}/messages
# ---------------------------------------------------------------------------

@router.post(
    "/{session_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send a user message and start the sampling loop",
)
async def send_message(
    session_id: str,
    body: SendMessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SendMessageResponse:
    session = await _get_session_or_404(session_id, db)

    state = await session_manager.get_or_create(session_id)

    # Optionally cancel existing run
    if body.interrupt_current:
        await session_manager.cancel_run(session_id)

    # Prevent duplicate concurrent runs
    if session_manager.is_running(session_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "already_running",
                "message": "A sampling loop is already running for this session. "
                           "Send interrupt_current=true to cancel it first.",
            },
        )

    # Persist the user message
    msg_id = str(uuid.uuid4())
    user_message = Message(
        id=msg_id,
        session_id=session_id,
        role="user",
        content_json=[{"type": "text", "text": body.content}],
        display_role="user",
    )
    db.add(user_message)
    await db.execute(
        update(Session)
        .where(Session.id == session_id)
        .values(status="running", updated_at=datetime.utcnow())
    )
    await db.commit()

    # Count messages before this run (for diff computation later)
    count_result = await db.execute(
        select(func.count(Message.id))
        .where(
            Message.session_id == session_id,
            Message.display_role.in_(["user", "assistant", "tool"]),
        )
    )
    messages_before = count_result.scalar_one()

    # Snapshot session config (avoid passing db session across async boundaries)
    session_snapshot = {
        "model": session.model,
        "provider": session.provider,
        "tool_version": session.tool_version,
        "max_tokens": session.max_tokens,
        "only_n_most_recent_images": session.only_n_most_recent_images,
        "system_prompt_suffix": session.system_prompt_suffix,
        "thinking_budget": session.thinking_budget,
        "token_efficient_tools_beta": session.token_efficient_tools_beta,
        "api_key_encrypted": session.api_key_encrypted,
    }

    # Launch background task
    task = asyncio.create_task(
        _run_sampling_loop(session_id, session_snapshot, messages_before, state)
    )
    state.active_task = task

    base_url = str(request.base_url).rstrip("/")
    return SendMessageResponse(
        message_id=msg_id,
        session_id=session_id,
        status="accepted",
        stream_url=f"{base_url}/sessions/{session_id}/stream",
    )


# ---------------------------------------------------------------------------
# GET /sessions/{id}/stream  (SSE)
# ---------------------------------------------------------------------------

async def _sse_generator(
    session_id: str,
    queue: asyncio.Queue,
    request: Request,
) -> AsyncGenerator[str, None]:
    """Yields SSE-formatted strings. Ends on None sentinel or client disconnect."""
    event_id = 0
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                # Heartbeat to keep the connection alive through proxies
                yield ": heartbeat\n\n"
                if await request.is_disconnected():
                    break
                continue

            if item is None:
                # Sentinel from signal_done() — stream is finished
                break

            payload = json.loads(item)
            event_type = payload.get("event", "message")
            event_id += 1
            yield f"id: {event_id}\nevent: {event_type}\ndata: {item}\n\n"

            if await request.is_disconnected():
                break
    finally:
        session_manager.unsubscribe(session_id, queue)


@router.get(
    "/{session_id}/stream",
    summary="SSE stream of agent events for this session",
)
async def stream_events(
    session_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    await _get_session_or_404(session_id, db)
    queue = await session_manager.subscribe(session_id)
    return StreamingResponse(
        _sse_generator(session_id, queue, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# DELETE /sessions/{id}/run
# ---------------------------------------------------------------------------

@router.delete(
    "/{session_id}/run",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel the currently running sampling loop",
)
async def cancel_run(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    await _get_session_or_404(session_id, db)

    if not session_manager.is_running(session_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "not_running", "message": "No loop is currently running"},
        )

    await session_manager.cancel_run(session_id)
