"""Agent session logic for V1 compatibility and V2 phase execution."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from claude_code_sdk import ClaudeSDKClient

from client import create_client
from progress import print_session_header, print_progress_summary
from prompts import get_coding_prompt, get_initializer_prompt, copy_spec_to_project

AUTO_CONTINUE_DELAY_SECONDS = 3


async def run_agent_session(
    client: ClaudeSDKClient,
    message: str,
    project_dir: Path,
) -> tuple[str, str]:
    """Run a single SDK session and stream response text."""
    _ = project_dir
    print("Sending prompt to Claude Agent SDK...\n")

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
                        if is_error:
                            print(f"   [Error] {str(getattr(block, 'content', ''))[:300]}", flush=True)
                        else:
                            print("   [Done]", flush=True)

        print("\n" + "-" * 70 + "\n")
        return "continue", response_text
    except Exception as exc:  # pragma: no cover
        print(f"Error during agent session: {exc}")
        return "error", str(exc)


async def run_phase_session(project_dir: Path, model: str, prompt: str, phase: str) -> str:
    """Run one phase in a fresh context and return plain-text summary."""
    client = create_client(project_dir=project_dir, model=model, phase=phase)
    async with client:
        status, response = await run_agent_session(client, prompt, project_dir)
    if status == "error":
        raise RuntimeError(response)
    return response


async def run_autonomous_agent(
    project_dir: Path,
    model: str,
    max_iterations: Optional[int] = None,
) -> None:
    """Legacy V1 autonomous loop (initializer + coding agent)."""
    print("\n" + "=" * 70)
    print("  AUTONOMOUS CODING AGENT DEMO (V1 COMPAT MODE)")
    print("=" * 70)

    project_dir.mkdir(parents=True, exist_ok=True)
    tests_file = project_dir / "feature_list.json"
    is_first_run = not tests_file.exists()

    if is_first_run:
        copy_spec_to_project(project_dir)
    else:
        print_progress_summary(project_dir)

    iteration = 0
    while True:
        iteration += 1
        if max_iterations and iteration > max_iterations:
            break

        print_session_header(iteration, is_first_run)
        prompt = get_initializer_prompt() if is_first_run else get_coding_prompt()
        phase = "planner" if is_first_run else "builder"
        await run_phase_session(project_dir=project_dir, model=model, prompt=prompt, phase=phase)
        is_first_run = False
        print_progress_summary(project_dir)
        await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

    print("\nDone!")
