"""
Label-localization demo: upload an image, type what to find, see where the
model points.

    uv run uvicorn dev_ui.localization_demo.server:app --reload --port 8001

The point of this server is to make the resize/rescale pipeline concrete:

  1. Your original image is W0 x H0.
  2. We resize it to Ws x Hs with `target_image_size` (computer_use/image.py)
     so the API does not resize it again server-side.
  3. The model is forced (via `tool_choice`) to call a `point_at` tool with
     `(x, y)` in the *Ws x Hs* space, because that is the only image it saw.
  4. We scale those back to original space with `x * W0/Ws, y * H0/Hs`.

The page draws a crosshair on both the sent image and the original so you can
see the two coordinate spaces side by side.
"""

import io
import re
import time
from pathlib import Path
from typing import Annotated, Any, get_args

import anthropic
from anthropic.types import ToolParam
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

import constants
from computer_use.image import resize_and_encode
from computer_use.loop import _effort_kwargs

app = FastAPI()
_static = Path(__file__).parent / "static"
_assets = Path(__file__).parent.parent / "assets"
app.mount("/assets", StaticFiles(directory=_assets), name="assets")
_client = anthropic.Anthropic()

_POINT_AT_TOOL: ToolParam = {
    "name": "point_at",
    "description": "Point at the requested element by giving its pixel coordinates.",
    "input_schema": {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "pixels from the left edge"},
            "y": {"type": "integer", "description": "pixels from the top edge"},
        },
        "required": ["x", "y"],
    },
}

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _safe_substitute(template: str, **values: object) -> str:
    """Replace ``{name}`` placeholders without ``str.format``'s attribute/index
    traversal (which would let a user-supplied template reach ``__globals__``
    and similar). Only bare ``{word}`` placeholders are recognised; anything
    not in ``values`` raises ``KeyError``."""

    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in values:
            raise KeyError(key)
        return str(values[key])

    return _PLACEHOLDER_RE.sub(repl, template)


DEFAULT_PROMPT_TEMPLATE = (
    "Point at: {label}\n\n"
    "Give the pixel coordinates of its centre. "
    "The image is {sent_w}x{sent_h} pixels."
)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_static / "index.html")


@app.get("/meta")
def meta() -> dict[str, Any]:
    return {
        "models": [m.value for m in constants.Model] + list(constants.cfg.extra_models),
        "default_model": constants.Model.HAIKU_4_5.value,
        "thinking_efforts": list(get_args(constants.ThinkingEffort)),
        "effort_supported_models": sorted(constants.EFFORT_SUPPORTED_MODELS),
        "default_prompt_template": DEFAULT_PROMPT_TEMPLATE,
        "point_at_tool": _POINT_AT_TOOL,
    }


@app.post("/localize")
def localize(
    image: Annotated[UploadFile, File()],
    label: Annotated[str, Form()],
    model: Annotated[str, Form()] = constants.Model.HAIKU_4_5.value,
    thinking_effort: Annotated[constants.ThinkingEffort, Form()] = "off",
    prompt_template: Annotated[str, Form()] = DEFAULT_PROMPT_TEMPLATE,
) -> JSONResponse:
    raw = image.file.read()
    pil = Image.open(io.BytesIO(raw)).convert("RGB")
    orig_w, orig_h = pil.width, pil.height

    b64, (sent_w, sent_h) = resize_and_encode(pil, min_bytes=0)

    try:
        effort_kwargs = _effort_kwargs(model, thinking_effort)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    try:
        prompt = _safe_substitute(prompt_template, label=label, sent_w=sent_w, sent_h=sent_h)
    except KeyError as e:
        return JSONResponse(
            {
                "error": f"unknown placeholder {{{e.args[0]}}}; allowed: {{label}}, {{sent_w}}, {{sent_h}}"
            },
            status_code=400,
        )

    start = time.monotonic()
    response = _client.messages.create(
        model=model,
        max_tokens=2048,
        tools=[_POINT_AT_TOOL],
        tool_choice={"type": "tool", "name": "point_at"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        **effort_kwargs,
    )
    elapsed = round(time.monotonic() - start, 2)

    tool_use = next(b for b in response.content if b.type == "tool_use")
    coords = tool_use.input
    assert isinstance(coords, dict)
    sx, sy = coords["x"], coords["y"]
    assert isinstance(sx, int) and isinstance(sy, int)
    ox = round(sx * orig_w / sent_w)
    oy = round(sy * orig_h / sent_h)

    return JSONResponse(
        {
            "label": label,
            "model": model,
            "thinking_effort": thinking_effort,
            "prompt": prompt,
            "elapsed_s": elapsed,
            "original_size": [orig_w, orig_h],
            "sent_size": [sent_w, sent_h],
            "sent_image_b64": b64,
            "point_sent": [sx, sy],
            "point_original": [ox, oy],
            "scale": [orig_w / sent_w, orig_h / sent_h],
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }
    )
