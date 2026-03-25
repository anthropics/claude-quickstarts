from __future__ import annotations

import asyncio

from security import bash_security_hook, validate_chmod_command


def test_blocks_disallowed_command() -> None:
    result = asyncio.run(
        bash_security_hook({"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}})
    )
    assert result.get("decision") == "block"


def test_allows_safe_command() -> None:
    result = asyncio.run(
        bash_security_hook({"tool_name": "Bash", "tool_input": {"command": "npm install"}})
    )
    assert result == {}


def test_chmod_validation() -> None:
    allowed, _ = validate_chmod_command("chmod +x init.sh")
    assert allowed
    blocked, _ = validate_chmod_command("chmod 777 init.sh")
    assert not blocked
