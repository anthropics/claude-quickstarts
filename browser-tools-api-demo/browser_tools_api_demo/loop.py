"""
Sampling loop for browser automation with Claude
"""

import os
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Any, Optional, cast

import httpx
from anthropic import (
    Anthropic,
    AnthropicBedrock,
    AnthropicVertex,
    APIError,
)
from anthropic.types.beta import (
    BetaCacheControlEphemeralParam,
    BetaContentBlockParam,
    BetaImageBlockParam,
    BetaMessage,
    BetaMessageParam,
    BetaTextBlock,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
    BetaToolUseBlockParam,
)

from .tools import BrowserTool, ToolCollection, ToolResult

PROMPT_CACHING_BETA_FLAG = "prompt-caching-2024-07-31"
BROWSER_TOOLS_BETA_FLAG = "browser-tools-2025-09-10"

class APIProvider(StrEnum):
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    VERTEX = "vertex"

# Browser-specific system prompt
BROWSER_SYSTEM_PROMPT = f"""<SYSTEM_CAPABILITY>
* You are using a web browser to interact with websites and web applications.
* You have access to browser actions like navigate, click, type, scroll, and screenshot.
* Chromium is the browser being used via Playwright automation.
* The current date is {datetime.today().strftime("%A, %B %-d, %Y")}.
</SYSTEM_CAPABILITY>

<BROWSER_STATE_AWARENESS>
CRITICAL: The browser maintains its state between conversations!
* You will receive a screenshot showing the CURRENT browser state at the start of each turn
* LOOK AT THE SCREENSHOT to see what page is currently displayed
* If you're already on the correct page, DO NOT navigate again - just proceed with the requested action
* DO NOT repeat previous navigation steps if already on the destination page
* Example: If asked to "click Interpretability" and screenshot shows you're on the Research page, just click Interpretability - DO NOT re-navigate to Anthropic or Research first
</BROWSER_STATE_AWARENESS>

<BROWSER_GUIDELINES>
* When navigating to a URL, use the full URL including https:// or http://
* Take screenshots to see the current state of the page
* If a page is loading slowly, use the wait action to give it time
* For form filling, click on input fields before typing
* Use scroll actions to see more content on long pages
* Use the key action for keyboard shortcuts (e.g., "ctrl+a" to select all)
</BROWSER_GUIDELINES>

<CRITICAL_FOR_CONTENT_EXTRACTION>
* To READ or EXTRACT text content from a webpage, you MUST use one of these actions:
  - read_page: Returns the DOM structure with all text content and element references
  - get_page_text: Returns all text content from the page in a readable format
* The screenshot action ONLY returns an image and CANNOT extract text
* Example workflow for reading content:
  1. navigate to the URL
  2. Use get_page_text or read_page to extract the actual text
  3. Only use screenshot for visual confirmation if needed
</CRITICAL_FOR_CONTENT_EXTRACTION>

<IMPORTANT>
* When a page shows popups or modals, try to close them or work around them
* Always verify actions succeeded - use appropriate actions to confirm
* If clicking on an element doesn't work with coordinates, try clicking nearby or scrolling first
* Be patient with page loads and dynamic content
</IMPORTANT>"""

async def sampling_loop(
    *,
    model: str,
    provider: APIProvider,
    system_prompt_suffix: str,
    messages: list[BetaMessageParam],
    output_callback: Callable[[BetaContentBlockParam], None],
    tool_output_callback: Callable[[ToolResult, str], None],
    api_response_callback: Callable[
        [httpx.Request, httpx.Response | object | None, Exception | None], None
    ],
    api_key: str,
    only_n_most_recent_images: int | None = None,
    max_tokens: int = 4096,
    browser_tool: Optional[BrowserTool] = None,
):
    """
    Sampling loop for browser automation.

    Args:
        browser_tool: Optional persistent browser tool instance. If not provided, creates a new one.
    """
    # Reuse existing browser tool or create a new one
    if browser_tool is None:
        # Create browser tool with environment dimensions (fallback to WIDTH/HEIGHT from Docker)
        browser_width = int(os.environ.get('BROWSER_WIDTH', os.environ.get('WIDTH', '1920')))
        browser_height = int(os.environ.get('BROWSER_HEIGHT', os.environ.get('HEIGHT', '1080')))
        browser_tool = BrowserTool(width=browser_width, height=browser_height)

    tool_collection = ToolCollection(browser_tool)

    # Build system prompt
    system = BetaTextBlockParam(
        type="text",
        text=f"{BROWSER_SYSTEM_PROMPT}{' ' + system_prompt_suffix if system_prompt_suffix else ''}",
    )

    while True:
        # Configure client and betas
        betas = [BROWSER_TOOLS_BETA_FLAG]
        enable_prompt_caching = False

        if provider == APIProvider.ANTHROPIC:
            client = Anthropic(api_key=api_key, max_retries=4)
            enable_prompt_caching = True
        elif provider == APIProvider.VERTEX:
            client = AnthropicVertex()
        elif provider == APIProvider.BEDROCK:
            client = AnthropicBedrock()
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        if enable_prompt_caching:
            betas.append(PROMPT_CACHING_BETA_FLAG)
            # Add cache control to system prompt
            system = BetaTextBlockParam(
                type="text",
                text=system["text"],
                cache_control=BetaCacheControlEphemeralParam(type="ephemeral"),
            )

        # Take screenshot if needed
        screenshot_base64 = None
        if only_n_most_recent_images:
            # Ensure browser is initialized and page is ready before screenshot
            await tool_collection.tool_map["browser"]._ensure_browser()

            # Wait a moment for any pending navigation to complete
            import asyncio
            await asyncio.sleep(0.5)

            screenshot_result = await tool_collection.tool_map["browser"](
                action="screenshot"
            )
            if screenshot_result and screenshot_result.base64_image:
                screenshot_base64 = screenshot_result.base64_image
        # Filter recent images
        if only_n_most_recent_images:
            _maybe_filter_to_n_most_recent_images(messages, only_n_most_recent_images)

            if screenshot_base64:
                # Add screenshot to the last user message if it exists, otherwise create new message
                screenshot_block = BetaImageBlockParam(
                    type="image",
                    source={
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screenshot_base64,
                    }
                )

                if messages and messages[-1]["role"] == "user":
                    # Append to existing user message
                    last_content = messages[-1]["content"]
                    if isinstance(last_content, str):
                        messages[-1]["content"] = [
                            BetaTextBlockParam(type="text", text=last_content),
                            screenshot_block
                        ]
                    elif isinstance(last_content, list):
                        messages[-1]["content"].append(screenshot_block)
                else:
                    # Create new user message with just the screenshot
                    messages.append({
                        "role": "user",
                        "content": [screenshot_block]
                    })

        # Make API call
        try:
            response = client.beta.messages.create(
                max_tokens=max_tokens,
                messages=messages,
                model=model,
                system=[system],
                tools=tool_collection.to_params(),
                betas=betas,
            )
        except Exception as e:
            api_response_callback(None, None, e)
            raise e

        api_response_callback(None, response, None)

        # Process response
        assistant_message = BetaMessageParam(
            role="assistant",
            content=[]
        )

        for content_block in response.content:
            if content_block.type == "text":
                output_callback({"type": "text", "text": content_block.text})
                assistant_message["content"].append(
                    {"type": "text", "text": content_block.text}
                )

            elif content_block.type == "tool_use":
                tool_use_id = content_block.id
                tool_name = content_block.name
                tool_input = content_block.input

                output_callback(content_block.model_dump())

                # Execute tool
                try:
                    tool = tool_collection.tool_map.get(tool_name)
                    if not tool:
                        raise ValueError(f"Unknown tool: {tool_name}")

                    result = await tool(**tool_input)
                    tool_output_callback(result, tool_use_id)

                    # Add tool use and result to message
                    assistant_message["content"].append(
                        BetaToolUseBlockParam(
                            type="tool_use",
                            id=tool_use_id,
                            name=tool_name,
                            input=tool_input
                        )
                    )

                    tool_result = BetaToolResultBlockParam(
                        type="tool_result",
                        tool_use_id=tool_use_id,
                        content=[]
                    )

                    if result.output:
                        tool_result["content"].append({
                            "type": "text",
                            "text": result.output
                        })
                    if result.base64_image:
                        tool_result["content"].append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": result.base64_image
                            }
                        })
                    if result.error:
                        tool_result["is_error"] = True
                        tool_result["content"].append({
                            "type": "text",
                            "text": f"Error: {result.error}"
                        })

                    messages.append({"role": "assistant", "content": [
                        BetaToolUseBlockParam(
                            type="tool_use",
                            id=tool_use_id,
                            name=tool_name,
                            input=tool_input
                        )
                    ]})
                    messages.append({"role": "user", "content": [tool_result]})

                except Exception as e:
                    error_result = BetaToolResultBlockParam(
                        type="tool_result",
                        tool_use_id=tool_use_id,
                        is_error=True,
                        content=[{"type": "text", "text": str(e)}]
                    )
                    messages.append({"role": "assistant", "content": [
                        BetaToolUseBlockParam(
                            type="tool_use",
                            id=tool_use_id,
                            name=tool_name,
                            input=tool_input
                        )
                    ]})
                    messages.append({"role": "user", "content": [error_result]})

        # Check if we need to continue
        if not any(block.type == "tool_use" for block in response.content):
            messages.append(assistant_message)
            return messages

def _maybe_filter_to_n_most_recent_images(
    messages: list[BetaMessageParam],
    images_to_keep: int,
    min_removal_threshold: int = 10,
):
    """
    Filter messages to keep only the N most recent images.
    """
    if images_to_keep <= 0:
        raise ValueError("images_to_keep must be > 0")

    total_images = sum(
        1
        for message in messages
        if message["role"] == "user"
        for block in message.get("content", [])
        if isinstance(block, dict) and block.get("type") == "image"
    )

    images_to_remove = total_images - images_to_keep
    if images_to_remove < min_removal_threshold:
        return

    images_removed = 0
    for message in messages:
        if message["role"] == "user" and isinstance(message.get("content"), list):
            new_content = []
            for block in message["content"]:
                if isinstance(block, dict) and block.get("type") == "image":
                    if images_removed < images_to_remove:
                        images_removed += 1
                        continue
                new_content.append(block)
            message["content"] = new_content