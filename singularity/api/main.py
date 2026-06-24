"""
Singularity — FastAPI vrstva.

Endpointy:
  POST /task                   Zadání úkolu (sync, volitelně force_provider)
  POST /task/stream            SSE streaming verze (Fáze 1)
  POST /task/async             Async fronta — vrátí task_id okamžitě (Fáze 3)
  POST /task/compare           Paralelní run na Claude + Gemini (Fáze 3)
  POST /task/batch             Dávkové odeslání úkolů do fronty (Fáze 4)
  GET  /task/{id}/status       Stav async tasku (Fáze 3)
  GET  /task/{id}/result       Výsledek async tasku (Fáze 3)
  GET  /task/{id}/wait         Long-poll čekání na výsledek (Fáze 5)
  GET  /queue/status           Stav fronty (Fáze 4)
  POST /approve                Human-in-the-loop schválení/zamítnutí
  POST /e-stop                 Nouzové zastavení
  GET  /memory/{uid}           Zobrazení paměti uživatele
  GET  /sessions/{uid}         Konverzační historie + náklady (Fáze 1)
  GET  /sessions/{uid}/export  JSON export session (Fáze 3)
  GET  /sessions               Seznam aktivních uživatelů (Fáze 1)
  GET  /providers              Stav providerů
  GET  /health/providers       Okamžitý health check všech providerů (Fáze 2)
  POST /router/strategy        Runtime změna routing strategie
  GET  /metrics                Prometheus metriky
  GET  /tasks/{id}/providers   Který model zpracoval který krok
  GET  /dashboard              Admin dashboard (Fáze 2)
  POST /budget/{uid}           Nastavení cost limitu uživatele (Fáze 4)
  GET  /budget/{uid}           Zobrazení stavu budgetu uživatele (Fáze 4)
  DELETE /budget/{uid}         Odstranění cost limitu uživatele (Fáze 4)
  POST /rate-limits/{uid}      Nastavení RPM limitu uživatele (Fáze 5)
  GET  /rate-limits/{uid}      Stav RPM limitu uživatele (Fáze 5)
  DELETE /rate-limits/{uid}    Odebrání RPM limitu uživatele (Fáze 5)
  WS   /ws/{uid}               Real-time node-level streaming (Fáze 1)
  GET  /health                 Health check
"""
from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel

from api.dashboard import get_dashboard_html
from core import telemetry
from core.budget_manager import BudgetManager
from core.graph import SingularityCore
from core.health_monitor import HealthMonitor
from core.session_store import ConversationTurn, SessionStore, estimate_cost
from core.task_queue import TaskPriority, TaskQueue
from core.user_limiter import UserRateLimiter
from evals.evaluator import OmegaEvaluator

log = structlog.get_logger()

# Singletony (jeden na proces)
core: SingularityCore | None = None
evaluator: OmegaEvaluator | None = None
health_monitor: HealthMonitor | None = None
task_queue: TaskQueue = TaskQueue()
session_store: SessionStore = SessionStore()
budget_manager: BudgetManager = BudgetManager()
user_limiter: UserRateLimiter = UserRateLimiter()

# Jednoduchý in-memory záznam provider_log per task (v produkci: Redis)
_task_provider_log: dict[str, dict] = {}

_MAX_CONTEXT_TURNS = 3  # kolik posledních turnů vstupuje jako kontext


def _build_session_context(user_id: str) -> str:
    """Sestaví řetězec posledních N turnů z session store pro multi-turn kontext."""
    history = session_store.get_history(user_id)
    turns = history["turns"][-_MAX_CONTEXT_TURNS:]
    if not turns:
        return ""
    return "\n".join(
        f"[Turn {i + 1}]\nTask: {t['task']}\nResponse: {t['response'][:300]}"
        for i, t in enumerate(turns)
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler — inicializace singletonů, health monitoru a task queue."""
    global core, evaluator, health_monitor
    core = SingularityCore()
    evaluator = OmegaEvaluator()
    health_monitor = HealthMonitor(core.router, interval_s=30.0)
    health_monitor.start()
    task_queue.start(core)
    log.info("singularity_started", strategy=core.router.strategy)
    yield
    health_monitor.stop()
    task_queue.stop()
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
    callback_url: str = ""     # Fáze 4: webhook po dokončení async tasku
    priority: str = "NORMAL"   # Fáze 5: CRITICAL | HIGH | NORMAL | LOW


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


class BatchTaskRequest(BaseModel):
    tasks: list[TaskRequest]


class BudgetRequest(BaseModel):
    limit_usd: float


class RateLimitRequest(BaseModel):
    rpm: int


# ── REST endpointy ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "version": "0.1.0"}


@app.post("/task", response_model=TaskResponse)
async def submit_task(req: TaskRequest) -> TaskResponse:
    assert core is not None and evaluator is not None
    session_id = str(uuid.uuid4())
    log.info("task_received", user_id=req.user_id, session_id=session_id)

    session_context = _build_session_context(req.user_id)

    try:
        result = await core.run(
            task=req.task,
            user_id=req.user_id,
            session_id=session_id,
            approved=req.approved,
            force_provider=req.force_provider,
            session_context=session_context,
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

    # Ulož turn do session store (Fáze 3: včetně eval_scores)
    cost = estimate_cost(result["response"], result["provider_log"])
    session_store.add_turn(
        req.user_id,
        ConversationTurn(
            task=req.task,
            response=result["response"],
            provider_log=result["provider_log"],
            risk_score=result.get("risk_score", 0.0),
            cost_usd=cost,
            eval_scores=eval_scores,
        ),
    )

    return TaskResponse(
        session_id=session_id,
        response=result["response"],
        eval_scores=eval_scores,
        provider_log=result["provider_log"],
    )


@app.post("/task/async")
async def submit_task_async(req: TaskRequest) -> dict:
    """Zařadí úkol do fronty a okamžitě vrátí task_id (Fáze 3 + 5)."""
    assert core is not None
    if not budget_manager.is_allowed(req.user_id):
        raise HTTPException(status_code=402, detail="Budget exceeded")
    if not user_limiter.check_and_record(req.user_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    try:
        priority = TaskPriority[req.priority.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Neznámá priorita: {req.priority}")
    session_context = _build_session_context(req.user_id)
    task_id = await task_queue.submit(
        task=req.task,
        user_id=req.user_id,
        approved=req.approved,
        force_provider=req.force_provider,
        session_context=session_context,
        callback_url=req.callback_url,
        priority=priority,
    )
    return {"task_id": task_id, "status": "queued", "priority": priority.name, "queue_size": task_queue.queue_size()}


@app.get("/task/{task_id}/status")
async def get_task_status(task_id: str) -> dict:
    """Vrátí stav async tasku (Fáze 3)."""
    status = task_queue.get_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Neznámé task_id")
    return status


@app.get("/task/{task_id}/result")
async def get_task_result(task_id: str) -> dict:
    """Vrátí výsledek dokončeného async tasku (Fáze 3)."""
    result = task_queue.get_result(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Neznámé task_id")
    return result


@app.get("/task/{task_id}/wait")
async def wait_for_task(task_id: str, timeout: float = 60.0) -> dict:
    """
    Long-poll: blokuje až do dokončení tasku nebo vypršení timeoutu (Fáze 5).
    timeout: maximální čekání v sekundách (výchozí 60, max 300).
    """
    timeout = min(max(timeout, 1.0), 300.0)
    result = await task_queue.wait(task_id, timeout=timeout)
    if result is None:
        status = task_queue.get_status(task_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Neznámé task_id")
        raise HTTPException(status_code=408, detail="Timeout — task ještě nedoběhl")
    return result


@app.post("/task/compare")
async def compare_task(req: TaskRequest) -> dict:
    """
    Spustí úkol paralelně na Claude i Gemini a vrátí porovnání (Fáze 3).
    Pokud Gemini není k dispozici, vrátí pouze výsledek Clauda.
    """
    assert core is not None
    session_context = _build_session_context(req.user_id)
    sid_claude = str(uuid.uuid4())
    sid_gemini = str(uuid.uuid4())

    run_kwargs = dict(
        task=req.task,
        user_id=req.user_id,
        approved=req.approved,
        session_context=session_context,
    )

    results = await asyncio.gather(
        core.run(**run_kwargs, session_id=sid_claude, force_provider="claude"),
        core.run(**run_kwargs, session_id=sid_gemini, force_provider="gemini"),
        return_exceptions=True,
    )

    def _fmt(r, sid):
        if isinstance(r, Exception):
            return {"error": str(r), "session_id": sid}
        return {**r, "session_id": sid}

    return {
        "task": req.task,
        "claude": _fmt(results[0], sid_claude),
        "gemini": _fmt(results[1], sid_gemini),
        "gemini_enabled": core.router.gemini_enabled,
    }


@app.post("/task/batch")
async def submit_task_batch(req: BatchTaskRequest) -> dict:
    """
    Dávkové odeslání úkolů do fronty (Fáze 4).
    Maximum 10 úkolů na požadavek.
    """
    assert core is not None
    if len(req.tasks) == 0:
        raise HTTPException(status_code=400, detail="Prázdná dávka")
    if len(req.tasks) > 10:
        raise HTTPException(status_code=400, detail="Maximum je 10 úkolů na dávku")

    task_ids = []
    for t in req.tasks:
        if not budget_manager.is_allowed(t.user_id):
            raise HTTPException(status_code=402, detail=f"Budget exceeded for user {t.user_id}")
        session_context = _build_session_context(t.user_id)
        task_id = await task_queue.submit(
            task=t.task,
            user_id=t.user_id,
            approved=t.approved,
            force_provider=t.force_provider,
            session_context=session_context,
            callback_url=t.callback_url,
        )
        task_ids.append(task_id)

    return {"task_ids": task_ids, "count": len(task_ids), "queue_size": task_queue.queue_size()}


@app.get("/queue/status")
async def queue_status() -> dict:
    """Vrátí aktuální stav fronty (Fáze 4)."""
    return {"queue_size": task_queue.queue_size()}


@app.post("/task/stream")
async def stream_task(req: TaskRequest) -> StreamingResponse:
    """SSE streaming endpoint: posílá progress event po každém uzlu grafu."""
    assert core is not None
    session_id = str(uuid.uuid4())
    log.info("task_stream_received", user_id=req.user_id, session_id=session_id)

    session_context = _build_session_context(req.user_id)

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
                session_context=session_context,
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


@app.get("/sessions/{user_id}/export")
async def export_session(user_id: str) -> Response:
    """JSON export kompletní session historie (Fáze 3)."""
    history = session_store.get_history(user_id)
    payload = json.dumps(history, ensure_ascii=False, indent=2)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="session_{user_id}.json"'},
    )


@app.get("/health/providers")
async def health_check_providers() -> dict:
    """Okamžitý health check všech providerů (Fáze 2)."""
    assert health_monitor is not None
    results = await health_monitor.run_once()
    return {"results": results}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    """Admin dashboard — live přehled providerů, sessionů a metrik (Fáze 2)."""
    return HTMLResponse(content=get_dashboard_html())


# ── Budget endpointy (Fáze 4) ──────────────────────────────────────────────────

@app.post("/budget/{user_id}")
async def set_budget(user_id: str, req: BudgetRequest) -> dict:
    """Nastaví nebo aktualizuje cost limit uživatele (Fáze 4)."""
    budget_manager.set_budget(user_id, req.limit_usd)
    return budget_manager.get_status(user_id)


@app.get("/budget/{user_id}")
async def get_budget(user_id: str) -> dict:
    """Vrátí stav budgetu uživatele (Fáze 4)."""
    return budget_manager.get_status(user_id)


@app.delete("/budget/{user_id}")
async def delete_budget(user_id: str) -> dict:
    """Odstraní cost limit uživatele (nastaví na neomezeno, Fáze 4)."""
    budget_manager.set_budget(user_id, 0.0)  # 0 → None = neomezeno
    return budget_manager.get_status(user_id)


# ── Per-user rate limit endpointy (Fáze 5) ────────────────────────────────────

@app.post("/rate-limits/{user_id}")
async def set_rate_limit(user_id: str, req: RateLimitRequest) -> dict:
    """Nastaví RPM limit pro uživatele (Fáze 5). rpm=0 odebere omezení."""
    user_limiter.set_limit(user_id, req.rpm)
    return user_limiter.get_status(user_id)


@app.get("/rate-limits/{user_id}")
async def get_rate_limit(user_id: str) -> dict:
    """Vrátí stav RPM limitu a počet požadavků za poslední minutu (Fáze 5)."""
    return user_limiter.get_status(user_id)


@app.delete("/rate-limits/{user_id}")
async def delete_rate_limit(user_id: str) -> dict:
    """Odebere RPM limit a resetuje counter uživatele (Fáze 5)."""
    user_limiter.reset(user_id)
    return user_limiter.get_status(user_id)


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
