"""
Progress tracking utilities.
"""

import json
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def get_progress_summary(project_dir: Path) -> dict[str, Any]:
    """Get progress summary from feature_list.json."""
    feature_list = project_dir / "feature_list.json"

    if not feature_list.exists():
        return {
            "total": 0,
            "passing": 0,
            "failing": 0,
            "percent": 0.0,
        }

    try:
        with open(feature_list) as f:
            features = json.load(f)

        total = len(features)
        passing = sum(1 for f in features if f.get("passes", False))
        failing = total - passing
        percent = (passing / total * 100) if total > 0 else 0.0

        return {
            "total": total,
            "passing": passing,
            "failing": failing,
            "percent": percent,
        }
    except (json.JSONDecodeError, KeyError):
        return {
            "total": 0,
            "passing": 0,
            "failing": 0,
            "percent": 0.0,
        }


def print_progress_summary(project_dir: Path) -> None:
    """Print a progress summary to console."""
    summary = get_progress_summary(project_dir)

    if summary["total"] == 0:
        console.print("[dim]No feature list found yet.[/dim]")
        return

    console.print(
        f"[bold]Progress:[/bold] {summary['passing']}/{summary['total']} "
        f"({summary['percent']:.1f}%) "
        f"[green]✅ {summary['passing']}[/green] "
        f"[yellow]⏳ {summary['failing']}[/yellow]"
    )


def print_session_header(iteration: int, is_initializer: bool = False) -> None:
    """Print session header."""
    console.print()
    console.rule(f"[bold blue]Session {iteration}[/bold blue]")

    if is_initializer:
        console.print("[dim]Mode: Initializer (creating feature list)[/dim]")
    else:
        console.print("[dim]Mode: Coding (implementing features)[/dim]")

    console.print()
