"""
Singularity — Admin CLI (Fáze 9).

Usage:
  singularity serve [--host HOST] [--port PORT] [--workers N] [--reload]
  singularity health [--url URL]
  singularity keys create USER_ID [--url URL]
  singularity keys list [--user USER_ID] [--url URL]
  singularity keys revoke KEY [--url URL]
  singularity queue status [--url URL]
  singularity dlq list [--url URL]
  singularity dlq retry TASK_ID [--url URL]

Set SINGULARITY_URL env var to avoid passing --url on every call.
"""
from __future__ import annotations

import sys

import httpx
import typer

app = typer.Typer(name="singularity", help="Singularity admin CLI", no_args_is_help=True)

_DEFAULT_URL = "http://localhost:8001"


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _get(base: str, path: str, **params) -> dict:
    resp = httpx.get(f"{base}{path}", params={k: v for k, v in params.items() if v}, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


def _post(base: str, path: str, body: dict | None = None) -> dict:
    resp = httpx.post(f"{base}{path}", json=body or {}, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


def _delete(base: str, path: str) -> dict:
    resp = httpx.delete(f"{base}{path}", timeout=10.0)
    resp.raise_for_status()
    return resp.json()


# ── serve ─────────────────────────────────────────────────────────────────────

@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(8001, help="Bind port"),
    workers: int = typer.Option(1, help="Uvicorn worker processes"),
    reload: bool = typer.Option(False, "--reload/--no-reload", help="Auto-reload (dev only)"),
) -> None:
    """Start the Singularity API server."""
    import subprocess
    cmd = [
        sys.executable, "-m", "uvicorn", "api.main:app",
        "--host", host, "--port", str(port),
        "--workers", str(workers),
    ]
    if reload:
        cmd.append("--reload")
    subprocess.run(cmd, check=True)


# ── health ────────────────────────────────────────────────────────────────────

@app.command()
def health(
    url: str = typer.Option(_DEFAULT_URL, envvar="SINGULARITY_URL"),
) -> None:
    """Check liveness and readiness of a running server."""
    live = _get(url, "/health/live")
    typer.echo(f"live:  {live['status']}")
    try:
        ready = _get(url, "/health/ready")
        typer.echo(f"ready: {ready['status']}  strategy={ready.get('strategy', '')}")
    except httpx.HTTPStatusError as exc:
        typer.echo(f"ready: not ready ({exc.response.status_code})", err=True)


# ── keys ──────────────────────────────────────────────────────────────────────

keys_app = typer.Typer(help="Manage API keys", no_args_is_help=True)
app.add_typer(keys_app, name="keys")


@keys_app.command("create")
def keys_create(
    user_id: str = typer.Argument(..., help="User ID to create a key for"),
    url: str = typer.Option(_DEFAULT_URL, envvar="SINGULARITY_URL"),
) -> None:
    """Create a new API key for a user."""
    data = _post(url, "/api-keys", {"user_id": user_id})
    typer.echo(f"key: {data['key']}")


@keys_app.command("list")
def keys_list(
    user_id: str = typer.Option("", "--user", help="Filter by user ID"),
    url: str = typer.Option(_DEFAULT_URL, envvar="SINGULARITY_URL"),
) -> None:
    """List API keys, optionally filtered by user."""
    data = _get(url, "/api-keys", user_id=user_id)
    typer.echo(f"count: {data['count']}")
    for k in data["keys"]:
        typer.echo(f"  {k['key_prefix']}  user={k['user_id']}  revoked={k['revoked']}")


@keys_app.command("revoke")
def keys_revoke(
    key: str = typer.Argument(..., help="Full API key to revoke"),
    url: str = typer.Option(_DEFAULT_URL, envvar="SINGULARITY_URL"),
) -> None:
    """Revoke an API key."""
    data = _delete(url, f"/api-keys/{key}")
    typer.echo(f"status: {data['status']}")


# ── queue ─────────────────────────────────────────────────────────────────────

queue_app = typer.Typer(help="Task queue operations", no_args_is_help=True)
app.add_typer(queue_app, name="queue")


@queue_app.command("status")
def queue_status(
    url: str = typer.Option(_DEFAULT_URL, envvar="SINGULARITY_URL"),
) -> None:
    """Show current task queue depth."""
    data = _get(url, "/queue/status")
    typer.echo(f"queue_size: {data['queue_size']}")


# ── dlq ───────────────────────────────────────────────────────────────────────

dlq_app = typer.Typer(help="Dead-letter queue operations", no_args_is_help=True)
app.add_typer(dlq_app, name="dlq")


@dlq_app.command("list")
def dlq_list(
    url: str = typer.Option(_DEFAULT_URL, envvar="SINGULARITY_URL"),
) -> None:
    """List tasks in the dead-letter queue."""
    data = _get(url, "/dead-letter-queue")
    typer.echo(f"count: {data['count']}")
    for t in data["tasks"]:
        typer.echo(f"  {t['task_id']}  user={t['user_id']}  attempts={t['attempt']}")


@dlq_app.command("retry")
def dlq_retry(
    task_id: str = typer.Argument(..., help="Task ID to retry from DLQ"),
    url: str = typer.Option(_DEFAULT_URL, envvar="SINGULARITY_URL"),
) -> None:
    """Move a DLQ task back into the active queue."""
    data = _post(url, f"/dead-letter-queue/{task_id}/retry")
    typer.echo(f"status: {data['status']}")


if __name__ == "__main__":
    app()
