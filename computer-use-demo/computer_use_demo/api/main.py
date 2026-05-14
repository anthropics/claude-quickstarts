import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .routers import messages, sessions, vnc
from .schemas import HealthResponse

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Computer Use Demo API",
    version="1.0.0",
    description="FastAPI backend for the Anthropic Computer Use demo.",
    lifespan=lifespan,
)

# Routers
app.include_router(sessions.router)
app.include_router(messages.router)
app.include_router(vnc.router)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    return HealthResponse()


@app.get("/config", tags=["config"])
async def config() -> dict:
    """Return server-side defaults the frontend can use to pre-fill the form."""
    return {
        "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
    }


# Serve static frontend assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(str(STATIC_DIR / "index.html"))
