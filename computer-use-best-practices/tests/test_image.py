import random

import pytest
from PIL import Image

from computer_use.image import (
    ScreenshotTooSmall,
    n_tokens_for_img,
    resize_and_encode,
    target_image_size,
)
from constants import cfg


def _valid(w: int, h: int) -> bool:
    return (
        w <= cfg.max_edge_px and h <= cfg.max_edge_px and n_tokens_for_img(w, h) <= cfg.max_tokens
    )


def test_small_image_unchanged():
    assert target_image_size(800, 600) == (800, 600)


def test_long_edge_only_is_insufficient():
    # 1568x1014 has long-edge == cap but 56*37 = 2072 tokens > 1568.
    w, h = target_image_size(1568, 1014)
    assert (w, h) != (1568, 1014)
    assert _valid(w, h)
    # binary search returns the largest valid width; bumping by 1 must overflow
    assert not _valid(w + 1, round((w + 1) * 1014 / 1568))


def test_retina_mbp():
    w, h = target_image_size(3456, 2234)
    assert _valid(w, h)
    assert abs(w / h - 3456 / 2234) < 0.01


def test_portrait_transposed():
    lw, lh = target_image_size(3000, 2000)
    pw, ph = target_image_size(2000, 3000)
    assert (pw, ph) == (lh, lw)


def test_square():
    w, h = target_image_size(4000, 4000)
    assert w == h
    assert _valid(w, h)


def test_screenshot_too_small():
    # A degenerate capture (tiny solid color) encodes below the threshold.
    tiny = Image.new("RGB", (2, 2), (0, 0, 0))
    with pytest.raises(ScreenshotTooSmall) as exc:
        resize_and_encode(tiny)
    assert str(cfg.min_screenshot_bytes) in str(exc.value)

    # A realistic 800x600 capture with content is well above it.
    rng = random.Random(0)
    noise = Image.new("RGB", (800, 600))
    noise.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(800 * 600)]
    )
    b64, _ = resize_and_encode(noise)
    assert len(b64) > cfg.min_screenshot_bytes


@pytest.mark.parametrize("field", ["width", "height", "px_per_token", "max_edge_px", "max_tokens"])
@pytest.mark.parametrize("value", [0, -1])
def test_nonpositive_dimensions_and_limits_are_rejected(field: str, value: int) -> None:
    params = {
        "width": 800,
        "height": 600,
        "px_per_token": 28,
        "max_edge_px": 1568,
        "max_tokens": 1568,
    }
    params[field] = value
    with pytest.raises(ValueError, match="positive"):
        target_image_size(**params)


def test_impossible_one_pixel_budget_terminates() -> None:
    import subprocess
    import sys

    program = """from computer_use.image import target_image_size
try:
    target_image_size(1, 1, max_tokens=0)
except ValueError:
    pass
else:
    raise AssertionError('expected ValueError for an impossible budget')
"""
    subprocess.run([sys.executable, "-c", program], check=True, timeout=5)


def test_one_pixel_budget_remains_valid() -> None:
    assert target_image_size(1, 1, px_per_token=1, max_edge_px=1, max_tokens=1) == (1, 1)
