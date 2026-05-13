"""
Tool base class and collection.

Each tool is a class with three ClassVar attributes (`name`, `description`,
`input_schema`) and an `execute()` method. `to_param()` produces the
exact dict the Anthropic Messages API expects in its `tools=[...]` list, so
there is no server-side / beta-header magic: what you see here is what the
model sees.

`__init_subclass__` checks at import time that every property declared in
`input_schema` is also a keyword parameter of `execute()`, so schema and
implementation can't silently drift apart.
"""

import abc
import contextlib
import inspect
from typing import Any, ClassVar

from anthropic.types import ToolParam

from .result import ToolResult


class Tool(abc.ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    input_schema: ClassVar[dict[str, Any]]

    # Tools that dispatch on an `action` field validate inputs internally and
    # opt out of the signature check.
    validates_own_input: ClassVar[bool] = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls) or cls.validates_own_input:
            return
        props = set(cls.input_schema.get("properties", {}))
        required = set(cls.input_schema.get("required", []))
        params = inspect.signature(cls.execute).parameters
        execute_params = {k for k in params if k != "self"}
        missing = props - execute_params
        if missing:
            raise TypeError(
                f"{cls.__name__}.input_schema declares {sorted(missing)} but "
                f"execute() does not accept them"
            )
        for r in required:
            if params[r].default is not inspect.Parameter.empty:
                raise TypeError(
                    f"{cls.__name__}.input_schema marks {r!r} required but "
                    f"execute() gives it a default"
                )

    @classmethod
    def to_param(cls) -> ToolParam:
        return {
            "name": cls.name,
            "description": cls.description,
            "input_schema": cls.input_schema,
        }

    @abc.abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult: ...


class ToolCollection:
    """Maps tool name -> instance and dispatches calls."""

    def __init__(self, *tools: Tool) -> None:
        self._tools: dict[str, Tool] = {t.name: t for t in tools}

    def __iter__(self):
        return iter(self._tools.values())

    def __getitem__(self, name: str) -> Tool:
        return self._tools[name]

    def to_params(self, *, hosted_computer: bool = False) -> list[Any]:
        params: list[Any] = []
        for t in self._tools.values():
            hosted = getattr(t, "to_hosted_param", None)
            if hosted_computer and t.name == "computer" and callable(hosted):
                params.append(hosted())
            else:
                params.append(t.to_param())
        return params

    def close(self) -> None:
        """Release any resources held by tools (e.g. the Playwright browser).
        Safe to call multiple times; individual tool failures are swallowed so
        one bad close() doesn't prevent the rest from running."""
        for tool in self._tools.values():
            close = getattr(tool, "close", None)
            if callable(close):
                with contextlib.suppress(Exception):
                    close()

    def run(self, name: str, tool_input: object) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(error=f"Unknown tool: {name}")
        if not isinstance(tool_input, dict):
            return ToolResult(
                error=f"tool input must be an object, got {type(tool_input).__name__}"
            )
        try:
            return tool.execute(**tool_input)
        except Exception as e:
            return ToolResult(error=f"{type(e).__name__}: {e}")
