from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ToolVersion = Literal[
    "computer_use_20250124",
    "computer_use_20241022",
    "computer_use_20250429",
    "computer_use_20251124",
]
APIProvider = Literal["anthropic", "bedrock", "vertex"]


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class SessionCreateRequest(BaseModel):
    model: str = Field(default="claude-sonnet-4-5-20250929")
    provider: APIProvider = Field(default="anthropic")
    tool_version: ToolVersion = Field(default="computer_use_20250124")
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    only_n_most_recent_images: int | None = Field(default=3, ge=0)
    system_prompt_suffix: str = Field(default="", max_length=4096)
    thinking_budget: int | None = Field(default=None, ge=1024)
    token_efficient_tools_beta: bool = Field(default=False)
    api_key: str = Field(default="", description="Anthropic API key (required for anthropic provider)")


class SessionResponse(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    model: str
    provider: str
    tool_version: str
    max_tokens: int
    only_n_most_recent_images: int | None
    system_prompt_suffix: str
    thinking_budget: int | None
    token_efficient_tools_beta: bool
    status: str
    message_count: int = 0

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


class MessageResponse(BaseModel):
    id: str
    session_id: str
    created_at: datetime
    role: str
    content_json: Any
    display_role: str

    model_config = {"from_attributes": True}


class SessionDetailResponse(SessionResponse):
    messages: list[MessageResponse] = []


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=100_000)
    interrupt_current: bool = Field(
        default=False,
        description="Cancel any running loop before sending",
    )


class SendMessageResponse(BaseModel):
    message_id: str
    session_id: str
    status: str  # "accepted"
    stream_url: str


# ---------------------------------------------------------------------------
# SSE event data payloads
# ---------------------------------------------------------------------------

class TextEvent(BaseModel):
    event: Literal["text"] = "text"
    session_id: str
    timestamp: str
    text: str


class ThinkingEvent(BaseModel):
    event: Literal["thinking"] = "thinking"
    session_id: str
    timestamp: str
    thinking: str


class ToolUseEvent(BaseModel):
    event: Literal["tool_use"] = "tool_use"
    session_id: str
    timestamp: str
    tool_id: str
    tool_name: str
    tool_input: dict[str, Any]


class ToolResultEvent(BaseModel):
    event: Literal["tool_result"] = "tool_result"
    session_id: str
    timestamp: str
    tool_id: str
    output: str | None = None
    error: str | None = None
    screenshot_base64: str | None = None
    system_msg: str | None = None
    is_error: bool = False


class APIRequestEvent(BaseModel):
    event: Literal["api_request"] = "api_request"
    session_id: str
    timestamp: str
    method: str
    url: str
    body: Any = None


class APIResponseEvent(BaseModel):
    event: Literal["api_response"] = "api_response"
    session_id: str
    timestamp: str
    status_code: int
    body: Any = None


class APIErrorEvent(BaseModel):
    event: Literal["api_error"] = "api_error"
    session_id: str
    timestamp: str
    error_type: str
    message: str


class DoneEvent(BaseModel):
    event: Literal["done"] = "done"
    session_id: str
    timestamp: str
    total_messages: int
    final_status: str  # "completed" | "cancelled" | "error"


class ErrorEvent(BaseModel):
    event: Literal["error"] = "error"
    session_id: str
    timestamp: str
    code: str
    message: str


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = "1.0.0"
