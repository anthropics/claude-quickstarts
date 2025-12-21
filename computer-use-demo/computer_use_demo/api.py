"""
FastAPI backend for computer use demo with session management.
"""

import asyncio
import json
import os
import subprocess
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from functools import partial
from pathlib import PosixPath
from typing import Any, Callable, cast, get_args

import httpx
from anthropic import RateLimitError
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
)
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from computer_use_demo.loop import (
    APIProvider,
    sampling_loop,
)
from computer_use_demo.tools import ToolResult, ToolVersion

PROVIDER_TO_DEFAULT_MODEL_NAME: dict[APIProvider, str] = {
    APIProvider.ANTHROPIC: "claude-sonnet-4-5-20250929",
    APIProvider.BEDROCK: "anthropic.claude-3-5-sonnet-20241022-v2:0",
    APIProvider.VERTEX: "claude-3-5-sonnet-v2@20241022",
}


@dataclass(kw_only=True, frozen=True)
class ModelConfig:
    tool_version: ToolVersion
    max_output_tokens: int
    default_output_tokens: int
    has_thinking: bool = False


CLAUDE_4 = ModelConfig(
    tool_version="computer_use_20250429",
    max_output_tokens=64_000,
    default_output_tokens=1024 * 16,
    has_thinking=True,
)

CLAUDE_4_5 = ModelConfig(
    tool_version="computer_use_20250124",
    max_output_tokens=128_000,
    default_output_tokens=1024 * 16,
    has_thinking=True,
)

CLAUDE_4_WITH_ZOOMABLE_TOOL = ModelConfig(
    tool_version="computer_use_20251124",
    max_output_tokens=64_000,
    default_output_tokens=1024 * 16,
    has_thinking=True,
)

HAIKU_4_5 = ModelConfig(
    tool_version="computer_use_20250124",
    max_output_tokens=1024 * 8,
    default_output_tokens=1024 * 4,
    has_thinking=False,
)

MODEL_TO_MODEL_CONF: dict[str, ModelConfig] = {
    "claude-opus-4-1-20250805": CLAUDE_4,
    "claude-sonnet-4-20250514": CLAUDE_4,
    "claude-opus-4-20250514": CLAUDE_4,
    "claude-sonnet-4-5-20250929": CLAUDE_4_5,
    "anthropic.claude-sonnet-4-5-20250929-v1:0": CLAUDE_4_5,
    "claude-sonnet-4-5@20250929": CLAUDE_4_5,
    "claude-haiku-4-5-20251001": HAIKU_4_5,
    "anthropic.claude-haiku-4-5-20251001-v1:0": HAIKU_4_5,  # Bedrock
    "claude-haiku-4-5@20251001": HAIKU_4_5,  # Vertex
    "claude-opus-4-5-20251101": CLAUDE_4_WITH_ZOOMABLE_TOOL,
}

CONFIG_DIR = PosixPath("~/.anthropic").expanduser()
API_KEY_FILE = CONFIG_DIR / "api_key"

INTERRUPT_TEXT = "(user stopped or interrupted and wrote the following)"
INTERRUPT_TOOL_ERROR = "human stopped or interrupted tool execution"


class Sender(StrEnum):
    USER = "user"
    BOT = "assistant"
    TOOL = "tool"


@dataclass
class SessionState:
    """Session state management."""
    session_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    api_key: str = ""
    provider: APIProvider = APIProvider.ANTHROPIC
    model: str = ""
    tool_version: ToolVersion = field(default_factory=lambda: cast(ToolVersion, "computer_use_20250124"))
    has_thinking: bool = False
    output_tokens: int = 1024 * 16
    max_output_tokens: int = 128_000
    thinking_budget: int = 0
    only_n_most_recent_images: int = 3
    custom_system_prompt: str = ""
    hide_images: bool = False
    token_efficient_tools_beta: bool = False
    in_sampling_loop: bool = False
    auth_validated: bool = False
    responses: dict[str, tuple[httpx.Request, httpx.Response | object | None]] = field(default_factory=dict)
    tools: dict[str, ToolResult] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.model:
            object.__setattr__(self, 'model', PROVIDER_TO_DEFAULT_MODEL_NAME[self.provider])
        self._reset_model_conf()

    def _reset_model_conf(self):
        """Reset model configuration based on current model."""
        model_conf = MODEL_TO_MODEL_CONF.get(self.model, CLAUDE_4)
        object.__setattr__(self, 'tool_version', model_conf.tool_version)
        object.__setattr__(self, 'has_thinking', model_conf.has_thinking)
        object.__setattr__(self, 'output_tokens', model_conf.default_output_tokens)
        object.__setattr__(self, 'max_output_tokens', model_conf.max_output_tokens)
        object.__setattr__(self, 'thinking_budget', int(model_conf.default_output_tokens / 2))


# Global session storage (in production, use a proper database)
sessions: dict[str, SessionState] = {}

# Streaming connections: session_id -> list of connections
websocket_connections: dict[str, list[WebSocket]] = {}
sse_connections: dict[str, list[asyncio.Queue]] = {}


# Pydantic models for API
class SessionCreateRequest(BaseModel):
    api_key: str | None = None
    provider: str = "anthropic"
    model: str | None = None
    custom_system_prompt: str = ""
    only_n_most_recent_images: int = 3
    tool_version: str | None = None
    max_tokens: int | None = None
    thinking_enabled: bool = False
    thinking_budget: int | None = None
    token_efficient_tools_beta: bool = False


class SessionResponse(BaseModel):
    session_id: str
    created_at: datetime
    updated_at: datetime
    provider: str
    model: str
    message_count: int
    in_sampling_loop: bool


class MessageRequest(BaseModel):
    message: str
    interrupt: bool = False


class MessageResponse(BaseModel):
    session_id: str
    message_id: str
    status: str
    content: list[dict[str, Any]] | None = None


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]


# Event models for streaming
class StreamEvent(BaseModel):
    """Base event model for streaming."""
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: str
    data: dict[str, Any] = {}


class MessageStartEvent(StreamEvent):
    """Event emitted when message processing starts."""
    event_type: str = "message_start"
    data: dict[str, Any] = {"message_id": "", "message": ""}


class ContentBlockEvent(StreamEvent):
    """Event emitted when a content block is received."""
    event_type: str = "content_block"
    data: dict[str, Any] = {"block": {}}


class ToolUseEvent(StreamEvent):
    """Event emitted when a tool is being used."""
    event_type: str = "tool_use"
    data: dict[str, Any] = {"tool_name": "", "tool_id": "", "input": {}}


class ToolResultEvent(StreamEvent):
    """Event emitted when a tool result is received."""
    event_type: str = "tool_result"
    data: dict[str, Any] = {"tool_id": "", "output": "", "error": "", "has_image": False}


class MessageCompleteEvent(StreamEvent):
    """Event emitted when message processing completes."""
    event_type: str = "message_complete"
    data: dict[str, Any] = {"message_id": "", "final_messages": []}


class ErrorEvent(StreamEvent):
    """Event emitted when an error occurs."""
    event_type: str = "error"
    data: dict[str, Any] = {"error": "", "error_type": ""}


class ProgressEvent(StreamEvent):
    """Event emitted for general progress updates."""
    event_type: str = "progress"
    data: dict[str, Any] = {"status": "", "message": ""}


# FastAPI app
app = FastAPI(title="Computer Use Demo API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_from_storage(filename: str) -> str | None:
    """Load data from a file in the storage directory."""
    try:
        file_path = CONFIG_DIR / filename
        if file_path.exists():
            data = file_path.read_text().strip()
            if data:
                return data
    except Exception as e:
        print(f"Debug: Error loading {filename}: {e}")
    return None


def save_to_storage(filename: str, data: str) -> None:
    """Save data to a file in the storage directory."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        file_path = CONFIG_DIR / filename
        file_path.write_text(data)
        file_path.chmod(0o600)
    except Exception as e:
        print(f"Debug: Error saving {filename}: {e}")


def validate_auth(provider: APIProvider, api_key: str | None) -> str | None:
    """Validate authentication credentials."""
    if provider == APIProvider.ANTHROPIC:
        if not api_key:
            return "Enter your Claude API key to continue."
    if provider == APIProvider.BEDROCK:
        import boto3
        if not boto3.Session().get_credentials():
            return "You must have AWS credentials set up to use the Bedrock API."
    if provider == APIProvider.VERTEX:
        import google.auth
        from google.auth.exceptions import DefaultCredentialsError
        if not os.environ.get("CLOUD_ML_REGION"):
            return "Set the CLOUD_ML_REGION environment variable to use the Vertex API."
        try:
            google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        except DefaultCredentialsError:
            return "Your google cloud credentials are not set up correctly."
    return None


async def _emit_event(session_id: str, event: StreamEvent):
    """Emit an event to all connected WebSocket and SSE clients for a session."""
    event_dict = event.model_dump()
    
    # Emit to WebSocket connections
    if session_id in websocket_connections:
        disconnected = []
        for ws in websocket_connections[session_id]:
            try:
                await ws.send_json(event_dict)
            except Exception:
                disconnected.append(ws)
        # Remove disconnected connections
        for ws in disconnected:
            websocket_connections[session_id].remove(ws)
    
    # Emit to SSE connections
    if session_id in sse_connections:
        disconnected = []
        for queue in sse_connections[session_id]:
            try:
                await queue.put(event_dict)
            except Exception:
                disconnected.append(queue)
        # Remove disconnected connections
        for queue in disconnected:
            sse_connections[session_id].remove(queue)


def _create_tool_output_callback(
    tool_state: dict[str, ToolResult], session_id: str
) -> Callable[[ToolResult, str], None]:
    """Create a tool output callback that stores state and emits events."""
    def callback(tool_output: ToolResult, tool_id: str):
        """Handle a tool output by storing it to state and emitting event."""
        tool_state[tool_id] = tool_output
        
        # Emit event asynchronously
        asyncio.create_task(_emit_event(
            session_id,
            ToolResultEvent(
                session_id=session_id,
                data={
                    "tool_id": tool_id,
                    "output": tool_output.output or "",
                    "error": tool_output.error or "",
                    "has_image": bool(tool_output.base64_image),
                }
            )
        ))
    return callback


def _create_api_response_callback(
    response_state: dict[str, tuple[httpx.Request, httpx.Response | object | None]],
    session_id: str,
) -> Callable[[httpx.Request, httpx.Response | object | None, Exception | None], None]:
    """Create an API response callback that stores state and emits events."""
    def callback(
        request: httpx.Request,
        response: httpx.Response | object | None,
        error: Exception | None,
    ):
        """Handle an API response by storing it to state and emitting event."""
        response_id = datetime.now().isoformat()
        response_state[response_id] = (request, response)
        
        if error:
            asyncio.create_task(_emit_event(
                session_id,
                ErrorEvent(
                    session_id=session_id,
                    data={
                        "error": str(error),
                        "error_type": type(error).__name__,
                    }
                )
            ))
    return callback


def maybe_add_interruption_blocks(session: SessionState) -> list[BetaContentBlockParam]:
    """Add interruption blocks if session was interrupted."""
    if not session.in_sampling_loop:
        return []
    result = []
    if not session.messages:
        return []
    last_message = session.messages[-1]
    previous_tool_use_ids = [
        block["id"] for block in last_message.get("content", [])
        if isinstance(block, dict) and block.get("type") == "tool_use"
    ]
    for tool_use_id in previous_tool_use_ids:
        session.tools[tool_use_id] = ToolResult(error=INTERRUPT_TOOL_ERROR)
        result.append(
            BetaToolResultBlockParam(
                tool_use_id=tool_use_id,
                type="tool_result",
                content=INTERRUPT_TOOL_ERROR,
                is_error=True,
            )
        )
    result.append(BetaTextBlockParam(type="text", text=INTERRUPT_TEXT))
    return result


@contextmanager
def track_sampling_loop(session: SessionState):
    """Context manager to track sampling loop state."""
    session.in_sampling_loop = True
    session.updated_at = datetime.now()
    yield
    session.in_sampling_loop = False
    session.updated_at = datetime.now()


@app.post("/api/sessions", response_model=SessionResponse, status_code=201)
async def create_session(request: SessionCreateRequest) -> SessionResponse:
    """Create a new session."""
    session_id = str(uuid.uuid4())
    
    # Get API key from request or environment or storage
    api_key = request.api_key or load_from_storage("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
    
    # Determine provider
    provider = APIProvider(request.provider) if request.provider in [p.value for p in APIProvider] else APIProvider.ANTHROPIC
    
    # Create session state
    session = SessionState(
        session_id=session_id,
        api_key=api_key,
        provider=provider,
        custom_system_prompt=request.custom_system_prompt or load_from_storage("system_prompt") or "",
        only_n_most_recent_images=request.only_n_most_recent_images,
        token_efficient_tools_beta=request.token_efficient_tools_beta,
    )
    
    # Override model if provided
    if request.model:
        object.__setattr__(session, 'model', request.model)
        session._reset_model_conf()
    
    # Override tool version if provided
    if request.tool_version:
        object.__setattr__(session, 'tool_version', cast(ToolVersion, request.tool_version))
    
    # Override max tokens if provided
    if request.max_tokens:
        object.__setattr__(session, 'output_tokens', request.max_tokens)
    
    # Handle thinking
    if request.thinking_enabled:
        if request.thinking_budget:
            object.__setattr__(session, 'thinking_budget', request.thinking_budget)
    else:
        object.__setattr__(session, 'thinking_budget', 0)
    
    # Validate auth
    if auth_error := validate_auth(session.provider, session.api_key):
        raise HTTPException(status_code=400, detail=auth_error)
    
    session.auth_validated = True
    
    # Store session
    sessions[session_id] = session
    
    return SessionResponse(
        session_id=session_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        provider=session.provider.value,
        model=session.model,
        message_count=len(session.messages),
        in_sampling_loop=session.in_sampling_loop,
    )


@app.get("/api/sessions", response_model=SessionListResponse)
async def list_sessions() -> SessionListResponse:
    """List all sessions."""
    return SessionListResponse(
        sessions=[
            SessionResponse(
                session_id=session.session_id,
                created_at=session.created_at,
                updated_at=session.updated_at,
                provider=session.provider.value,
                model=session.model,
                message_count=len(session.messages),
                in_sampling_loop=session.in_sampling_loop,
            )
            for session in sessions.values()
        ]
    )


@app.get("/api/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    """Get a specific session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    return SessionResponse(
        session_id=session.session_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        provider=session.provider.value,
        model=session.model,
        message_count=len(session.messages),
        in_sampling_loop=session.in_sampling_loop,
    )


@app.delete("/api/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str):
    """Delete a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    del sessions[session_id]


@app.post("/api/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_message(
    session_id: str,
    request: MessageRequest,
    background_tasks: BackgroundTasks,
) -> MessageResponse:
    """Send a message to a session and process it."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    
    if not session.auth_validated:
        if auth_error := validate_auth(session.provider, session.api_key):
            raise HTTPException(status_code=400, detail=auth_error)
        session.auth_validated = True
    
    # Add user message
    message_id = str(uuid.uuid4())
    user_content = [
        *maybe_add_interruption_blocks(session),
        BetaTextBlockParam(type="text", text=request.message),
    ]
    
    session.messages.append({
        "role": Sender.USER,
        "content": user_content,
    })
    session.updated_at = datetime.now()
    
    # Emit message start event
    await _emit_event(
        session_id,
        MessageStartEvent(
            session_id=session_id,
            data={
                "message_id": message_id,
                "message": request.message,
            }
        )
    )
    
    # Process message in background
    background_tasks.add_task(
        process_message,
        session_id,
        message_id,
    )
    
    return MessageResponse(
        session_id=session_id,
        message_id=message_id,
        status="processing",
        content=None,
    )


async def process_message(session_id: str, message_id: str):
    """Process a message through the sampling loop."""
    if session_id not in sessions:
        return
    
    session = sessions[session_id]
    
    # Create streaming callbacks (synchronous, but schedule async tasks)
    def output_callback(content_block: BetaContentBlockParam):
        """Callback for content blocks from the API."""
        if isinstance(content_block, dict):
            # Emit tool use event if it's a tool use block
            if content_block.get("type") == "tool_use":
                asyncio.create_task(_emit_event(
                    session_id,
                    ToolUseEvent(
                        session_id=session_id,
                        data={
                            "tool_name": content_block.get("name", ""),
                            "tool_id": content_block.get("id", ""),
                            "input": content_block.get("input", {}),
                        }
                    )
                ))
            else:
                # Emit content block event
                asyncio.create_task(_emit_event(
                    session_id,
                    ContentBlockEvent(
                        session_id=session_id,
                        data={"block": content_block}
                    )
                ))
    
    with track_sampling_loop(session):
        try:
            await _emit_event(
                session_id,
                ProgressEvent(
                    session_id=session_id,
                    data={
                        "status": "processing",
                        "message": "Starting message processing...",
                    }
                )
            )
            
            session.messages = await sampling_loop(
                system_prompt_suffix=session.custom_system_prompt,
                model=session.model,
                provider=session.provider,
                messages=session.messages,
                output_callback=output_callback,
                tool_output_callback=_create_tool_output_callback(
                    session.tools,
                    session_id,
                ),
                api_response_callback=_create_api_response_callback(
                    session.responses,
                    session_id,
                ),
                api_key=session.api_key,
                only_n_most_recent_images=session.only_n_most_recent_images,
                tool_version=session.tool_version,
                max_tokens=session.output_tokens,
                thinking_budget=session.thinking_budget if session.thinking_budget > 0 else None,
                token_efficient_tools_beta=session.token_efficient_tools_beta,
            )
            
            # Emit completion event
            await _emit_event(
                session_id,
                MessageCompleteEvent(
                    session_id=session_id,
                    data={
                        "message_id": message_id,
                        "final_messages": session.messages[-5:] if len(session.messages) > 5 else session.messages,
                    }
                )
            )
        except Exception as e:
            print(f"Error processing message: {e}")
            await _emit_event(
                session_id,
                ErrorEvent(
                    session_id=session_id,
                    data={
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                )
            )
        finally:
            session.updated_at = datetime.now()


@app.get("/api/sessions/{session_id}/messages")
async def get_messages(session_id: str) -> dict[str, Any]:
    """Get all messages for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    return {
        "session_id": session_id,
        "messages": session.messages,
        "tools": {
            tool_id: {
                "output": tool_result.output,
                "error": tool_result.error,
                "base64_image": tool_result.base64_image,
            }
            for tool_id, tool_result in session.tools.items()
        },
    )


@app.post("/api/sessions/{session_id}/reset", response_model=SessionResponse)
async def reset_session(session_id: str) -> SessionResponse:
    """Reset a session (clear messages and restart desktop environment)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    
    # Clear messages and tools
    session.messages = []
    session.tools = {}
    session.responses = {}
    session.in_sampling_loop = False
    
    # Restart desktop environment
    subprocess.run("pkill Xvfb; pkill tint2", shell=True)  # noqa: ASYNC221
    await asyncio.sleep(1)
    subprocess.run("./start_all.sh", shell=True)  # noqa: ASYNC221
    
    session.updated_at = datetime.now()
    
    return SessionResponse(
        session_id=session.session_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        provider=session.provider.value,
        model=session.model,
        message_count=len(session.messages),
        in_sampling_loop=session.in_sampling_loop,
    )


@app.websocket("/ws/sessions/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time progress streaming."""
    if session_id not in sessions:
        await websocket.close(code=1008, reason="Session not found")
        return
    
    await websocket.accept()
    
    # Add connection to session
    if session_id not in websocket_connections:
        websocket_connections[session_id] = []
    websocket_connections[session_id].append(websocket)
    
    try:
        # Send initial connection event
        await websocket.send_json({
            "event_type": "connected",
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "data": {"message": "Connected to session stream"},
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (can be used for control commands)
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                
                # Handle client messages (e.g., interrupt, cancel)
                if data.get("type") == "interrupt":
                    session = sessions[session_id]
                    if session.in_sampling_loop:
                        # Mark for interruption
                        object.__setattr__(session, 'in_sampling_loop', False)
                        await websocket.send_json({
                            "event_type": "interrupted",
                            "timestamp": datetime.now().isoformat(),
                            "session_id": session_id,
                            "data": {"message": "Processing interrupted"},
                        })
            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({
                    "event_type": "keepalive",
                    "timestamp": datetime.now().isoformat(),
                    "session_id": session_id,
                    "data": {},
                })
            except WebSocketDisconnect:
                break
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # Remove connection
        if session_id in websocket_connections:
            if websocket in websocket_connections[session_id]:
                websocket_connections[session_id].remove(websocket)
            if not websocket_connections[session_id]:
                del websocket_connections[session_id]


@app.get("/api/sessions/{session_id}/stream")
async def sse_endpoint(session_id: str):
    """Server-Sent Events endpoint for real-time progress streaming."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    async def event_generator():
        """Generate SSE events."""
        # Create a queue for this connection
        queue = asyncio.Queue()
        
        # Add queue to session connections
        if session_id not in sse_connections:
            sse_connections[session_id] = []
        sse_connections[session_id].append(queue)
        
        try:
            # Send initial connection event
            yield f"event: connected\n"
            yield f"data: {json.dumps({'message': 'Connected to session stream', 'session_id': session_id})}\n\n"
            
            # Keep sending events from queue
            while True:
                try:
                    # Wait for event with timeout for keepalive
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    # Format as SSE
                    event_type = event.get("event_type", "message")
                    yield f"event: {event_type}\n"
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        except Exception as e:
            print(f"SSE error: {e}")
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            # Remove queue from connections
            if session_id in sse_connections:
                if queue in sse_connections[session_id]:
                    sse_connections[session_id].remove(queue)
                if not sse_connections[session_id]:
                    del sse_connections[session_id]
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "sessions": len(sessions)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8501)

