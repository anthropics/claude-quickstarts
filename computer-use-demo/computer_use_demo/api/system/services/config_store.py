"""File-backed config for the API key, base URL, and system-prompt suffix.

Values live under ``~/.anthropic/`` so they survive container restarts via
the mounted volume.
"""

from __future__ import annotations

from pathlib import Path

from computer_use_demo.settings import (
    API_KEY_FILE,
    BASE_URL_FILE,
    SYSTEM_PROMPT_FILE,
)


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text().strip()


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def get_api_key() -> str:
    return _read(API_KEY_FILE)


def set_api_key(value: str) -> None:
    _write(API_KEY_FILE, value)


def has_api_key() -> bool:
    return bool(get_api_key())


def get_base_url() -> str:
    return _read(BASE_URL_FILE)


def set_base_url(value: str) -> None:
    _write(BASE_URL_FILE, value)


def get_system_prompt() -> str:
    return _read(SYSTEM_PROMPT_FILE)


def set_system_prompt(value: str) -> None:
    _write(SYSTEM_PROMPT_FILE, value)
