import textwrap

from constants import Config, _coerce


def test_defaults() -> None:
    c = Config()
    assert c.jpeg_quality == 75
    assert c.enable_advisor_tool is False
    assert c.browser_viewport == (1456, 819)


def test_coerce_primitives() -> None:
    assert _coerce(Config, "jpeg_quality", "80") == 80
    assert _coerce(Config, "api_retry_base_delay", "2.5") == 2.5
    assert _coerce(Config, "enable_advisor_tool", "true") is True
    assert _coerce(Config, "enable_advisor_tool", "0") is False
    assert _coerce(Config, "advisor_max_uses", "none") is None
    assert _coerce(Config, "advisor_max_uses", "3") == 3
    assert _coerce(Config, "browser_viewport", "1280x720") == (1280, 720)
    assert _coerce(Config, "extra_models", "a, b ,c") == ("a", "b", "c")
    assert _coerce(Config, "image_prune_strategy", "none") == "none"


def test_load_from_toml(tmp_path) -> None:
    p = tmp_path / "c.toml"
    p.write_text(
        textwrap.dedent("""
        jpeg_quality = 90
        enable_advisor_tool = true
        browser_viewport = [1024, 768]
        extra_models = ["foo", "bar"]
        """)
    )
    c = Config.load(p)
    assert c.jpeg_quality == 90
    assert c.enable_advisor_tool is True
    assert c.browser_viewport == [1024, 768] or c.browser_viewport == (1024, 768)
    assert tuple(c.extra_models) == ("foo", "bar")


def test_env_var_overrides_toml(tmp_path, monkeypatch) -> None:
    p = tmp_path / "c.toml"
    p.write_text("jpeg_quality = 50\n")
    monkeypatch.setenv("CU_JPEG_QUALITY", "99")
    c = Config.load(p)
    assert c.jpeg_quality == 99


def test_with_overrides() -> None:
    c = Config().with_overrides(jpeg_quality="60", enable_editor_tool="false")
    assert c.jpeg_quality == 60
    assert c.enable_editor_tool is False


def test_coerce_extra_models_with_x_letter() -> None:
    assert _coerce(Config, "extra_models", "claude-experimental-v2") == ("claude-experimental-v2",)
    assert _coerce(Config, "extra_models", "model-x,other-x-y") == ("model-x", "other-x-y")


def test_coerce_dict_field_from_string_errors_clearly() -> None:
    """Dict-typed fields can't be set via env var; fail at load time rather
    than letting a raw str through to AttributeError later."""
    import pytest

    with pytest.raises(ValueError, match="dict-typed"):
        _coerce(Config, "thinking_effort", "high")
