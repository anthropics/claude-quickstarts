#!/usr/bin/env python3
"""
Autonomous Coding Agent Demo
============================

A minimal harness demonstrating long-running autonomous coding with Claude.
This script implements the two-agent pattern (initializer + coding agent) and
incorporates all the strategies from the long-running agents guide.

Example Usage:
    python autonomous_agent_demo.py --project-dir ./claude_clone_demo
    python autonomous_agent_demo.py --project-dir ./claude_clone_demo --max-iterations 5
"""

import argparse
import asyncio
import os
from pathlib import Path

from agent import run_autonomous_agent


def load_env_file() -> None:
    """Load environment variables from .env file if it exists."""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    # Remove quotes if present
                    value = value.strip().strip('"').strip("'")
                    # Only set if not already set in environment
                    if key.strip() and not os.environ.get(key.strip()):
                        os.environ[key.strip()] = value


# Configuration
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"  # For standard Anthropic API
DEFAULT_FOUNDRY_MODEL = "claude-sonnet-4-5"   # Common Foundry deployment name


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Autonomous Coding Agent Demo - Long-running agent harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start fresh project
  python autonomous_agent_demo.py --project-dir ./claude_clone

  # Use a specific model
  python autonomous_agent_demo.py --project-dir ./claude_clone --model claude-sonnet-4-5-20250929

  # Limit iterations for testing
  python autonomous_agent_demo.py --project-dir ./claude_clone --max-iterations 5

  # Continue existing project
  python autonomous_agent_demo.py --project-dir ./claude_clone

Environment Variables:
  Standard Anthropic API:
    ANTHROPIC_API_KEY            Your Anthropic API key

  Azure Foundry:
    ANTHROPIC_FOUNDRY_API_KEY    Your Azure Foundry API key
    CLAUDE_CODE_USE_FOUNDRY      Set to 1 to use Azure Foundry
    ANTHROPIC_FOUNDRY_RESOURCE   Your Azure Foundry resource name
    CLAUDE_MODEL                 Your deployment name (required for Foundry)
        """,
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("./autonomous_demo_project"),
        help="Directory for the project (default: generations/autonomous_demo_project). Relative paths automatically placed in generations/ directory.",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of agent iterations (default: unlimited)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"Claude model/deployment to use. For standard API: claude-sonnet-4-5-20250929. For Foundry: your deployment name. Can also set via CLAUDE_MODEL env var.",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    # Load .env file if present
    load_env_file()

    args = parse_args()

    # Check for API key (supports both standard and Azure Foundry)
    has_standard_key = os.environ.get("ANTHROPIC_API_KEY")
    has_foundry_key = os.environ.get("ANTHROPIC_FOUNDRY_API_KEY")
    use_foundry = os.environ.get("CLAUDE_CODE_USE_FOUNDRY") == "1"

    if not has_standard_key and not has_foundry_key:
        print("Error: No API key found")
        print("\nFor standard Anthropic API:")
        print("  export ANTHROPIC_API_KEY='your-api-key-here'")
        print("\nFor Azure Foundry:")
        print("  export ANTHROPIC_FOUNDRY_API_KEY='your-api-key'")
        print("  export CLAUDE_CODE_USE_FOUNDRY=1")
        print("  export ANTHROPIC_FOUNDRY_RESOURCE='your-resource-name'")
        print("  export CLAUDE_MODEL='your-deployment-name'")
        return

    # Determine model to use
    # Priority: CLI arg > env var > smart default
    model = args.model or os.environ.get("CLAUDE_MODEL")

    if not model:
        if use_foundry:
            # Use Foundry default
            model = DEFAULT_FOUNDRY_MODEL
            print(f"No model specified, using Foundry default: {model}")
            print("(To use a different deployment, set CLAUDE_MODEL in .env file or use --model flag)")
        else:
            # Use default for standard API
            model = DEFAULT_MODEL

    print(f"Using model/deployment: {model}")
    if use_foundry:
        print("(Azure Foundry mode)")
    print()

    # Automatically place projects in generations/ directory unless already specified
    project_dir = args.project_dir
    if not str(project_dir).startswith("generations/"):
        # Convert relative paths to be under generations/
        if project_dir.is_absolute():
            # If absolute path, use as-is
            pass
        else:
            # Prepend generations/ to relative paths
            project_dir = Path("generations") / project_dir

    # Run the agent
    try:
        asyncio.run(
            run_autonomous_agent(
                project_dir=project_dir,
                model=model,
                max_iterations=args.max_iterations,
            )
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        print("To resume, run the same command again")
    except Exception as e:
        print(f"\nFatal error: {e}")
        raise


if __name__ == "__main__":
    main()
