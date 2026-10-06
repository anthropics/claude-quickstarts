"""Tests for _maybe_filter_to_n_most_recent_images.

These regression tests cover the bug fixed in
https://github.com/anthropics/claude-quickstarts/issues/415 — namely that
screenshots in this demo are nested inside ``tool_result.content`` blocks,
not at the top level of user messages, so the filter must descend into
``tool_result`` blocks to find and remove them.
"""

from copy import deepcopy

from browser_use_demo.loop import _maybe_filter_to_n_most_recent_images


def _make_tool_result(tool_use_id: str, *, with_image: bool) -> dict:
    """Build a tool_result block in the shape the sampling loop produces."""
    content: list[dict] = [{"type": "text", "text": f"result for {tool_use_id}"}]
    if with_image:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": "iVBORw0KGgo=",  # 1px PNG, truncated
                },
            }
        )
    return {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}


def _conversation_with_n_screenshots(n: int) -> list[dict]:
    """Build a conversation of N user turns, each containing one tool_result screenshot."""
    messages: list[dict] = []
    for i in range(n):
        messages.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": f"tool_{i}",
                        "name": "browser",
                        "input": {"action": "screenshot"},
                    }
                ],
            }
        )
        messages.append(
            {
                "role": "user",
                "content": [_make_tool_result(f"tool_{i}", with_image=True)],
            }
        )
    return messages


def _count_images(messages: list[dict]) -> int:
    """Count images nested inside tool_result.content blocks."""
    total = 0
    for message in messages:
        if not isinstance(message.get("content"), list):
            continue
        for block in message["content"]:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            for inner in block.get("content", []):
                if isinstance(inner, dict) and inner.get("type") == "image":
                    total += 1
    return total


class TestFilterToolResultImages:
    """The filter must descend into tool_result blocks (issue #415)."""

    def test_keeps_n_most_recent_when_above_threshold(self):
        """With 20 screenshots, keep_n=3, min_removal_threshold=10 → 10 removed in one chunk, 10 kept."""
        messages = _conversation_with_n_screenshots(20)
        assert _count_images(messages) == 20

        _maybe_filter_to_n_most_recent_images(
            messages, images_to_keep=3, min_removal_threshold=10
        )

        # We requested keep=3, but the chunk-rounding rule rounds the number to
        # remove down to a multiple of min_removal_threshold (10). So
        # images_to_remove = 20 - 3 = 17, rounded to 10 → 10 kept.
        # This is the documented cache-friendly behavior, lifted verbatim from
        # computer-use-demo.
        assert _count_images(messages) == 10

    def test_removes_oldest_first(self):
        """When images are removed, the most recent ones must be kept."""
        messages = _conversation_with_n_screenshots(15)
        # Tag each image with its sequence number for identity-checking after the filter.
        seq = 0
        for message in messages:
            if not isinstance(message.get("content"), list):
                continue
            for block in message["content"]:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                for inner in block.get("content", []):
                    if isinstance(inner, dict) and inner.get("type") == "image":
                        inner["_seq"] = seq
                        seq += 1
        assert seq == 15

        _maybe_filter_to_n_most_recent_images(
            messages, images_to_keep=3, min_removal_threshold=10
        )

        # 15 - 3 = 12, rounded down to 10 → first 10 removed, last 5 kept.
        surviving_seqs = []
        for message in messages:
            if not isinstance(message.get("content"), list):
                continue
            for block in message["content"]:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                for inner in block.get("content", []):
                    if isinstance(inner, dict) and inner.get("type") == "image":
                        surviving_seqs.append(inner["_seq"])
        assert surviving_seqs == [10, 11, 12, 13, 14]

    def test_no_op_when_below_chunk_threshold(self):
        """Removals smaller than min_removal_threshold should not happen (cache friendly)."""
        messages = _conversation_with_n_screenshots(5)
        snapshot = deepcopy(messages)

        _maybe_filter_to_n_most_recent_images(
            messages, images_to_keep=3, min_removal_threshold=10
        )

        # 5 - 3 = 2 to remove, rounded to multiple of 10 → 0 removed.
        assert _count_images(messages) == 5
        assert messages == snapshot

    def test_only_touches_image_blocks(self):
        """Text blocks inside tool_result must be preserved."""
        messages = _conversation_with_n_screenshots(15)

        _maybe_filter_to_n_most_recent_images(
            messages, images_to_keep=3, min_removal_threshold=10
        )

        text_blocks = 0
        for message in messages:
            if not isinstance(message.get("content"), list):
                continue
            for block in message["content"]:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                for inner in block.get("content", []):
                    if isinstance(inner, dict) and inner.get("type") == "text":
                        text_blocks += 1
        # One text block per user turn — none removed.
        assert text_blocks == 15

    def test_top_level_image_blocks_are_not_touched(self):
        """Regression for the original buggy implementation, which scanned top-level
        image blocks in user messages. The fixed implementation must only descend
        into tool_result blocks and leave any free-standing image alone."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "look at this attachment"},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": "abc=",
                        },
                    },
                ],
            }
        ]
        snapshot = deepcopy(messages)

        _maybe_filter_to_n_most_recent_images(
            messages, images_to_keep=0, min_removal_threshold=1
        )

        assert messages == snapshot
