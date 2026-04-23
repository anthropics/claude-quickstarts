"""REST endpoints for the chat domain."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from computer_use_demo import settings
from computer_use_demo.api.chats.repo import ChatRepo, EventRepo, ImageRepo, MessageRepo
from computer_use_demo.api.chats.schemas import (
    ChatCreate,
    ChatDetail,
    ChatOut,
    MessageIn,
    MessageOut,
    StartTurnOut,
)
from computer_use_demo.api.chats.services.chat_manager import (
    ChatManager,
    TurnAlreadyRunning,
)
from computer_use_demo.api.deps import get_chat_manager, get_db
from computer_use_demo.api.system.services import config_store

router = APIRouter(prefix="/api/chats", tags=["chats"])


def _resolve_api_key() -> str:
    if settings.ANTHROPIC_API_KEY:
        return settings.ANTHROPIC_API_KEY
    stored = config_store.get_api_key()
    if stored:
        return stored
    raise HTTPException(
        status_code=400,
        detail="No API key configured. Set ANTHROPIC_API_KEY or PUT /api/system/api-key.",
    )


def _resolve_base_url() -> str | None:
    if settings.ANTHROPIC_BASE_URL:
        return settings.ANTHROPIC_BASE_URL
    stored = config_store.get_base_url()
    return stored or None


@router.post("", response_model=ChatOut, status_code=201)
async def create_chat(body: ChatCreate, db: AsyncSession = Depends(get_db)) -> ChatOut:
    row = await ChatRepo(db).create(
        title=body.title,
        model=body.model,
        provider=body.provider,
        tool_version=body.tool_version,
        system_prompt_suffix=body.system_prompt_suffix,
        max_tokens=body.max_tokens,
        thinking_budget=body.thinking_budget,
        only_n_most_recent_images=body.only_n_most_recent_images,
        token_efficient_tools_beta=body.token_efficient_tools_beta,
    )
    return ChatOut.model_validate(row).model_copy(update={"message_count": 0})


@router.get("", response_model=list[ChatOut])
async def list_chats(db: AsyncSession = Depends(get_db)) -> list[ChatOut]:
    rows = await ChatRepo(db).list_with_counts()
    return [
        ChatOut.model_validate(row).model_copy(update={"message_count": int(count)})
        for row, count in rows
    ]


@router.get("/{chat_id}", response_model=ChatDetail)
async def get_chat(chat_id: str, db: AsyncSession = Depends(get_db)) -> ChatDetail:
    row = await ChatRepo(db).get(chat_id)
    if row is None:
        raise HTTPException(status_code=404, detail="chat not found")
    messages = await MessageRepo(db).list_for_chat(chat_id)
    last_seq = await EventRepo(db).max_seq(chat_id)
    base = ChatOut.model_validate(row).model_dump()
    base["message_count"] = len(messages)
    base["messages"] = [MessageOut.model_validate(m) for m in messages]
    base["last_event_seq"] = last_seq
    return ChatDetail(**base)


@router.delete("/{chat_id}", status_code=204)
async def delete_chat(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
    manager: ChatManager = Depends(get_chat_manager),
) -> Response:
    await manager.cancel(chat_id)
    ok = await ChatRepo(db).delete(chat_id)
    if not ok:
        raise HTTPException(status_code=404, detail="chat not found")
    await db.commit()
    return Response(status_code=204)


@router.post("/{chat_id}/messages", response_model=StartTurnOut, status_code=202)
async def send_message(
    chat_id: str,
    body: MessageIn,
    db: AsyncSession = Depends(get_db),
    manager: ChatManager = Depends(get_chat_manager),
) -> StartTurnOut:
    row = await ChatRepo(db).get(chat_id)
    if row is None:
        raise HTTPException(status_code=404, detail="chat not found")
    if row.provider == "anthropic":
        api_key = _resolve_api_key()
        base_url = _resolve_base_url()
    else:
        api_key = ""
        base_url = None
    # Release the DB dependency before spawning the turn (which opens its own session).
    await db.commit()
    try:
        task = await manager.start_turn(
            chat_id=chat_id,
            api_key=api_key,
            base_url=base_url,
            user_content=body.content,
        )
    except TurnAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # Task name doubles as a correlation; the real turn_id is embedded in events.
    return StartTurnOut(turn_id=task.get_name(), status="running")


@router.post("/{chat_id}/cancel", status_code=204)
async def cancel_chat(
    chat_id: str, manager: ChatManager = Depends(get_chat_manager)
) -> Response:
    cancelled = await manager.cancel(chat_id)
    if not cancelled:
        raise HTTPException(status_code=409, detail="no turn in progress")
    return Response(status_code=204)


@router.get("/{chat_id}/images/{image_id}")
async def get_image(
    chat_id: str, image_id: str, db: AsyncSession = Depends(get_db)
) -> Response:
    img = await ImageRepo(db).get(image_id)
    if img is None or img.chat_id != chat_id:
        raise HTTPException(status_code=404, detail="image not found")
    return Response(content=img.bytes, media_type=img.mime)
