import pytest

import constants
from computer_use import __main__ as cli


def _names() -> list[str]:
    return [t.name for t in cli.build_tools()]


def _override(monkeypatch: pytest.MonkeyPatch, **kw: object) -> None:
    """Patch cfg to pure dataclass defaults plus the given overrides, ignoring
    whatever the local .env / CU_* environment may have set."""
    new = constants.Config().with_overrides(**kw)
    monkeypatch.setattr(constants, "cfg", new)
    monkeypatch.setattr(cli, "cfg", new)


def test_default_includes_both_sets(monkeypatch: pytest.MonkeyPatch) -> None:
    _override(monkeypatch)
    names = _names()
    assert "computer" in names
    assert "browser" in names


def test_disable_computer_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _override(monkeypatch, enable_computer_use_tools=False)
    names = _names()
    assert "computer" not in names
    assert "computer_batch" not in names
    assert "open_application" not in names
    assert "browser" in names
    assert "bash" in names


def test_disable_browser_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _override(monkeypatch, enable_browser_use_tools=False)
    names = _names()
    assert "browser" not in names
    assert "browser_batch" not in names
    assert "computer" in names


def test_both_disabled_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _override(monkeypatch, enable_computer_use_tools=False, enable_browser_use_tools=False)
    with pytest.raises(ValueError, match="At least one of"):
        cli.build_tools()
