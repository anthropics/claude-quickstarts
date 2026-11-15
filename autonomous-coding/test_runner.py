#!/usr/bin/env python3
"""
Quick Test Runner for Autonomous Coding Agent
==============================================

Simplified test harness for quick validation with minimal features.
"""

import argparse
import asyncio
import os
from pathlib import Path

from agent import run_autonomous_agent


DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Quick Test Runner - Test autonomous agent with minimal project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("./test_project"),
        help="Directory for the test project (default: generations/test_project)",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum number of agent iterations (default: 3 for quick testing)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )

    parser.add_argument(
        "--use-minimal-spec",
        action="store_true",
        help="Use minimal_test_spec.txt instead of app_spec.txt",
    )

    return parser.parse_args()


def setup_test_spec(project_dir: Path, use_minimal: bool) -> None:
    """Copy appropriate spec file to project directory."""
    prompts_dir = Path(__file__).parent / "prompts"

    if use_minimal:
        spec_source = prompts_dir / "minimal_test_spec.txt"
    else:
        spec_source = prompts_dir / "app_spec.txt"

    spec_dest = project_dir / "app_spec.txt"

    project_dir.mkdir(parents=True, exist_ok=True)

    import shutil
    shutil.copy2(spec_source, spec_dest)
    print(f"Copied spec: {spec_source.name} -> {spec_dest}")


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("\nGet your API key from: https://console.anthropic.com/")
        print("\nThen set it:")
        print("  export ANTHROPIC_API_KEY='your-api-key-here'")
        return

    # Automatically place projects in generations/ directory
    project_dir = args.project_dir
    if not str(project_dir).startswith("generations/"):
        if not project_dir.is_absolute():
            project_dir = Path("generations") / project_dir

    # Set up test spec
    setup_test_spec(project_dir, args.use_minimal_spec)

    print("\n" + "=" * 70)
    print("  QUICK TEST MODE")
    print("=" * 70)
    print(f"\nProject: {project_dir}")
    print(f"Max iterations: {args.max_iterations}")
    print(f"Using spec: {'minimal_test_spec.txt' if args.use_minimal_spec else 'app_spec.txt'}")
    print("\nThis will run for ~5-15 minutes depending on complexity.")
    print("Press Ctrl+C to stop early.\n")
    print("=" * 70)
    print()

    # Run the agent
    try:
        asyncio.run(
            run_autonomous_agent(
                project_dir=project_dir,
                model=args.model,
                max_iterations=args.max_iterations,
            )
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        print("To resume, run: python test_runner.py")
    except Exception as e:
        print(f"\nFatal error: {e}")
        raise


if __name__ == "__main__":
    main()
