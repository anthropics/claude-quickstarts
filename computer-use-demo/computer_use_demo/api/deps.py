"""Dependency providers for FastAPI routes."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from computer_use_demo.api.chats.services.agent_runner import AgentRunner
from computer_use_demo.api.chats.services.chat_manager import ChatManager
from computer_use_demo.api.chats.services.event_bus import EventBus
from computer_use_demo.api.db import session_scope


async def get_db() -> AsyncIterator[AsyncSession]:
    async with session_scope() as db:
        yield db


def get_bus(request: Request) -> EventBus:
    return request.app.state.bus


def get_chat_manager(request: Request) -> ChatManager:
    return request.app.state.chat_manager


def get_agent_runner(request: Request) -> AgentRunner:
    return request.app.state.agent_runner
