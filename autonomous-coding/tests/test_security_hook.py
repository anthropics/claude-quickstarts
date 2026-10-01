from __future__ import annotations

import asyncio

import pytest

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


def test_allows_pnpm_command() -> None:
    result = asyncio.run(
        bash_security_hook({"tool_name": "Bash", "tool_input": {"command": "pnpm install"}})
    )
    assert result == {}


@pytest.mark.parametrize(
    "command",
    [
        "cat ../secret.txt",
        "grep -r secret ../",
        "cat /etc/passwd",
        "chmod +x ../evil.sh",
    ],
)
def test_blocks_project_escape_paths(command: str) -> None:
    result = asyncio.run(
        bash_security_hook({"tool_name": "Bash", "tool_input": {"command": command}})
    )
    assert result.get("decision") == "block"


@pytest.mark.parametrize("command", ["../evil/init.sh", "/tmp/init.sh"])
def test_blocks_external_init_scripts(command: str) -> None:
    result = asyncio.run(
        bash_security_hook({"tool_name": "Bash", "tool_input": {"command": command}})
    )
    assert result.get("decision") == "block"


def test_allows_local_init_script() -> None:
    result = asyncio.run(
        bash_security_hook({"tool_name": "Bash", "tool_input": {"command": "./init.sh --production"}})
    )
    assert result == {}


def test_blocks_excessive_sleep() -> None:
    result = asyncio.run(
        bash_security_hook({"tool_name": "Bash", "tool_input": {"command": "sleep 9999"}})
    )
    assert result.get("decision") == "block"


def test_allows_short_sleep() -> None:
    result = asyncio.run(
        bash_security_hook({"tool_name": "Bash", "tool_input": {"command": "sleep 2"}})
    )
    assert result == {}


@pytest.mark.parametrize("command", ["npm install malicious-package", "pnpm add left-pad"])
def test_blocks_package_installs_with_explicit_dependencies(command: str) -> None:
    result = asyncio.run(
        bash_security_hook({"tool_name": "Bash", "tool_input": {"command": command}})
    )
    assert result.get("decision") == "block"
