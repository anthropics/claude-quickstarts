import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(64), nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096, nullable=False)
    only_n_most_recent_images: Mapped[int | None] = mapped_column(Integer, nullable=True)
    system_prompt_suffix: Mapped[str] = mapped_column(Text, default="", nullable=False)
    thinking_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_efficient_tools_beta: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # "idle" | "running" | "cancelled" | "error"
    status: Mapped[str] = mapped_column(String(32), default="idle", nullable=False)

    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="session", order_by="Message.created_at", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_sessions_created_at", "created_at"),
        Index("ix_sessions_status", "status"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    # "user" | "assistant" — Anthropic API role
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    # Full serialized BetaContentBlockParam list (or string)
    content_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    # "user" | "assistant" | "tool" | "api_request" | "api_response"
    display_role: Mapped[str] = mapped_column(String(32), nullable=False)

    session: Mapped["Session"] = relationship("Session", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_session_id", "session_id"),
        Index("ix_messages_session_created", "session_id", "created_at"),
    )
