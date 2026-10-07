"""Exercise the computer toolset with the calls a model would make, against a VNC server, with no API key and no model.

Usage:

    python exercise.py

The script connects the example driver to the VNC server at `VNC_HOST:VNC_PORT` and sends the toolset the `tool_use`
calls a model would send, through the entry point the tool runner uses. It prints each `tool_result` as the model would
see it, then checks it:

- `screenshot` (a PNG of the whole screen), `left_click` at the screen's centre, `type`, `key`, `wait` and a second
  `screenshot` showing what the typing did: all answered;
- `left_click` just off the screen, and `zoom`, which the driver leaves out: both refused (`is_error`).

The first call that comes back differently ends the script with a failed assertion, so the script also works as a smoke
check. It requires what run.py requires, minus the API key.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import struct
import sys
from typing import Any

from anthropic.tools.computer import BetaAbstractComputerToolset20260801
from anthropic.types.beta import BetaToolResultBlockParam, BetaToolUseBlock

from vnc_computer import VncComputer


def call(
    computer: BetaAbstractComputerToolset20260801, name: str, input: dict[str, object]
) -> BetaToolResultBlockParam:
    """Send one tool call as the model would, and print the result as the model would see it."""
    tool_use = BetaToolUseBlock(type="tool_use", id=f"toolu_{name}", name=name, input=input, toolset_name="computer")
    result = computer.tool_result(tool_use)
    print(f"\n{name} {json.dumps(input)} -> {'refused' if result.get('is_error') else 'answered'}")
    for block in blocks_of(result):
        if block.get("type") == "image":
            # The screenshot's bytes would flood the terminal, so their count is shown instead.
            block = {**block, "source": {**block["source"], "data": f"<{len(image_of(result))} bytes>"}}
        print("  " + json.dumps(block))
    return result


def blocks_of(result: BetaToolResultBlockParam) -> list[dict[str, Any]]:
    """Return the result's content blocks. `content` is a string or a list of blocks; a string is one text block."""
    content = result.get("content", "")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [dict(block) for block in content]


def text_of(result: BetaToolResultBlockParam) -> str:
    return "\n".join(str(block.get("text", "")) for block in blocks_of(result))


def image_of(result: BetaToolResultBlockParam) -> bytes:
    """Return the bytes of the result's first image block, or empty bytes."""
    for block in blocks_of(result):
        if block.get("type") == "image":
            return base64.b64decode(block["source"]["data"])
    return b""


def assert_screen_png(computer: VncComputer, result: BetaToolResultBlockParam) -> None:
    """Check that the result is a PNG of the whole screen, by its 8-byte signature and the size in its IHDR chunk."""
    png = image_of(result)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", png[16:24]) == (computer.width, computer.height), (
        "expected that screenshot is a PNG of the whole screen"
    )


def main() -> None:
    argparse.ArgumentParser(
        description="Exercise the computer toolset against a VNC server, without a model."
    ).parse_args()
    try:
        # No one is at the terminal, so this confirm approves every call.
        computer = VncComputer(
            host=os.environ.get("VNC_HOST", "127.0.0.1"),
            port=int(os.environ.get("VNC_PORT", "5900")),
            confirm=lambda context: True,
        )
    except (OSError, RuntimeError) as error:  # There is no VNC server there, or one this example cannot talk to.
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
    with computer:
        first = call(computer, "screenshot", {})
        assert_screen_png(computer, first)
        centre = [computer.width // 2, computer.height // 2]
        assert not call(computer, "left_click", {"coordinate": centre}).get("is_error"), (
            "expected that left_click at the centre is answered"
        )
        assert not call(computer, "type", {"text": "hello"}).get("is_error"), "expected that type is answered"
        assert not call(computer, "key", {"text": "Return"}).get("is_error"), "expected that key Return is answered"
        assert not call(computer, "wait", {"duration": 1}).get("is_error"), "expected that wait 1 is answered"
        # x11vnc can take a few seconds to show what the click and the typing did, so the second screenshot gets a few
        # tries.
        second = call(computer, "screenshot", {})
        for _ in range(5):
            assert_screen_png(computer, second)
            if image_of(second) != image_of(first):
                break
            call(computer, "wait", {"duration": 1})
            second = call(computer, "screenshot", {})
        assert image_of(second) != image_of(first), (
            "expected that a later screenshot differs from the first: the click and the typing showed"
        )
        # This point is one pixel past the screen's edge. The driver refuses it rather than clamping, so the model sees
        # its mistake.
        outside = call(computer, "left_click", {"coordinate": [computer.width, computer.height]})
        assert outside.get("is_error") is True and "outside" in text_of(outside), (
            "expected that left_click off the screen is refused"
        )
        # The driver does not implement zoom, so the SDK reports it disabled and refuses the call itself.
        zoomed = call(computer, "zoom", {"region": [0, 0, 100, 100]})
        assert zoomed.get("is_error") is True, "expected that zoom is refused as disabled"
    print("\nAll calls came back as expected.")


if __name__ == "__main__":
    main()
