"""
Singularity — Dynamic Tool Registry (Fáze 16).

Runtime registration of callable tools — both in-process async handlers and
HTTP-callback tools (webhook-style). Registered tools are available for
injection into SingularityCore and for direct invocation via the REST API.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

import structlog

log = structlog.get_logger()

_NAME_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


def _validate_name(name: str) -> None:
    if not name or not all(c in _NAME_CHARS for c in name):
        raise ValueError(
            f"Tool name must contain only alphanumeric chars, underscores, or hyphens: {name!r}"
        )


@dataclass
class ToolDefinition:
    name: str
    description: str
    params_schema: dict
    handler: Callable[..., Awaitable[Any]]
    tool_type: str = "internal"  # "internal" | "http"
    callback_url: str = ""

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "description": self.description,
            "params_schema": self.params_schema,
            "tool_type": self.tool_type,
        }
        if self.callback_url:
            d["callback_url"] = self.callback_url
        return d


class ToolRegistry:
    """
    Thread-safe registry for async callable tools.

    Usage:
        registry.register("my_tool", "Does X", schema, async_handler)
        registry.register_http("remote_tool", "Does Y", schema, "https://...")
        result = await registry.invoke("my_tool", arg1=val1)
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._lock = threading.Lock()

    def register(
        self,
        name: str,
        description: str,
        params_schema: dict,
        handler: Callable[..., Awaitable[Any]],
    ) -> None:
        """Register an in-process async handler as a tool."""
        _validate_name(name)
        with self._lock:
            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                params_schema=params_schema,
                handler=handler,
                tool_type="internal",
            )
        log.info("tool_registered", name=name, tool_type="internal")

    def register_http(
        self,
        name: str,
        description: str,
        params_schema: dict,
        callback_url: str,
    ) -> None:
        """Register an HTTP-callback tool: invocation POSTs kwargs as JSON to callback_url."""
        _validate_name(name)
        if not callback_url:
            raise ValueError("callback_url must not be empty for http tools")
        _url = callback_url  # captured in closure

        async def _http_handler(**kwargs: Any) -> Any:
            import httpx  # lazy import to keep startup fast

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(_url, json=kwargs)
                resp.raise_for_status()
                return resp.json()

        with self._lock:
            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                params_schema=params_schema,
                handler=_http_handler,
                tool_type="http",
                callback_url=callback_url,
            )
        log.info("tool_registered", name=name, tool_type="http", callback_url=callback_url)

    def unregister(self, name: str) -> bool:
        """Remove a tool. Returns False if the name was not registered."""
        with self._lock:
            if name not in self._tools:
                return False
            del self._tools[name]
        log.info("tool_unregistered", name=name)
        return True

    async def invoke(self, name: str, **kwargs: Any) -> Any:
        """Invoke a registered tool by name. Raises KeyError if not found."""
        with self._lock:
            tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"No tool registered: {name!r}")
        log.info("tool_invoked", name=name, param_keys=sorted(kwargs.keys()))
        return await tool.handler(**kwargs)

    def get_tool(self, name: str) -> ToolDefinition | None:
        with self._lock:
            return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        with self._lock:
            return [t.to_dict() for t in self._tools.values()]

    def tool_count(self) -> int:
        with self._lock:
            return len(self._tools)
