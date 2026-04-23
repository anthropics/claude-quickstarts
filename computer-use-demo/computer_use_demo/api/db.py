"""Async SQLAlchemy engine, session factory, and generic CRUD repository."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, ClassVar, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from computer_use_demo.settings import DATABASE_URL


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _apply_sqlite_pragmas(engine: AsyncEngine) -> None:
    from sqlalchemy import event

    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "connect")
    def _on_connect(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


def init_engine(url: str | None = None) -> AsyncEngine:
    global _engine, _session_factory
    target = url or DATABASE_URL
    _engine = create_async_engine(target, future=True)
    if target.startswith("sqlite"):
        _apply_sqlite_pragmas(_engine)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        init_engine()
    assert _engine is not None
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        init_engine()
    assert _session_factory is not None
    return _session_factory


async def create_all() -> None:
    from computer_use_demo.api.chats import models  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


ModelT = TypeVar("ModelT", bound=Base)


class Repo(Generic[ModelT]):
    """Base class for async repositories. Subclasses must set ``model``."""

    model: ClassVar[type[ModelT]]  # type: ignore[misc]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **fields: Any) -> ModelT:
        row = self.model(**fields)
        self._session.add(row)
        await self._session.flush()
        return row

    async def get(self, id_: str) -> ModelT | None:
        return await self._session.get(self.model, id_)

    async def list(self, *, order_by: Any = None) -> list[ModelT]:
        stmt = select(self.model)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        result = await self._session.execute(stmt)
        return list(result.scalars())

    async def update(self, id_: str, **fields: Any) -> ModelT | None:
        row = await self.get(id_)
        if row is None:
            return None
        for key, value in fields.items():
            setattr(row, key, value)
        return row

    async def delete(self, id_: str) -> bool:
        row = await self.get(id_)
        if row is None:
            return False
        await self._session.delete(row)
        return True
