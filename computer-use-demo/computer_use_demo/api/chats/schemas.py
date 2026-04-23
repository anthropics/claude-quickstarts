"""Pydantic v2 request/response models for the chat domain."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatCreate(BaseModel):
    title: str | None = None
    model: str
    provider: Literal["anthropic", "bedrock", "vertex"]
    tool_version: str
    system_prompt_suffix: str = ""
    max_tokens: int = 4096
    thinking_budget: int | None = None
    only_n_most_recent_images: int | None = None
    token_efficient_tools_beta: bool = False


class ChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str | None
    model: str
    provider: str
    tool_version: str
    system_prompt_suffix: str
    max_tokens: int
    thinking_budget: int | None
    only_n_most_recent_images: int | None
    token_efficient_tools_beta: bool
    status: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    turn_id: str | None
    role: str
    content: Any = Field(validation_alias="content_json")
    created_at: datetime


class ChatDetail(ChatOut):
    messages: list[MessageOut] = []
    last_event_seq: int = 0


class MessageIn(BaseModel):
    content: str


class StartTurnOut(BaseModel):
    turn_id: str
    status: str


class EventEnvelope(BaseModel):
    v: int = 1
    chat_id: str
    turn_id: str | None
    seq: int
    ts: datetime
    type: str
    data: dict[str, Any] = Field(default_factory=dict)
