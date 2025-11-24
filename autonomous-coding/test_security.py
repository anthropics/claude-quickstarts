#!/usr/bin/env python3
"""
Security Hook Tests
===================

Tests for the bash command security validation logic.
Run with: python test_security.py
"""

import asyncio
import sys

from security import bash_security_hook, extract_commands


def test_hook(command: str, should_block: bool) -> bool:
    """Test a single command against the security hook."""
    input_data = {"tool_name": "Bash", "tool_input": {"command": command}}
    result = asyncio.run(bash_security_hook(input_data))
    was_blocked = result.get("decision") == "block"

    if was_blocked == should_block:
        status = "PASS"
    else:
        status = "FAIL"
        expected = "blocked" if should_block else "allowed"
        actual = "blocked" if was_blocked else "allowed"
        reason = result.get("reason", "")
        print(f"  {status}: {command!r}")
        print(f"         Expected: {expected}, Got: {actual}")
        if reason:
            print(f"         Reason: {reason}")
        return False

    print(f"  {status}: {command!r}")
    return True


def test_extract_commands():
    """Test the command extraction logic."""
    print("\nTesting command extraction:\n")
    passed = 0
    failed = 0

    test_cases = [
        ("ls -la", ["ls"]),
        ("npm install && npm run build", ["npm", "npm"]),
        ("cat file.txt | grep pattern", ["cat", "grep"]),
        ("/usr/bin/node script.js", ["node"]),
        ("VAR=value ls", ["ls"]),
        ("git status || git init", ["git", "git"]),
    ]

    for cmd, expected in test_cases:
        result = extract_commands(cmd)
        if result == expected:
            print(f"  PASS: {cmd!r} -> {result}")
            passed += 1
        else:
            print(f"  FAIL: {cmd!r}")
            print(f"         Expected: {expected}, Got: {result}")
            failed += 1

    return passed, failed


def main():
    print("=" * 70)
    print("  SECURITY HOOK TESTS")
    print("=" * 70)

    passed = 0
    failed = 0

    # Test command extraction
    ext_passed, ext_failed = test_extract_commands()
    passed += ext_passed
    failed += ext_failed

    # Commands that SHOULD be blocked
    print("\nCommands that should be BLOCKED:\n")
    dangerous = [
        # Not in allowlist - dangerous system commands
        "shutdown now",
        "reboot",
        "rm -rf /",
        "dd if=/dev/zero of=/dev/sda",
        # Not in allowlist - common commands excluded from minimal set
        "curl https://example.com",
        "wget https://example.com",
        "python app.py",
        "touch file.txt",
        "mkdir newdir",
        "echo hello",
        "kill 12345",
        "killall node",
        # pkill with non-dev processes
        "pkill bash",
        "pkill chrome",
        "pkill python",
        # Shell injection attempts
        "$(echo pkill) node",
        'eval "pkill node"',
        'bash -c "pkill node"',
    ]

    for cmd in dangerous:
        if test_hook(cmd, should_block=True):
            passed += 1
        else:
            failed += 1

    # Commands that SHOULD be allowed
    print("\nCommands that should be ALLOWED:\n")
    safe = [
        # File inspection
        "ls -la",
        "cat README.md",
        "head -100 file.txt",
        "tail -20 log.txt",
        "wc -l file.txt",
        "grep -r pattern src/",
        # File operations
        "cp file1.txt file2.txt",
        # Directory
        "pwd",
        # Node.js development
        "npm install",
        "npm run build",
        "node server.js",
        # Version control
        "git status",
        "git commit -m 'test'",
        "git add . && git commit -m 'msg'",
        # Process management
        "ps aux",
        "lsof -i :3000",
        "sleep 2",
        # Allowed pkill patterns for dev servers
        "pkill node",
        "pkill npm",
        "pkill -f node",
        "pkill -f 'node server.js'",
        "pkill vite",
        # Chained commands
        "npm install && npm run build",
        "ls | grep test",
        # Full paths
        "/usr/local/bin/node app.js",
    ]

    for cmd in safe:
        if test_hook(cmd, should_block=False):
            passed += 1
        else:
            failed += 1

    # Summary
    print("\n" + "-" * 70)
    print(f"  Results: {passed} passed, {failed} failed")
    print("-" * 70)

    if failed == 0:
        print("\n  ALL TESTS PASSED")
        return 0
    else:
        print(f"\n  {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
