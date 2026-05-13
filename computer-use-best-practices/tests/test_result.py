from computer_use.tools.result import IMAGE_OMITTED_ON_ERROR, ToolResult


def test_errored_result_replaces_image_with_placeholder():
    r = ToolResult(error="boom", base64_image="abc")
    content = r.to_api_content()
    assert all(b["type"] == "text" for b in content)
    texts = [b["text"] for b in content if b["type"] == "text"]
    assert "boom" in texts
    assert IMAGE_OMITTED_ON_ERROR in texts


def test_ok_result_emits_image():
    r = ToolResult(output="ok", base64_image="abc")
    types = [b["type"] for b in r.to_api_content()]
    assert types == ["text", "image"]
