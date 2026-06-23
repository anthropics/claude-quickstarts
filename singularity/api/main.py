"""
Singularity — FastAPI vrstva.

Endpointy:
  POST /task                 Zadání úkolu (volitelně force_provider)
  POST /task/stream          SSE streaming verze /task (Fáze 1)
  POST /approve              Human-in-the-loop schválení/zamítnutí
  POST /e-stop               Nouzové zastavení
  GET  /memory/{uid}         Zobrazení paměti uživatele
  GET  /sessions/{uid}       Konverzační historie + náklady (Fáze 1)
  GET  /sessions             Seznam aktivních uživatelů (Fáze 1)
  GET  /providers            Stav providerů (health, cost, latency, cooldown)
  POST /router/strategy      Runtime změna routing strategie
  GET  /metrics              Prometheus metriky
  GET  /tasks/{id}/providers Který model zpracoval který krok
  WS   /ws/{uid}             Real-time node-level streaming (Fáze 1)
  GET  /health               Health check
"""
from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from core import telemetry
from core.graph import SingularityCore
from core.session_store import ConversationTurn, SessionStore, estimate_cost
from evals.evaluator import OmegaEvaluator

log = structlog.get_logger()

# Singletony (jeden na proces)
core: SingularityCore | None = None
evaluator: OmegaEvaluator | None = None
session_store: SessionStore = SessionStore()

# Jednoduchý in-memory záznam provider_log per task (v produkci: Redis)
_task_provider_log: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler — inicializace singletonů (náhrada deprecated on_event)."""
    global core, evaluator
    core = SingularityCore()
    evaluator = OmegaEvaluator()
    log.info("singularity_started", strategy=core.router.strategy)
    yield
    log.info("singularity_shutdown")


app = FastAPI(
    title="Singularity API",
    version="0.1.0",
    description="Multi-LLM Meta-Cognitive Core (Claude + Gemini)",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # V produkci: omezit na konkrétní domény
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Modely ────────────────────────────────────────────────────────────────────

class TaskRequest(BaseModel):
    task: str
    user_id: str = "default"
    approved: bool = False
    force_provider: str = ""   # "" | "claude" | "gemini"


class ApprovalRequest(BaseModel):
    session_id: str
    approved: bool


class StrategyRequest(BaseModel):
    strategy: str


class TaskResponse(BaseModel):
    session_id: str
    response: str
    eval_scores: dict
    provider_log: dict


# ── REST endpointy ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "version": "0.1.0"}


@app.post("/task", response_model=TaskResponse)
async def submit_task(req: TaskRequest) -> TaskResponse:
    assert core is not None and evaluator is not None
    session_id = str(uuid.uuid4())
    log.info("task_received", user_id=req.user_id, session_id=session_id)

    try:
        result = await core.run(
            task=req.task,
            user_id=req.user_id,
            session_id=session_id,
            approved=req.approved,
            force_provider=req.force_provider,
        )
    except Exception as exc:
        log.error("task_error", error=str(exc), session_id=session_id)
        raise HTTPException(status_code=500, detail=str(exc))

    _task_provider_log[session_id] = result["provider_log"]

    try:
        eval_scores = evaluator.evaluate_response(req.task, result["response"])
    except Exception as exc:
        log.warning("eval_failed", error=str(exc))
        eval_scores = {}

    # Ulož turn do session store
    cost = estimate_cost(result["response"], result["provider_log"])
    session_store.add_turn(
        req.user_id,
        ConversationTurn(
            task=req.task,
            response=result["response"],
            provider_log=result["provider_log"],
            risk_score=result.get("risk_score", 0.0),
            cost_usd=cost,
        ),
    )

    return TaskResponse(
        session_id=session_id,
        response=result["response"],
        eval_scores=eval_scores,
        provider_log=result["provider_log"],
    )


@app.post("/task/stream")
async def stream_task(req: TaskRequest) -> StreamingResponse:
    """SSE streaming endpoint: posílá progress event po každém uzlu grafu."""
    assert core is not None
    session_id = str(uuid.uuid4())
    log.info("task_stream_received", user_id=req.user_id, session_id=session_id)

    async def event_generator():
        started = json.dumps({"event": "started", "session_id": session_id})
        yield f"data: {started}\n\n"
        try:
            async for event in core.run_stream(
                task=req.task,
                user_id=req.user_id,
                session_id=session_id,
                approved=req.approved,
                force_provider=req.force_provider,
            ):
                payload = {**event, "session_id": session_id}
                yield f"data: {json.dumps(payload)}\n\n"

                if event.get("event") == "completed":
                    _task_provider_log[session_id] = event.get("provider_log", {})
                    cost = estimate_cost(
                        event.get("response", ""), event.get("provider_log", {})
                    )
                    session_store.add_turn(
                        req.user_id,
                        ConversationTurn(
                            task=req.task,
                            response=event.get("response", ""),
                            provider_log=event.get("provider_log", {}),
                            risk_score=event.get("risk_score", 0.0),
                            cost_usd=cost,
                        ),
                    )
        except Exception as exc:
            err = json.dumps({"event": "error", "message": str(exc), "session_id": session_id})
            yield f"data: {err}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/approve")
async def approve_task(req: ApprovalRequest) -> dict:
    status = "approved" if req.approved else "rejected"
    log.info("approval_decision", session_id=req.session_id, status=status)
    return {"status": status, "session_id": req.session_id}


@app.post("/e-stop")
async def emergency_stop() -> dict:
    assert core is not None
    core.e_stop()
    log.critical("E_STOP_API_TRIGGERED")
    return {"status": "E_STOP_ACTIVATED"}


@app.get("/memory/{user_id}")
async def get_memory(user_id: str) -> dict:
    assert core is not None
    try:
        memories = core.memory.get_all(user_id=user_id)
        return {"user_id": user_id, "count": len(memories), "memories": memories}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/providers")
async def list_providers() -> dict:
    assert core is not None
    return {
        "strategy": core.router.strategy,
        "gemini_enabled": core.router.gemini_enabled,
        "providers": [p.status() for p in core.router.all_providers()],
    }


@app.post("/router/strategy")
async def set_strategy(req: StrategyRequest) -> dict:
    assert core is not None
    try:
        core.router.set_strategy(req.strategy)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok", "strategy": core.router.strategy}


@app.get("/metrics")
async def metrics() -> Response:
    payload, content_type = telemetry.metrics_payload()
    return Response(content=payload, media_type=content_type)


@app.get("/tasks/{session_id}/providers")
async def task_providers(session_id: str) -> dict:
    plog = _task_provider_log.get(session_id)
    if plog is None:
        raise HTTPException(status_code=404, detail="Neznámé session_id")
    return {"session_id": session_id, "provider_log": plog}


@app.get("/sessions/{user_id}")
async def get_session(user_id: str) -> dict:
    """Vrátí konverzační historii a kumulativní náklady pro uživatele."""
    return session_store.get_history(user_id)


@app.get("/sessions")
async def list_sessions() -> dict:
    """Vrátí seznam uživatelů s aktivními session."""
    return {"users": session_store.list_users()}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str) -> None:
    """
    Node-level streaming (Fáze 1): klient dostane event po každém uzlu grafu.

    Protokol:
      ← {"event": "started",        "session_id": "..."}
      ← {"event": "node_completed", "node": "plan", "provider": "gemini", ...}
      ← {"event": "node_completed", "node": "execute", ...}
      ...
      ← {"event": "completed",      "response": "...", "provider_log": {...}}
    """
    assert core is not None
    await websocket.accept()
    log.info("ws_connected", user_id=user_id)

    try:
        while True:
            data = await websocket.receive_json()
            task = data.get("task", "")
            session_id = str(uuid.uuid4())

            await websocket.send_json({"event": "started", "session_id": session_id})

            try:
                async for event in core.run_stream(
                    task=task,
                    user_id=user_id,
                    session_id=session_id,
                    approved=data.get("approved", False),
                    force_provider=data.get("force_provider", ""),
                ):
                    await websocket.send_json({**event, "session_id": session_id})

                    if event.get("event") == "completed":
                        _task_provider_log[session_id] = event.get("provider_log", {})
                        cost = estimate_cost(
                            event.get("response", ""), event.get("provider_log", {})
                        )
                        session_store.add_turn(
                            user_id,
                            ConversationTurn(
                                task=task,
                                response=event.get("response", ""),
                                provider_log=event.get("provider_log", {}),
                                risk_score=event.get("risk_score", 0.0),
                                cost_usd=cost,
                            ),
                        )
            except Exception as exc:
                await websocket.send_json({"event": "error", "message": str(exc)})
    except WebSocketDisconnect:
        log.info("ws_disconnected", user_id=user_id)
