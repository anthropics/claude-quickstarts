"""Per-model repositories for the chat domain.

Each class inherits the generic CRUD (``create/get/list/update/delete``)
from :class:`computer_use_demo.api.db.Repo` and adds the queries the
domain actually needs (counts, date-ordered listings, seq-scoped replays).
"""

from __future__ import annotations

from sqlalchemy import desc, func, select

from computer_use_demo.api.chats.models import (
    Chat,
    Event,
    Image,
    Message,
    ToolResultRow,
)
from computer_use_demo.api.db import Repo


class ChatRepo(Repo[Chat]):
    model = Chat

    async def list_with_counts(self) -> list[tuple[Chat, int]]:
        """Chats newest-first, each paired with its message count."""
        stmt = (
            select(Chat, func.count(Message.id))
            .outerjoin(Message, Message.chat_id == Chat.id)
            .group_by(Chat.id)
            .order_by(desc(Chat.created_at))
        )
        result = await self._session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]


class MessageRepo(Repo[Message]):
    model = Message

    async def list_for_chat(self, chat_id: str) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars())


class ToolResultRepo(Repo[ToolResultRow]):
    model = ToolResultRow


class ImageRepo(Repo[Image]):
    model = Image


class EventRepo(Repo[Event]):
    model = Event

    async def list_since(self, chat_id: str, since_seq: int) -> list[Event]:
        stmt = (
            select(Event)
            .where(Event.chat_id == chat_id, Event.seq > since_seq)
            .order_by(Event.seq)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars())

    async def max_seq(self, chat_id: str) -> int:
        stmt = select(func.coalesce(func.max(Event.seq), 0)).where(
            Event.chat_id == chat_id
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())
