"""Orchestrates a single assistant turn: drives the sampling loop, persists
messages/events, fans out to WebSocket subscribers, and serialises tool
actions against the shared desktop.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from computer_use_demo import loop as loop_module
from computer_use_demo.api.chats.models import Chat as ChatRow
from computer_use_demo.api.chats.repo import (
    ChatRepo,
    EventRepo,
    ImageRepo,
    MessageRepo,
    ToolResultRepo,
)
from computer_use_demo.api.chats.services.event_bus import EventBus
from computer_use_demo.api.db import session_scope
from computer_use_demo.tools import ToolCollection, ToolResult
from computer_use_demo.tools.groups import TOOL_GROUPS_BY_VERSION

logger = logging.getLogger(__name__)

# Only one agent turn may run at a time on the shared Xvfb desktop.
# The lock is held for the entire sampling loop (not just individual tool
# calls) so concurrent chats cannot interleave actions on the screen.
DESKTOP_LOCK = asyncio.Lock()


_background_tasks: set[asyncio.Task] = set()


class AgentRunner:
    def __init__(self, bus: EventBus, sampling_loop=loop_module.sampling_loop) -> None:
        self._bus = bus
        self._sampling_loop = sampling_loop

    async def run_turn(
        self,
        *,
        chat_id: str,
        api_key: str,
        base_url: str | None = None,
        user_content: str,
    ) -> None:
        turn_id = str(uuid.uuid4())
        try:
            params, messages = await self._prepare(chat_id, turn_id, user_content)
        except Exception as exc:
            logger.exception("failed to prepare turn")
            await self._emit(chat_id, turn_id, "error", {"message": str(exc)})
            await self._set_status(chat_id, "error")
            return

        await self._emit(
            chat_id,
            turn_id,
            "turn_started",
            {"message_count": len(messages)},
        )

        tool_runner = _make_tool_runner(params["tool_version"])

        block_counter = {"n": -1}
        tool_use_info: dict[str, dict[str, Any]] = {}

        def delta_cb(event: Any) -> None:
            self._publish_delta(chat_id, turn_id, event, block_counter)

        def output_cb(block: Any) -> None:
            block_counter["n"] += 1
            block_data = _normalise_block(block)
            if block_data.get("type") == "tool_use" and block_data.get("id"):
                tool_use_info[block_data["id"]] = {
                    "name": block_data.get("name"),
                    "input": block_data.get("input", {}),
                }
            self._publish_nowait(
                chat_id,
                turn_id,
                "assistant_block",
                {"block_index": block_counter["n"], "block": block_data},
            )

        def tool_output_cb(result: ToolResult, tool_use_id: str) -> None:
            info = tool_use_info.get(tool_use_id, {})
            task = asyncio.create_task(
                self._handle_tool_result(
                    chat_id,
                    turn_id,
                    result,
                    tool_use_id,
                    tool_name=info.get("name"),
                    tool_input=info.get("input", {}),
                )
            )
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

        api_error: dict[str, Any] = {}

        def api_response_cb(_req, response, error) -> None:
            self._publish_nowait(
                chat_id,
                turn_id,
                "api_meta",
                _summarise_api_response(response, error),
            )
            if error is not None:
                api_error["message"] = str(error)
                api_error["code"] = type(error).__name__
                self._publish_nowait(
                    chat_id,
                    turn_id,
                    "error",
                    {"message": api_error["message"], "code": api_error["code"]},
                )

        initial_len = len(messages)
        async with DESKTOP_LOCK:
            try:
                final_messages = await self._sampling_loop(
                    model=params["model"],
                    provider=params["provider"],
                    system_prompt_suffix=params["system_prompt_suffix"],
                    messages=messages,
                    output_callback=output_cb,
                    tool_output_callback=tool_output_cb,
                    api_response_callback=api_response_cb,
                    api_key=api_key,
                    base_url=base_url,
                    only_n_most_recent_images=params["only_n_most_recent_images"],
                    max_tokens=params["max_tokens"],
                    tool_version=params["tool_version"],
                    thinking_budget=params["thinking_budget"],
                    token_efficient_tools_beta=params["token_efficient_tools_beta"],
                    delta_callback=delta_cb,
                    tool_runner=tool_runner,
                )
            except asyncio.CancelledError:
                await self._emit(chat_id, turn_id, "cancelled", {})
                await self._set_status(chat_id, "idle")
                raise
            except Exception as exc:
                logger.exception("sampling loop failed")
                await self._emit(chat_id, turn_id, "error", {"message": str(exc)})
                await self._set_status(chat_id, "error")
                return

        await self._persist_new_messages(chat_id, turn_id, final_messages, initial_len)
        if api_error:
            # Sampling loop swallows APIStatusError and returns normally; surface it
            # as an error turn instead of a silent "turn_complete".
            await self._set_status(chat_id, "error")
        else:
            await self._emit(chat_id, turn_id, "turn_complete", {})
            await self._set_status(chat_id, "idle")

    # --- helpers -----------------------------------------------------------

    async def _prepare(
        self, chat_id: str, turn_id: str, user_content: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        async with session_scope() as db:
            chats = ChatRepo(db)
            row: ChatRow | None = await chats.get(chat_id)
            if row is None:
                raise ValueError(f"chat {chat_id} not found")
            user_content_json = [{"type": "text", "text": user_content}]
            await MessageRepo(db).create(
                chat_id=chat_id,
                turn_id=turn_id,
                role="user",
                content_json=user_content_json,
            )
            await chats.update(chat_id, status="running")
            db_messages = await MessageRepo(db).list_for_chat(chat_id)
            params = {
                "model": row.model,
                "provider": loop_module.APIProvider(row.provider),
                "tool_version": row.tool_version,
                "system_prompt_suffix": row.system_prompt_suffix or "",
                "max_tokens": row.max_tokens,
                "thinking_budget": row.thinking_budget,
                "only_n_most_recent_images": row.only_n_most_recent_images,
                "token_efficient_tools_beta": row.token_efficient_tools_beta,
            }
            messages = [
                {"role": m.role, "content": m.content_json} for m in db_messages
            ]
        return params, messages

    async def _persist_new_messages(
        self,
        chat_id: str,
        turn_id: str,
        final_messages: list[dict[str, Any]],
        start_index: int,
    ) -> None:
        # Persist anything appended during the loop (assistant + tool-result user msgs).
        new = final_messages[start_index:]
        if not new:
            return
        async with session_scope() as db:
            messages = MessageRepo(db)
            for msg in new:
                await messages.create(
                    chat_id=chat_id,
                    turn_id=turn_id,
                    role=msg["role"],
                    content_json=msg["content"],
                )

    async def _handle_tool_result(
        self,
        chat_id: str,
        turn_id: str,
        result: ToolResult,
        tool_use_id: str,
        *,
        tool_name: str | None = None,
        tool_input: dict[str, Any] | None = None,
    ) -> None:
        image_id: str | None = None
        if result.base64_image:
            try:
                raw = base64.b64decode(result.base64_image)
                async with session_scope() as db:
                    img = await ImageRepo(db).create(
                        chat_id=chat_id, bytes=raw, mime="image/png"
                    )
                    image_id = img.id
            except Exception:
                logger.exception("failed to persist tool screenshot")
        async with session_scope() as db:
            await ToolResultRepo(db).create(
                chat_id=chat_id,
                turn_id=turn_id,
                tool_use_id=tool_use_id,
                output=result.output,
                error=result.error,
                system=result.system,
                image_id=image_id,
            )
        data: dict[str, Any] = {
            "tool_use_id": tool_use_id,
            "tool_name": tool_name,
            "tool_action": (tool_input or {}).get("action"),
            "output": result.output,
            "error": result.error,
        }
        if image_id:
            data["image_url"] = f"/api/chats/{chat_id}/images/{image_id}"
        await self._emit(chat_id, turn_id, "tool_result", data)

    def _publish_delta(
        self,
        chat_id: str,
        turn_id: str,
        event: Any,
        block_counter: dict[str, int],
    ) -> None:
        etype = getattr(event, "type", None)
        if etype == "content_block_start":
            block_index = getattr(event, "index", block_counter["n"] + 1)
            block = getattr(event, "content_block", None)
            block_dict = _normalise_block(block) if block is not None else {}
            self._publish_nowait(
                chat_id,
                turn_id,
                "block_start",
                {"block_index": block_index, "block": block_dict},
            )
        elif etype == "content_block_delta":
            delta = getattr(event, "delta", None)
            block_index = getattr(event, "index", block_counter["n"])
            dtype = getattr(delta, "type", None)
            if dtype == "text_delta":
                self._publish_nowait(
                    chat_id,
                    turn_id,
                    "text_delta",
                    {"block_index": block_index, "text": getattr(delta, "text", "")},
                )
            elif dtype == "thinking_delta":
                self._publish_nowait(
                    chat_id,
                    turn_id,
                    "thinking_delta",
                    {
                        "block_index": block_index,
                        "text": getattr(delta, "thinking", ""),
                    },
                )
            elif dtype == "input_json_delta":
                self._publish_nowait(
                    chat_id,
                    turn_id,
                    "input_json_delta",
                    {
                        "block_index": block_index,
                        "partial_json": getattr(delta, "partial_json", ""),
                    },
                )

    def _publish_nowait(
        self,
        chat_id: str,
        turn_id: str | None,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        task = asyncio.create_task(self._emit(chat_id, turn_id, event_type, data))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    async def _emit(
        self,
        chat_id: str,
        turn_id: str | None,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        seq = await self._bus.next_seq(chat_id)
        ts = datetime.now(timezone.utc)
        envelope = {
            "v": 1,
            "chat_id": chat_id,
            "turn_id": turn_id,
            "seq": seq,
            "ts": ts.isoformat(),
            "type": event_type,
            "data": data,
        }
        try:
            async with session_scope() as db:
                await EventRepo(db).create(
                    chat_id=chat_id,
                    turn_id=turn_id,
                    seq=seq,
                    type=event_type,
                    data_json=data,
                )
        except Exception:
            logger.exception("failed to persist event")
        self._bus.publish(chat_id, envelope)

    async def _set_status(self, chat_id: str, status: str) -> None:
        try:
            async with session_scope() as db:
                await ChatRepo(db).update(chat_id, status=status)
        except Exception:
            logger.exception("failed to update chat status")


def _make_tool_runner(tool_version: str):
    """Return a tool dispatch callable for the given tool version."""
    group = TOOL_GROUPS_BY_VERSION[tool_version]
    collection = ToolCollection(*(cls() for cls in group.tools))

    async def runner(name: str, tool_input: dict[str, Any]) -> ToolResult:
        return await collection.run(name=name, tool_input=tool_input)

    return runner


def _normalise_block(block: Any) -> dict[str, Any]:
    if isinstance(block, dict):
        return block
    if hasattr(block, "model_dump"):
        return block.model_dump()
    return {"repr": repr(block)}


def _summarise_api_response(response: Any, error: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if error is not None:
        out["error"] = str(error)
    if response is None:
        return out
    # BetaMessage-like
    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason is not None:
        out["stop_reason"] = stop_reason
    usage = getattr(response, "usage", None)
    if usage is not None and hasattr(usage, "model_dump"):
        out["usage"] = usage.model_dump()
    request_id = getattr(response, "id", None)
    if request_id:
        out["id"] = request_id
    # httpx.Response-like
    status_code = getattr(response, "status_code", None)
    if status_code is not None:
        out["status"] = status_code
    return out
