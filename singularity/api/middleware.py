"""
Singularity — HTTP middleware (Fáze 8).

RequestContextMiddleware:
  - generates / propagates X-Request-ID header
  - binds request_id into contextvars for the whole request lifecycle
  - adds X-Response-Time (ms) to every response
  - logs each request at DEBUG level via structlog
"""
from __future__ import annotations

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.request_context import clear_request_context, set_request_context

log = structlog.get_logger()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", "")
        rid, _ = set_request_context(request_id=request_id)
        t0 = time.monotonic()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = round((time.monotonic() - t0) * 1000, 2)
            response.headers["X-Request-ID"] = rid
            response.headers["X-Response-Time"] = f"{elapsed_ms}ms"
            log.debug(
                "http_request",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
                request_id=rid,
            )
            clear_request_context()
        return response
