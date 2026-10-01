"""Agent implementation with Claude API and tools."""

from __future__ import annotations

import asyncio
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic

from .tools.base import Tool
from .utils.connections import setup_mcp_connections
from .utils.event_util import (
    AgentEvent,
    EventCallback,
    EventDispatcher,
    EventType,
    LoggingCallback,
)
from .utils.history_util import MessageHistory
from .utils.tool_util import execute_tools


@dataclass
class ModelConfig:
    """Configuration settings for Claude model parameters."""

    # Available models include:
    # - claude-sonnet-4-20250514 (default)
    # - claude-opus-4-20250514
    # - claude-haiku-4-5-20251001
    # - claude-3-5-sonnet-20240620
    # - claude-3-haiku-20240307
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
        callbacks: list[EventCallback] | None = None,
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
            callbacks: Event callbacks invoked at each agent lifecycle phase.
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

        callbacks_list = list(callbacks or [])
        if self.verbose:
            callbacks_list.insert(0, LoggingCallback)
        self._dispatcher = EventDispatcher(callbacks_list)

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
        await self._dispatcher.emit(AgentEvent(
            type=EventType.USER_INPUT,
            agent_name=self.name,
            payload={"input": user_input},
        ))
        await self.history.add_message("user", user_input, None)

        tool_dict = {tool.name: tool for tool in self.tools}

        while True:
            self.history.truncate()
            params = self._prepare_message_params()

            # Merge headers properly - default beta header can be overridden by message_params
            default_headers = {"anthropic-beta": "code-execution-2025-05-22"}
            if "extra_headers" in params:
                # Pop extra_headers from params and merge with defaults
                custom_headers = params.pop("extra_headers")
                merged_headers = {**default_headers, **custom_headers}
            else:
                merged_headers = default_headers

            response = self.client.messages.create(
                **params,
                extra_headers=merged_headers
            )
            tool_calls = [
                block for block in response.content if block.type == "tool_use"
            ]

            for block in response.content:
                if block.type == "text":
                    await self._dispatcher.emit(AgentEvent(
                        type=EventType.AGENT_RESPONSE,
                        agent_name=self.name,
                        payload={"text": block.text},
                    ))
                elif block.type == "tool_use":
                    await self._dispatcher.emit(AgentEvent(
                        type=EventType.TOOL_CALL,
                        agent_name=self.name,
                        payload={
                            "tool_name": block.name,
                            "tool_input": block.input,
                            "tool_use_id": block.id,
                        },
                    ))

            await self.history.add_message(
                "assistant", response.content, response.usage
            )

            if tool_calls:
                tool_results = await execute_tools(
                    tool_calls,
                    tool_dict,
                )
                for result in tool_results:
                    event_type = (
                        EventType.TOOL_ERROR
                        if result.get("is_error")
                        else EventType.TOOL_RESULT
                    )
                    await self._dispatcher.emit(AgentEvent(
                        type=event_type,
                        agent_name=self.name,
                        payload={
                            "tool_use_id": result["tool_use_id"],
                            "content": result["content"],
                        },
                    ))
                await self.history.add_message("user", tool_results)
            else:
                await self._dispatcher.emit(AgentEvent(
                    type=EventType.LOOP_END,
                    agent_name=self.name,
                    payload={},
                ))
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
