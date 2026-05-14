import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..crypto import decrypt_api_key, encrypt_api_key
from ..database import get_db
from ..models import Message, Session
from ..schemas import (
    SessionCreateRequest,
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
)
from ..session_manager import session_manager

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _session_to_response(session: Session, message_count: int = 0) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        model=session.model,
        provider=session.provider,
        tool_version=session.tool_version,
        max_tokens=session.max_tokens,
        only_n_most_recent_images=session.only_n_most_recent_images,
        system_prompt_suffix=session.system_prompt_suffix,
        thinking_budget=session.thinking_budget,
        token_efficient_tools_beta=session.token_efficient_tools_beta,
        status=session.status if not session_manager.is_running(session.id) else "running",
        message_count=message_count,
    )


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new computer-use session",
)
async def create_session(
    body: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    if body.provider == "anthropic" and not body.api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="api_key is required for the anthropic provider",
        )

    session = Session(
        id=str(uuid.uuid4()),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        model=body.model,
        provider=body.provider,
        tool_version=body.tool_version,
        max_tokens=body.max_tokens,
        only_n_most_recent_images=body.only_n_most_recent_images,
        system_prompt_suffix=body.system_prompt_suffix,
        thinking_budget=body.thinking_budget,
        token_efficient_tools_beta=body.token_efficient_tools_beta,
        api_key_encrypted=encrypt_api_key(body.api_key),
        status="idle",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_to_response(session, message_count=0)


@router.get(
    "",
    response_model=SessionListResponse,
    summary="List all sessions, newest first",
)
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> SessionListResponse:
    total_result = await db.execute(select(func.count(Session.id)))
    total = total_result.scalar_one()

    result = await db.execute(
        select(Session).order_by(Session.created_at.desc()).limit(limit).offset(offset)
    )
    sessions = result.scalars().all()

    # Get message counts in one query
    count_result = await db.execute(
        select(Message.session_id, func.count(Message.id).label("cnt"))
        .where(Message.session_id.in_([s.id for s in sessions]))
        .group_by(Message.session_id)
    )
    counts = {row.session_id: row.cnt for row in count_result}

    return SessionListResponse(
        sessions=[_session_to_response(s, counts.get(s.id, 0)) for s in sessions],
        total=total,
    )


@router.get(
    "/{session_id}",
    response_model=SessionDetailResponse,
    summary="Get session detail with all messages",
)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> SessionDetailResponse:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    msg_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()

    base = _session_to_response(session, message_count=len(messages))
    return SessionDetailResponse(
        **base.model_dump(),
        messages=[
            {
                "id": m.id,
                "session_id": m.session_id,
                "created_at": m.created_at,
                "role": m.role,
                "content_json": m.content_json,
                "display_role": m.display_role,
            }
            for m in messages
        ],
    )


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a session and all its messages",
)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Cancel any running loop and remove in-memory state
    await session_manager.remove(session_id)

    await db.delete(session)
    await db.commit()
