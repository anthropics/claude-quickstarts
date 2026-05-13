from typing import Any, ClassVar

from computer_use.tools.base import Tool
from computer_use.tools.batch import _batch_description, _batch_schema, _BatchResult, _BatchTool
from computer_use.tools.result import IMAGE_OMITTED_ON_ERROR, ToolResult


class _Fake(Tool):
    name = "fake"
    description = "x"
    validates_own_input = True
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"action": {"type": "string"}},
        "required": ["action"],
    }

    def execute(self, *, action: str, **_: Any) -> ToolResult:
        if action == "boom":
            return ToolResult(error="exploded")
        if action == "throw":
            raise KeyError("coordinate")
        if action == "shot":
            return ToolResult(base64_image="abc")
        return ToolResult(output=f"did {action}")


class FakeBatch(_BatchTool):
    name: ClassVar[str] = "fake_batch"
    description: ClassVar[str] = _batch_description("fake")
    input_schema: ClassVar[dict[str, Any]] = _batch_schema(_Fake.input_schema)

    def __init__(self, inner: _Fake) -> None:
        super().__init__(inner)


def test_batch_aggregates_and_interleaves_images():
    batch = FakeBatch(_Fake())
    res = batch.execute(actions=[{"action": "a"}, {"action": "shot"}, {"action": "b"}])
    types = [b["type"] for b in res.to_api_content()]
    assert types == ["text", "text", "image", "text"]
    assert not res.is_error


def test_batch_stops_on_error():
    batch = FakeBatch(_Fake())
    res = batch.execute(actions=[{"action": "a"}, {"action": "boom"}, {"action": "b"}])
    assert res.is_error
    assert res.error is not None
    assert "actions[1]" in res.error
    assert "1 skipped" in res.error
    assert all(b["type"] == "text" for b in res.to_api_content())


def test_batch_step_exception_keeps_prior_results():
    """An exception mid-batch is caught and reported; results from earlier
    steps (including images) survive."""
    batch = FakeBatch(_Fake())
    res = batch.execute(actions=[{"action": "shot"}, {"action": "throw"}, {"action": "b"}])
    assert res.is_error
    assert isinstance(res, _BatchResult)
    assert len(res._items) == 2
    assert res._items[0][1].base64_image == "abc"
    err = res._items[1][1].error
    assert err is not None and "KeyError" in err
    assert res.error is not None and "actions[1]" in res.error


def test_errored_batch_replaces_images_with_placeholder():
    """If any step errors, the batch is is_error=true and the API rejects image
    blocks in errored tool_results, so prior-step images become text placeholders."""
    batch = FakeBatch(_Fake())
    res = batch.execute(actions=[{"action": "shot"}, {"action": "boom"}])
    assert res.is_error
    content = res.to_api_content()
    assert all(b["type"] == "text" for b in content)
    texts = [b["text"] for b in content if b["type"] == "text"]
    assert IMAGE_OMITTED_ON_ERROR in texts
