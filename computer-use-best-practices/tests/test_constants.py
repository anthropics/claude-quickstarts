import pytest


def test_autocompaction_trigger_floor(capsys):
    from constants import AUTOCOMPACTION_MIN_TRIGGER, Config

    c = Config().with_overrides(autocompaction_trigger_tokens=12_000)
    assert c.autocompaction_trigger_tokens == AUTOCOMPACTION_MIN_TRIGGER
    assert "clamping" in capsys.readouterr().err

    c = Config().with_overrides(autocompaction_trigger_tokens=80_000)
    assert c.autocompaction_trigger_tokens == 80_000


def test_provider_first_party_feature_validation():
    from constants import Config

    with pytest.raises(ValueError, match=r"enable_autocompaction.*first-party"):
        Config().with_overrides(provider="vertex", enable_autocompaction=True)

    with pytest.raises(ValueError, match=r"enable_advisor_tool, enable_autocompaction"):
        Config().with_overrides(
            provider="bedrock", enable_advisor_tool=True, enable_autocompaction=True
        )

    c = Config().with_overrides(
        provider="vertex", enable_autocompaction=False, enable_advisor_tool=False
    )
    assert c.provider == "vertex"

    c = Config().with_overrides(provider="anthropic", enable_autocompaction=True)
    assert c.provider == "anthropic"
