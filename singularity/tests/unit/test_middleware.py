"""
Tests for RequestContextMiddleware + request context (Fáze 8).
"""
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.middleware import RequestContextMiddleware
from core.request_context import get_request_id


@pytest.fixture()
def app():
    _app = FastAPI()
    _app.add_middleware(RequestContextMiddleware)

    @_app.get("/ping")
    async def ping():
        return {"request_id": get_request_id()}

    return _app


@pytest.mark.asyncio
async def test_response_has_request_id_header(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/ping")
    assert "x-request-id" in r.headers
    assert len(r.headers["x-request-id"]) == 36  # UUID4 canonical form


@pytest.mark.asyncio
async def test_response_has_response_time_header(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/ping")
    assert "x-response-time" in r.headers
    assert r.headers["x-response-time"].endswith("ms")


@pytest.mark.asyncio
async def test_client_request_id_is_echoed(app):
    custom_id = "test-req-abc-123"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/ping", headers={"X-Request-ID": custom_id})
    assert r.headers["x-request-id"] == custom_id


@pytest.mark.asyncio
async def test_request_id_available_inside_handler(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/ping")
    body = r.json()
    assert body["request_id"] == r.headers["x-request-id"]


@pytest.mark.asyncio
async def test_sequential_requests_get_unique_ids(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.get("/ping")
        r2 = await client.get("/ping")
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]
