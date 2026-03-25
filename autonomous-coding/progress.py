"""Progress tracking utilities for autonomous coding harness."""

from __future__ import annotations

import json
from pathlib import Path


def count_passing_tests(project_dir: Path) -> tuple[int, int]:
    tests_file = project_dir / "feature_list.json"
    if not tests_file.exists():
        return 0, 0
    try:
        tests = json.loads(tests_file.read_text())
        total = len(tests)
        passing = sum(1 for test in tests if test.get("passes", False))
        return passing, total
    except (json.JSONDecodeError, OSError):
        return 0, 0


def print_session_header(session_num: int, is_initializer: bool) -> None:
    session_type = "INITIALIZER" if is_initializer else "CODING AGENT"
    print("\n" + "=" * 70)
    print(f"  SESSION {session_num}: {session_type}")
    print("=" * 70 + "\n")


def print_progress_summary(project_dir: Path) -> None:
    passing, total = count_passing_tests(project_dir)
    run_state = project_dir / "state" / "run_state.json"
    if run_state.exists():
        try:
            state = json.loads(run_state.read_text())
            print(
                "\nRun State: "
                f"status={state.get('status')} "
                f"round={state.get('current_round')}/{state.get('max_rounds')} "
                f"planner_complete={state.get('planner_complete')}"
            )
        except json.JSONDecodeError:
            print("\nRun State: unreadable run_state.json")

    if total > 0:
        print(f"Backlog progress: {passing}/{total} tests passing ({(passing/total)*100:.1f}%)")
    else:
        print("Backlog progress: feature_list.json not yet created")
