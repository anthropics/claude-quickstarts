#!/usr/bin/env python3
"""
Security Hook Tests
===================

Tests for the bash command security validation logic.
Run with: python test_security.py
"""

import asyncio
import sys

from security import (
    bash_security_hook,
    extract_commands,
    validate_chmod_command,
    validate_init_script,
)


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


def test_validate_chmod():
    """Test chmod command validation."""
    print("\nTesting chmod validation:\n")
    passed = 0
    failed = 0

    # Test cases: (command, should_be_allowed, description)
    test_cases = [
        # Allowed cases
        ("chmod +x init.sh", True, "basic +x"),
        ("chmod +x script.sh", True, "+x on any script"),
        ("chmod u+x init.sh", True, "user +x"),
        ("chmod a+x init.sh", True, "all +x"),
        ("chmod ug+x init.sh", True, "user+group +x"),
        ("chmod +x file1.sh file2.sh", True, "multiple files"),
        # Blocked cases
        ("chmod 777 init.sh", False, "numeric mode"),
        ("chmod 755 init.sh", False, "numeric mode 755"),
        ("chmod +w init.sh", False, "write permission"),
        ("chmod +r init.sh", False, "read permission"),
        ("chmod -x init.sh", False, "remove execute"),
        ("chmod -R +x dir/", False, "recursive flag"),
        ("chmod --recursive +x dir/", False, "long recursive flag"),
        ("chmod +x", False, "missing file"),
    ]

    for cmd, should_allow, description in test_cases:
        allowed, reason = validate_chmod_command(cmd)
        if allowed == should_allow:
            print(f"  PASS: {cmd!r} ({description})")
            passed += 1
        else:
            expected = "allowed" if should_allow else "blocked"
            actual = "allowed" if allowed else "blocked"
            print(f"  FAIL: {cmd!r} ({description})")
            print(f"         Expected: {expected}, Got: {actual}")
            if reason:
                print(f"         Reason: {reason}")
            failed += 1

    return passed, failed


def test_validate_init_script():
    """Test init.sh script execution validation."""
    print("\nTesting init.sh validation:\n")
    passed = 0
    failed = 0

    # Test cases: (command, should_be_allowed, description)
    test_cases = [
        # Allowed cases
        ("./init.sh", True, "basic ./init.sh"),
        ("./init.sh arg1 arg2", True, "with arguments"),
        ("/path/to/init.sh", True, "absolute path"),
        ("../dir/init.sh", True, "relative path with init.sh"),
        # Blocked cases
        ("./setup.sh", False, "different script name"),
        ("./init.py", False, "python script"),
        ("bash init.sh", False, "bash invocation"),
        ("sh init.sh", False, "sh invocation"),
        ("./malicious.sh", False, "malicious script"),
        ("./init.sh; rm -rf /", False, "command injection attempt"),
    ]

    for cmd, should_allow, description in test_cases:
        allowed, reason = validate_init_script(cmd)
        if allowed == should_allow:
            print(f"  PASS: {cmd!r} ({description})")
            passed += 1
        else:
            expected = "allowed" if should_allow else "blocked"
            actual = "allowed" if allowed else "blocked"
            print(f"  FAIL: {cmd!r} ({description})")
            print(f"         Expected: {expected}, Got: {actual}")
            if reason:
                print(f"         Reason: {reason}")
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

    # Test chmod validation
    chmod_passed, chmod_failed = test_validate_chmod()
    passed += chmod_passed
    failed += chmod_failed

    # Test init.sh validation
    init_passed, init_failed = test_validate_init_script()
    passed += init_passed
    failed += init_failed

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
        # chmod with disallowed modes
        "chmod 777 file.sh",
        "chmod 755 file.sh",
        "chmod +w file.sh",
        "chmod -R +x dir/",
        # Non-init.sh scripts
        "./setup.sh",
        "./malicious.sh",
        "bash script.sh",
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
        "mkdir newdir",
        "mkdir -p path/to/dir",
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
        # chmod +x (allowed)
        "chmod +x init.sh",
        "chmod +x script.sh",
        "chmod u+x init.sh",
        "chmod a+x init.sh",
        # init.sh execution (allowed)
        "./init.sh",
        "./init.sh --production",
        "/path/to/init.sh",
        # Combined chmod and init.sh
        "chmod +x init.sh && ./init.sh",
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
