"""Connection handling for MCP servers."""

from abc import ABC, abstractmethod
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

from ..tools.mcp_tool import MCPTool


class MCPConnection(ABC):
    """Base class for MCP server connections."""

    def __init__(self):
        self.session = None
        self._rw_ctx = None
        self._session_ctx = None

    @abstractmethod
    async def _create_rw_context(self):
        """Create the read/write context based on connection type."""

    async def __aenter__(self):
        """Initialize MCP server connection."""
        self._rw_ctx = await self._create_rw_context()
        read_write = await self._rw_ctx.__aenter__()
        read, write = read_write
        self._session_ctx = ClientSession(read, write)
        self.session = await self._session_ctx.__aenter__()
        await self.session.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up MCP server connection resources."""
        try:
            if self._session_ctx:
                await self._session_ctx.__aexit__(exc_type, exc_val, exc_tb)
            if self._rw_ctx:
                await self._rw_ctx.__aexit__(exc_type, exc_val, exc_tb)
        except Exception as e:
            print(f"Error during cleanup: {e}")
        finally:
            self.session = None
            self._session_ctx = None
            self._rw_ctx = None

    async def list_tools(self) -> Any:
        """Retrieve available tools from the MCP server."""
        response = await self.session.list_tools()
        return response.tools

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> Any:
        """Call a tool on the MCP server with provided arguments."""
        return await self.session.call_tool(tool_name, arguments=arguments)


class MCPConnectionStdio(MCPConnection):
    """MCP connection using standard input/output."""

    def __init__(
        self, command: str, args: list[str] = [], env: dict[str, str] = None
    ):
        super().__init__()
        self.command = command
        self.args = args
        self.env = env

    async def _create_rw_context(self):
        return stdio_client(
            StdioServerParameters(
                command=self.command, args=self.args, env=self.env
            )
        )


class MCPConnectionSSE(MCPConnection):
    """MCP connection using Server-Sent Events."""

    def __init__(self, url: str, headers: dict[str, str] = None):
        super().__init__()
        self.url = url
        self.headers = headers or {}

    async def _create_rw_context(self):
        return sse_client(url=self.url, headers=self.headers)


def create_mcp_connection(config: dict[str, Any]) -> MCPConnection:
    """Factory function to create the appropriate MCP connection."""
    conn_type = config.get("type", "stdio").lower()

    if conn_type == "stdio":
        if not config.get("command"):
            raise ValueError("Command is required for STDIO connections")
        return MCPConnectionStdio(
            command=config["command"],
            args=config.get("args"),
            env=config.get("env"),
        )

    elif conn_type == "sse":
        if not config.get("url"):
            raise ValueError("URL is required for SSE connections")
        return MCPConnectionSSE(
            url=config["url"], headers=config.get("headers")
        )

    else:
        raise ValueError(f"Unsupported connection type: {conn_type}")


async def setup_mcp_connections(
    mcp_servers: list[dict[str, Any]] | None,
    stack: AsyncExitStack,
) -> list[MCPTool]:
    """Set up MCP server connections and create tool interfaces."""
    if not mcp_servers:
        return []

    mcp_tools = []

    for config in mcp_servers:
        try:
            connection = create_mcp_connection(config)
            await stack.enter_async_context(connection)
            tool_definitions = await connection.list_tools()

            for tool_info in tool_definitions:
                mcp_tools.append(
                    MCPTool(
                        name=tool_info.name,
                        description=tool_info.description
                        or f"MCP tool: {tool_info.name}",
                        input_schema=tool_info.inputSchema,
                        connection=connection,
                    )
                )

        except Exception as e:
            print(f"Error setting up MCP server {config}: {e}")

    print(
        f"Loaded {len(mcp_tools)} MCP tools from {len(mcp_servers)} servers."
    )
    return mcp_tools
