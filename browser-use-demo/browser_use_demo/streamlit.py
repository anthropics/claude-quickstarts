"""
Browser Use Demo - Streamlit interface for browser automation with Claude
"""

import asyncio
import base64
import os
import traceback
from datetime import datetime
from enum import StrEnum
from functools import partial
from pathlib import PosixPath
from typing import cast

import streamlit as st
from anthropic import RateLimitError
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
)

from browser_use_demo.loop import (
    APIProvider,
    sampling_loop,
)
from browser_use_demo.tools import ToolResult

PROVIDER_TO_DEFAULT_MODEL_NAME: dict[APIProvider, str] = {
    APIProvider.ANTHROPIC: "claude-sonnet-4-20250514",
    APIProvider.BEDROCK: "anthropic.claude-3-5-sonnet-20241022-v2:0",
    APIProvider.VERTEX: "claude-3-5-sonnet-v2@20241022",
}

CONFIG_DIR = PosixPath("~/.anthropic").expanduser()
API_KEY_FILE = CONFIG_DIR / "api_key"

STREAMLIT_STYLE = """
<style>
    /* Hide the streamlit deploy button */
    .stDeployButton {
        visibility: hidden;
    }
    section[data-testid="stSidebar"] {
        width: 360px !important;
    }
    /* Make the chat input stick to the bottom */
    .stChatInputContainer {
        position: sticky;
        bottom: 0;
        background: white;
        z-index: 999;
    }
</style>
"""

# Browser-specific models that support browser_use_20250910
# Only Claude 4+ models for browser use
BROWSER_COMPATIBLE_MODELS = [
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    "bobcat-v21-prod",
]

class Sender(StrEnum):
    USER = "user"
    BOT = "assistant"
    TOOL = "tool"

def setup_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "api_key" not in st.session_state:
        st.session_state.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if "provider" not in st.session_state:
        st.session_state.provider = APIProvider.ANTHROPIC
    if "model" not in st.session_state:
        st.session_state.model = PROVIDER_TO_DEFAULT_MODEL_NAME[
            st.session_state.provider
        ]
    if "max_tokens" not in st.session_state:
        st.session_state.max_tokens = 8192
    if "system_prompt" not in st.session_state:
        st.session_state.system_prompt = ""
    if "hide_screenshots" not in st.session_state:
        st.session_state.hide_screenshots = False
    if "tools" not in st.session_state:
        st.session_state.tools = {}

def authenticate():
    """Handle API key authentication."""
    if st.session_state.provider == APIProvider.ANTHROPIC:
        if not st.session_state.api_key:
            st.error("Please provide your Anthropic API key in the sidebar")
            st.stop()
    return True

def _render_message(
    sender: Sender,
    message: str | BetaContentBlockParam | ToolResult,
):
    """Render a message in the chat interface."""
    # Handle tool results
    is_tool_result = not isinstance(message, str | dict)
    if not message or (
        is_tool_result
        and st.session_state.hide_screenshots
        and not hasattr(message, "error")
        and not hasattr(message, "output")
    ):
        return

    with st.chat_message(sender):
        if is_tool_result:
            message = cast(ToolResult, message)
            if message.output:
                st.markdown(message.output)
            if message.error:
                st.error(message.error)
            if message.base64_image and not st.session_state.hide_screenshots:
                st.image(base64.b64decode(message.base64_image))
        elif isinstance(message, dict):
            if message["type"] == "text":
                st.write(message["text"])
            elif message["type"] == "tool_use":
                st.code(f"Tool Use: {message['name']}\nInput: {message['input']}")
            elif message.get("type") == "tool_result":
                # Handle tool results stored in messages
                tool_id = message.get("tool_use_id")
                if tool_id and tool_id in st.session_state.tools:
                    tool_result = st.session_state.tools[tool_id]
                    if tool_result.output:
                        st.markdown(tool_result.output)
                    if tool_result.error:
                        st.error(tool_result.error)
                    if tool_result.base64_image and not st.session_state.hide_screenshots:
                        st.image(base64.b64decode(tool_result.base64_image))
            else:
                # Handle other message types
                st.write(message)
        else:
            st.markdown(message)

async def run_agent(user_input: str):
    """Run the browser automation agent with user input."""
    try:
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })

        # Display user message
        _render_message(Sender.USER, user_input)

        # Prepare messages for API
        api_messages = []
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                api_messages.append({
                    "role": "user",
                    "content": msg["content"]
                })
            else:
                api_messages.append(msg)

        # Setup callbacks for streaming responses
        def output_callback(content_block: BetaContentBlockParam):
            """Handle agent output - both text and tool use."""
            _render_message(Sender.BOT, content_block)

        def tool_output_callback(result: ToolResult, tool_id: str):
            """Handle tool execution results."""
            st.session_state.tools[tool_id] = result
            _render_message(Sender.TOOL, result)

        def api_response_callback(request, response, error):
            """Handle API responses."""
            if error:
                st.error(f"API Error: {error}")

        # Run the agent
        response = await sampling_loop(
            model=st.session_state.model,
            provider=st.session_state.provider,
            system_prompt_suffix=st.session_state.system_prompt,
            messages=api_messages,
            output_callback=output_callback,
            tool_output_callback=tool_output_callback,
            api_response_callback=api_response_callback,
            api_key=st.session_state.api_key,
            max_tokens=st.session_state.max_tokens,
        )

        # Store the response in session state
        if response and "content" in response:
            st.session_state.messages.append({
                "role": "assistant",
                "content": response["content"]
            })

    except RateLimitError:
        st.error("Rate limit exceeded. Please wait before sending another message.")
    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.code(traceback.format_exc())

def main():
    """Main application entry point."""
    st.set_page_config(
        page_title="Claude Browser Use Demo",
        page_icon="🌐",
        layout="wide"
    )

    st.markdown(STREAMLIT_STYLE, unsafe_allow_html=True)

    setup_state()

    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        # API Provider (fixed to Anthropic for browser use)
        st.selectbox(
            "API Provider",
            options=[APIProvider.ANTHROPIC],
            index=0,
            key="provider",
            disabled=True,
            help="Browser Use requires Anthropic API"
        )

        # Model selection (only browser-compatible models)
        st.selectbox(
            "Model",
            options=BROWSER_COMPATIBLE_MODELS,
            index=0,
            key="model"
        )

        # API Key
        st.text_input(
            "Anthropic API Key",
            type="password",
            value=st.session_state.api_key,
            key="api_key",
            help="Get your API key from https://console.anthropic.com"
        )

        # Max tokens
        st.number_input(
            "Max Output Tokens",
            min_value=1024,
            max_value=32768,
            value=st.session_state.max_tokens,
            step=1024,
            key="max_tokens"
        )

        # System prompt
        st.text_area(
            "Additional System Prompt",
            value=st.session_state.system_prompt,
            key="system_prompt",
            help="Add custom instructions for the browser agent"
        )

        # Hide screenshots
        st.checkbox(
            "Hide Screenshots",
            value=st.session_state.hide_screenshots,
            key="hide_screenshots",
            help="Hide screenshot outputs in the chat"
        )

        # Clear conversation
        if st.button("Clear Conversation", type="secondary"):
            st.session_state.messages = []
            st.session_state.tools = {}
            st.rerun()

    # Main chat interface
    st.title("🌐 Claude Browser Use Demo")
    st.markdown(
        "This demo showcases Claude's ability to interact with web browsers using "
        "Playwright automation. Ask Claude to navigate websites, fill forms, "
        "extract information, and more!"
    )

    # Authenticate
    if not authenticate():
        return

    # Display conversation history
    for message in st.session_state.messages:
        if message["role"] == "user":
            _render_message(Sender.USER, message["content"])
        elif message["role"] == "assistant":
            if isinstance(message["content"], list):
                for block in message["content"]:
                    if block.get("type") == "tool_result":
                        _render_message(Sender.TOOL, st.session_state.tools.get(block.get("tool_use_id")))
                    else:
                        _render_message(Sender.BOT, block)
            else:
                _render_message(Sender.BOT, message["content"])

    # Chat input
    if prompt := st.chat_input("Ask Claude to browse the web..."):
        asyncio.run(run_agent(prompt))

if __name__ == "__main__":
    main()