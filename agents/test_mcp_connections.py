"""Offline MCP transport and agent dispatch regression tests."""

import asyncio
import json
import unittest
from contextlib import AsyncExitStack
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from anthropic.types import TextBlock, ToolUseBlock

from .agent import Agent
from .parallel_search import PARALLEL_SEARCH_SERVER
from .tools.think import ThinkTool
from .utils.connections import (
    MCPConnectionSSE,
    MCPConnectionStdio,
    MCPConnectionStreamableHTTP,
    create_mcp_connection,
    setup_mcp_connections,
)


class HTTPServerFixture:
    """Serve MCP JSON-RPC responses while recording actual HTTP requests."""

    def __init__(self):
        self.requests = []
        self.clients = []
        self.async_client = httpx.AsyncClient

    def handle(self, request):
        self.requests.append(request)
        if request.method == "GET":
            return httpx.Response(405)
        body = json.loads(request.content)
        if "id" not in body:
            return httpx.Response(202)
        method = body["method"]
        if method == "initialize":
            result = {
                "protocolVersion": body["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "test-search", "version": "1"},
            }
        elif method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": "web_search",
                        "description": "Search the web",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "objective": {"type": "string"},
                            },
                            "required": ["objective"],
                        },
                    }
                ]
            }
        elif method == "tools/call":
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": "TaskGroup waits for its tasks: https://docs.python.org/3/library/asyncio-task.html",
                    }
                ]
            }
        else:
            raise AssertionError(f"Unexpected MCP method: {method}")
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": result,
            },
        )

    def client(self, **kwargs):
        client = self.async_client(transport=httpx.MockTransport(self.handle), **kwargs)
        self.clients.append(client)
        return client


class MCPConnectionTests(unittest.IsolatedAsyncioTestCase):
    def test_factory_preserves_existing_transports(self):
        self.assertIsInstance(
            create_mcp_connection({"command": "python"}), MCPConnectionStdio
        )
        self.assertIsInstance(
            create_mcp_connection({"type": "sse", "url": "https://example.com"}),
            MCPConnectionSSE,
        )
        self.assertIsInstance(
            create_mcp_connection(PARALLEL_SEARCH_SERVER), MCPConnectionStreamableHTTP
        )
        with self.assertRaisesRegex(ValueError, "URL is required"):
            create_mcp_connection({"type": "streamable_http"})
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            create_mcp_connection({"type": "unknown"})

    async def test_stdio_and_sse_arguments_are_preserved(self):
        config = {"command": "python", "args": ["server.py"], "env": {"TEST": "1"}}
        connection = create_mcp_connection(config)
        with patch("agents.utils.connections.stdio_client") as transport:
            await connection._create_rw_context()
            params = transport.call_args.args[0]
            self.assertEqual(
                (params.command, params.args, params.env),
                ("python", ["server.py"], {"TEST": "1"}),
            )
        connection = create_mcp_connection(
            {
                "type": "sse",
                "url": "https://example.com/sse",
                "headers": {"X-Test": "value"},
            }
        )
        with patch("agents.utils.connections.sse_client") as transport:
            await connection._create_rw_context()
            transport.assert_called_once_with(
                url="https://example.com/sse", headers={"X-Test": "value"}
            )

    async def test_loader_executes_tool_and_closes_http_client(self):
        server = HTTPServerFixture()
        with patch(
            "agents.utils.connections.httpx.AsyncClient", side_effect=server.client
        ):
            async with AsyncExitStack() as stack:
                tools = await setup_mcp_connections([PARALLEL_SEARCH_SERVER], stack)
                self.assertEqual([tool.name for tool in tools], ["web_search"])
                result = await tools[0].execute(objective="TaskGroup documentation")
                self.assertIn("https://docs.python.org", result)
                connection = tools[0].connection
        self.assertIsNone(connection.session)
        self.assertTrue(all(client.is_closed for client in server.clients))
        methods = []
        for request in server.requests:
            self.assertEqual(str(request.url), PARALLEL_SEARCH_SERVER["url"])
            self.assertEqual(request.headers["User-Agent"], "claude-quickstarts/agents")
            self.assertNotIn("Authorization", request.headers)
            if request.content:
                methods.append(json.loads(request.content)["method"])
        self.assertIn("initialize", methods)
        self.assertIn("tools/list", methods)
        self.assertIn("tools/call", methods)

    async def test_cancellation_closes_transport(self):
        server = HTTPServerFixture()
        connection = create_mcp_connection(PARALLEL_SEARCH_SERVER)
        with (
            patch(
                "agents.utils.connections.httpx.AsyncClient", side_effect=server.client
            ),
            self.assertRaises(asyncio.CancelledError),
        ):
            async with connection:
                raise asyncio.CancelledError()
        self.assertIsNone(connection.session)
        self.assertIsNone(connection._rw_ctx)
        self.assertTrue(all(client.is_closed for client in server.clients))

    async def test_failed_initialization_closes_transport(self):
        server = HTTPServerFixture()
        connection = create_mcp_connection(PARALLEL_SEARCH_SERVER)
        with (
            patch(
                "agents.utils.connections.httpx.AsyncClient", side_effect=server.client
            ),
            patch(
                "agents.utils.connections.ClientSession.initialize",
                side_effect=RuntimeError("initialization failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "initialization failed"),
        ):
            await connection.__aenter__()
        self.assertIsNone(connection.session)
        self.assertTrue(all(client.is_closed for client in server.clients))

    async def test_agent_loop_dispatches_loaded_tool_and_restores_local_tools(self):
        server = HTTPServerFixture()
        calls = []

        def create(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                self.assertIn("web_search", [tool["name"] for tool in kwargs["tools"]])
                content = [
                    ToolUseBlock(
                        type="tool_use",
                        id="search-1",
                        name="web_search",
                        input={"objective": "TaskGroup"},
                    )
                ]
            else:
                result = kwargs["messages"][-1]["content"][0]
                self.assertEqual(result["tool_use_id"], "search-1")
                self.assertIn("https://docs.python.org", result["content"])
                content = [
                    TextBlock(type="text", text="TaskGroup waits for its tasks.")
                ]
            return SimpleNamespace(
                content=content,
                usage=SimpleNamespace(input_tokens=20, output_tokens=10),
            )

        client = SimpleNamespace(
            messages=SimpleNamespace(
                create=create,
                count_tokens=lambda **kwargs: SimpleNamespace(input_tokens=2),
            )
        )
        local_tool = ThinkTool()
        agent = Agent(
            name="test",
            system="Use search",
            tools=[local_tool],
            mcp_servers=[PARALLEL_SEARCH_SERVER],
            client=client,
        )
        with patch(
            "agents.utils.connections.httpx.AsyncClient", side_effect=server.client
        ):
            response = await agent.run_async("What is TaskGroup?")
        self.assertEqual(response.content[0].text, "TaskGroup waits for its tasks.")
        self.assertEqual(len(calls), 2)
        self.assertEqual(agent.tools, [local_tool])
        self.assertTrue(all(client.is_closed for client in server.clients))


if __name__ == "__main__":
    unittest.main()
