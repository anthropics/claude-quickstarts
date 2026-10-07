"""Exercise the browser toolset with the calls a model would make, against a local page: no API key, no model.

Usage:

    python exercise.py

The script serves a small page on localhost, launches the example driver with a URL policy that admits that page and
nothing else, and sends the toolset the `tool_use` calls a model would send, through the entry point the tool runner
uses. It prints each `tool_result` as the model would see it, then checks it:

- `navigate` to the page, `read_page`, `left_click` on a `ref_N` from the read and `get_page_text` showing what the
  click did: all answered;
- `navigate` to the same page by `127.0.0.1`, and `wait` for longer than 30 s: both refused (`is_error`).

The first call that comes back differently ends the script with a failed assertion, so the script also works as a smoke
check.
Requires what run.py requires, minus the API key.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from anthropic.tools import ToolError
from anthropic.tools.browser import (
    BetaAbstractBrowserToolset20260801,
    BetaURLContext,
    BetaURLPolicy,
)
from anthropic.types.beta import BetaToolResultBlockParam, BetaToolUseBlock
from typing_extensions import override

from cdp_browser import CdpBrowser

PAGE = b"""<!doctype html>
<title>Exercise page</title>
<h1>Exercise page</h1>
<p id="status">The button has not been clicked.</p>
<button onclick="document.getElementById('status').textContent = 'The button was clicked.'">Click me</button>
<p><a href="/about">About this page</a></p>
"""


class PageHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE)

    @override
    def log_message(self, format: str, *args: Any) -> None:
        pass  # keep the HTTP server's request log out of the output


def only(origin: str) -> BetaURLPolicy:
    """A URL policy that admits this script's own server and nothing else."""

    def policy(_context: BetaURLContext, url: str) -> None:
        try:
            parts = urlsplit(url.replace("\\", "/"))  # parsed as a browser reads the address: a backslash is a slash
        except ValueError:
            raise ToolError(f"blocked: {url} could not be parsed") from None
        if f"{parts.scheme}://{parts.netloc}" != origin:
            raise ToolError(f"blocked: {url} is outside this exercise's page")

    return policy


def call(browser: BetaAbstractBrowserToolset20260801, name: str, input: dict[str, object]) -> BetaToolResultBlockParam:
    """Send one tool call as the model would, and print the result as the model would see it."""
    tool_use = BetaToolUseBlock(type="tool_use", id=f"toolu_{name}", name=name, input=input, toolset_name="browser")
    result = browser.tool_result(tool_use)
    print(f"\n{name} {json.dumps(input)} -> {'refused' if result.get('is_error') else 'answered'}")
    for block in blocks_of(result):
        print("  " + json.dumps(block))
    return result


def blocks_of(result: BetaToolResultBlockParam) -> list[dict[str, object]]:
    """The result's content blocks. `content` is a string or a list of blocks. A string becomes one text block."""
    content = result.get("content", "")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [dict(block) for block in content]


def text_of(result: BetaToolResultBlockParam) -> str:
    return "\n".join(str(block.get("text", "")) for block in blocks_of(result))


def main() -> None:
    argparse.ArgumentParser(
        description="Exercise the browser toolset against a local page, without a model."
    ).parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", 0), PageHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://localhost:{server.server_port}"

    try:
        browser = CdpBrowser(headless=True, url_policy=only(origin))
    except (OSError, RuntimeError, ToolError) as error:  # no usable Chromium, or one that did not start or answer
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
    with browser:
        assert not call(browser, "navigate", {"url": f"{origin}/"}).get("is_error"), (
            "expected that navigate to the page is answered"
        )
        tree = text_of(call(browser, "read_page", {}))
        button = next((line for line in tree.splitlines() if "Click me" in line), "")
        ref = re.search(r"ref_\d+", button)
        assert ref is not None, "expected that read_page lists the button with a ref"
        clicked = call(browser, "left_click", {"target": {"type": "ref", "ref": ref.group()}})
        assert not clicked.get("is_error"), "expected that left_click on the button's ref is answered"
        text = call(browser, "get_page_text", {})
        assert "The button was clicked." in text_of(text), "expected that get_page_text shows the click's effect"
        # Same page, but the policy admits only the localhost address, so the SDK refuses this call before the driver
        # runs.
        probe = call(browser, "navigate", {"url": f"http://127.0.0.1:{server.server_port}/"})
        refusal = text_of(probe)
        assert (
            probe.get("is_error") is True
            and refusal.startswith("blocked:")
            and "outside this exercise's page" in refusal
        ), "expected that navigate to 127.0.0.1 is refused by the policy"
        waited = call(browser, "wait", {"duration": 31})
        assert waited.get("is_error") is True and "between 0 and 30" in text_of(waited), (
            "expected that wait for longer than 30 s is refused for its duration"
        )
    server.shutdown()
    print("\nAll calls came back as expected.")


if __name__ == "__main__":
    main()
