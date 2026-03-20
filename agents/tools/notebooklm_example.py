#!/usr/bin/env python3

"""Example: Using NotebookLM with Claude Agent

This script demonstrates how to create a Claude agent with NotebookLM MCP
server access and use it to research and analyze documents.

Prerequisites:
    - pip install notebooklm-mcp-cli
    - Set ANTHROPIC_API_KEY environment variable
"""

import os
import sys
from pathlib import Path

# Add agents module to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import Agent, ModelConfig


def main():
    """Create and run an agent with NotebookLM MCP server."""

    # Verify API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    # Create agent with NotebookLM MCP server
    agent = Agent(
        name="NotebookLM Research Assistant",
        system="""You are a research assistant with access to Google NotebookLM.

You can help users:
- Create and manage NotebookLM notebooks
- Add research sources (URLs, YouTube videos, documents)
- Generate audio notes and summaries
- Extract insights and create outlines
- Perform detailed research on any topic

When the user asks you to research something, use the NotebookLM tools to:
1. Create a new notebook (if needed)
2. Add relevant sources
3. Generate insights or audio notes
4. Summarize findings for the user

Be helpful and thorough in your research.""",
        mcp_servers=[
            {
                "type": "stdio",
                "command": "python3",
                "args": ["agents/tools/notebooklm_mcp.py"]
            }
        ],
        config=ModelConfig(max_tokens=4096),
        verbose=True
    )

    # Example prompts to try
    example_prompts = [
        "List my NotebookLM notebooks",
        "Create a new notebook called 'Python Learning' and add a source from python.org",
        "Generate audio notes for one of my existing notebooks",
    ]

    print("\n" + "="*60)
    print("NotebookLM Research Assistant")
    print("="*60)
    print("\nExample prompts to try:")
    for i, prompt in enumerate(example_prompts, 1):
        print(f"{i}. {prompt}")
    print("\nEnter 'quit' to exit\n")

    # Interactive loop
    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break

            # Run agent
            response = agent.run(user_input)

            # Extract and print response text
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"\nAssistant: {block.text}\n")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
