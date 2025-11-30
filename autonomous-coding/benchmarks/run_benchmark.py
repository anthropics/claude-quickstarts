#!/usr/bin/env python3
"""
Benchmark Runner for Autonomous Coding Tools

Runs the same spec against multiple tools and captures metrics.
Results are stored in benchmarks/results/<tool>/<tier>/

Usage:
    python run_benchmark.py --tier t2 --tools junior,claudiomiro
    python run_benchmark.py --all  # Run all tiers on all tools
"""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal

BENCHMARK_DIR = Path(__file__).parent
RESULTS_DIR = BENCHMARK_DIR / "results"

TIERS = ["t0_validation", "t1_email_validator", "t2_todo_cli", "t3_rest_api", "t4_url_shortener"]
TOOLS = ["junior", "claudiomiro", "codemachine", "roma"]

# Tool configurations
TOOL_CONFIGS = {
    "junior": {
        "command": "junior build --spec {spec} -o {output} --max-iterations {max_iter}",
        "max_iterations": {"t0": 1, "t1": 3, "t2": 5, "t3": 10, "t4": 15},
        "requires": ["junior"],
    },
    "claudiomiro": {
        "command": "cd {output} && claudiomiro --prompt=\"$(cat {spec})\" --limit={max_iter}",
        "max_iterations": {"t0": 2, "t1": 5, "t2": 10, "t3": 20, "t4": 30},
        "requires": ["claudiomiro"],
    },
    "codemachine": {
        "setup": "mkdir -p {output}/.codemachine/inputs && cp {spec} {output}/.codemachine/inputs/specifications.md",
        "command": "cd {output} && codemachine --dir . --max-iterations {max_iter}",
        "max_iterations": {"t0": 1, "t1": 3, "t2": 5, "t3": 10, "t4": 15},
        "requires": ["codemachine"],
    },
    "roma": {
        "command": "roma-dspy solve \"$(cat {spec})\" --max-depth {max_iter} --output json > {output}/result.json",
        "max_iterations": {"t0": 1, "t1": 2, "t2": 3, "t3": 4, "t4": 5},
        "requires": ["roma-dspy"],
    },
}


@dataclass
class BenchmarkMetrics:
    """Metrics captured during benchmark run."""
    tool: str
    tier: str
    start_time: str = ""
    end_time: str = ""
    duration_seconds: float = 0.0
    iterations_used: int = 0
    max_iterations: int = 0
    exit_code: int = -1

    # Quality metrics (filled by evaluate.py)
    tests_total: int = 0
    tests_passed: int = 0
    lint_errors: int = 0
    type_errors: int = 0
    features_requested: int = 0
    features_implemented: int = 0

    # Cost metrics (if available)
    tokens_input: int = 0
    tokens_output: int = 0
    estimated_cost_usd: float = 0.0

    # Human intervention
    interventions: int = 0
    intervention_notes: list = field(default_factory=list)

    # Scores (0-100)
    completeness_score: float = 0.0
    correctness_score: float = 0.0
    efficiency_score: float = 0.0
    quality_score: float = 0.0
    autonomy_score: float = 0.0
    overall_score: float = 0.0

    error: str = ""


def check_tool_available(tool: str) -> bool:
    """Check if a tool is installed and available."""
    config = TOOL_CONFIGS.get(tool, {})
    for cmd in config.get("requires", []):
        result = subprocess.run(
            ["which", cmd],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return False
    return True


def get_tier_short(tier: str) -> str:
    """Extract t1, t2, etc from tier name."""
    return tier.split("_")[0]


def run_tool(tool: str, tier: str, spec_path: Path, output_dir: Path, max_iter: int) -> BenchmarkMetrics:
    """Run a single tool on a spec and capture metrics."""
    metrics = BenchmarkMetrics(tool=tool, tier=tier, max_iterations=max_iter)
    config = TOOL_CONFIGS.get(tool)

    if not config:
        metrics.error = f"Unknown tool: {tool}"
        return metrics

    if not check_tool_available(tool):
        metrics.error = f"Tool not installed: {tool}"
        return metrics

    # Prepare output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run setup if needed
    if "setup" in config:
        setup_cmd = config["setup"].format(
            spec=spec_path,
            output=output_dir,
            max_iter=max_iter
        )
        subprocess.run(setup_cmd, shell=True, cwd=output_dir)

    # Build command
    cmd = config["command"].format(
        spec=spec_path,
        output=output_dir,
        max_iter=max_iter
    )

    # Run benchmark
    metrics.start_time = datetime.now().isoformat()
    start = time.time()

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=output_dir if tool != "junior" else None,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour max
        )
        metrics.exit_code = result.returncode

        # Save stdout/stderr
        (output_dir / "benchmark_stdout.txt").write_text(result.stdout)
        (output_dir / "benchmark_stderr.txt").write_text(result.stderr)

    except subprocess.TimeoutExpired:
        metrics.error = "Timeout (1 hour)"
        metrics.exit_code = -1
    except Exception as e:
        metrics.error = str(e)
        metrics.exit_code = -1

    end = time.time()
    metrics.end_time = datetime.now().isoformat()
    metrics.duration_seconds = round(end - start, 2)

    return metrics


def save_metrics(metrics: BenchmarkMetrics, output_dir: Path):
    """Save metrics to JSON file."""
    metrics_file = output_dir / "metrics.json"
    metrics_file.write_text(json.dumps(asdict(metrics), indent=2))
    print(f"  Metrics saved to {metrics_file}")


def run_benchmark(
    tiers: list[str],
    tools: list[str],
    force: bool = False
) -> list[BenchmarkMetrics]:
    """Run benchmarks for specified tiers and tools."""
    all_metrics = []

    for tier in tiers:
        spec_path = BENCHMARK_DIR / tier / "spec.txt"
        if not spec_path.exists():
            print(f"Spec not found: {spec_path}")
            continue

        tier_short = get_tier_short(tier)

        for tool in tools:
            output_dir = RESULTS_DIR / tool / tier
            metrics_file = output_dir / "metrics.json"

            # Skip if already run (unless force)
            if metrics_file.exists() and not force:
                print(f"Skipping {tool}/{tier} (already exists, use --force to rerun)")
                with open(metrics_file) as f:
                    metrics = BenchmarkMetrics(**json.load(f))
                all_metrics.append(metrics)
                continue

            # Get max iterations for this tier
            config = TOOL_CONFIGS.get(tool, {})
            max_iter = config.get("max_iterations", {}).get(tier_short, 10)

            print(f"\n{'='*60}")
            print(f"Running: {tool} on {tier}")
            print(f"Max iterations: {max_iter}")
            print(f"Output: {output_dir}")
            print(f"{'='*60}")

            # Clean output directory
            if output_dir.exists():
                shutil.rmtree(output_dir)

            metrics = run_tool(tool, tier, spec_path, output_dir, max_iter)
            save_metrics(metrics, output_dir)
            all_metrics.append(metrics)

            if metrics.error:
                print(f"  ERROR: {metrics.error}")
            else:
                print(f"  Completed in {metrics.duration_seconds}s (exit code: {metrics.exit_code})")

    return all_metrics


def print_summary(all_metrics: list[BenchmarkMetrics]):
    """Print a summary table of results."""
    print("\n" + "="*80)
    print("BENCHMARK SUMMARY")
    print("="*80)

    # Group by tier
    by_tier = {}
    for m in all_metrics:
        if m.tier not in by_tier:
            by_tier[m.tier] = {}
        by_tier[m.tier][m.tool] = m

    print(f"\n{'Tier':<25} {'Tool':<15} {'Duration':<12} {'Exit':<6} {'Error'}")
    print("-" * 80)

    for tier in sorted(by_tier.keys()):
        for tool in sorted(by_tier[tier].keys()):
            m = by_tier[tier][tool]
            duration = f"{m.duration_seconds}s" if m.duration_seconds > 0 else "N/A"
            error = m.error[:30] + "..." if len(m.error) > 30 else m.error
            print(f"{tier:<25} {tool:<15} {duration:<12} {m.exit_code:<6} {error}")


def main():
    parser = argparse.ArgumentParser(description="Run autonomous coding benchmarks")
    parser.add_argument(
        "--tier", "-t",
        choices=["t0", "t1", "t2", "t3", "t4", "all"],
        default="t2",
        help="Benchmark tier to run (default: t2)"
    )
    parser.add_argument(
        "--tools",
        type=str,
        default="junior",
        help="Comma-separated list of tools (default: junior)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force rerun even if results exist"
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List available tools and exit"
    )

    args = parser.parse_args()

    if args.list_tools:
        print("Available tools:")
        for tool in TOOLS:
            available = "✓" if check_tool_available(tool) else "✗"
            print(f"  {available} {tool}")
        return

    # Parse tiers
    if args.tier == "all":
        tiers = TIERS
    else:
        tier_map = {
            "t0": "t0_validation",
            "t1": "t1_email_validator",
            "t2": "t2_todo_cli",
            "t3": "t3_rest_api",
            "t4": "t4_url_shortener",
        }
        tiers = [tier_map[args.tier]]

    # Parse tools
    tools = [t.strip() for t in args.tools.split(",")]

    # Validate tools
    for tool in tools:
        if tool not in TOOLS:
            print(f"Unknown tool: {tool}")
            print(f"Available: {', '.join(TOOLS)}")
            sys.exit(1)

    print(f"Benchmarking: {', '.join(tools)}")
    print(f"Tiers: {', '.join(tiers)}")

    # Run benchmarks
    all_metrics = run_benchmark(tiers, tools, args.force)

    # Print summary
    print_summary(all_metrics)

    print(f"\nResults saved to: {RESULTS_DIR}")
    print("Run 'python evaluate.py' to score the results")


if __name__ == "__main__":
    main()
