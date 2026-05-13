from typing import Any

from computer_use.loop import _set_trailing_cache_control, _truncate_to_last_compaction
from constants import AUTOCOMPACTION_SUPPORTED_MODELS, COMPACTION_BETA, Model


# Compaction block types are not in the SDK's MessageParam content union yet,
# so test fixtures are typed as list[Any] rather than list[MessageParam].
def _msgs() -> list[Any]:
    return [
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": [{"type": "text", "text": "a"}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "1", "content": []}]},
        {
            "role": "assistant",
            "content": [
                {"type": "compaction", "content": "summary of turns 1-3"},
                {"type": "text", "text": "continuing"},
            ],
        },
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "2", "content": []}]},
    ]


def test_truncate_drops_before_compaction() -> None:
    m = _msgs()
    _truncate_to_last_compaction(m)
    assert len(m) == 2
    assert m[0]["role"] == "assistant"
    assert m[0]["content"][0]["type"] == "compaction"


def test_truncate_noop_without_compaction() -> None:
    m: list[Any] = [
        {"role": "user", "content": "x"},
        {"role": "assistant", "content": [{"type": "text"}]},
    ]
    _truncate_to_last_compaction(m)
    assert len(m) == 2


def test_truncate_picks_most_recent() -> None:
    m = _msgs()
    m.append(
        {"role": "assistant", "content": [{"type": "compaction", "content": "second summary"}]}
    )
    m.append({"role": "user", "content": "follow-up"})
    _truncate_to_last_compaction(m)
    assert len(m) == 2
    assert m[0]["content"][0]["content"] == "second summary"


def test_cache_control_lands_on_compaction_when_last_cacheable() -> None:
    m: list[Any] = [
        {"role": "assistant", "content": [{"type": "compaction", "content": "s"}]},
        {"role": "user", "content": "follow-up"},
    ]
    _set_trailing_cache_control(m)
    assert m[0]["content"][0]["cache_control"] == {"type": "ephemeral"}


def test_cache_control_ladders_last_n() -> None:
    m: list[Any] = [
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": str(i), "content": []}]}
        for i in range(5)
    ]
    _set_trailing_cache_control(m)
    marks = ["cache_control" in msg["content"][0] for msg in m]
    assert marks == [False, False, True, True, True]
    # Idempotent: re-running keeps exactly the last 3 marked.
    _set_trailing_cache_control(m)
    assert ["cache_control" in msg["content"][0] for msg in m] == marks


def test_cache_control_on_mixed_compaction_and_tool_result() -> None:
    m = _msgs()
    _truncate_to_last_compaction(m)
    _set_trailing_cache_control(m)
    assert "cache_control" in m[-1]["content"][0]  # trailing tool_result
    assert "cache_control" in m[0]["content"][0]  # compaction (within last 3)


def test_compaction_beta_header() -> None:
    assert COMPACTION_BETA == "compact-2026-01-12"


def test_supported_models_excludes_haiku() -> None:
    assert Model.HAIKU_4_5.value not in AUTOCOMPACTION_SUPPORTED_MODELS
    assert Model.SONNET_4_6.value in AUTOCOMPACTION_SUPPORTED_MODELS
    assert Model.OPUS_4_6.value in AUTOCOMPACTION_SUPPORTED_MODELS
