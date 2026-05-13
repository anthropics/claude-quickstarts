"""
Image sizing and encoding.

The API's vision encoder tiles images into 28x28 patches and caps both the long
edge (1568 px) and the total tile count (1568). If we send an image that
violates either, the server resizes it *again* before the model sees it, and
then the model emits click coordinates in a space we never observed, producing
systematic click drift (~14% on a 16:10 MacBook screen).

So: pre-resize every screenshot to the largest dimensions that satisfy *both*
constraints, and remember those dimensions to scale model coordinates back to
screen space.

`target_image_size` is a direct port of the API's reference algorithm.
"""

import base64
import io

from PIL import Image

from constants import cfg


class ScreenshotTooSmall(ValueError):
    pass


def n_tokens_for_px(px: int, px_per_token: int = cfg.px_per_token) -> int:
    """ceil(px / px_per_token) using integer math."""
    return (px - 1) // px_per_token + 1


def n_tokens_for_img(w: int, h: int, px_per_token: int = cfg.px_per_token) -> int:
    return n_tokens_for_px(w, px_per_token) * n_tokens_for_px(h, px_per_token)


def target_image_size(
    width: int,
    height: int,
    *,
    px_per_token: int = cfg.px_per_token,
    max_edge_px: int = cfg.max_edge_px,
    max_tokens: int = cfg.max_tokens,
) -> tuple[int, int]:
    """
    Largest (w, h) preserving aspect ratio with long-edge <= max_edge_px and
    tile-count <= max_tokens. Returns the input unchanged if already valid.
    """
    if (
        width <= max_edge_px
        and height <= max_edge_px
        and n_tokens_for_img(width, height, px_per_token) <= max_tokens
    ):
        return width, height

    # Normalize to landscape for the search; transpose result back.
    if height > width:
        w, h = target_image_size(
            height, width, px_per_token=px_per_token, max_edge_px=max_edge_px, max_tokens=max_tokens
        )
        return h, w

    aspect = width / height
    lo, hi = 1, width  # lo always valid, hi always invalid

    while True:
        if lo + 1 == hi:
            return lo, max(round(lo / aspect), 1)
        mid_w = (lo + hi) // 2
        mid_h = max(round(mid_w / aspect), 1)
        if mid_w <= max_edge_px and n_tokens_for_img(mid_w, mid_h, px_per_token) <= max_tokens:
            lo = mid_w
        else:
            hi = mid_w


def resize_and_encode(
    img: Image.Image, *, min_bytes: int = cfg.min_screenshot_bytes
) -> tuple[str, tuple[int, int]]:
    """
    Resize `img` to its target size (no-op if already within budget), encode as
    JPEG, and return (base64_string, (sent_width, sent_height)).

    `min_bytes` defaults to the screenshot sanity threshold; pass 0 when
    encoding arbitrary images (e.g. the editor `view` command) where a small
    file is legitimate rather than a sign of a failed capture.
    """
    tw, th = target_image_size(img.width, img.height)
    if (tw, th) != (img.width, img.height):
        img = img.resize((tw, th), Image.Resampling.LANCZOS)
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=cfg.jpeg_quality)
    data = buf.getvalue()
    if len(data) < min_bytes:
        raise ScreenshotTooSmall(
            f"Screenshot is {len(data)} bytes (< {min_bytes}). This usually "
            f"means Screen Recording permission is missing or the capture failed."
        )
    return base64.standard_b64encode(data).decode("ascii"), (tw, th)
