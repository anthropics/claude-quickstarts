"""Test for the _maybe_filter_to_n_most_recent_images function."""

from typing import cast

from anthropic.types.beta import BetaMessageParam


def test_filter_image_count():
    """Test that the function returns the expected number of images."""
    from computer_use_demo.loop import _maybe_filter_to_n_most_recent_images

    # Create minimal message structure with 3 images
    messages = cast(
        list[BetaMessageParam],
        [
            {
                "role": "user",
                "content": [{"type": "tool_result", "content": [{"type": "image"}]}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "content": [{"type": "image"}]}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "content": [{"type": "image"}]}],
            },
        ],
    )

    # Filter to keep only 2 most recent images
    _maybe_filter_to_n_most_recent_images(
        messages, images_to_keep=2, min_removal_threshold=1
    )

    # Count remaining images
    image_count = sum(
        1
        for message in messages
        for block in (
            message["content"] if isinstance(message["content"], list) else []
        )
        for content in block.get("content", [])
        if isinstance(content, dict) and content.get("type") == "image"
    )

    # Verify count
    assert image_count == 2
