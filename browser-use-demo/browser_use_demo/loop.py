"""
Sampling loop for browser automation with Claude
"""

import os
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Optional

import httpx

from anthropic import (
    Anthropic,
    AnthropicBedrock,
    AnthropicVertex,
)
from anthropic.types.beta import (
    BetaCacheControlEphemeralParam,
    BetaContentBlockParam,
    BetaMessageParam,
    BetaTextBlockParam,
)

from .message_handler import MessageBuilder, ResponseProcessor
from .tools import BrowserTool, ToolCollection, ToolResult

PROMPT_CACHING_BETA_FLAG = "prompt-caching-2024-07-31"


class APIProvider(StrEnum):
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    VERTEX = "vertex"


# Browser-specific system prompt
BROWSER_SYSTEM_PROMPT = f"""<SYSTEM_CAPABILITY>
* You control a Chromium browser via Playwright automation.
* The current date is {datetime.today().strftime("%A, %B %-d, %Y")}.
</SYSTEM_CAPABILITY>

<TOOL_GUIDANCE>
You receive a screenshot at the start of each turn. Look at it to see the current page - if you're already where you need to be, don't re-navigate.

After navigating to a new page, always call read_page to get element references (ref_1, ref_2, etc.) before interacting with the page. Use these refs with your interaction tools (click, type, hover, form_input, etc.). Refs are more reliable than coordinates.

When you need to extract or read text content from a page, always use get_page_text - don't try to read text from screenshots.

If DOM-based actions (refs) aren't working, fall back to screenshot + coordinate-based actions.
</TOOL_GUIDANCE>

<TIPS>
* Prefer get_page_text over scrolling when looking for information - it's faster and more reliable
* Use execute_js to extract data from JavaScript variables, localStorage, or trigger behaviors not accessible through clicks
* Use full URLs with https://
* Use wait for slow-loading pages
* Use scroll_to with a ref to reveal elements
* Use form_input with refs for form fields
* Use key for shortcuts (e.g., "ctrl+a")
* Close popups when they appear
* Verify actions succeeded before moving on
</TIPS>"""


async def sampling_loop(
    *,
    model: str,
    provider: APIProvider,
    system_prompt_suffix: str,
    messages: list[BetaMessageParam],
    output_callback: Callable[[BetaContentBlockParam], None],
    tool_output_callback: Callable[[ToolResult, str], None],
    api_response_callback: Callable[
        [httpx.Request | None, httpx.Response | object | None, Exception | None], None
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
        # Create browser tool with standard dimensions
        browser_tool = BrowserTool()

    tool_collection = ToolCollection(browser_tool)

    # Build system prompt
    system = BetaTextBlockParam(
        type="text",
        text=f"{BROWSER_SYSTEM_PROMPT}{' ' + system_prompt_suffix if system_prompt_suffix else ''}",
    )

    while True:
        # Configure client and betas
        betas = []
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

        # Make API call
        try:
            api_kwargs = {
                "max_tokens": max_tokens,
                "messages": messages,
                "model": model,
                "system": [system],
                "tools": tool_collection.to_params(),
            }
            # Only include betas if there are any (e.g., prompt caching)
            if betas:
                api_kwargs["betas"] = betas
                response = client.beta.messages.create(**api_kwargs)
            else:
                # Use regular messages API when no beta features are needed
                response = client.messages.create(**api_kwargs)
        except Exception as e:
            api_response_callback(None, None, e)
            raise e

        api_response_callback(None, response, None)

        # Process response using our new abstractions
        processor = ResponseProcessor()
        processed = processor.process_response(response)

        # Output all content blocks to callbacks
        for content_block in processed.assistant_content:
            output_callback(content_block)

        # Build and append the complete assistant message (preserves text + tools)
        builder = MessageBuilder()
        builder.add_assistant_message(messages, processed.assistant_content)

        # Execute tools and collect results if there are any tool uses
        if processed.tool_uses:
            tool_results = await processor.execute_tools(
                processed.tool_uses,
                tool_collection,
                tool_output_callback
            )

            # Add all tool results as a single user message
            builder.add_tool_results(messages, tool_results)

            # Continue the loop to process any follow-up
        else:
            # No tools used, conversation can end here
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
