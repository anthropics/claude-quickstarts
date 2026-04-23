"""ORM models for the chat domain: Chat, Message, ToolResult, Image, Event."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from computer_use_demo.api.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str | None] = mapped_column(String(255))
    model: Mapped[str] = mapped_column(String(128))
    provider: Mapped[str] = mapped_column(String(32))
    tool_version: Mapped[str] = mapped_column(String(64))
    system_prompt_suffix: Mapped[str] = mapped_column(Text, default="")
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    thinking_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    only_n_most_recent_images: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    token_efficient_tools_beta: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(16), default="idle")
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    messages: Mapped[list[Message]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_chat_created", "chat_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    chat_id: Mapped[str] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), index=True
    )
    turn_id: Mapped[str | None] = mapped_column(String(36), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content_json: Mapped[Any] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    chat: Mapped[Chat] = relationship(back_populates="messages")


class ToolResultRow(Base):
    __tablename__ = "tool_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    chat_id: Mapped[str] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), index=True
    )
    turn_id: Mapped[str | None] = mapped_column(String(36), index=True)
    tool_use_id: Mapped[str] = mapped_column(String(128), unique=True)
    output: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    system: Mapped[str | None] = mapped_column(Text)
    image_id: Mapped[str | None] = mapped_column(
        ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=_now)


class Image(Base):
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    chat_id: Mapped[str] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), index=True
    )
    mime: Mapped[str] = mapped_column(String(64), default="image/png")
    bytes: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(default=_now)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_chat_seq", "chat_id", "seq", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    chat_id: Mapped[str] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), index=True
    )
    turn_id: Mapped[str | None] = mapped_column(String(36), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(32))
    data_json: Mapped[Any] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=_now)
