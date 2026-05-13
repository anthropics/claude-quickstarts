"""
Uniform tool result container.

A tool returns at most one text payload and at most one image. The batch tools
compose multiple ToolResults and override `to_api_content` to interleave them.
"""

from dataclasses import dataclass, field
from typing import Any

from anthropic.types import DocumentBlockParam, ImageBlockParam, TextBlockParam

ContentBlockParam = TextBlockParam | ImageBlockParam | DocumentBlockParam


def image_block(b64_jpeg: str) -> ImageBlockParam:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_jpeg},
    }


def document_block(b64_pdf: str) -> DocumentBlockParam:
    return {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": b64_pdf},
    }


# The API rejects non-text blocks inside a tool_result with is_error=true; emit
# this placeholder instead so the model still knows the content was produced.
MEDIA_OMITTED_ON_ERROR = "[Media Omitted due to error]"
IMAGE_OMITTED_ON_ERROR = MEDIA_OMITTED_ON_ERROR


@dataclass
class ToolResult:
    output: str | None = None
    base64_image: str | None = None
    base64_pdf: str | None = None
    error: str | None = None
    # Free-form metadata surfaced to the debug UI (e.g. coordinate-scale info).
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def is_error(self) -> bool:
        return self.error is not None

    def to_api_content(self) -> list[ContentBlockParam]:
        """Render as a list of tool_result content blocks."""
        blocks: list[ContentBlockParam] = []
        text = self.error if self.is_error else self.output
        if text:
            blocks.append({"type": "text", "text": text})
        for media, builder in ((self.base64_image, image_block), (self.base64_pdf, document_block)):
            if media:
                blocks.append(
                    {"type": "text", "text": MEDIA_OMITTED_ON_ERROR}
                    if self.is_error
                    else builder(media)
                )
        if not blocks:
            blocks.append({"type": "text", "text": "(no output)"})
        return blocks
