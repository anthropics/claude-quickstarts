"""
CLI Entry Point for Autonomous Agent.

Usage:
    autonomous-agent build --spec app_spec.txt      # Build new project from spec
    autonomous-agent feature --spec feature.txt    # Add feature to existing codebase
    autonomous-agent status                         # Check progress
    autonomous-agent init                           # Initialize config

    # Short alias
    aa build --spec app_spec.txt
"""

import asyncio
import os
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import load_config, init_config, DEFAULT_CONFIG
from .runner import run_build_agent, run_feature_agent
from .progress import get_progress_summary

console = Console()


@click.group()
@click.version_option()
def main():
    """Autonomous Agent - AI-powered coding assistant for long-running tasks."""
    pass


@main.command()
@click.option(
    "--spec",
    type=click.Path(exists=True, path_type=Path),
    default="app_spec.txt",
    help="Project specification file",
)
@click.option(
    "--project-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: generations/<spec-name>)",
)
@click.option(
    "--max-iterations",
    type=int,
    default=None,
    help="Max agent iterations (default: unlimited)",
)
@click.option(
    "--model",
    type=str,
    default=None,
    help="Claude model (default: from config)",
)
def build(spec: Path, project_dir: Path | None, max_iterations: int | None, model: str | None):
    """Build a new project from a specification file.

    This is for GREENFIELD projects - building from scratch.

    Example:
        autonomous-agent build --spec my_app_spec.txt
        autonomous-agent build --spec spec.txt --max-iterations 5
    """
    config = load_config()

    # Use spec filename as project name if no dir specified
    if project_dir is None:
        project_name = spec.stem.replace("_spec", "").replace("_", "-")
        project_dir = Path("generations") / project_name

    model = model or config.get("model", DEFAULT_CONFIG["model"])

    console.print(Panel.fit(
        f"[bold blue]Building new project[/bold blue]\n"
        f"Spec: {spec}\n"
        f"Output: {project_dir}\n"
        f"Model: {model}",
        title="🚀 Autonomous Agent"
    ))

    try:
        asyncio.run(run_build_agent(
            spec_file=spec,
            project_dir=project_dir,
            model=model,
            max_iterations=max_iterations,
        ))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Run same command to resume.[/yellow]")


@main.command()
@click.option(
    "--spec",
    type=click.Path(exists=True, path_type=Path),
    default="feature_spec.txt",
    help="Feature specification file",
)
@click.option(
    "--project-dir",
    type=click.Path(exists=True, path_type=Path),
    default=Path.cwd(),
    help="Project directory (default: current directory)",
)
@click.option(
    "--max-iterations",
    type=int,
    default=None,
    help="Max agent iterations (default: unlimited)",
)
@click.option(
    "--model",
    type=str,
    default=None,
    help="Claude model (default: from config)",
)
def feature(spec: Path, project_dir: Path, max_iterations: int | None, model: str | None):
    """Add a feature to an EXISTING codebase.

    This is for adding features to existing projects.
    The agent will analyze your codebase and match existing patterns.

    Example:
        cd /path/to/your/project
        autonomous-agent feature --spec feature_spec.txt
        autonomous-agent feature --spec my_feature.txt --max-iterations 3
    """
    config = load_config()
    model = model or config.get("model", DEFAULT_CONFIG["model"])

    console.print(Panel.fit(
        f"[bold green]Adding feature to existing project[/bold green]\n"
        f"Spec: {spec}\n"
        f"Project: {project_dir}\n"
        f"Model: {model}",
        title="🔧 Feature Agent"
    ))

    try:
        asyncio.run(run_feature_agent(
            spec_file=spec,
            project_dir=project_dir,
            model=model,
            max_iterations=max_iterations,
        ))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Run same command to resume.[/yellow]")


@main.command()
@click.option(
    "--project-dir",
    type=click.Path(exists=True, path_type=Path),
    default=Path.cwd(),
    help="Project directory to check",
)
def status(project_dir: Path):
    """Show progress status of the current project.

    Example:
        autonomous-agent status
        autonomous-agent status --project-dir ./my_project
    """
    feature_list = project_dir / "feature_list.json"
    progress_file = project_dir / "claude-progress.txt"

    if not feature_list.exists():
        console.print("[yellow]No feature_list.json found. Run 'build' or 'feature' first.[/yellow]")
        return

    summary = get_progress_summary(project_dir)

    table = Table(title="Project Status")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Features", str(summary["total"]))
    table.add_row("Completed", f"{summary['passing']} ✅")
    table.add_row("Remaining", f"{summary['failing']} ⏳")
    table.add_row("Progress", f"{summary['percent']:.1f}%")

    console.print(table)

    if progress_file.exists():
        console.print("\n[bold]Latest Progress Notes:[/bold]")
        notes = progress_file.read_text().strip().split("\n")
        for line in notes[-10:]:  # Last 10 lines
            console.print(f"  {line}")


@main.command()
@click.option(
    "--global",
    "global_config",
    is_flag=True,
    help="Initialize global config (~/.config/autonomous-agent/)",
)
def init(global_config: bool):
    """Initialize configuration files.

    Creates config file with default settings.

    Example:
        autonomous-agent init           # Local .autonomous-agent.yaml
        autonomous-agent init --global  # Global config
    """
    config_path = init_config(global_config=global_config)
    console.print(f"[green]Created config at: {config_path}[/green]")
    console.print("\nEdit this file to customize:")
    console.print("  - Default model")
    console.print("  - Allowed bash commands")
    console.print("  - Cost limits")


@main.command()
@click.argument("template", type=click.Choice(["app", "feature"]))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path",
)
def template(template: str, output: Path | None):
    """Generate a specification template.

    Example:
        autonomous-agent template app -o my_app_spec.txt
        autonomous-agent template feature -o feature_spec.txt
    """
    from .templates import get_template

    content = get_template(template)

    if output is None:
        output = Path(f"{template}_spec.txt")

    output.write_text(content)
    console.print(f"[green]Created template: {output}[/green]")
    console.print(f"\nEdit this file, then run:")
    if template == "app":
        console.print(f"  autonomous-agent build --spec {output}")
    else:
        console.print(f"  autonomous-agent feature --spec {output}")


if __name__ == "__main__":
    main()
