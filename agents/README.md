# Agents

A minimal educational implementation of LLM agents using the Claude API.

> **Note:** This is NOT an SDK, but a reference implementation of key concepts

## Overview & Core Components

This repo demonstrates how to [build effective agents](https://www.anthropic.com/engineering/building-effective-agents) with the Claude API. It shows how sophisticated AI behaviors can emerge from a simple foundation: LLMs using tools in a loop. This implementation is not prescriptive - the core logic is <300 lines of code and deliberately lacks production features. Feel free to translate these patterns to your language and production stack ([Claude Code](https://docs.claude.com/en/docs/agents-and-tools/claude-code/overview) can help!)

It contains three components:

- `agent.py`: Manages Claude API interactions and tool execution
- `tools/`: Tool implementations (both native and MCP tools)
- `utils/`: Utilities for message history and MCP server connections

## Usage

```python
from agents.agent import Agent
from agents.tools.think import ThinkTool

# Create an agent with both local tools and MCP server tools
agent = Agent(
    name="MyAgent",
    system="You are a helpful assistant.",
    tools=[ThinkTool()],  # Local tools
    mcp_servers=[
        {
            "type": "stdio",
            "command": "python",
            "args": ["-m", "mcp_server"],
        },
    ]
)

# Run the agent
response = agent.run("What should I consider when buying a new laptop?")
```

From this foundation, you can add domain-specific tools, optimize performance, or implement custom response handling. We remain deliberately unopinionated - this backbone simply gets you started with fundamentals.

## Requirements

- Python 3.8+
- Claude API key (set as `ANTHROPIC_API_KEY` environment variable)
- `anthropic` Python library
- `mcp` Python library