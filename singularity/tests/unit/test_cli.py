"""
Tests for Singularity admin CLI (Fáze 9).

Patches cli.main._get/_post/_delete to avoid I/O conflicts between
the Typer CliRunner and httpx mock transports.
"""
from unittest.mock import patch

import httpx
import pytest
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def test_health_shows_live_and_ready():
    with patch("cli.main._get", side_effect=[
        {"status": "alive"},
        {"status": "ready", "strategy": "static"},
    ]):
        result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
    assert "alive" in result.output
    assert "ready" in result.output
    assert "static" in result.output


def test_keys_create_prints_key():
    with patch("cli.main._post", return_value={"key": "sk-sg-testkey", "user_id": "alice"}):
        result = runner.invoke(app, ["keys", "create", "alice"])
    assert result.exit_code == 0
    assert "sk-sg-testkey" in result.output


def test_keys_list_shows_count():
    with patch("cli.main._get", return_value={
        "count": 2,
        "keys": [
            {"key_prefix": "sk-sg-abc...", "user_id": "bob", "revoked": False},
            {"key_prefix": "sk-sg-def...", "user_id": "bob", "revoked": True},
        ],
    }):
        result = runner.invoke(app, ["keys", "list"])
    assert result.exit_code == 0
    assert "count: 2" in result.output
    assert "bob" in result.output


def test_queue_status_shows_depth():
    with patch("cli.main._get", return_value={"queue_size": 5}):
        result = runner.invoke(app, ["queue", "status"])
    assert result.exit_code == 0
    assert "queue_size: 5" in result.output


def test_dlq_list_shows_tasks():
    with patch("cli.main._get", return_value={
        "count": 1,
        "tasks": [{"task_id": "abc-123", "user_id": "carol", "attempt": 3}],
    }):
        result = runner.invoke(app, ["dlq", "list"])
    assert result.exit_code == 0
    assert "count: 1" in result.output
    assert "abc-123" in result.output


def test_dlq_retry_reports_status():
    with patch("cli.main._post", return_value={"status": "requeued", "task_id": "abc-123"}):
        result = runner.invoke(app, ["dlq", "retry", "abc-123"])
    assert result.exit_code == 0
    assert "requeued" in result.output
