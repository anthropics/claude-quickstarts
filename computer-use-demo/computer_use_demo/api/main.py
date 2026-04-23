"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from computer_use_demo.api import health
from computer_use_demo.api.chats import controllers as chat_routes, ws as chat_ws
from computer_use_demo.api.chats.services.agent_runner import AgentRunner
from computer_use_demo.api.chats.services.chat_manager import ChatManager
from computer_use_demo.api.chats.services.event_bus import EventBus
from computer_use_demo.api.db import create_all, dispose, init_engine
from computer_use_demo.api.system import controllers as system_routes
from computer_use_demo.settings import CORS_ALLOW_ORIGINS

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine()
    await create_all()
    bus = EventBus()
    runner = AgentRunner(bus)
    manager = ChatManager(bus=bus, runner=runner)
    app.state.bus = bus
    app.state.agent_runner = runner
    app.state.chat_manager = manager
    try:
        yield
    finally:
        await manager.shutdown_all()
        await dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Computer Use Demo", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOW_ORIGINS or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(system_routes.router)
    app.include_router(chat_routes.router)
    app.include_router(chat_ws.router)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @app.get("/", include_in_schema=False)
        async def index() -> FileResponse:
            return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
