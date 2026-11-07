"""
Unit test — app version is a single source of truth (no drift).
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import APP_VERSION, app


def _pyproject_version() -> str:
    root = Path(__file__).resolve().parents[2]  # singularity/
    data = tomllib.loads((root / "pyproject.toml").read_text())
    return data["project"]["version"]


def test_app_version_is_semver():
    assert re.match(r"^\d+\.\d+\.\d+", APP_VERSION)


def test_app_version_matches_pyproject():
    # importlib.metadata may report the installed dist version; when running
    # from source the fallback must equal pyproject's declared version.
    assert APP_VERSION == _pyproject_version()


def test_fastapi_app_version_synced():
    assert app.version == APP_VERSION


@pytest.mark.asyncio
async def test_health_reports_app_version():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://v") as c:
        r = await c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == APP_VERSION
    assert body["version"] != "0.1.0"  # regression guard for the old hardcode
