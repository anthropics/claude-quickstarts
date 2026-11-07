"""
Singularity — Structured logging configuration (Fáze 10).

Configures structlog globally:
  - merges per-request contextvars (request_id, user_id from Fáze 8)
  - JSON output in production, ConsoleRenderer in dev
  - feeds events into LogBuffer for GET /logs/recent
"""
from __future__ import annotations

import logging

import structlog

from core.log_buffer import LogBuffer


def configure_logging(
    level: str = "INFO",
    log_format: str = "json",
    log_buffer: LogBuffer | None = None,
) -> None:
    """
    Configure structlog globally.

    level:      Python log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    log_format: "json" for structured JSON output; "console" for human-readable
    log_buffer: optional LogBuffer processor inserted before the renderer
    """
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_buffer is not None:
        shared_processors.append(log_buffer)

    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,  # False so tests can reconfigure
    )

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        level=numeric_level,
        force=True,
    )
