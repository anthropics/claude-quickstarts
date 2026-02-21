"""
Thin FastAPI bridge for the Anthropic “Computer‑Use” demo
"""

import os, uuid, asyncio
from typing import Dict, List, Callable

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from anthropic.types.beta import (
    BetaTextBlockParam,
    BetaContentBlockParam,
    BetaTextBlock,          # dataclass in newer SDKs
)
from computer_use_demo.loop import sampling_loop, APIProvider

# ────────────────────────────────────────────────────────────────────
# FastAPI boiler‑plate
# ────────────────────────────────────────────────────────────────────
app = FastAPI(title="Computer‑Use REST bridge")

class ChatRequest(BaseModel):
    session_id: str | None = None        # keep context between turns
    user_message: str
    system_suffix: str | None = None     # optional extra instructions

class ChatResponse(BaseModel):
    session_id: str
    assistant_message: str

# ────────────────────────────────────────────────────────────────────
# Very simple in‑memory conversation store
# (swap for Redis / DB if you need persistence)
# ────────────────────────────────────────────────────────────────────
_conversations: Dict[str, List[dict]] = {}

def _new_session() -> str:
    return uuid.uuid4().hex

# ────────────────────────────────────────────────────────────────────
# Helper: add the user message to the convo list
# ────────────────────────────────────────────────────────────────────
def _append_user_message(messages: List[dict], text: str):
    messages.append(
        {
            "role": "user",
            "content": [BetaTextBlockParam(type="text", text=text)],
        }
    )

# ────────────────────────────────────────────────────────────────────
# Main endpoint
# ────────────────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(500, "ANTHROPIC_API_KEY env‑var is missing")

    # fetch (or create) the conversation
    sid = req.session_id or _new_session()
    messages = _conversations.setdefault(sid, [])

    # add the new user turn
    _append_user_message(messages, req.user_message)

    # collect assistant text as it streams
    text_chunks: List[str] = []

    def output_cb(block: BetaContentBlockParam):
        # Newer SDK: dataclass objects
        if isinstance(block, BetaTextBlock):
            text_chunks.append(block.text)
        # Older SDK: plain dicts
        elif isinstance(block, dict) and block.get("type") == "text":
            text_chunks.append(block["text"])

    # we’re ignoring tool_output and api_response for now
    noop: Callable[..., None] = lambda *a, **k: None

    # drive Claude + tools
    messages = await sampling_loop(
        model="claude-3-5-sonnet-20241022",
        provider=APIProvider.ANTHROPIC,
        system_prompt_suffix=req.system_suffix or "",
        messages=messages,
        output_callback=output_cb,
        tool_output_callback=noop,
        api_response_callback=noop,
        api_key=api_key,
    )

    # persist updated history
    _conversations[sid] = messages

    return ChatResponse(
        session_id=sid,
        assistant_message="".join(text_chunks).strip(),
    )
