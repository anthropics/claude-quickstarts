# NotebookLM MCP Server Integration

This directory includes a NotebookLM MCP Server wrapper (`notebooklm_mcp.py`) that enables Claude agents to interact directly with Google NotebookLM.

## Setup

### 1. Install Dependencies

The NotebookLM MCP server is provided by the `notebooklm-mcp-cli` package:

```bash
pip install notebooklm-mcp-cli
```

### 2. Configure Your Agent

Add the NotebookLM MCP server to your agent's configuration:

```python
from agents.agent import Agent

agent = Agent(
    name="NotebookLM Assistant",
    system="You are an AI assistant with access to NotebookLM. Help users research and analyze documents.",
    mcp_servers=[
        {
            "type": "stdio",
            "command": "python3",
            "args": ["agents/tools/notebooklm_mcp.py"]
        }
    ]
)
```

### 3. Authenticate

When you first use NotebookLM tools, the agent will guide you to authenticate with Google:

1. The agent will ask you to log in to NotebookLM
2. A Chrome browser window will open automatically
3. Sign in with your Google account
4. Your session will persist for future conversations

**Important**: Your Google credentials never leave your machine. Authentication happens locally using browser login.

## Available Tools

The NotebookLM MCP server exposes 35+ tools for notebook management:

- **Notebook Management**: `notebook_list`, `notebook_create`, `notebook_delete`, `notebook_get`
- **Source Management**: `source_add`, `source_delete`, `source_list`, `source_sync`
- **Audio Generation**: `audio_create`, `audio_get`, `audio_list`, `audio_download`
- **Research**: `notebook_research`, `notebook_insights`, `notebook_outline`
- **Studio Artifacts**: `artifact_create`, `artifact_get`, `artifact_list`
- **And more!**

## Example Usage

```python
# Create a notebook with research documents
user_input = """
Create a NotebookLM notebook called 'AI Research' and add these sources:
- https://arxiv.org/abs/2401.00000
- https://github.com/anthropics/anthropic-sdk-python

Then generate audio notes about the key topics.
"""

response = agent.run(user_input)
```

## Troubleshooting

### Command not found: notebooklm-mcp

Make sure `notebooklm-mcp-cli` is installed in your Python environment:

```bash
pip install notebooklm-mcp-cli
which notebooklm-mcp  # Verify installation
```

### Authentication fails

- Clear your browser cache if you're having login issues
- Try logging in again: the agent will prompt you when needed
- Session cookies are stored locally in your home directory

### Server connection issues

Ensure the MCP server is properly configured in your agent:

```python
# Verify the path to notebooklm_mcp.py
import os
mcp_path = os.path.join(os.path.dirname(__file__), "agents/tools/notebooklm_mcp.py")
print(f"MCP script exists: {os.path.exists(mcp_path)}")
```

## Architecture

The integration uses the MCP (Model Context Protocol) to bridge Claude and NotebookLM:

```
Claude Agent
    ↓
MCPConnection (stdio)
    ↓
notebooklm_mcp.py (wrapper)
    ↓
notebooklm-mcp (official MCP server)
    ↓
Google NotebookLM API
```

Each MCP tool is automatically wrapped by the `MCPTool` class and made available to the agent.
