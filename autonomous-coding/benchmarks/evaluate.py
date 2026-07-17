#!/usr/bin/env python3
"""
Evaluation Script for Benchmark Results

Analyzes the output of each benchmark run and calculates scores.

Usage:
    python evaluate.py                    # Evaluate all results
    python evaluate.py --tier t2          # Evaluate specific tier
    python evaluate.py --tool junior      # Evaluate specific tool
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

BENCHMARK_DIR = Path(__file__).parent
RESULTS_DIR = BENCHMARK_DIR / "results"

# Expected features per tier (for completeness scoring)
EXPECTED_FEATURES = {
    "t1_email_validator": {
        "files": ["email_validator.py", "test_email_validator.py"],
        "functions": ["validate_email"],
        "test_count": 5,
    },
    "t2_todo_cli": {
        "files": ["src/todo_cli/cli.py", "tests/test_cli.py", "pyproject.toml"],
        "commands": ["add", "list", "complete", "delete"],
        "test_count": 10,
    },
    "t3_rest_api": {
        "files": [
            "src/api/main.py",
            "src/api/routes/auth.py",
            "src/api/routes/notes.py",
            "src/api/models.py",
        ],
        "endpoints": [
            "POST /auth/register",
            "POST /auth/login",
            "GET /notes",
            "POST /notes",
            "GET /notes/{id}",
            "PUT /notes/{id}",
            "DELETE /notes/{id}",
        ],
        "test_count": 15,
    },
    "t4_url_shortener": {
        "files": [
            "src/shortener/main.py",
            "src/shortener/routes/urls.py",
            "src/shortener/services/analytics.py",
        ],
        "endpoints": [
            "POST /shorten",
            "GET /{slug}",
            "GET /api/urls",
            "GET /api/urls/{slug}/stats",
        ],
        "test_count": 20,
    },
}


def count_files(output_dir: Path, patterns: list[str]) -> tuple[int, int]:
    """Count how many expected files exist. Returns (found, expected)."""
    found = 0
    for pattern in patterns:
        # Handle glob patterns
        if "*" in pattern:
            matches = list(output_dir.glob(pattern))
            if matches:
                found += 1
        else:
            if (output_dir / pattern).exists():
                found += 1
    return found, len(patterns)


def run_tests(output_dir: Path) -> tuple[int, int]:
    """Run pytest and return (passed, total)."""
    # Check if pytest is available in the project
    has_tests = (
        list(output_dir.glob("**/test_*.py")) or
        list(output_dir.glob("**/tests/*.py"))
    )

    if not has_tests:
        return 0, 0

    try:
        result = subprocess.run(
            ["uv", "run", "pytest", "-v", "--tb=no", "-q"],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=120
        )

        # Parse pytest output for pass/fail counts
        output = result.stdout + result.stderr

        # Look for "X passed" pattern
        import re
        passed_match = re.search(r"(\d+) passed", output)
        failed_match = re.search(r"(\d+) failed", output)

        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0

        return passed, passed + failed

    except subprocess.TimeoutExpired:
        return 0, 0
    except Exception as e:
        print(f"    Test error: {e}")
        return 0, 0


def run_lint(output_dir: Path) -> int:
    """Run ruff and return error count."""
    try:
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "."],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=60
        )

        # Count errors in output
        if result.returncode == 0:
            return 0

        # Count lines that look like errors
        errors = len([
            line for line in result.stdout.split("\n")
            if line.strip() and not line.startswith("Found")
        ])
        return errors

    except Exception:
        return -1  # Unable to run


def calculate_scores(
    tier: str,
    output_dir: Path,
    duration: float,
    max_iter: int,
    exit_code: int
) -> dict:
    """Calculate all scores for a benchmark result."""
    expected = EXPECTED_FEATURES.get(tier, {})
    scores = {}

    # 1. Completeness (30%) - files and structure
    expected_files = expected.get("files", [])
    files_found, files_expected = count_files(output_dir, expected_files)
    scores["completeness_score"] = round((files_found / max(files_expected, 1)) * 100, 1)

    # 2. Correctness (25%) - tests passing
    tests_passed, tests_total = run_tests(output_dir)
    expected_tests = expected.get("test_count", 1)

    if tests_total > 0:
        pass_rate = tests_passed / tests_total
        coverage_rate = min(tests_total / expected_tests, 1.0)
        scores["correctness_score"] = round((pass_rate * 0.7 + coverage_rate * 0.3) * 100, 1)
    else:
        scores["correctness_score"] = 0.0

    scores["tests_passed"] = tests_passed
    scores["tests_total"] = tests_total

    # 3. Efficiency (20%) - time and iterations
    # Base: T1 should take <5min, T2 <15min, T3 <30min, T4 <60min
    time_limits = {"t1": 300, "t2": 900, "t3": 1800, "t4": 3600}
    tier_short = tier.split("_")[0]
    time_limit = time_limits.get(tier_short, 1800)

    if duration > 0:
        time_score = max(0, 100 - (duration / time_limit) * 50)
    else:
        time_score = 0

    scores["efficiency_score"] = round(time_score, 1)

    # 4. Quality (15%) - linting
    lint_errors = run_lint(output_dir)
    if lint_errors == 0:
        scores["quality_score"] = 100.0
    elif lint_errors < 0:
        scores["quality_score"] = 50.0  # Unable to run
    else:
        scores["quality_score"] = round(max(0, 100 - lint_errors * 5), 1)

    scores["lint_errors"] = max(0, lint_errors)

    # 5. Autonomy (10%) - successful completion without intervention
    if exit_code == 0:
        scores["autonomy_score"] = 100.0
    elif exit_code > 0:
        scores["autonomy_score"] = 50.0  # Completed with issues
    else:
        scores["autonomy_score"] = 0.0  # Failed/timeout

    # Overall weighted score
    scores["overall_score"] = round(
        scores["completeness_score"] * 0.30 +
        scores["correctness_score"] * 0.25 +
        scores["efficiency_score"] * 0.20 +
        scores["quality_score"] * 0.15 +
        scores["autonomy_score"] * 0.10,
        1
    )

    return scores


def evaluate_result(tool: str, tier: str) -> dict | None:
    """Evaluate a single benchmark result."""
    output_dir = RESULTS_DIR / tool / tier
    metrics_file = output_dir / "metrics.json"

    if not metrics_file.exists():
        return None

    print(f"\nEvaluating: {tool}/{tier}")

    # Load existing metrics
    with open(metrics_file) as f:
        metrics = json.load(f)

    # Skip if already has error
    if metrics.get("error"):
        print(f"  Skipped (error: {metrics['error']})")
        return metrics

    # Calculate scores
    scores = calculate_scores(
        tier=tier,
        output_dir=output_dir,
        duration=metrics.get("duration_seconds", 0),
        max_iter=metrics.get("max_iterations", 10),
        exit_code=metrics.get("exit_code", -1)
    )

    # Update metrics with scores
    metrics.update(scores)

    # Save updated metrics
    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"  Completeness: {scores['completeness_score']}%")
    print(f"  Correctness:  {scores['correctness_score']}% ({scores['tests_passed']}/{scores['tests_total']} tests)")
    print(f"  Efficiency:   {scores['efficiency_score']}%")
    print(f"  Quality:      {scores['quality_score']}% ({scores['lint_errors']} lint errors)")
    print(f"  Autonomy:     {scores['autonomy_score']}%")
    print(f"  OVERALL:      {scores['overall_score']}%")

    return metrics


def print_comparison_table(all_metrics: list[dict]):
    """Print a comparison table of all results."""
    if not all_metrics:
        return

    print("\n" + "=" * 100)
    print("COMPARISON TABLE")
    print("=" * 100)

    # Header
    print(f"\n{'Tool':<15} {'Tier':<20} {'Complete':<10} {'Correct':<10} {'Efficient':<10} {'Quality':<10} {'OVERALL':<10}")
    print("-" * 100)

    # Sort by tier, then tool
    sorted_metrics = sorted(all_metrics, key=lambda x: (x.get("tier", ""), x.get("tool", "")))

    for m in sorted_metrics:
        if m.get("error"):
            print(f"{m.get('tool', 'N/A'):<15} {m.get('tier', 'N/A'):<20} {'ERROR: ' + m.get('error', '')[:40]}")
        else:
            print(
                f"{m.get('tool', 'N/A'):<15} "
                f"{m.get('tier', 'N/A'):<20} "
                f"{m.get('completeness_score', 0):<10.1f} "
                f"{m.get('correctness_score', 0):<10.1f} "
                f"{m.get('efficiency_score', 0):<10.1f} "
                f"{m.get('quality_score', 0):<10.1f} "
                f"{m.get('overall_score', 0):<10.1f}"
            )

    # Summary by tool (average scores)
    print("\n" + "-" * 100)
    print("AVERAGES BY TOOL")
    print("-" * 100)

    tools = set(m.get("tool") for m in sorted_metrics if not m.get("error"))
    for tool in sorted(tools):
        tool_metrics = [m for m in sorted_metrics if m.get("tool") == tool and not m.get("error")]
        if tool_metrics:
            avg_overall = sum(m.get("overall_score", 0) for m in tool_metrics) / len(tool_metrics)
            avg_complete = sum(m.get("completeness_score", 0) for m in tool_metrics) / len(tool_metrics)
            avg_correct = sum(m.get("correctness_score", 0) for m in tool_metrics) / len(tool_metrics)
            print(f"{tool:<15} Avg Overall: {avg_overall:.1f}% | Complete: {avg_complete:.1f}% | Correct: {avg_correct:.1f}%")


def main():
    parser = argparse.ArgumentParser(description="Evaluate benchmark results")
    parser.add_argument("--tier", "-t", help="Evaluate specific tier only")
    parser.add_argument("--tool", help="Evaluate specific tool only")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    all_metrics = []

    # Find all results
    if not RESULTS_DIR.exists():
        print("No results found. Run benchmarks first.")
        return

    for tool_dir in sorted(RESULTS_DIR.iterdir()):
        if not tool_dir.is_dir():
            continue

        tool = tool_dir.name
        if args.tool and tool != args.tool:
            continue

        for tier_dir in sorted(tool_dir.iterdir()):
            if not tier_dir.is_dir():
                continue

            tier = tier_dir.name
            if args.tier and not tier.startswith(args.tier):
                continue

            metrics = evaluate_result(tool, tier)
            if metrics:
                all_metrics.append(metrics)

    if args.json:
        print(json.dumps(all_metrics, indent=2))
    else:
        print_comparison_table(all_metrics)


if __name__ == "__main__":
    main()
