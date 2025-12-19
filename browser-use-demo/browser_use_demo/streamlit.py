"""
Browser Use Demo - Streamlit interface for browser automation with Claude
"""

import asyncio
import base64
import io
import json
import os
import time
import traceback
import zipfile
from datetime import datetime
from pathlib import PosixPath

import streamlit as st
from anthropic.types.beta import BetaContentBlockParam

from anthropic import RateLimitError
from browser_use_demo.loop import APIProvider, sampling_loop
from browser_use_demo.message_renderer import MessageRenderer, Sender
from browser_use_demo.tools import ToolResult

PROVIDER_TO_DEFAULT_MODEL_NAME: dict[APIProvider, str] = {
    APIProvider.ANTHROPIC: "claude-sonnet-4-5-20250929",
    APIProvider.BEDROCK: "anthropic.claude-sonnet-4-5-20250929-v1:0",
    APIProvider.VERTEX: "claude-sonnet-4-5@20250929",
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

# Claude 4.5 models for browser automation
BROWSER_COMPATIBLE_MODELS = [
    "claude-sonnet-4-5-20250929",
    "claude-opus-4-5-20251101",
    "claude-haiku-4-5-20251001",
]


def setup_state():
    """Initialize session state variables."""
    # Import here to avoid circular imports when browser_tool lambda is evaluated
    from browser_use_demo.tools import BrowserTool

    # Define all defaults in one place - use lambdas for lazy evaluation of complex values
    defaults = {
        # UI State
        "messages": [],
        "system_prompt": "",
        "hide_screenshots": False,
        "rendered_message_count": 0,  # Track rendered messages to avoid re-rendering
        "last_error": None,  # Store last error message to display persistently
        # API Configuration
        "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "provider": APIProvider.ANTHROPIC,
        "max_tokens": 8192,
        "model": lambda: PROVIDER_TO_DEFAULT_MODEL_NAME[st.session_state.provider],
        # Runtime State
        "tools": {},
        "event_loop": None,  # Persistent event loop for async operations
        "chat_disabled": False,  # Simple flag to disable chat input
        "active_messages": [],  # Store messages for current interaction
        "active_response_container": None,  # Container reference for streaming responses
        # Complex initialization - browser tool (inline lambda)
        "browser_tool": lambda: BrowserTool(),
    }

    # Apply all defaults - evaluate lambdas when needed
    for key, default_value in defaults.items():
        if key not in st.session_state:
            # If it's a callable (lambda), call it to get the actual value
            if callable(default_value):
                st.session_state[key] = default_value()
            else:
                st.session_state[key] = default_value


def _clean_text_extraction_markers(text: str) -> str:
    """Remove text extraction markers and return a summary."""
    if "__PAGE_EXTRACTED__" not in text and "__TEXT_EXTRACTED__" not in text:
        return text

    lines = text.split("\n")
    summary = []
    for line in lines:
        if "__FULL_CONTENT__" in line:
            break
        if "__PAGE_EXTRACTED__" not in line and "__TEXT_EXTRACTED__" not in line:
            summary.append(line)
    return "\n".join(summary) + "\n[Full content extracted but truncated for readability]"


def create_transcript_zip(messages: list, include_images: bool = False) -> bytes:
    """Create a ZIP archive containing the transcript and optionally images.

    Args:
        messages: List of message dictionaries from session state
        include_images: Whether to include images as separate files

    Returns:
        Bytes of the ZIP archive
    """
    # Create an in-memory ZIP file
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        if include_images:
            # Extract images and create transcript with file references
            transcript_json, image_files = extract_images_from_messages(messages)

            # Add images to ZIP
            for idx, img_data in enumerate(image_files):
                filename = f"images/screenshot_{idx+1:04d}.png"
                try:
                    img_bytes = base64.b64decode(img_data)
                    zip_file.writestr(filename, img_bytes)
                except Exception as e:
                    print(f"Error adding image to ZIP: {e}")

            # Add README
            readme_content = f"""Browser Use Demo - Conversation Transcript
Generated: {datetime.now().isoformat()}

This archive contains:
- transcript.json: The conversation transcript
- images/: {len(image_files)} screenshot images referenced in the transcript

The transcript is in JSON format with images stored as separate PNG files.
Image references in the transcript point to files in the images/ directory.
"""
            zip_file.writestr("README.txt", readme_content)
        else:
            # Just create transcript without images
            transcript_json = format_transcript_for_download(messages, False)

            readme_content = f"""Browser Use Demo - Conversation Transcript
Generated: {datetime.now().isoformat()}

This archive contains:
- transcript.json: The conversation transcript (text only)

The transcript is in JSON format and includes all text messages from the conversation.
"""
            zip_file.writestr("README.txt", readme_content)

        # Add the transcript JSON to the ZIP
        zip_file.writestr("transcript.json", transcript_json)

    # Get the ZIP file bytes
    zip_buffer.seek(0)
    return zip_buffer.read()


class ImageExtractor:
    """Helper class to extract images and track their file references."""

    def __init__(self):
        self.image_files = []
        self.image_counter = 0

    def extract_image(self, source: dict) -> dict:
        """Extract an image and return a file reference."""
        if source.get("type") == "base64":
            self.image_counter += 1
            self.image_files.append(source.get("data", ""))
            return {
                "type": "image",
                "file": f"images/screenshot_{self.image_counter:04d}.png"
            }
        else:
            return {"type": "image", "note": "No image data"}

    def process_image_content(self, item: dict) -> dict:
        """Process image content type."""
        source = item.get("source", {})
        return self.extract_image(source)

    def process_text_content(self, item: dict) -> dict:
        """Process text content type."""
        return {
            "type": "text",
            "text": _clean_text_extraction_markers(item.get("text", ""))
        }

    def process_tool_use_content(self, item: dict) -> dict:
        """Process tool use content type."""
        return {
            "type": "tool_use",
            "name": item.get("name", ""),
            "input": item.get("input", {})
        }

    def process_tool_result_content(self, item: dict) -> dict:
        """Process tool result content type."""
        tool_content = []
        for content_item in item.get("content", []):
            if isinstance(content_item, dict):
                content_type = content_item.get("type")
                if content_type == "image":
                    source = content_item.get("source", {})
                    tool_content.append(self.extract_image(source))
                elif content_type == "text":
                    tool_content.append(self.process_text_content(content_item))
                else:
                    tool_content.append(content_item)

        return {
            "type": "tool_result",
            "tool_use_id": item.get("tool_use_id", ""),
            "content": tool_content
        }

    def process_default_content(self, item: dict) -> dict:
        """Default processor for unknown content types."""
        return _format_content_item(item, False)


def extract_images_from_messages(messages: list) -> tuple:
    """Extract images from messages and create transcript with file references.

    Returns:
        Tuple of (transcript_json, list_of_base64_image_data)
    """
    extractor = ImageExtractor()

    # Content type processors
    processors = {
        "image": extractor.process_image_content,
        "text": extractor.process_text_content,
        "tool_use": extractor.process_tool_use_content,
        "tool_result": extractor.process_tool_result_content,
    }

    def process_content(content):
        """Process content using appropriate processors."""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            processed = []
            for item in content:
                if isinstance(item, dict):
                    content_type = item.get("type")
                    processor = processors.get(content_type, extractor.process_default_content)
                    processed.append(processor(item))
                else:
                    processed.append(str(item))
            return processed
        else:
            return str(content)

    # Build transcript
    transcript = {
        "timestamp": datetime.now().isoformat(),
        "format_version": "2.0",
        "image_storage": "separate_files",
        "conversation": []
    }

    # Process all messages
    for message in messages:
        cleaned_message = {
            "role": message.get("role"),
            "timestamp": datetime.now().isoformat(),
            "content": process_content(message.get("content", ""))
        }
        transcript["conversation"].append(cleaned_message)

    return json.dumps(transcript, indent=2, ensure_ascii=False), extractor.image_files


def format_transcript_for_download(messages: list, include_images: bool = False) -> str:
    """Format conversation messages into a readable transcript.

    Args:
        messages: List of message dictionaries from session state
        include_images: Whether to include base64 image data in the transcript

    Returns:
        Formatted JSON string of the conversation
    """
    transcript = {
        "timestamp": datetime.now().isoformat(),
        "format_version": "1.0",
        "includes_images": include_images,
        "conversation": []
    }

    for message in messages:
        cleaned_message = {
            "role": message.get("role"),
            "timestamp": datetime.now().isoformat(),
            "content": _format_message_content(message.get("content", ""), include_images)
        }
        transcript["conversation"].append(cleaned_message)

    return json.dumps(transcript, indent=2, ensure_ascii=False)


def _format_text_content(item: dict, include_images: bool = False) -> dict:
    """Format a text content block."""
    return {
        "type": "text",
        "text": _clean_text_extraction_markers(item.get("text", ""))
    }


def _format_tool_use_content(item: dict, include_images: bool = False) -> dict:
    """Format a tool use content block."""
    return {
        "type": "tool_use",
        "name": item.get("name", ""),
        "input": item.get("input", {})
    }


def _format_tool_result_content(item: dict, include_images: bool = False) -> dict:
    """Format a tool result content block."""
    tool_content = []
    for content_item in item.get("content", []):
        if isinstance(content_item, dict):
            content_type = content_item.get("type")
            if content_type == "text":
                text = _clean_text_extraction_markers(content_item.get("text", ""))
                tool_content.append({"type": "text", "text": text})
            elif content_type == "image":
                if include_images:
                    source = content_item.get("source", {})
                    if source.get("type") == "base64":
                        tool_content.append({
                            "type": "image",
                            "media_type": source.get("media_type", "image/png"),
                            "base64_data": source.get("data", "")
                        })
                else:
                    tool_content.append({"type": "image", "note": "Screenshot taken"})

    return {
        "type": "tool_result",
        "tool_use_id": item.get("tool_use_id", ""),
        "content": tool_content
    }


def _format_image_content(item: dict, include_images: bool = False) -> dict:
    """Format an image content block."""
    if include_images:
        source = item.get("source", {})
        if source.get("type") == "base64":
            return {
                "type": "image",
                "media_type": source.get("media_type", "image/png"),
                "base64_data": source.get("data", "")
            }
    return {"type": "image", "note": "Image/Screenshot included"}


def _format_default_content(item: dict, include_images: bool = False) -> dict:
    """Format unknown content types - fallback handler."""
    return item


# Strategy pattern: Map content types to their formatting functions
CONTENT_FORMATTERS = {
    "text": _format_text_content,
    "tool_use": _format_tool_use_content,
    "tool_result": _format_tool_result_content,
    "image": _format_image_content,
}


def _format_content_item(item, include_images: bool = False):
    """Format a single content item using the appropriate formatter.

    Uses the Strategy pattern to dispatch to the correct formatter based on content type.
    """
    if not isinstance(item, dict):
        return str(item)

    content_type = item.get("type")
    formatter = CONTENT_FORMATTERS.get(content_type, _format_default_content)
    return formatter(item, include_images)


def _format_message_content(content, include_images: bool = False):
    """Format message content based on its type.

    This is the main entry point that handles different content structures.
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        return [_format_content_item(item, include_images) for item in content]
    else:
        return str(content)


def authenticate():
    """Handle API key authentication."""
    if st.session_state.provider == APIProvider.ANTHROPIC:
        if not st.session_state.api_key:
            st.error("Please provide your Anthropic API key in the sidebar")
            st.stop()
    return True


def get_or_create_event_loop():
    """Get existing event loop or create a new one if needed.

    This function ensures we have a valid event loop for async operations,
    reusing existing loops when possible to avoid Playwright issues with asyncio.run().

    Returns:
        The active asyncio event loop.
    """
    if st.session_state.event_loop is None or st.session_state.event_loop.is_closed():
        st.session_state.event_loop = asyncio.new_event_loop()

    asyncio.set_event_loop(st.session_state.event_loop)
    return st.session_state.event_loop


async def run_agent(user_input: str):
    """Run the browser automation agent with user input."""
    try:
        # Ensure chat is disabled while processing
        st.session_state.chat_disabled = True

        # Create message renderer
        renderer = MessageRenderer(st.session_state)

        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Display user message in active container
        with st.session_state.active_response_container:
            renderer.render(Sender.USER, user_input)

        # Clear active messages for new interaction
        st.session_state.active_messages = []

        # Prepare messages for API - preserve full conversation history
        api_messages = list(st.session_state.messages)

        # Setup callbacks for streaming responses
        def output_callback(content_block: BetaContentBlockParam):
            """Handle agent output - both text and tool use."""
            # Stream to active container in real-time
            with st.session_state.active_response_container:
                renderer.render(Sender.BOT, content_block)
            # Store for later persistence
            st.session_state.active_messages.append(("assistant", content_block))

        def tool_output_callback(result: ToolResult, tool_id: str):
            """Handle tool execution results."""
            st.session_state.tools[tool_id] = result
            # Stream to active container in real-time
            with st.session_state.active_response_container:
                renderer.render(Sender.TOOL, result)
            # Store for later persistence
            st.session_state.active_messages.append(("tool", result, tool_id))

        def api_response_callback(request, response, error):
            """Handle API responses."""
            if error:
                with st.session_state.active_response_container:
                    st.error(f"API Error: {error}")

        # Run the agent with persistent browser tool
        updated_messages = await sampling_loop(
            model=st.session_state.model,
            provider=st.session_state.provider,
            system_prompt_suffix=st.session_state.system_prompt,
            messages=api_messages,
            output_callback=output_callback,
            tool_output_callback=tool_output_callback,
            api_response_callback=api_response_callback,
            api_key=st.session_state.api_key,
            max_tokens=st.session_state.max_tokens,
            browser_tool=st.session_state.browser_tool,  # Pass persistent browser instance
            only_n_most_recent_images=3,  # Keep only 3 most recent screenshots for context
        )

        # Update session state with the complete message history
        if updated_messages:
            st.session_state.messages = updated_messages

        # Re-enable chat input
        st.session_state.chat_disabled = False

        # Trigger a rerun to update the history display
        st.rerun()

    except RateLimitError:
        error_msg = "Rate limit exceeded. Please wait before sending another message."
        st.session_state.last_error = {"message": error_msg, "traceback": None}
        with st.session_state.active_response_container:
            st.error(error_msg)
        st.session_state.chat_disabled = False
        st.rerun()
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        error_traceback = traceback.format_exc()
        st.session_state.last_error = {"message": error_msg, "traceback": error_traceback}
        with st.session_state.active_response_container:
            st.error(error_msg)
            st.code(error_traceback)
        st.session_state.chat_disabled = False
        st.rerun()


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
            help="Browser Use requires Anthropic API",
        )

        # Model selection (only browser-compatible models)
        st.selectbox("Model", options=BROWSER_COMPATIBLE_MODELS, index=0, key="model")

        # API Key
        st.text_input(
            "Anthropic API Key",
            type="password",
            value=st.session_state.api_key,
            key="api_key",
            help="Get your API key from https://console.anthropic.com",
        )

        # Max tokens
        st.number_input(
            "Max Output Tokens",
            min_value=1024,
            max_value=32768,
            value=st.session_state.max_tokens,
            step=1024,
            key="max_tokens",
        )

        # System prompt
        st.text_area(
            "Additional System Prompt",
            value=st.session_state.system_prompt,
            key="system_prompt",
            help="Add custom instructions for the browser agent",
        )

        # Hide screenshots
        st.checkbox(
            "Hide Screenshots",
            value=st.session_state.hide_screenshots,
            key="hide_screenshots",
            help="Hide screenshot outputs in the chat",
        )

        # Conversation Management Section
        st.divider()
        st.subheader("💬 Conversation")

        # Download transcript options and button
        if st.session_state.messages:
            # Checkbox to include images
            include_images = st.checkbox(
                "Include images in transcript",
                value=False,
                help="Include screenshots as separate PNG files in a ZIP archive"
            )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            if include_images:
                # Generate ZIP with images
                zip_data = create_transcript_zip(
                    st.session_state.messages,
                    include_images=True
                )

                # Show file size
                file_size_kb = len(zip_data) / 1024
                if file_size_kb > 1024:
                    size_str = f"{file_size_kb / 1024:.1f} MB"
                else:
                    size_str = f"{file_size_kb:.1f} KB"

                st.download_button(
                    label=f"📦 Download Transcript ZIP ({size_str})",
                    data=zip_data,
                    file_name=f"browser_demo_transcript_{timestamp}.zip",
                    mime="application/zip",
                    help=f"Download conversation with images as ZIP archive ({size_str})",
                    type="primary",
                    use_container_width=True,
                )
            else:
                # Generate JSON only
                transcript_json = format_transcript_for_download(
                    st.session_state.messages,
                    include_images=False
                )

                # Show file size
                file_size_kb = len(transcript_json.encode('utf-8')) / 1024
                if file_size_kb > 1024:
                    size_str = f"{file_size_kb / 1024:.1f} MB"
                else:
                    size_str = f"{file_size_kb:.1f} KB"

                st.download_button(
                    label=f"📄 Download Transcript JSON ({size_str})",
                    data=transcript_json,
                    file_name=f"browser_demo_transcript_{timestamp}.json",
                    mime="application/json",
                    help=f"Download conversation transcript as JSON ({size_str})",
                    type="primary",
                    use_container_width=True,
                )
        else:
            st.info("No messages to download yet", icon="💬")

        # Clear conversation
        if st.button("🗑️ Clear Conversation", type="secondary", use_container_width=True):
            st.session_state.messages = []
            st.session_state.tools = {}
            st.session_state.rendered_message_count = 0
            st.session_state.active_messages = []
            st.session_state.chat_disabled = False
            st.rerun()

        # Reset browser to blank page
        if st.button("Reset Browser", type="secondary"):
            async def reset_browser():
                if st.session_state.browser_tool._page:
                    await st.session_state.browser_tool._page.goto("about:blank")

            if st.session_state.event_loop is None or st.session_state.event_loop.is_closed():
                st.session_state.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(st.session_state.event_loop)
            st.session_state.event_loop.run_until_complete(reset_browser())
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


    # Create container for conversation history
    history_container = st.container()

    # Display conversation history in the history container
    renderer = MessageRenderer(st.session_state)
    with history_container:
        renderer.render_conversation_history(st.session_state.messages)

    # Create container for active/streaming responses
    active_container = st.container()
    st.session_state.active_response_container = active_container

    # Simple callback to disable chat input on submit
    def disable_chat_callback():
        st.session_state.chat_disabled = True

    # Show persistent error message if there is one
    if st.session_state.last_error:
        st.error(st.session_state.last_error["message"])
        if st.session_state.last_error["traceback"]:
            with st.expander("Show full traceback"):
                st.code(st.session_state.last_error["traceback"])
        if st.button("Clear Error"):
            st.session_state.last_error = None
            st.rerun()

    # Show status when chat is disabled
    if st.session_state.chat_disabled:
        st.info("🤖 Claude is currently processing your request. Please wait...")

    # Simple chat input with disabled state
    prompt = st.chat_input(
        "Ask Claude to browse the web...",
        disabled=st.session_state.chat_disabled,
        on_submit=disable_chat_callback
    )

    if prompt:
        # Clear any previous error when starting a new request
        st.session_state.last_error = None
        # Process the prompt
        loop = get_or_create_event_loop()
        loop.run_until_complete(run_agent(prompt))


if __name__ == "__main__":
    main()
