def test_get_system_info(client):
    resp = client.get("/api/system")
    assert resp.status_code == 200
    body = resp.json()
    assert "anthropic" in body["providers"]
    assert body["default_provider"]
    assert body["models"]
    assert body["tool_versions"]


def test_api_key_roundtrip(client):
    put = client.put("/api/system/api-key", json={"api_key": "sk-test"})
    assert put.status_code == 200
    assert put.json() == {"has_key": True}
    got = client.get("/api/system/api-key")
    assert got.json() == {"has_key": True}


def test_base_url_roundtrip(client):
    put = client.put(
        "/api/system/base-url", json={"base_url": "https://proxy.example.com"}
    )
    assert put.status_code == 200
    assert put.json() == {"base_url": "https://proxy.example.com"}
    got = client.get("/api/system/base-url")
    assert got.json() == {"base_url": "https://proxy.example.com"}


def test_system_prompt_roundtrip(client):
    put = client.put("/api/system/system-prompt", json={"suffix": "be brief"})
    assert put.status_code == 200
    assert put.json()["suffix"] == "be brief"
    got = client.get("/api/system/system-prompt")
    assert got.json()["suffix"] == "be brief"
