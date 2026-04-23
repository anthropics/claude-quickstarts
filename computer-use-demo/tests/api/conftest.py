"""Shared fixtures for API tests.

Env vars are set at module import so that ``computer_use_demo.settings`` picks
up a tempfile-backed SQLite URL instead of the real ``~/.anthropic/db.sqlite``.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest import mock

_TMPDIR = Path(tempfile.mkdtemp(prefix="cud_test_"))
os.environ["COMPUTER_USE_DATA_DIR"] = str(_TMPDIR)
os.environ["COMPUTER_USE_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMPDIR}/test.sqlite"
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

import pytest  # noqa: E402
from anthropic.types import TextBlock, ToolUseBlock  # noqa: E402
from anthropic.types.beta import BetaMessage  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from computer_use_demo.api.chats.services import (  # noqa: E402
    agent_runner as runner_module,
)
from computer_use_demo.api.main import create_app  # noqa: E402


class FakeStream:
    """Mimics ``AsyncMessageStream``: async-iterable + ``get_final_message``."""

    def __init__(self, final_message, events=None):
        self._final = final_message
        self._events = events or []

    def __aiter__(self):
        async def gen():
            for ev in self._events:
                yield ev

        return gen()

    async def get_final_message(self):
        return self._final


class FakeStreamManager:
    def __init__(self, final_message, events=None):
        self._stream = FakeStream(final_message, events)

    async def __aenter__(self):
        return self._stream

    async def __aexit__(self, *a):
        return False


def make_final_message(
    *, content, stop_reason="end_turn", msg_id="msg_1"
) -> BetaMessage:
    return mock.Mock(
        spec=BetaMessage,
        content=content,
        stop_reason=stop_reason,
        usage=None,
        id=msg_id,
    )


def text_block(text: str) -> TextBlock:
    return TextBlock(type="text", text=text)


def tool_use_block(*, block_id: str, name: str, inp: dict) -> ToolUseBlock:
    return ToolUseBlock(type="tool_use", id=block_id, name=name, input=inp)


class MockToolCollection:
    """Stand-in for ToolCollection that records invocations and never touches the desktop."""

    instances: list[MockToolCollection] = []

    def __init__(self, *tools):
        self.calls: list[tuple[str, dict]] = []
        MockToolCollection.instances.append(self)

    def to_params(self):
        return []

    async def run(self, *, name: str, tool_input: dict):
        self.calls.append((name, tool_input))
        return mock.Mock(
            output=f"ran {name}", error=None, base64_image=None, system=None
        )


@pytest.fixture(autouse=True)
def _reset_db_state():
    """Reset the module-level async engine between tests so schema/state is clean."""
    import computer_use_demo.api.db as db_mod

    db_mod._engine = None
    db_mod._session_factory = None
    db_path = _TMPDIR / "test.sqlite"
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(db_path) + suffix)
        if candidate.exists():
            candidate.unlink()
    yield


@pytest.fixture
def fake_stream_factory():
    def _factory(streams: list[FakeStreamManager]):
        return mock.MagicMock(side_effect=streams)

    return _factory


@pytest.fixture
def patch_anthropic(monkeypatch):
    """Patch AsyncAnthropic so tests can script streaming responses."""

    scripted: list[FakeStreamManager] = []

    def configure(streams: list[FakeStreamManager]):
        scripted.clear()
        scripted.extend(streams)

    client = mock.MagicMock()

    def _stream_side_effect(**_kwargs):
        if not scripted:
            raise AssertionError("no scripted stream configured")
        return scripted.pop(0)

    client.beta.messages.stream.side_effect = _stream_side_effect

    monkeypatch.setattr(
        "computer_use_demo.loop.AsyncAnthropic", lambda *a, **kw: client
    )
    # Replace tool collection in both the loop and the agent_runner tool-runner factory.
    monkeypatch.setattr("computer_use_demo.loop.ToolCollection", MockToolCollection)
    monkeypatch.setattr(runner_module, "ToolCollection", MockToolCollection)
    MockToolCollection.instances = []

    return configure


@pytest.fixture
def client(patch_anthropic):
    app = create_app()
    with TestClient(app) as c:
        c.app_ref = app  # type: ignore[attr-defined]
        yield c
