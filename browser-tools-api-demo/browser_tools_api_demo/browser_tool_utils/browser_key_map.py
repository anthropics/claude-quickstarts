"""Key mapping for browser keyboard input via Chrome DevTools Protocol."""

from typing import TypedDict


class KeyInfo(TypedDict, total=False):
    key: str
    code: str
    keyCode: int
    text: str
    isKeypad: bool


KEY_MAP: dict[str, KeyInfo] = {
    # Enter keys
    "enter": {"key": "Enter", "code": "Enter", "keyCode": 13, "text": "\r"},
    "return": {"key": "Enter", "code": "Enter", "keyCode": 13, "text": "\r"},
    "kp_enter": {
        "key": "Enter",
        "code": "Enter",
        "keyCode": 13,
        "text": "\r",
        "isKeypad": True,
    },
    # Navigation keys
    "tab": {"key": "Tab", "code": "Tab", "keyCode": 9},
    "delete": {"key": "Delete", "code": "Delete", "keyCode": 46},
    "backspace": {"key": "Backspace", "code": "Backspace", "keyCode": 8},
    "escape": {"key": "Escape", "code": "Escape", "keyCode": 27},
    "esc": {"key": "Escape", "code": "Escape", "keyCode": 27},
    "space": {"key": " ", "code": "Space", "keyCode": 32, "text": " "},
    " ": {"key": " ", "code": "Space", "keyCode": 32, "text": " "},
    # Arrow keys
    "arrowup": {"key": "ArrowUp", "code": "ArrowUp", "keyCode": 38},
    "arrowdown": {"key": "ArrowDown", "code": "ArrowDown", "keyCode": 40},
    "arrowleft": {"key": "ArrowLeft", "code": "ArrowLeft", "keyCode": 37},
    "arrowright": {"key": "ArrowRight", "code": "ArrowRight", "keyCode": 39},
    "up": {"key": "ArrowUp", "code": "ArrowUp", "keyCode": 38},
    "down": {"key": "ArrowDown", "code": "ArrowDown", "keyCode": 40},
    "left": {"key": "ArrowLeft", "code": "ArrowLeft", "keyCode": 37},
    "right": {"key": "ArrowRight", "code": "ArrowRight", "keyCode": 39},
    # Page navigation
    "home": {"key": "Home", "code": "Home", "keyCode": 36},
    "end": {"key": "End", "code": "End", "keyCode": 35},
    "pageup": {"key": "PageUp", "code": "PageUp", "keyCode": 33},
    "pagedown": {"key": "PageDown", "code": "PageDown", "keyCode": 34},
    # Function keys
    "f1": {"key": "F1", "code": "F1", "keyCode": 112},
    "f2": {"key": "F2", "code": "F2", "keyCode": 113},
    "f3": {"key": "F3", "code": "F3", "keyCode": 114},
    "f4": {"key": "F4", "code": "F4", "keyCode": 115},
    "f5": {"key": "F5", "code": "F5", "keyCode": 116},
    "f6": {"key": "F6", "code": "F6", "keyCode": 117},
    "f7": {"key": "F7", "code": "F7", "keyCode": 118},
    "f8": {"key": "F8", "code": "F8", "keyCode": 119},
    "f9": {"key": "F9", "code": "F9", "keyCode": 120},
    "f10": {"key": "F10", "code": "F10", "keyCode": 121},
    "f11": {"key": "F11", "code": "F11", "keyCode": 122},
    "f12": {"key": "F12", "code": "F12", "keyCode": 123},
    # Special characters
    ";": {"key": ";", "code": "Semicolon", "keyCode": 186, "text": ";"},
    "=": {"key": "=", "code": "Equal", "keyCode": 187, "text": "="},
    ",": {"key": ",", "code": "Comma", "keyCode": 188, "text": ","},
    "-": {"key": "-", "code": "Minus", "keyCode": 189, "text": "-"},
    ".": {"key": ".", "code": "Period", "keyCode": 190, "text": "."},
    "/": {"key": "/", "code": "Slash", "keyCode": 191, "text": "/"},
    "`": {"key": "`", "code": "Backquote", "keyCode": 192, "text": "`"},
    "[": {"key": "[", "code": "BracketLeft", "keyCode": 219, "text": "["},
    "\\": {"key": "\\", "code": "Backslash", "keyCode": 220, "text": "\\"},
    "]": {"key": "]", "code": "BracketRight", "keyCode": 221, "text": "]"},
    "'": {"key": "'", "code": "Quote", "keyCode": 222, "text": "'"},
    "!": {"key": "!", "code": "Digit1", "keyCode": 49, "text": "!"},
    "@": {"key": "@", "code": "Digit2", "keyCode": 50, "text": "@"},
    "#": {"key": "#", "code": "Digit3", "keyCode": 51, "text": "#"},
    "$": {"key": "$", "code": "Digit4", "keyCode": 52, "text": "$"},
    "%": {"key": "%", "code": "Digit5", "keyCode": 53, "text": "%"},
    "^": {"key": "^", "code": "Digit6", "keyCode": 54, "text": "^"},
    "&": {"key": "&", "code": "Digit7", "keyCode": 55, "text": "&"},
    "*": {"key": "*", "code": "Digit8", "keyCode": 56, "text": "*"},
    "(": {"key": "(", "code": "Digit9", "keyCode": 57, "text": "("},
    ")": {"key": ")", "code": "Digit0", "keyCode": 48, "text": ")"},
    "_": {"key": "_", "code": "Minus", "keyCode": 189, "text": "_"},
    "+": {"key": "+", "code": "Equal", "keyCode": 187, "text": "+"},
    "{": {"key": "{", "code": "BracketLeft", "keyCode": 219, "text": "{"},
    "}": {"key": "}", "code": "BracketRight", "keyCode": 221, "text": "}"},
    "|": {"key": "|", "code": "Backslash", "keyCode": 220, "text": "|"},
    ":": {"key": ":", "code": "Semicolon", "keyCode": 186, "text": ":"},
    '"': {"key": '"', "code": "Quote", "keyCode": 222, "text": '"'},
    "<": {"key": "<", "code": "Comma", "keyCode": 188, "text": "<"},
    ">": {"key": ">", "code": "Period", "keyCode": 190, "text": ">"},
    "?": {"key": "?", "code": "Slash", "keyCode": 191, "text": "?"},
    "~": {"key": "~", "code": "Backquote", "keyCode": 192, "text": "~"},
    # Lock keys
    "capslock": {"key": "CapsLock", "code": "CapsLock", "keyCode": 20},
    "numlock": {"key": "NumLock", "code": "NumLock", "keyCode": 144},
    "scrolllock": {"key": "ScrollLock", "code": "ScrollLock", "keyCode": 145},
    # Media keys
    "pause": {"key": "Pause", "code": "Pause", "keyCode": 19},
    "insert": {"key": "Insert", "code": "Insert", "keyCode": 45},
    "printscreen": {"key": "PrintScreen", "code": "PrintScreen", "keyCode": 44},
    # Numpad
    "numpad0": {
        "key": "0",
        "code": "Numpad0",
        "keyCode": 96,
        "isKeypad": True,
    },
    "numpad1": {
        "key": "1",
        "code": "Numpad1",
        "keyCode": 97,
        "isKeypad": True,
    },
    "numpad2": {
        "key": "2",
        "code": "Numpad2",
        "keyCode": 98,
        "isKeypad": True,
    },
    "numpad3": {
        "key": "3",
        "code": "Numpad3",
        "keyCode": 99,
        "isKeypad": True,
    },
    "numpad4": {
        "key": "4",
        "code": "Numpad4",
        "keyCode": 100,
        "isKeypad": True,
    },
    "numpad5": {
        "key": "5",
        "code": "Numpad5",
        "keyCode": 101,
        "isKeypad": True,
    },
    "numpad6": {
        "key": "6",
        "code": "Numpad6",
        "keyCode": 102,
        "isKeypad": True,
    },
    "numpad7": {
        "key": "7",
        "code": "Numpad7",
        "keyCode": 103,
        "isKeypad": True,
    },
    "numpad8": {
        "key": "8",
        "code": "Numpad8",
        "keyCode": 104,
        "isKeypad": True,
    },
    "numpad9": {
        "key": "9",
        "code": "Numpad9",
        "keyCode": 105,
        "isKeypad": True,
    },
    "numpadmultiply": {
        "key": "*",
        "code": "NumpadMultiply",
        "keyCode": 106,
        "isKeypad": True,
    },
    "numpadadd": {
        "key": "+",
        "code": "NumpadAdd",
        "keyCode": 107,
        "isKeypad": True,
    },
    "numpadsubtract": {
        "key": "-",
        "code": "NumpadSubtract",
        "keyCode": 109,
        "isKeypad": True,
    },
    "numpaddecimal": {
        "key": ".",
        "code": "NumpadDecimal",
        "keyCode": 110,
        "isKeypad": True,
    },
    "numpaddivide": {
        "key": "/",
        "code": "NumpadDivide",
        "keyCode": 111,
        "isKeypad": True,
    },
}
