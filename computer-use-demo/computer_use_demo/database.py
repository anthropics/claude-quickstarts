"""
Database models and session management for chat history persistence.
"""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Database URL - defaults to SQLite, can be overridden with DATABASE_URL env var
DATABASE_URL = (
    "sqlite+aiosqlite:///./computer_use_demo.db"
    if not __import__("os").getenv("DATABASE_URL")
    else __import__("os").getenv("DATABASE_URL").replace("postgresql://", "postgresql+asyncpg://")
)


class Base(DeclarativeBase):
    """Base class for database models."""
    pass


class SessionModel(Base):
    """Database model for sessions."""
    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True, index=True)
    api_key = Column(String, nullable=True)  # Encrypted or hashed in production
    provider = Column(String, nullable=False, default="anthropic")
    model = Column(String, nullable=False)
    tool_version = Column(String, nullable=False)
    has_thinking = Column(Boolean, default=False)
    output_tokens = Column(Integer, default=16384)
    max_output_tokens = Column(Integer, default=131072)
    thinking_budget = Column(Integer, default=0)
    only_n_most_recent_images = Column(Integer, default=3)
    custom_system_prompt = Column(Text, default="")
    hide_images = Column(Boolean, default=False)
    token_efficient_tools_beta = Column(Boolean, default=False)
    in_sampling_loop = Column(Boolean, default=False)
    auth_validated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class MessageModel(Base):
    """Database model for messages."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)  # user, assistant, tool
    content = Column(JSON, nullable=False)  # Store message content as JSON
    message_index = Column(Integer, nullable=False)  # Order of message in conversation
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class ToolResultModel(Base):
    """Database model for tool results."""
    __tablename__ = "tool_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, nullable=False, index=True)
    tool_id = Column(String, nullable=False, index=True)
    tool_name = Column(String, nullable=True)
    output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    has_image = Column(Boolean, default=False)
    base64_image = Column(Text, nullable=True)  # Store base64 encoded images
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class APIResponseModel(Base):
    """Database model for API request/response logs."""
    __tablename__ = "api_responses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, nullable=False, index=True)
    response_id = Column(String, nullable=False, index=True)
    request_method = Column(String, nullable=True)
    request_url = Column(String, nullable=True)
    request_headers = Column(JSON, nullable=True)
    request_body = Column(Text, nullable=True)
    response_status = Column(Integer, nullable=True)
    response_headers = Column(JSON, nullable=True)
    response_body = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


# Create async engine and session
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Get database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

