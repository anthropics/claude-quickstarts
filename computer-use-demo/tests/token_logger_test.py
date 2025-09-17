"""
Tests for the token_logger module.

These tests verify that token usage tracking functions correctly.
"""

from unittest.mock import MagicMock

import httpx

from computer_use_demo.token_logger import (
    TokenUsage,
    analyze_message_payload,
    extract_token_usage_from_response,
    get_current_session,
    log_image_truncation,
    reset_session,
)


def test_token_usage_update_from_headers():
    """Test updating token counts from API response headers."""
    token_usage = TokenUsage(session_id="test-session")

    # Test with empty headers
    token_usage.update_from_headers({})
    assert token_usage.input_tokens == 0
    assert token_usage.output_tokens == 0

    # Test with valid headers
    headers = {
        "anthropic-input-tokens": "100",
        "anthropic-output-tokens": "50",
    }
    token_usage.update_from_headers(headers)
    assert token_usage.input_tokens == 100
    assert token_usage.output_tokens == 50
    assert token_usage.total_tokens == 150
    assert token_usage.request_count == 1

    # Test with additional request
    headers = {
        "anthropic-input-tokens": "200",
        "anthropic-output-tokens": "100",
    }
    token_usage.update_from_headers(headers)
    assert token_usage.input_tokens == 300
    assert token_usage.output_tokens == 150
    assert token_usage.total_tokens == 450
    assert token_usage.request_count == 2


def test_extract_token_usage_from_response():
    """Test extracting token usage from API response."""
    # Test with None response
    assert extract_token_usage_from_response(None) == {}

    # Test with response without headers
    response = MagicMock()
    delattr(response, "headers")
    assert extract_token_usage_from_response(response) == {}

    # Test with valid response
    response = httpx.Response(
        200,
        headers={
            "anthropic-input-tokens": "100",
            "anthropic-output-tokens": "50",
        },
    )
    token_usage = extract_token_usage_from_response(response)
    assert token_usage["input_tokens"] == 100
    assert token_usage["output_tokens"] == 50
    assert token_usage["total_tokens"] == 150


def test_analyze_message_payload():
    """Test analyzing message payload size and composition."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Hello, world!"},
                {"type": "image", "source": {"type": "base64", "data": "abc"}},
            ],
        },
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Hi there!"},
                {"type": "tool_use", "name": "test_tool", "input": {}},
            ],
        },
    ]

    analysis = analyze_message_payload(messages)
    assert analysis["message_count"] == 2
    assert analysis["text_blocks"] == 2
    assert analysis["image_blocks"] == 1
    assert analysis["tool_blocks"] == 1


def test_global_session_management():
    """Test global token usage session management."""
    # Reset the session
    reset_session()

    # Get the current session
    session = get_current_session()
    assert session.input_tokens == 0
    assert session.output_tokens == 0

    # Update the session
    headers = {
        "anthropic-input-tokens": "100",
        "anthropic-output-tokens": "50",
    }
    session.update_from_headers(headers)

    # Get the session again and verify it's the same session
    session2 = get_current_session()
    assert session2.input_tokens == 100
    assert session2.output_tokens == 50

    # Reset the session and verify it's reset
    reset_session()
    session3 = get_current_session()
    assert session3.input_tokens == 0
    assert session3.output_tokens == 0


def test_log_image_truncation():
    """Test logging image truncation."""
    # This function doesn't return anything, so we just call it to ensure it doesn't raise
    log_image_truncation(10, 5)

    # Get the current session and verify it's not affected
    session = get_current_session()
    assert session.input_tokens == 0
    assert session.output_tokens == 0
