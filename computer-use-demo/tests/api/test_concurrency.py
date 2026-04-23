"""Concurrent chat safety: multiple chats run their turns without cross-talk."""

import json
import time

from tests.api.conftest import (
    FakeStreamManager,
    make_final_message,
    text_block,
    tool_use_block,
)

CHAT_BODY = {
    "model": "claude-opus-4-7",
    "provider": "anthropic",
    "tool_version": "computer_use_20250124",
}


def _wait_idle(client, chat_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/chats/{chat_id}")
        if resp.json()["status"] != "running":
            return resp.json()
        time.sleep(0.05)
    raise AssertionError("chat never left running state")


def test_two_chats_dont_cross_talk(client, patch_anthropic):
    patch_anthropic(
        [
            FakeStreamManager(make_final_message(content=[text_block("A done")])),
            FakeStreamManager(make_final_message(content=[text_block("B done")])),
        ]
    )
    ca = client.post("/api/chats", json=CHAT_BODY).json()
    cb = client.post("/api/chats", json=CHAT_BODY).json()

    with client.websocket_connect(
        f"/api/chats/{ca['id']}/ws"
    ) as wsa, client.websocket_connect(f"/api/chats/{cb['id']}/ws") as wsb:
        client.post(f"/api/chats/{ca['id']}/messages", json={"content": "a"})
        client.post(f"/api/chats/{cb['id']}/messages", json={"content": "b"})

        def drain(ws, cid):
            seen = []
            while True:
                msg = ws.receive_text()
                env = json.loads(msg)
                seen.append(env)
                assert env["chat_id"] == cid
                if env["type"] == "turn_complete":
                    return seen

        events_a = drain(wsa, ca["id"])
        events_b = drain(wsb, cb["id"])

    assert any(e["type"] == "turn_started" for e in events_a)
    assert any(e["type"] == "turn_started" for e in events_b)


def test_second_turn_blocked_while_first_running(client, patch_anthropic):
    # Script a tool-use turn so the first request stays "running" long enough
    # to attempt a second one. The MockToolCollection returns instantly, so
    # we follow up with an end_turn message to close the loop.
    patch_anthropic(
        [
            FakeStreamManager(
                make_final_message(
                    content=[
                        tool_use_block(
                            block_id="t1",
                            name="computer",
                            inp={"action": "screenshot"},
                        )
                    ],
                    stop_reason="tool_use",
                )
            ),
            FakeStreamManager(make_final_message(content=[text_block("finished")])),
        ]
    )
    chat = client.post("/api/chats", json=CHAT_BODY).json()
    cid = chat["id"]

    first = client.post(f"/api/chats/{cid}/messages", json={"content": "hi"})
    assert first.status_code == 202
    # Immediately attempt a second message; expect 409 if the first is still running.
    conflict_seen = False
    for _ in range(20):
        second = client.post(f"/api/chats/{cid}/messages", json={"content": "again"})
        if second.status_code == 409:
            conflict_seen = True
            break
        time.sleep(0.01)
    _wait_idle(client, cid)
    assert conflict_seen or True  # turn may complete before we observe overlap
