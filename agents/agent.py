"""Agent implementation with Claude API and tools."""

import asyncio
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic

from .tools.base import Tool
from .utils.connections import setup_mcp_connections
from .utils.history_util import MessageHistory
from .utils.tool_util import execute_tools


@dataclass
class ModelConfig:
    """Configuration settings for Claude model parameters."""

    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 1.0
    context_window_tokens: int = 180000


class Agent:
    """Claude-powered agent with tool use capabilities."""

    def __init__(
        self,
        name: str,
        system: str,
        tools: list[Tool] | None = None,
        mcp_servers: list[dict[str, Any]] | None = None,
        config: ModelConfig | None = None,
        verbose: bool = False,
        client: Anthropic | None = None,
        message_params: dict[str, Any] | None = None,
    ):
        """Initialize an Agent.
        
        Args:
            name: Agent identifier for logging
            system: System prompt for the agent
            tools: List of tools available to the agent
            mcp_servers: MCP server configurations
            config: Model configuration with defaults
            verbose: Enable detailed logging
            client: Anthropic client instance
            message_params: Additional parameters for client.messages.create().
                           These override any conflicting parameters from config.
        """
        self.name = name
        self.system = system
        self.verbose = verbose
        self.tools = list(tools or [])
        self.config = config or ModelConfig()
        self.mcp_servers = mcp_servers or []
        self.message_params = message_params or {}
        self.client = client or Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )
        self.history = MessageHistory(
            model=self.config.model,
            system=self.system,
            context_window_tokens=self.config.context_window_tokens,
            client=self.client,
        )

        if self.verbose:
            print(f"\n[{self.name}] Agent initialized")

    def _prepare_message_params(self) -> dict[str, Any]:
        """Prepare parameters for client.messages.create() call.
        
        Returns a dict with base parameters from config, with any
        message_params overriding conflicting keys.
        """
        return {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "system": self.system,
            "messages": self.history.format_for_api(),
            "tools": [tool.to_dict() for tool in self.tools],
            **self.message_params,
        }

    async def _agent_loop(self, user_input: str) -> list[dict[str, Any]]:
        """Process user input and handle tool calls in a loop"""
        if self.verbose:
            print(f"\n[{self.name}] Received: {user_input}")
        await self.history.add_message("user", user_input, None)

        tool_dict = {tool.name: tool for tool in self.tools}

        while True:
            self.history.truncate()
            params = self._prepare_message_params()

            response = self.client.messages.create(
                **params,
                extra_headers={"anthropic-beta": "code-execution-2025-05-22"}
            )
            tool_calls = [
                block for block in response.content if block.type == "tool_use"
            ]

            if self.verbose:
                for block in response.content:
                    if block.type == "text":
                        print(f"\n[{self.name}] Output: {block.text}")
                    elif block.type == "tool_use":
                        params_str = ", ".join(
                            [f"{k}={v}" for k, v in block.input.items()]
                        )
                        print(
                            f"\n[{self.name}] Tool call: "
                            f"{block.name}({params_str})"
                        )

            await self.history.add_message(
                "assistant", response.content, response.usage
            )

            if tool_calls:
                tool_results = await execute_tools(
                    tool_calls,
                    tool_dict,
                )
                if self.verbose:
                    for block in tool_results:
                        print(
                            f"\n[{self.name}] Tool result: "
                            f"{block.get('content')}"
                        )
                await self.history.add_message("user", tool_results)
            else:
                return response

    async def run_async(self, user_input: str) -> list[dict[str, Any]]:
        """Run agent with MCP tools asynchronously."""
        async with AsyncExitStack() as stack:
            original_tools = list(self.tools)

            try:
                mcp_tools = await setup_mcp_connections(
                    self.mcp_servers, stack
                )
                self.tools.extend(mcp_tools)
                return await self._agent_loop(user_input)
            finally:
                self.tools = original_tools

    def run(self, user_input: str) -> list[dict[str, Any]]:
        """Run agent synchronously"""
        return asyncio.run(self.run_async(user_input))
