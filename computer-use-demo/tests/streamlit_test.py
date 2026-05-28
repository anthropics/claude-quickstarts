from unittest import mock

import pytest
from anthropic.types import TextBlockParam
from streamlit.testing.v1 import AppTest

from computer_use_demo.streamlit import Sender


@pytest.fixture
def streamlit_app():
    return AppTest.from_file("computer_use_demo/streamlit.py")


def test_streamlit(streamlit_app: AppTest):
    streamlit_app.run()
    streamlit_app.text_input[1].set_value("sk-ant-0000000000000").run()
    with mock.patch("computer_use_demo.loop.sampling_loop") as patch:
        streamlit_app.chat_input[0].set_value("Hello").run()
        assert patch.called
        assert patch.call_args.kwargs["messages"] == [
            {
                "role": Sender.USER,
                "content": [TextBlockParam(text="Hello", type="text")],
            }
        ]
        assert not streamlit_app.exception


@pytest.mark.parametrize(
    ("model", "expected_modes"),
    [
        # Undated alias of an extended-only model: adaptive must not be offered.
        ("claude-sonnet-4-5", ["off", "extended"]),
        # Adaptive-only models: the manual thinking budget must not be offered.
        ("claude-opus-4-7", ["adaptive", "off"]),
        ("claude-opus-4-8", ["adaptive", "off"]),
        # Bedrock form of a known family resolves to that family's config.
        ("anthropic.claude-sonnet-4-5-20250929-v1:0", ["off", "extended"]),
        # Unknown model: every mode is selectable, defaulting to off.
        ("some-unknown-model", ["off", "adaptive", "extended"]),
    ],
)
def test_thinking_modes_follow_selected_model(
    streamlit_app: AppTest, model: str, expected_modes: list[str]
):
    streamlit_app.run()
    streamlit_app.text_input[0].set_value(model).run()
    thinking_radios = [r for r in streamlit_app.radio if r.label == "Thinking"]
    assert len(thinking_radios) == 1
    assert list(thinking_radios[0].options) == [m.capitalize() for m in expected_modes]
    assert streamlit_app.session_state["thinking_mode"] == expected_modes[0]
    assert not streamlit_app.exception
