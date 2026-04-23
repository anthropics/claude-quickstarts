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


def _wait_idle(client, chat_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/chats/{chat_id}")
        if resp.json()["status"] != "running":
            return resp.json()
        time.sleep(0.05)
    raise AssertionError("chat never left running state")


def test_create_and_list_chat(client):
    resp = client.post("/api/chats", json={"title": "hi", **CHAT_BODY})
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "hi"
    assert body["status"] == "idle"
    assert body["message_count"] == 0

    lst = client.get("/api/chats").json()
    assert any(c["id"] == body["id"] for c in lst)


def test_get_chat_detail(client):
    created = client.post("/api/chats", json=CHAT_BODY).json()
    detail = client.get(f"/api/chats/{created['id']}").json()
    assert detail["id"] == created["id"]
    assert detail["messages"] == []


def test_send_message_completes_without_tools(client, patch_anthropic):
    patch_anthropic(
        [
            FakeStreamManager(
                make_final_message(content=[text_block("Hello!")]),
                events=[],
            )
        ]
    )
    chat = client.post("/api/chats", json=CHAT_BODY).json()
    resp = client.post(
        f"/api/chats/{chat['id']}/messages",
        json={"content": "hi there"},
    )
    assert resp.status_code == 202
    final = _wait_idle(client, chat["id"])
    assert final["status"] == "idle"
    roles = [m["role"] for m in final["messages"]]
    assert roles == ["user", "assistant"]
    # Regression: messages must serialise as `content`, not the DB-side alias.
    assert all("content" in m and "content_json" not in m for m in final["messages"])
    assert final["messages"][0]["content"] == [{"type": "text", "text": "hi there"}]


def test_delete_chat(client):
    created = client.post("/api/chats", json=CHAT_BODY).json()
    resp = client.delete(f"/api/chats/{created['id']}")
    assert resp.status_code == 204
    missing = client.get(f"/api/chats/{created['id']}")
    assert missing.status_code == 404


def test_send_message_without_api_key_fails(monkeypatch, client):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Also clear any file-stored key.
    from computer_use_demo.api.system.services import config_store

    config_store.set_api_key("")
    chat = client.post("/api/chats", json=CHAT_BODY).json()
    resp = client.post(f"/api/chats/{chat['id']}/messages", json={"content": "hi"})
    assert resp.status_code == 400
