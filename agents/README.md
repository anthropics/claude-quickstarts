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

## Hosted web search with Streamable HTTP

The connection loader accepts `stdio` (the default), `sse`, and
`streamable_http` configurations. For hosted MCP servers, set `type` to
`streamable_http`, provide `url`, and optionally pass request `headers`.

[Parallel Search MCP](https://docs.parallel.ai/integrations/mcp/search-mcp)
provides free web search and page fetching without a Parallel account or API key.
Anonymous searches use Fast mode; the free tier is intended for exploration and
light use and has rate limits. This example explicitly opts in to Parallel:

```python
from agents.agent import Agent
from agents.parallel_search import PARALLEL_SEARCH_SERVER

agent = Agent(
    name="WebResearcher",
    system="Research the question with web_search and cite source URLs.",
    mcp_servers=[PARALLEL_SEARCH_SERVER],
)
```

Run these commands from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r agents/requirements.txt

# Try the MCP loader and search tool without calling Claude:
python -m agents.parallel_search --search-only "Python asyncio TaskGroup documentation"

# Run the agent loop (requires ANTHROPIC_API_KEY in your environment):
python -m agents.parallel_search "What does Python's asyncio TaskGroup do? Cite sources."
```

The agent loads `web_search` and `web_fetch` from the server and dispatches them
through the same MCP tool wrapper as other servers. The example sends a
`claude-quickstarts/agents` User-Agent on its MCP requests. Existing agents and
their selected servers are unchanged.

Run the offline transport and agent-loop tests from the repository root with
`python -m unittest agents.test_mcp_connections`.

## Requirements

- Python 3.10+
- Claude API key (set as `ANTHROPIC_API_KEY` environment variable)
- `anthropic` Python library, 1.0 or later
- `mcp` Python library, 1.30 or later (below 2)
- `httpx` Python library
