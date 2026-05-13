"""
Tool panel: a tiny FastAPI server + static page for poking tools by hand.

    uv run uvicorn dev_ui.tool_panel.server:app --reload

Open http://127.0.0.1:8000. Each tool gets a card with form inputs derived
from its input_schema; results render as JSON, screenshots inline. Clicking a
screenshot fills the nearest `coordinate` field with the image-pixel position
and shows the corresponding screen-pixel position.
"""

import time
from pathlib import Path
from typing import Any

from anthropic.types import ToolParam
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from computer_use.__main__ import build_tools
from computer_use.preflight import accessibility_granted, screen_recording_granted

app = FastAPI()
_tools = build_tools()
_static = Path(__file__).parent / "static"
_assets = Path(__file__).parent.parent / "assets"
app.mount("/assets", StaticFiles(directory=_assets), name="assets")


class RunRequest(BaseModel):
    tool: str
    input: dict[str, Any]
    delay: float = 0.0


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_static / "index.html")


@app.get("/tools")
def list_tools() -> list[ToolParam]:
    return _tools.to_params()


@app.get("/preflight")
def preflight() -> dict[str, bool]:
    return {
        "screen_recording": screen_recording_granted(),
        "accessibility": accessibility_granted(),
    }


@app.post("/run")
def run(req: RunRequest) -> dict[str, Any]:
    if req.delay:
        time.sleep(req.delay)
    t0 = time.perf_counter()
    res = _tools.run(req.tool, req.input)
    return {
        "ms": round((time.perf_counter() - t0) * 1000),
        "error": res.error,
        "content": res.to_api_content(),
        "meta": res.meta,
    }
