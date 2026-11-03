#!/usr/bin/env python3

"""NotebookLM MCP Server wrapper.

This module wraps the notebooklm-mcp server provided by the notebooklm-mcp-cli package.
It allows Claude agents to interact with Google NotebookLM directly through MCP tools.

The notebooklm-mcp-cli package must be installed:
    pip install notebooklm-mcp-cli

Authentication:
    The first time you use NotebookLM tools, the agent will guide you through
    browser-based Google login. Your session will persist across multiple runs.
"""

import sys
import subprocess

if __name__ == "__main__":
    # Run the notebooklm-mcp server provided by the notebooklm-mcp-cli package
    # This server exposes 35+ tools for managing NotebookLM notebooks, sources,
    # audio generation, and more.
    try:
        result = subprocess.run(
            ["notebooklm-mcp"],
            check=False
        )
        sys.exit(result.returncode)
    except FileNotFoundError:
        print(
            "Error: notebooklm-mcp command not found.\n"
            "Please install notebooklm-mcp-cli:\n"
            "    pip install notebooklm-mcp-cli",
            file=sys.stderr
        )
        sys.exit(1)
