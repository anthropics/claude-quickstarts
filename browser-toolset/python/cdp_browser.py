"""A minimal example of the browser toolset interface over the Chrome DevTools Protocol (CDP): one Chromium tab, five
tools, no browser library.

It shows the interface. It is not production code. It implements `BetaAbstractBrowserToolset20260801` with the tools a
first run needs (`navigate`, `read_page`, `left_click`, `get_page_text` and `wait`), against one tab of a Chromium it
launches. The SDK turns off every other tool in the toolset's `configs` and offers the model only these.

It leaves dialogs and downloads unhandled and does not recover a page that stops answering. It lacks request
interception, so the URL policy judges only the addresses the model asks for. See the README.

Read "Running a browser toolset safely" in the SDK guide (browser-toolset.md) before pointing it at anything but a
throwaway profile inside a sandbox, because the pages the model visits affect what it does next.

Run it with run.py, which contains the install and run instructions.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import IO, Any

from anthropic.tools import ToolError
from anthropic.tools.browser import (
    BetaAbstractBrowserToolset20260801,
    BetaBrowserNavigateResult,
    BetaBrowserState,
    BetaToolsetCallContext,
)
from anthropic.types.beta import (
    BetaBrowserGetPageTextInput,
    BetaBrowserLeftClickInput,
    BetaBrowserNavigateInput,
    BetaBrowserReadPageInput,
    BetaBrowserWaitInput,
)
from typing_extensions import override
from websockets.sync.client import ClientConnection, connect

COMMAND_TIMEOUT_S = 30  # every CDP command, and the wait for a page to load
TAB_ID = "tab_1"


def find_chrome(chrome_path: str | None = None) -> str:
    """The Chromium binary: the argument, else `CHROME_PATH`, else one of the usual names on `PATH`. A path to a missing
    binary fails at launch."""
    configured = chrome_path or os.environ.get("CHROME_PATH")
    if configured:
        return configured
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    raise RuntimeError("No Chromium binary found: set CHROME_PATH or install google-chrome / chromium.")


class CdpBrowser(BetaAbstractBrowserToolset20260801):
    """One Chromium tab driven over CDP. Keyword arguments beyond `headless` and `chrome_path` are the SDK's toolset
    options (`url_policy`, `configs`, `confirm` and the rest), passed on unchanged."""

    def __init__(self, *, headless: bool = True, chrome_path: str | None = None, **options: Any) -> None:
        super().__init__(**options)
        self._process: subprocess.Popen[bytes] | None = None
        self._profile_dir: str | None = None
        self._log: IO[bytes] | None = None  # Chromium's stderr, kept in the profile dir for the failure message
        self._socket: ClientConnection | None = None
        self._session_id = ""
        self._next_id = 1
        self._events: list[dict[str, Any]] = []
        try:
            self._connect(self._launch(headless, chrome_path))
        except BaseException:
            self.close()
            raise

    def _launch(self, headless: bool, chrome_path: str | None) -> str:
        """Start Chromium with a fresh profile and return its browser DevTools endpoint."""
        binary = find_chrome(chrome_path)
        self._profile_dir = tempfile.mkdtemp(prefix="cdp-browser-")
        self._log = open(Path(self._profile_dir) / "chromium.log", "w+b")  # closed in close()
        self._process = subprocess.Popen(
            [
                binary,
                *(["--headless=new"] if headless else []),
                "--remote-debugging-port=0",
                f"--user-data-dir={self._profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--disable-extensions",
                "--disable-sync",
                "--window-size=1280,720",
                # Chromium cannot start its own sandbox as root, and most containers run it as root.
                *(["--no-sandbox"] if hasattr(os, "geteuid") and os.geteuid() == 0 else []),
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=self._log,
        )
        # Chromium writes the port and the browser endpoint's path to DevToolsActivePort once it listens.
        port_file = Path(self._profile_dir) / "DevToolsActivePort"
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if port_file.exists():
                lines = port_file.read_text().split("\n")
                if len(lines) >= 2 and lines[0].strip().isdigit() and lines[1].startswith("/"):
                    return f"ws://127.0.0.1:{lines[0].strip()}{lines[1].strip()}"
            if self._process.poll() is not None:
                break
            time.sleep(0.05)
        self._log.seek(0)
        output = self._log.read().decode(errors="replace").strip()
        raise RuntimeError(f"Chromium did not start: {output.splitlines()[-1] if output else 'no output'}")

    def _connect(self, ws_url: str) -> None:
        """Open a tab, attach to it and enable the domains the tools use."""
        self._socket = connect(ws_url, max_size=None, proxy=None)  # a loopback socket, so skip any proxy
        target_id = self._send("Target.createTarget", {"url": "about:blank"})["targetId"]
        self._session_id = self._send("Target.attachToTarget", {"targetId": target_id, "flatten": True})["sessionId"]
        self._send("Page.enable")
        self._send("Page.setLifecycleEventsEnabled", {"enabled": True})
        self._send("Runtime.enable")

    @override
    def close(self) -> None:
        """Stop Chromium and remove its profile. It is safe to call more than once, and `with` calls it for you."""
        super().close()
        if self._socket is not None:
            try:
                self._send("Browser.close")
            except Exception:
                pass  # the browser may be gone already, and the code below stops the process either way
            self._socket.close()
            self._socket = None
        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        if self._log is not None:
            self._log.close()
            self._log = None
        if self._profile_dir is not None:
            # Chromium can still be writing to the profile as it exits, so a file written during removal stays behind.
            shutil.rmtree(self._profile_dir, ignore_errors=True)
            self._profile_dir = None

    def _send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send one CDP command and return its result."""
        assert self._socket is not None
        message_id = self._next_id
        self._next_id += 1
        command: dict[str, Any] = {"id": message_id, "method": method, "params": params or {}}
        if self._session_id and not method.startswith(("Target.", "Browser.")):  # these go to the browser itself
            command["sessionId"] = self._session_id
        self._socket.send(json.dumps(command))
        deadline = time.monotonic() + COMMAND_TIMEOUT_S
        try:
            while True:
                message = self._receive(deadline)
                if message.get("id") != message_id:
                    continue
                if "error" in message:
                    raise ToolError(f"{method} failed: {message['error'].get('message', 'unknown error')}")
                result: dict[str, Any] = message.get("result", {})
                return result
        except TimeoutError:
            raise ToolError(f"{method} timed out") from None

    def _receive(self, deadline: float) -> dict[str, Any]:
        """Return the next message from the browser, or raise `TimeoutError` at the deadline. Also record any
        `DOMContentLoaded` lifecycle event, which `navigate` waits for."""
        assert self._socket is not None
        raw = self._socket.recv(timeout=max(0.0, deadline - time.monotonic()))
        message: dict[str, Any] = json.loads(raw)
        if message.get("method") == "Page.lifecycleEvent" and message["params"].get("name") == "DOMContentLoaded":
            self._events.append(message)
        return message

    def _evaluate(self, expression: str) -> Any:
        """Run JavaScript in the page and return its value."""
        result = self._send("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        if "exceptionDetails" in result:
            details = result["exceptionDetails"].get("exception", {}).get("description") or "error"
            raise ToolError(f"the page script failed: {details}")
        return result.get("result", {}).get("value")

    def _page_info(self) -> tuple[str, str]:
        """The tab's current address and title."""
        info: dict[str, str] = self._evaluate(PAGE_INFO) or {}
        return str(info.get("url", "about:blank")), str(info.get("title", ""))

    @override
    def navigate(self, context: BetaToolsetCallContext, input: BetaBrowserNavigateInput) -> BetaBrowserNavigateResult:
        if input.url in ("back", "forward", "reload"):
            raise ToolError("This example only navigates to a URL; back, forward and reload are not supported.")
        # Open an address without a scheme as https, the same way the URL policy reads it.
        url = input.url if re.match(r"[a-z][a-z0-9+.-]*:", input.url, re.I) else f"https://{input.url}"
        self._events.clear()
        started = self._send("Page.navigate", {"url": url})
        if started.get("errorText"):
            raise ToolError(f"navigate failed: {started['errorText']}")
        loader_id = started.get("loaderId")
        if loader_id is not None:  # absent for a same-document navigation (a #fragment): no new document
            # Wait until the new document is parsed (DOMContentLoaded), not until its images and other sub-resources
            # load.
            deadline = time.monotonic() + COMMAND_TIMEOUT_S
            try:
                while not any(event["params"].get("loaderId") == loader_id for event in self._events):
                    self._receive(deadline)
            except TimeoutError:
                raise ToolError(f"navigate failed: the page did not load within {COMMAND_TIMEOUT_S} s") from None
            self._events.clear()
        url, title = self._page_info()
        return BetaBrowserNavigateResult(url=url, title=title or None)

    @override
    def read_page(self, context: BetaToolsetCallContext, input: BetaBrowserReadPageInput) -> str:
        return self._evaluate(READ_PAGE) or ""

    @override
    def left_click(self, context: BetaToolsetCallContext, input: BetaBrowserLeftClickInput) -> None:
        if input.target.type == "ref":
            point = self._evaluate(RESOLVE_REF % json.dumps(input.target.ref))
            if not point:
                raise ToolError(f"Unknown or stale ref: {input.target.ref}. Call read_page again for current refs.")
            x, y = point["x"], point["y"]
        else:
            x, y = input.target.x, input.target.y
        self._send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        for kind in ("mousePressed", "mouseReleased"):
            self._send("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1})
        time.sleep(0.1)  # let the page react before the next call reads it

    @override
    def get_page_text(self, context: BetaToolsetCallContext, input: BetaBrowserGetPageTextInput) -> str:
        return self._evaluate(PAGE_TEXT) or ""

    @override
    def wait(self, context: BetaToolsetCallContext, input: BetaBrowserWaitInput) -> None:
        # The SDK leaves `duration` unbounded, and the tool's documented maximum is 30 seconds.
        if not 0 <= input.duration <= 30:
            raise ToolError("duration: must be between 0 and 30 seconds")
        time.sleep(input.duration)

    @override
    def _browser_state(self, context: BetaToolsetCallContext) -> BetaBrowserState:
        try:
            url, title = self._page_info()
        except Exception:
            url, title = "about:blank", ""  # the browser is gone or not answering, and the next call reports it
        return BetaBrowserState(tabs=[{"tab_id": TAB_ID, "url": url, "title": title, "active": True}])


# --- the JavaScript the tools run in the page ---

# Assigns `ref_N` to each rendered h1-h3, link, button and form control of the current document and lists them one per
# line. The refs are stored on `window`, so a navigation drops them.
READ_PAGE = """(() => {
  const refs = (window.__cdpBrowserRefs ||= { next: 1, byRef: new Map(), byElement: new WeakMap() });
  const roles = { A: 'link', BUTTON: 'button', INPUT: 'textbox', SELECT: 'combobox', TEXTAREA: 'textbox' };
  const name = (el) => (el.getAttribute('aria-label') || el.innerText || el.value || el.placeholder || '')
    .trim().replace(/\\s+/g, ' ').slice(0, 80);
  const lines = [];
  const selector = 'h1, h2, h3, a[href], button, input, select, textarea, [role=button], [role=link]';
  for (const el of document.querySelectorAll(selector)) {
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) continue;  // not rendered
    let ref = refs.byElement.get(el);
    if (!ref) { ref = 'ref_' + refs.next++; refs.byElement.set(el, ref); refs.byRef.set(ref, el); }
    const role = el.getAttribute('role') || roles[el.tagName] || 'heading';
    lines.push(`- ${role} "${name(el)}" [${ref}]`);
  }
  return lines.join('\\n');
})()"""

# The viewport centre of the ref's element, after scrolling it into view, or null if the document lacks the ref.
RESOLVE_REF = """((ref) => {
  const el = window.__cdpBrowserRefs && window.__cdpBrowserRefs.byRef.get(ref);
  if (!el || !el.isConnected) return null;
  el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
})(%s)"""

PAGE_INFO = "({ url: location.href, title: document.title })"
PAGE_TEXT = "document.body ? document.body.innerText : ''"
