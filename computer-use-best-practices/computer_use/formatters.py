"""
Message-history transformations applied before each API call.

The interesting one is `StripImagesAtIntervals`. Naively keeping "the last N"
screenshots means that on every turn past N a *different* old image gets
replaced (so the byte prefix of the request changes) and the prompt cache
misses. The interval scheme instead lets the kept-count climb from
`min_images` to `min_images + interval - 1` and then drop back, so for
`interval` consecutive turns the *same* oldest images map to the *same*
placeholder text and the cache prefix is stable. You pay one cache write every
`interval` turns instead of every turn.
"""

import json
import sys
from typing import Any

from anthropic.types import MessageParam, TextBlockParam

_PLACEHOLDER: TextBlockParam = {"type": "text", "text": "[Image Omitted]"}


def _image_slots(messages: list[MessageParam]) -> list[tuple[list[Any], int]]:
    """Return (container, index) for every image block inside tool_result content,
    in document order, so callers can replace them in place."""
    slots: list[tuple[list[Any], int]] = []
    for msg in messages:
        content = msg["content"]
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            inner = block.get("content")
            if not isinstance(inner, list):
                continue
            for i, sub in enumerate(inner):
                if isinstance(sub, dict) and sub.get("type") == "image":
                    slots.append((inner, i))
    return slots


class StripOldestImages:
    """Keep only the most recent `keep` images. Simple but cache-hostile."""

    def __init__(self, keep: int) -> None:
        self.keep = keep

    def __call__(self, messages: list[MessageParam]) -> None:
        slots = _image_slots(messages)
        for container, i in slots[: max(len(slots) - self.keep, 0)]:
            container[i] = dict(_PLACEHOLDER)


class StripImagesAtIntervals:
    """Cache-friendly image bounding.

    Keeps ``(total % interval) + min_images`` images. As new
    screenshots arrive the kept-count steps 3, 4, …, 3+interval-1, 3, 4, … so
    the set of *removed* images (and therefore the serialized request prefix)
    only changes once every `interval` turns.
    """

    def __init__(self, min_images: int, interval: int, max_message_mb: float | None = None) -> None:
        self.min_images = min_images
        self.interval = interval
        self.max_message_mb = max_message_mb
        self._offset = 0

    def __call__(self, messages: list[MessageParam]) -> None:
        slots = _image_slots(messages)
        total = len(slots)
        self._offset = max(0, min(self._offset, total))
        keep = ((total - self._offset) % self.interval) + self.min_images
        if total > keep:
            for container, i in slots[: total - keep]:
                container[i] = dict(_PLACEHOLDER)
        if self.max_message_mb is None:
            return
        mb = len(json.dumps(messages, default=str)) / 1_000_000
        if mb <= self.max_message_mb:
            return
        print(
            f"[formatters] serialized request {mb:.1f} MB exceeds "
            f"{self.max_message_mb} MB cap; force-pruning to {self.min_images} image(s) "
            f"and resetting interval cycle.",
            file=sys.stderr,
        )
        slots = _image_slots(messages)
        for container, i in slots[: max(len(slots) - self.min_images, 0)]:
            container[i] = dict(_PLACEHOLDER)
        # _offset must reflect the *post*-prune image count so the next call's
        # `(total - _offset) % interval` starts a fresh cycle from min_images.
        self._offset = min(len(slots), self.min_images)
