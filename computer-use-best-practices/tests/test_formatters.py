import copy
from typing import Any

from anthropic.types import ImageBlockParam, MessageParam

from computer_use.formatters import StripImagesAtIntervals, StripOldestImages


def _img(tag: str) -> ImageBlockParam:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": tag},
    }


def _msgs(n: int) -> list[MessageParam]:
    return [
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": str(i), "content": [_img(str(i))]}],
        }
        for i in range(n)
    ]


def _inner_contents(msgs: list[MessageParam]) -> list[list[Any]]:
    """Return each tool_result's inner content list, in document order."""
    out: list[list[Any]] = []
    for m in msgs:
        content = m["content"]
        if not isinstance(content, list):
            continue
        for b in content:
            if isinstance(b, dict) and b["type"] == "tool_result":
                inner = b.get("content")
                if isinstance(inner, list):
                    out.append(inner)
    return out


def _surviving(msgs: list[MessageParam]) -> list[str]:
    out: list[str] = []
    for inner in _inner_contents(msgs):
        for sub in inner:
            if sub.get("type") == "image":
                out.append(sub["source"]["data"])
    return out


def test_simple_keeps_last_n():
    msgs = _msgs(5)
    StripOldestImages(keep=2)(msgs)
    assert _surviving(msgs) == ["3", "4"]


def test_interval_kept_count_cycles():
    f = StripImagesAtIntervals(min_images=3, interval=4)
    seen: list[int] = []
    for n in range(1, 12):
        msgs = _msgs(n)
        f(msgs)
        seen.append(len(_surviving(msgs)))
    # Nothing dropped until total > min; then kept-count cycles 3,4,5,6,3,4,5,6,…
    assert seen == [1, 2, 3, 3, 4, 5, 6, 3, 4, 5, 6]


def test_interval_prefix_stable_within_window():
    """Within one interval window, growing the history by one image must not
    change which earlier images were replaced; that is what keeps the prompt
    cache prefix identical."""
    f = StripImagesAtIntervals(min_images=3, interval=4)
    a = _msgs(9)
    f(a)
    b = _msgs(10)
    f(b)
    # Both runs replace exactly the first 5 images and keep the rest.
    assert _surviving(a) == ["5", "6", "7", "8"]
    assert _surviving(b) == ["5", "6", "7", "8", "9"]
    # And the first 9 messages serialize identically.
    assert a == b[:9]


def test_interval_replacement_is_text_block():
    f = StripImagesAtIntervals(min_images=1, interval=2)
    msgs = _msgs(5)
    f(msgs)
    first = _inner_contents(msgs)[0][0]
    assert first == {"type": "text", "text": "[Image Omitted]"}


def test_interval_noop_when_under_min():
    f = StripImagesAtIntervals(min_images=3, interval=4)
    msgs = _msgs(2)
    snapshot = copy.deepcopy(msgs)
    f(msgs)
    assert msgs == snapshot


def test_max_message_mb_force_prunes_and_resets_offset(capsys):
    msgs = _msgs(5)
    s = StripImagesAtIntervals(min_images=2, interval=10, max_message_mb=0.0005)
    s(msgs)
    # _offset is the post-prune surviving count so the cycle restarts cleanly.
    assert s._offset == 2
    remaining = sum(1 for c in _inner_contents(msgs) if c[0].get("type") == "image")
    assert remaining == 2
    assert "exceeds" in capsys.readouterr().err

    msgs2 = _msgs(8)
    StripImagesAtIntervals(min_images=2, interval=10, max_message_mb=10.0)(msgs2)
    remaining2 = sum(1 for c in _inner_contents(msgs2) if c[0].get("type") == "image")
    assert remaining2 == 8


def test_force_prune_then_cycle_resumes():
    """Regression: after a force-prune the kept-count must climb again
    (min, min+1, ...) rather than getting pinned at min_images forever."""
    s = StripImagesAtIntervals(min_images=2, interval=10, max_message_mb=0.0005)
    msgs = _msgs(5)
    s(msgs)  # force-prunes 5 -> 2
    assert len(_surviving(msgs)) == 2

    # Now relax the cap (cap was hit because images were huge; here we just
    # simulate "subsequent turns are under the cap") and add one image per turn.
    s.max_message_mb = None
    seen: list[int] = []
    for new in range(5, 12):
        msgs.append(
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": str(new), "content": [_img(str(new))]}
                ],
            }
        )
        s(msgs)
        seen.append(len(_surviving(msgs)))
    assert seen == [3, 4, 5, 6, 7, 8, 9]
