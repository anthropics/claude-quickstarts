import json
import time

from tests.api.conftest import (
    FakeStreamManager,
    make_final_message,
    text_block,
)

CHAT_BODY = {
    "model": "claude-opus-4-7",
    "provider": "anthropic",
    "tool_version": "computer_use_20250124",
}


def _drain_until(websocket, predicate, *, timeout=5.0):
    deadline = time.time() + timeout
    events = []
    while time.time() < deadline:
        msg = websocket.receive_text()
        env = json.loads(msg)
        events.append(env)
        if predicate(env):
            return events
    raise AssertionError(f"predicate never matched; saw: {[e['type'] for e in events]}")


def test_ws_streams_turn_events(client, patch_anthropic):
    patch_anthropic(
        [
            FakeStreamManager(
                make_final_message(content=[text_block("Hi!")]),
                events=[],
            )
        ]
    )
    chat = client.post("/api/chats", json=CHAT_BODY).json()
    cid = chat["id"]

    with client.websocket_connect(f"/api/chats/{cid}/ws") as ws:
        client.post(f"/api/chats/{cid}/messages", json={"content": "hello"})
        events = _drain_until(ws, lambda e: e["type"] == "turn_complete")
        types = [e["type"] for e in events]
        assert "turn_started" in types
        assert "turn_complete" in types
        # Each envelope carries an increasing seq and the chat id.
        seqs = [e["seq"] for e in events]
        assert seqs == sorted(seqs)
        assert all(e["chat_id"] == cid for e in events)


def test_ws_replay_with_since_seq(client, patch_anthropic):
    patch_anthropic(
        [
            FakeStreamManager(
                make_final_message(content=[text_block("Done")]),
                events=[],
            )
        ]
    )
    chat = client.post("/api/chats", json=CHAT_BODY).json()
    cid = chat["id"]

    # First subscriber sees the whole turn.
    with client.websocket_connect(f"/api/chats/{cid}/ws") as ws:
        client.post(f"/api/chats/{cid}/messages", json={"content": "hello"})
        first = _drain_until(ws, lambda e: e["type"] == "turn_complete")

    max_seq = max(e["seq"] for e in first)
    # Reconnect with since_seq at the midpoint — should replay the remaining events.
    mid = first[len(first) // 2]["seq"]
    with client.websocket_connect(f"/api/chats/{cid}/ws?since_seq={mid}") as ws:
        # Immediately after accept, replay arrives. Collect available frames.
        replay = []
        while True:
            try:
                msg = ws.receive_text(timeout=0.5)
            except Exception:
                break
            replay.append(json.loads(msg))
            if replay and replay[-1]["seq"] >= max_seq:
                break
    assert all(e["seq"] > mid for e in replay)
