"""
Security hooks for Autonomous Agent.

Validates bash commands against a configurable allowlist.
"""

import os
import shlex
from typing import Any

from .config import get_allowed_commands


def extract_commands(command_string: str) -> list[str]:
    """Extract command names from a shell command string."""
    import re

    commands = []
    segments = re.split(r'(?<!["\'])\s*;\s*(?!["\'])', command_string)

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        try:
            tokens = shlex.split(segment)
        except ValueError:
            return []  # Fail-safe: block unparseable commands

        if not tokens:
            continue

        expect_command = True
        for token in tokens:
            if token in ("|", "||", "&&", "&"):
                expect_command = True
                continue

            if token in ("if", "then", "else", "elif", "fi", "for", "while",
                        "until", "do", "done", "case", "esac", "in", "!", "{", "}"):
                continue

            if token.startswith("-"):
                continue

            if "=" in token and not token.startswith("="):
                continue

            if expect_command:
                cmd = os.path.basename(token)
                commands.append(cmd)
                expect_command = False

    return commands


def validate_command(command: str, allowed_commands: set[str] | None = None) -> tuple[bool, str]:
    """
    Validate a bash command against the allowlist.

    Returns:
        (is_allowed, reason_if_blocked)
    """
    if allowed_commands is None:
        allowed_commands = get_allowed_commands()

    commands = extract_commands(command)

    if not commands:
        return False, f"Could not parse command: {command}"

    for cmd in commands:
        if cmd not in allowed_commands:
            return False, f"Command '{cmd}' not in allowlist. Add to config if needed."

    # Extra validation for dangerous commands
    if "rm" in commands:
        if "-rf" in command or "-r" in command:
            # Only allow rm -rf on safe paths
            if ".." in command or command.strip().endswith("rm -rf /"):
                return False, "Dangerous rm command blocked"

    if "pkill" in commands:
        # Only allow killing dev processes
        allowed_processes = {"node", "npm", "npx", "vite", "next", "python"}
        try:
            tokens = shlex.split(command)
            target = [t for t in tokens if not t.startswith("-")][-1]
            if target.split()[0] not in allowed_processes:
                return False, f"pkill only allowed for: {allowed_processes}"
        except (ValueError, IndexError):
            return False, "Could not validate pkill target"

    return True, ""


async def bash_security_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None = None,
    context: Any = None,
) -> dict[str, Any]:
    """Pre-tool-use hook that validates bash commands."""
    if input_data.get("tool_name") != "Bash":
        return {}

    command = input_data.get("tool_input", {}).get("command", "")
    if not command:
        return {}

    is_allowed, reason = validate_command(command)

    if not is_allowed:
        return {
            "decision": "block",
            "reason": reason,
        }

    return {}
