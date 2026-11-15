"""
Agent Runner - Core execution logic for autonomous coding sessions.
"""

import asyncio
import json
import shutil
from pathlib import Path

from claude_code_sdk import ClaudeCodeOptions, ClaudeSDKClient
from claude_code_sdk.types import HookMatcher
from rich.console import Console

from .config import load_config, DEFAULT_CONFIG
from .security import bash_security_hook
from .progress import print_session_header, print_progress_summary
from .templates import get_prompt

console = Console()

# Tools available to the agent
BUILTIN_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]


def create_client(
    project_dir: Path,
    model: str,
    system_prompt: str,
) -> ClaudeSDKClient:
    """Create a configured Claude SDK client."""
    config = load_config()

    # Security settings
    security_settings = {
        "sandbox": {
            "enabled": config.get("security", {}).get("sandbox_enabled", True),
            "autoAllowBashIfSandboxed": True,
        },
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

    # Write settings file
    settings_file = project_dir / ".claude_settings.json"
    with open(settings_file, "w") as f:
        json.dump(security_settings, f, indent=2)

    return ClaudeSDKClient(
        options=ClaudeCodeOptions(
            model=model,
            system_prompt=system_prompt,
            allowed_tools=BUILTIN_TOOLS,
            hooks={
                "PreToolUse": [
                    HookMatcher(matcher="Bash", hooks=[bash_security_hook]),
                ],
            },
            max_turns=config.get("max_turns", DEFAULT_CONFIG["max_turns"]),
            cwd=str(project_dir.resolve()),
            settings=str(settings_file.resolve()),
        )
    )


async def run_agent_session(
    client: ClaudeSDKClient,
    prompt: str,
) -> tuple[str, str]:
    """Run a single agent session."""
    console.print("[dim]Starting agent session...[/dim]\n")

    try:
        await client.query(prompt)

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
                        console.print(f"\n[cyan][Tool: {block.name}][/cyan]", highlight=False)

            elif msg_type == "UserMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    if type(block).__name__ == "ToolResultBlock":
                        is_error = getattr(block, "is_error", False)
                        content = getattr(block, "content", "")
                        if "blocked" in str(content).lower():
                            console.print(f"   [red][BLOCKED][/red] {content}")
                        elif is_error:
                            console.print(f"   [yellow][Error][/yellow] {str(content)[:200]}")
                        else:
                            console.print("   [green][Done][/green]")

        print("\n" + "-" * 70 + "\n")
        return "continue", response_text

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return "error", str(e)


async def run_build_agent(
    spec_file: Path,
    project_dir: Path,
    model: str,
    max_iterations: int | None = None,
) -> None:
    """Run the build agent for greenfield projects."""
    config = load_config()
    delay = config.get("auto_continue_delay", DEFAULT_CONFIG["auto_continue_delay"])

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # Check if first run
    feature_list = project_dir / "feature_list.json"
    is_first_run = not feature_list.exists()

    if is_first_run:
        # Copy spec to project
        shutil.copy(spec_file, project_dir / "app_spec.txt")
        console.print("[dim]Copied spec to project directory[/dim]")

    # Main loop
    iteration = 0
    while True:
        iteration += 1

        if max_iterations and iteration > max_iterations:
            console.print(f"\n[yellow]Reached max iterations ({max_iterations})[/yellow]")
            break

        print_session_header(iteration, is_first_run and iteration == 1)

        system_prompt = (
            "You are an expert full-stack developer building a production-quality application. "
            "Focus on clean code, thorough testing, and incremental progress."
        )

        client = create_client(project_dir, model, system_prompt)

        if is_first_run and iteration == 1:
            prompt = get_prompt("initializer")
        else:
            prompt = get_prompt("coding")

        async with client:
            status, _ = await run_agent_session(client, prompt)

        print_progress_summary(project_dir)

        if status == "error":
            console.print("[yellow]Error encountered, retrying...[/yellow]")

        console.print(f"\n[dim]Continuing in {delay}s...[/dim]")
        await asyncio.sleep(delay)

    console.print("\n[bold green]Session complete![/bold green]")
    print_progress_summary(project_dir)


async def run_feature_agent(
    spec_file: Path,
    project_dir: Path,
    model: str,
    max_iterations: int | None = None,
) -> None:
    """Run the feature agent for existing codebases."""
    config = load_config()
    delay = config.get("auto_continue_delay", DEFAULT_CONFIG["auto_continue_delay"])

    # Validate spec exists
    if not spec_file.exists():
        console.print(f"[red]Feature spec not found: {spec_file}[/red]")
        console.print("\nCreate a feature_spec.txt with:")
        console.print("  autonomous-agent template feature -o feature_spec.txt")
        return

    # Check if first run
    feature_list = project_dir / "feature_list.json"
    is_first_run = not feature_list.exists()

    # Main loop
    iteration = 0
    while True:
        iteration += 1

        if max_iterations and iteration > max_iterations:
            console.print(f"\n[yellow]Reached max iterations ({max_iterations})[/yellow]")
            break

        print_session_header(iteration, is_first_run and iteration == 1)

        system_prompt = (
            "You are an expert developer joining an existing project. "
            "Your primary goal is to MATCH existing patterns and conventions. "
            "Read existing code before writing new code. "
            "Make minimal, focused changes that blend seamlessly."
        )

        client = create_client(project_dir, model, system_prompt)

        if is_first_run and iteration == 1:
            prompt = get_prompt("feature_initializer")
        else:
            prompt = get_prompt("feature_coding")

        async with client:
            status, _ = await run_agent_session(client, prompt)

        print_progress_summary(project_dir)

        if status == "error":
            console.print("[yellow]Error encountered, retrying...[/yellow]")

        console.print(f"\n[dim]Continuing in {delay}s...[/dim]")
        await asyncio.sleep(delay)

    console.print("\n[bold green]Session complete![/bold green]")
    print_progress_summary(project_dir)
