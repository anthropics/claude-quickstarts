"""
Unit testy — jednoduché rozhraní pro pokládání tasků (`GET /ui`). Plně offline.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from api.task_ui import get_task_ui_html


def test_get_task_ui_html_shape():
    html = get_task_ui_html()
    assert isinstance(html, str) and len(html) > 500
    assert "<form" in html
    assert "fetch(" in html
    # odesílá na /task a čte klíčová pole odpovědi
    assert "/task" in html
    assert 'id="task"' in html
    assert "provider_log" in html


@pytest.mark.asyncio
async def test_ui_route_serves_html():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://ui") as c:
        r = await c.get("/ui")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    body = r.text
    assert 'id="task"' in body
    assert "/task" in body
