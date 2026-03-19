# Cross-Validated Search Agent

A Claude agent that uses cross-validated web search for hallucination-free responses.

## Overview

This example demonstrates how to build a Claude agent that uses cross-validated web search to prevent hallucinations. Every fact is verified against multiple sources before being presented.

## Why Cross-Validated Search?

- 🔍 **Cross-validation** across multiple search engines (DuckDuckGo, Bing, Google)
- ✅ **Confidence scoring** (Verified / Likely True / Uncertain / Likely False)
- 🆓 **Zero API keys** - completely free
- 🔌 **MCP protocol** - works with Claude Desktop

## Installation

```bash
pip install cross-validated-search anthropic mcp
```

## Usage

### Basic Agent

```python
from agents.agent import Agent
from tools.cross_validated_search import CrossValidatedSearchTool

# Create an agent with cross-validated search
agent = Agent(
    name="FactChecker",
    system="You are a helpful assistant that verifies facts before answering.",
    tools=[CrossValidatedSearchTool()],
)

# Run the agent
response = agent.run("What is the latest version of Python?")
print(response)
```

### With MCP Server

```python
agent = Agent(
    name="ResearchAgent",
    system="You are a research assistant that provides verified information.",
    mcp_servers=[
        {
            "type": "stdio",
            "command": "cross-validated-mcp",
            "args": [],
        },
    ]
)

response = agent.run("Research the latest advances in AI")
```

## Tools

### CrossValidatedSearchTool

Search the web with cross-validation:

```python
from tools.cross_validated_search import CrossValidatedSearchTool

tool = CrossValidatedSearchTool()

# Search for information
result = tool.run("What is the population of Tokyo?")
# Returns: answer, confidence, sources
```

### FactCheckTool

Verify claims with evidence:

```python
from tools.fact_check import FactCheckTool

tool = FactCheckTool()

# Fact-check a claim
result = tool.run("Python 3.14 is released")
# Returns: status (verified/likely_true/uncertain/likely_false), evidence
```

## Confidence Levels

| Level | Meaning | When to Use |
|-------|---------|-------------|
| ✅ Verified | 3+ sources agree | Cite as fact |
| 🟢 Likely True | 2 sources agree | Cite with confidence note |
| 🟡 Uncertain | Single source | Flag as unverified |
| 🔴 Likely False | Major contradictions | Do not use |

## Examples

### Example 1: Basic Fact-Checking

```python
from agents.agent import Agent
from tools.cross_validated_search import CrossValidatedSearchTool

agent = Agent(
    name="FactChecker",
    system="""You are a fact-checking assistant. 
    Always verify claims using cross_validated_search.
    Report the confidence level of your answers.""",
    tools=[CrossValidatedSearchTool()],
)

response = agent.run("Is Python 3.14 released?")
# Output includes confidence level and sources
```

### Example 2: Research Agent

```python
from agents.agent import Agent
from tools.cross_validated_search import CrossValidatedSearchTool

agent = Agent(
    name="ResearchAgent",
    system="""You are a research assistant.
    Use cross_validated_search to find verified information.
    Always cite your sources and report confidence levels.""",
    tools=[CrossValidatedSearchTool()],
)

response = agent.run("What are the latest advances in RAG?")
```

### Example 3: News Agent

```python
from agents.agent import Agent
from tools.cross_validated_search import CrossValidatedSearchTool

agent = Agent(
    name="NewsAgent",
    system="""You are a news assistant.
    Use cross_validated_search with search_type='news' to find recent news.
    Verify information across multiple sources.""",
    tools=[CrossValidatedSearchTool()],
)

response = agent.run("What are the latest AI news?")
```

## Architecture

```
cross-validated-search-agent/
├── README.md
├── agent.py              # Agent implementation
├── tools/
│   ├── __init__.py
│   ├── cross_validated_search.py  # Main search tool
│   └── fact_check.py              # Fact-checking tool
└── requirements.txt
```

## Requirements

- Python 3.8+
- `anthropic` library
- `cross-validated-search` library
- `mcp` library (for MCP integration)

## Links

- cross-validated-search: https://github.com/wd041216-bit/cross-validated-search
- PyPI: https://pypi.org/project/cross-validated-search/
- Claude API: https://docs.anthropic.com/