"""A minimal example of the computer toolset interface over VNC. It drives one desktop with ten tools and no VNC
library.

It shows the interface. It is not production code. It implements `BetaAbstractComputerToolset20260801` with the
tools a first run needs (`screenshot`, the clicks, `mouse_move`, `scroll`, `key`, `type` and `wait`) against a VNC
server that asks for no password. The SDK reports every other tool as disabled and offers the model only these.

It reads the screen unscaled, in the Raw encoding, over RFB 3.7 or newer. It refuses a screen larger than 1920×1200
and a server that needs a password. See the README.

Read "Running a computer toolset safely" in the SDK guide (computer-toolset.md) before pointing it at anything but
a throwaway desktop, because what the model sees on screen steers what it does next.

Run it with run.py, which contains the install and run instructions.
"""

from __future__ import annotations

import base64
import io
import socket
import struct
import time
from typing import Any

from anthropic.tools import ToolError
from anthropic.tools.computer import (
    BetaAbstractComputerToolset20260801,
    BetaScreenshotResult,
    BetaToolsetCallContext,
)
from anthropic.types.beta import (
    BetaComputerScreenshotInput,
    BetaComputerDoubleClickInput,
    BetaComputerKeyInput,
    BetaComputerLeftClickInput,
    BetaComputerMouseMoveInput,
    BetaComputerRightClickInput,
    BetaComputerScrollInput,
    BetaComputerTripleClickInput,
    BetaComputerTypeInput,
    BetaComputerWaitInput,
)
from PIL import Image
from typing_extensions import override

# Screenshots are not scaled, and a screen this size stays inside the API's image limits.
MAX_WIDTH, MAX_HEIGHT = 1920, 1200
# RFB's KeyEvent message takes X11 keysyms. These are the keysyms of the key names the model uses. A single
# character is its own keysym.
KEYSYMS = {
    "return": 0xFF0D, "enter": 0xFF0D, "tab": 0xFF09, "escape": 0xFF1B, "backspace": 0xFF08, "delete": 0xFFFF,
    "insert": 0xFF63, "home": 0xFF50, "end": 0xFF57, "page_up": 0xFF55, "page_down": 0xFF56, "space": 0x20,
    "left": 0xFF51, "up": 0xFF52, "right": 0xFF53, "down": 0xFF54, "shift": 0xFFE1, "ctrl": 0xFFE3,
    "control": 0xFFE3, "alt": 0xFFE9, "super": 0xFFEB, "cmd": 0xFFEB, "win": 0xFFEB,
    **{f"f{n}": 0xFFBD + n for n in range(1, 13)},
}  # fmt: skip
# These are RFB's PointerEvent button-mask values. The wheel is four buttons, one per direction.
LEFT, RIGHT = 1, 4
WHEEL = {"up": 8, "down": 16, "left": 32, "right": 64}


def keysym(name: str) -> int:
    """Return the keysym of a key name (case-insensitive) or of a single character."""
    if len(name) == 1:
        return ord(name) if ord(name) < 0x100 else 0x01000000 | ord(name)  # Beyond Latin-1, it is the Unicode keysym.
    if name.lower() not in KEYSYMS:
        raise ToolError(f"unknown key {name!r}; use a single character or a name such as Return, Page_Up or F5")
    return KEYSYMS[name.lower()]


class VncComputer(BetaAbstractComputerToolset20260801):
    """Drive one desktop over VNC, speaking RFB 3.7 or newer to a server without a password. Keyword arguments beyond
    `host` and `port` are the SDK's toolset options (`configs`, `confirm` and the rest) and are passed on unchanged."""

    def __init__(self, *, host: str = "127.0.0.1", port: int = 5900, **options: Any) -> None:
        super().__init__(**options)
        # A server that stops answering fails the call after 10 s rather than hanging the run.
        self._socket = socket.create_connection((host, port), timeout=10)
        self._stream = self._socket.makefile("rb")
        # VNC cannot report where the pointer is, so a click without a coordinate uses the last position set here.
        self._cursor = (0, 0)
        self.width, self.height = self._handshake()
        if self.width > MAX_WIDTH or self.height > MAX_HEIGHT:
            raise RuntimeError(
                f"the screen is {self.width}x{self.height}; lower it to {MAX_WIDTH}x{MAX_HEIGHT} or less"
            )

    def _handshake(self) -> tuple[int, int]:
        """Do the RFB handshake (version, security, ClientInit, ServerInit), then set the pixel format and encoding."""
        version = min(self._read(12), b"RFB 003.008\n")  # A newer server accepts 3.8, the newest this example speaks.
        if version not in (b"RFB 003.007\n", b"RFB 003.008\n"):
            raise RuntimeError(f"expected an RFB 3.7 or newer server; it greeted with {version!r}")
        self._socket.sendall(version)
        if 1 not in self._read(self._read(1)[0]):  # Security type 1 is None, which means no password.
            raise RuntimeError(
                "this example needs a VNC server without a password; see the README for the Xvnc command"
            )
        self._socket.sendall(b"\x01")
        if version == b"RFB 003.008\n" and self._read(4) != b"\0\0\0\0":  # Only 3.8 sends a SecurityResult here.
            raise RuntimeError("the VNC server refused the connection")
        self._socket.sendall(b"\x01")  # ClientInit asks for a shared session, so a person can watch the same desktop.
        width, height = struct.unpack(">HH", self._read(4))
        # The server's pixel format is skipped, because ours is set below.
        (name_length,) = struct.unpack(">16xI", self._read(20))
        self._read(name_length)
        # SetPixelFormat asks for 32-bit true-colour pixels with red in the lowest byte, so each pixel arrives as
        # R, G, B, X and Pillow reads the frame as is. SetEncodings asks for Raw only.
        self._socket.sendall(struct.pack(">BxxxBBBBHHHBBBxxx", 0, 32, 24, 0, 1, 255, 255, 255, 0, 8, 16))
        self._socket.sendall(struct.pack(">BxHi", 2, 1, 0))
        return width, height

    def _read(self, count: int) -> bytes:
        data = self._stream.read(count)
        if len(data) < count:
            raise RuntimeError("the VNC server closed the connection")
        return data

    @override
    def close(self) -> None:
        super().close()
        self._stream.close()
        self._socket.close()

    def _move(self, x: int, y: int, buttons: int = 0) -> None:
        """Send one PointerEvent. A point off the screen is refused, not clamped, so the model sees its mistake."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise ToolError(f"({x}, {y}) is outside the {self.width}x{self.height} screen")
        self._socket.sendall(struct.pack(">BBHH", 5, buttons, x, y))
        self._cursor = (x, y)

    def _keys(self, keysyms: list[int], down: bool) -> None:
        """Send the KeyEvents of a chord, pressed in order or released in reverse."""
        for sym in keysyms if down else reversed(keysyms):
            self._socket.sendall(struct.pack(">BBxxI", 4, down, sym))

    def _click(self, coordinate: list[int] | None, modifiers: str | None, button: int, times: int = 1) -> None:
        """Press and release `button` at the coordinate, or at the cursor, while holding the modifier chord."""
        x, y = coordinate or self._cursor
        self._move(x, y)
        held = [keysym(name) for name in modifiers.split("+")] if modifiers else []
        self._keys(held, True)
        for _ in range(times):
            self._move(x, y, button)
            self._move(x, y)
            time.sleep(0.01)  # Clicks this far apart register separately and still count as one double or triple click.
        self._keys(held, False)

    @override
    def screenshot(
        self, context: BetaToolsetCallContext, input: BetaComputerScreenshotInput
    ) -> BetaScreenshotResult:
        time.sleep(0.5)  # VNC has no signal that an action is done, so the desktop gets time to draw the last one.
        # Ask for the whole screen with a FramebufferUpdateRequest, then read messages until the FramebufferUpdate.
        self._socket.sendall(struct.pack(">BBHHHH", 3, 0, 0, 0, self.width, self.height))
        while (kind := self._read(1)[0]) != 0:
            if kind == 3:  # A ServerCutText says the clipboard changed; its text is skipped.
                self._read(struct.unpack(">3xI", self._read(7))[0])
            elif kind != 2:  # Type 2 is a Bell, which is ignored.
                raise RuntimeError(f"unexpected message type {kind} from the VNC server")
        frame = bytearray(self.width * self.height * 4)
        (rectangles,) = struct.unpack(">xH", self._read(3))
        for _ in range(rectangles):
            x, y, width, height, encoding = struct.unpack(">HHHHi", self._read(12))
            if encoding != 0:
                raise RuntimeError(f"the VNC server sent encoding {encoding}; only Raw was asked for")
            pixels = self._read(width * height * 4)
            for row in range(height):
                start = ((y + row) * self.width + x) * 4
                frame[start : start + width * 4] = pixels[row * width * 4 : (row + 1) * width * 4]
        png = io.BytesIO()
        Image.frombytes("RGB", (self.width, self.height), bytes(frame), "raw", "RGBX").save(png, "PNG")
        return BetaScreenshotResult(data=base64.b64encode(png.getvalue()).decode())

    @override
    def mouse_move(self, context: BetaToolsetCallContext, input: BetaComputerMouseMoveInput) -> None:
        x, y = input.coordinate
        self._move(x, y)

    @override
    def left_click(self, context: BetaToolsetCallContext, input: BetaComputerLeftClickInput) -> None:
        self._click(input.coordinate, input.text, LEFT)

    @override
    def right_click(self, context: BetaToolsetCallContext, input: BetaComputerRightClickInput) -> None:
        self._click(input.coordinate, input.text, RIGHT)

    @override
    def double_click(self, context: BetaToolsetCallContext, input: BetaComputerDoubleClickInput) -> None:
        self._click(input.coordinate, input.text, LEFT, times=2)

    @override
    def triple_click(self, context: BetaToolsetCallContext, input: BetaComputerTripleClickInput) -> None:
        self._click(input.coordinate, input.text, LEFT, times=3)

    @override
    def scroll(self, context: BetaToolsetCallContext, input: BetaComputerScrollInput) -> None:
        self._click(input.coordinate, input.text, WHEEL[input.scroll_direction], times=input.scroll_amount)

    @override
    def key(self, context: BetaToolsetCallContext, input: BetaComputerKeyInput) -> None:
        keysyms = [keysym(name) for name in input.text.split("+")]
        for _ in range(input.repeat or 1):
            self._keys(keysyms, True)
            self._keys(keysyms, False)

    @override
    def type(self, context: BetaToolsetCallContext, input: BetaComputerTypeInput) -> None:
        for char in input.text:
            sym = [keysym({"\n": "Return", "\t": "Tab"}.get(char, char))]
            self._keys(sym, True)
            self._keys(sym, False)
            time.sleep(0.012)  # Typed at wire speed, a terminal's echo and its output interleave; this paces the keys.

    @override
    def wait(self, context: BetaToolsetCallContext, input: BetaComputerWaitInput) -> None:
        time.sleep(input.duration)
