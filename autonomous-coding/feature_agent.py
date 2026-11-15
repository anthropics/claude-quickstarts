#!/usr/bin/env python3
"""
Feature Development Agent
=========================

A variant of the autonomous coding agent designed for adding features
to EXISTING codebases (not greenfield projects).

Key differences from autonomous_agent_demo.py:
- Uses feature_spec.txt instead of app_spec.txt
- Uses feature-focused prompts (20-50 tasks, not 200)
- Emphasizes matching existing patterns
- Works in YOUR project directory (not generations/)

Usage:
    # Run in your project root
    cd /path/to/your/project
    python /path/to/feature_agent.py --spec feature_spec.txt

    # Or specify project directory
    python feature_agent.py --project-dir /path/to/your/project --spec feature_spec.txt
"""

import argparse
import asyncio
import os
import shutil
from pathlib import Path

from claude_code_sdk import ClaudeCodeOptions, ClaudeSDKClient
from claude_code_sdk.types import HookMatcher

# Import from sibling modules
import sys
sys.path.insert(0, str(Path(__file__).parent))
from security import bash_security_hook
from progress import print_session_header, print_progress_summary


# Configuration
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
AUTO_CONTINUE_DELAY_SECONDS = 3
PROMPTS_DIR = Path(__file__).parent / "prompts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Feature Development Agent - Add features to existing codebases",
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path.cwd(),
        help="Your project directory (default: current directory)",
    )

    parser.add_argument(
        "--spec",
        type=Path,
        default=Path("feature_spec.txt"),
        help="Feature specification file (default: feature_spec.txt in project dir)",
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
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )

    return parser.parse_args()


def load_prompt(name: str) -> str:
    """Load a prompt template."""
    # First try feature-specific prompts
    feature_prompt = PROMPTS_DIR / f"feature_{name}_prompt.md"
    if feature_prompt.exists():
        return feature_prompt.read_text()

    # Fall back to standard prompts
    standard_prompt = PROMPTS_DIR / f"{name}_prompt.md"
    return standard_prompt.read_text()


def create_client(project_dir: Path, model: str) -> ClaudeSDKClient:
    """Create Claude SDK client configured for existing codebase work."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    # More permissive settings for existing projects
    # (the agent needs to read/understand existing code)
    security_settings = {
        "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True},
        "permissions": {
            "defaultMode": "acceptEdits",
            "allow": [
                "Read(./**)",
                "Write(./**)",
                "Edit(./**)",
                "Glob(./**)",
                "Grep(./**)",
                "Bash(*)",
            ],
        },
    }

    settings_file = project_dir / ".claude_settings.json"
    import json
    with open(settings_file, "w") as f:
        json.dump(security_settings, f, indent=2)

    return ClaudeSDKClient(
        options=ClaudeCodeOptions(
            model=model,
            system_prompt=(
                "You are an expert developer joining an existing project. "
                "Your primary goal is to MATCH existing patterns and conventions. "
                "Read existing code before writing new code. "
                "Make minimal, focused changes that blend seamlessly with the codebase."
            ),
            allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
            hooks={
                "PreToolUse": [
                    HookMatcher(matcher="Bash", hooks=[bash_security_hook]),
                ],
            },
            max_turns=1000,
            cwd=str(project_dir.resolve()),
            settings=str(settings_file.resolve()),
        )
    )


async def run_agent_session(client: ClaudeSDKClient, message: str) -> tuple[str, str]:
    """Run a single agent session."""
    print("Starting agent session...\n")

    try:
        await client.query(message)

        response_text = ""
        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__
                    if block_type == "TextBlock" and hasattr(block, "text"):
                        response_text += block.text
                        print(block.text, end="", flush=True)
                    elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                        print(f"\n[Tool: {block.name}]", flush=True)

            elif msg_type == "UserMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    if type(block).__name__ == "ToolResultBlock":
                        is_error = getattr(block, "is_error", False)
                        content = getattr(block, "content", "")
                        if "blocked" in str(content).lower():
                            print(f"   [BLOCKED] {content}", flush=True)
                        elif is_error:
                            print(f"   [Error] {str(content)[:200]}", flush=True)
                        else:
                            print("   [Done]", flush=True)

        print("\n" + "-" * 70 + "\n")
        return "continue", response_text

    except Exception as e:
        print(f"Error: {e}")
        return "error", str(e)


async def run_feature_agent(
    project_dir: Path,
    spec_file: Path,
    model: str,
    max_iterations: int | None = None,
) -> None:
    """Run the feature development agent."""
    print("\n" + "=" * 70)
    print("  FEATURE DEVELOPMENT AGENT")
    print("  (For existing codebases)")
    print("=" * 70)
    print(f"\nProject: {project_dir}")
    print(f"Spec: {spec_file}")
    print(f"Model: {model}")
    print()

    # Validate spec file exists
    full_spec_path = project_dir / spec_file if not spec_file.is_absolute() else spec_file
    if not full_spec_path.exists():
        print(f"Error: Feature spec not found at {full_spec_path}")
        print("\nCreate a feature_spec.txt file describing your feature.")
        print("See prompts/feature_spec_template.txt for the format.")
        return

    # Check if this is first run or continuation
    feature_list = project_dir / "feature_list.json"
    is_first_run = not feature_list.exists()

    if is_first_run:
        print("First run - will analyze codebase and create implementation plan")
        print()
        print("=" * 70)
        print("  The agent will:")
        print("  1. Explore your existing codebase")
        print("  2. Read your feature specification")
        print("  3. Create feature_list.json with 20-50 tasks")
        print("  4. Start implementation if time permits")
        print("=" * 70)
    else:
        print("Continuing feature implementation")
        print_progress_summary(project_dir)

    # Main loop
    iteration = 0

    while True:
        iteration += 1

        if max_iterations and iteration > max_iterations:
            print(f"\nReached max iterations ({max_iterations})")
            break

        print_session_header(iteration, is_first_run and iteration == 1)

        client = create_client(project_dir, model)

        if is_first_run and iteration == 1:
            prompt = load_prompt("initializer")
        else:
            prompt = load_prompt("coding")

        async with client:
            status, response = await run_agent_session(client, prompt)

        if status == "continue":
            print(f"\nContinuing in {AUTO_CONTINUE_DELAY_SECONDS}s...")
            print_progress_summary(project_dir)
            await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)
        elif status == "error":
            print("\nError encountered, retrying...")
            await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

        if max_iterations is None or iteration < max_iterations:
            await asyncio.sleep(1)

    print("\n" + "=" * 70)
    print("  SESSION COMPLETE")
    print("=" * 70)
    print_progress_summary(project_dir)


def main():
    args = parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set")
        return

    try:
        asyncio.run(
            run_feature_agent(
                project_dir=args.project_dir,
                spec_file=args.spec,
                model=args.model,
                max_iterations=args.max_iterations,
            )
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted. Run same command to resume.")
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()
