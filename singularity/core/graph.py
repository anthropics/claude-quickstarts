"""
Singularity — SingularityCore (LangGraph stavový automat).

Kognitivní smyčka:  PLAN → EXECUTE → CRITIQUE → (AWAIT_APPROVAL?) → SYNTHESIZE → REFLECT

Rozšíření oproti Omega:
  - multi-LLM orchestrace přes LLMRouter (Claude + Gemini)
  - provider_log: záznam, který model zpracoval který krok
  - provider_switches: počet failover přepnutí

Bezpečnostní vrstvy:
  1. Risk scoring (Kritik)
  2. Human-in-the-loop (await_approval)
  3. E-STOP (okamžité přerušení)
  4. Max iterations guard
"""
from __future__ import annotations

from typing import Annotated

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from agents.base import AgentRole
from agents.swarm import SingularitySwarm
from config.settings import settings
from core.limiter import ProviderRateLimiter
from core.router import LLMRouter
from memory.mem0_store import OmegaMemory
from providers.claude_provider import ClaudeProvider

log = structlog.get_logger()


class SingularityState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    session_id: str
    task: str
    agent_outputs: dict
    risk_score: float
    awaiting_approval: bool
    approved: bool
    final_response: str
    iteration: int
    e_stop: bool
    provider_log: dict          # AgentRole.value → provider name
    active_provider: str
    force_provider: str         # "" = nech routeru, jinak vynuť provider
    session_context: str        # multi-turn: posledních N turnů (Fáze 2)


def build_router(strategy: str | None = None) -> LLMRouter:
    """Sestaví LLMRouter z konfigurace (Claude vždy, Gemini volitelně)."""
    claude = ClaudeProvider(
        api_key=settings.anthropic_api_key.get_secret_value(),
        model=settings.primary_cloud_model,
    )

    gemini = None
    if settings.enable_gemini and settings.gemini_api_key is not None:
        try:
            from providers.gemini_provider import GeminiProvider

            gemini = GeminiProvider(
                api_key=settings.gemini_api_key.get_secret_value(),
                model=settings.gemini_model,
            )
        except Exception as exc:
            log.warning("gemini_init_failed_degrading_to_claude", error=str(exc))
            gemini = None

    return LLMRouter(claude=claude, gemini=gemini, strategy=strategy or settings.routing_strategy)


class SingularityCore:
    """LangGraph orchestrátor implementující kognitivní smyčku Singularity."""

    def __init__(self, router: LLMRouter | None = None) -> None:
        self.router = router or build_router()
        self.limiter = ProviderRateLimiter()
        self.swarm = SingularitySwarm(self.router, self.limiter)
        self.memory = OmegaMemory()
        self.graph = self._build_graph()

    # ── Sestavení grafu ────────────────────────────────────────────────────────

    def _build_graph(self):
        builder = StateGraph(SingularityState)

        builder.add_node("plan", self._plan_node)
        builder.add_node("execute", self._execute_node)
        builder.add_node("critique", self._critique_node)
        builder.add_node("await_approval", self._await_approval_node)
        builder.add_node("synthesize", self._synthesize_node)
        builder.add_node("reflect", self._reflect_node)
        builder.add_node("e_stop", self._e_stop_node)

        builder.set_entry_point("plan")
        builder.add_edge("plan", "execute")
        builder.add_edge("execute", "critique")

        builder.add_conditional_edges(
            "critique",
            self._route_after_critique,
            {"await_approval": "await_approval", "synthesize": "synthesize", "e_stop": "e_stop"},
        )
        builder.add_conditional_edges(
            "await_approval",
            self._route_after_approval,
            {"synthesize": "synthesize", "plan": "plan", "e_stop": "e_stop"},
        )

        builder.add_edge("synthesize", "reflect")
        builder.add_edge("reflect", END)
        builder.add_edge("e_stop", END)

        return builder.compile()

    # ── Uzly ────────────────────────────────────────────────────────────────────

    async def _plan_node(self, state: SingularityState) -> dict:
        if state.get("e_stop"):
            return {}

        log.info("node_plan", task=state["task"][:80])

        # Kritická oprava z Omega: paměť nesmí shodit graf
        try:
            memories = self.memory.search(state["task"], user_id=state["user_id"], limit=3)
        except Exception as exc:
            log.warning("memory_search_degraded", error=str(exc))
            memories = []
        memory_context = (
            "\n".join(m.get("memory", "") for m in memories)
            if memories
            else "Žádné relevantní vzpomínky (paměť dočasně nedostupná)."
        )

        session_ctx = state.get("session_context", "")
        full_context = f"Dostupné vzpomínky:\n{memory_context}"
        if session_ctx:
            full_context = f"Historie konverzace:\n{session_ctx}\n\n{full_context}"

        output = await self.swarm.run_agent(
            AgentRole.PLANNER,
            state["task"],
            context=full_context,
        )

        return {
            "agent_outputs": {**state.get("agent_outputs", {}), AgentRole.PLANNER: output},
            "messages": [AIMessage(content=f"[PLÁNOVAČ]\n{output.content}")],
            "iteration": state.get("iteration", 0) + 1,
            "provider_log": {**state.get("provider_log", {}), "plan": output.provider_used},
            "active_provider": output.provider_used,
        }

    async def _execute_node(self, state: SingularityState) -> dict:
        plan = state["agent_outputs"].get(AgentRole.PLANNER)
        context = plan.content if plan else ""

        outputs = await self.swarm.orchestrate(
            state["task"],
            roles=[AgentRole.RESEARCHER, AgentRole.PROGRAMMER],
            context=context,
        )

        merged = {**state.get("agent_outputs", {}), **outputs}
        messages = [
            AIMessage(content=f"[{r.value.upper()}]\n{o.content}") for r, o in outputs.items()
        ]
        plog = {**state.get("provider_log", {})}
        for r, o in outputs.items():
            plog[r.value] = o.provider_used

        return {"agent_outputs": merged, "messages": messages, "provider_log": plog}

    async def _critique_node(self, state: SingularityState) -> dict:
        all_outputs = "\n\n".join(
            f"=={r.value}==\n{o.content}" for r, o in state.get("agent_outputs", {}).items()
        )

        critique = await self.swarm.run_agent(
            AgentRole.CRITIC, state["task"], context=all_outputs
        )

        max_risk = max(
            [o.risk_score for o in state.get("agent_outputs", {}).values()] + [critique.risk_score]
        )

        merged = {**state.get("agent_outputs", {}), AgentRole.CRITIC: critique}
        plog = {**state.get("provider_log", {}), "critique": critique.provider_used}

        return {
            "agent_outputs": merged,
            "risk_score": max_risk,
            "awaiting_approval": max_risk >= settings.risk_threshold,
            "messages": [AIMessage(content=f"[KRITIK]\n{critique.content}")],
            "provider_log": plog,
        }

    async def _await_approval_node(self, state: SingularityState) -> dict:
        log.warning(
            "awaiting_human_approval",
            risk_score=state["risk_score"],
            task=state["task"][:80],
        )
        return {
            "awaiting_approval": True,
            "messages": [
                AIMessage(
                    content=(
                        f"⚠️ RIZIKO {state['risk_score']:.2f} ≥ {settings.risk_threshold} "
                        "— čekám na schválení operátora."
                    )
                )
            ],
        }

    async def _synthesize_node(self, state: SingularityState) -> dict:
        all_outputs = "\n\n".join(
            f"=={r.value}==\n{o.content}" for r, o in state.get("agent_outputs", {}).items()
        )

        synthesis = await self.swarm.run_agent(
            AgentRole.COMMUNICATOR, state["task"], context=all_outputs
        )

        try:
            self.memory.store_episode(
                content=f"TASK: {state['task']}\nRESULT: {synthesis.content[:500]}",
                user_id=state["user_id"],
                session_id=state["session_id"],
            )
        except Exception as exc:
            log.warning("episode_store_failed", error=str(exc))

        plog = {**state.get("provider_log", {}), "synthesize": synthesis.provider_used}
        return {
            "final_response": synthesis.content,
            "messages": [AIMessage(content=synthesis.content)],
            "provider_log": plog,
        }

    async def _reflect_node(self, state: SingularityState) -> dict:
        if state["risk_score"] < 0.4:
            try:
                self.memory.store_workflow(
                    name=f"workflow_{state['session_id'][:8]}",
                    steps=[
                        state["task"],
                        "PLAN → EXECUTE → CRITIQUE → SYNTHESIZE",
                        f"risk_score={state['risk_score']:.2f}",
                        f"providers={state.get('provider_log', {})}",
                    ],
                    user_id=state["user_id"],
                )
                log.info("workflow_saved", session=state["session_id"][:8])
            except Exception as exc:
                log.warning("workflow_save_failed", error=str(exc))

            msg = (
                f"✅ Reflexe: iterace={state['iteration']}, risk={state['risk_score']:.2f}. "
                "Workflow uloženo."
            )
        else:
            msg = (
                f"⚠️ Reflexe: risk={state['risk_score']:.2f}, "
                "workflow neuloženo (překročen práh rizika)."
            )

        return {"messages": [AIMessage(content=msg)]}

    async def _e_stop_node(self, state: SingularityState) -> dict:
        log.critical("E_STOP_ACTIVATED", session=state.get("session_id"))
        return {
            "final_response": "🔴 E-STOP: Všechny procesy zastaveny operátorem.",
            "e_stop": True,
            "messages": [AIMessage(content="🔴 E-STOP aktivován operátorem.")],
        }

    # ── Routery ──────────────────────────────────────────────────────────────────

    def _route_after_critique(self, state: SingularityState) -> str:
        if state.get("e_stop"):
            return "e_stop"
        if state.get("awaiting_approval") and settings.require_human_approval:
            return "await_approval"
        return "synthesize"

    def _route_after_approval(self, state: SingularityState) -> str:
        if state.get("e_stop"):
            return "e_stop"
        if state.get("approved"):
            return "synthesize"
        if state.get("iteration", 0) < settings.max_iterations:
            return "plan"
        return "e_stop"

    # ── Veřejné API ──────────────────────────────────────────────────────────────

    def _make_initial_state(
        self,
        task: str,
        user_id: str,
        session_id: str,
        approved: bool = False,
        force_provider: str = "",
        session_context: str = "",
    ) -> SingularityState:
        return {
            "messages": [HumanMessage(content=task)],
            "user_id": user_id,
            "session_id": session_id,
            "task": task,
            "agent_outputs": {},
            "risk_score": 0.0,
            "awaiting_approval": False,
            "approved": approved,
            "final_response": "",
            "iteration": 0,
            "e_stop": False,
            "provider_log": {},
            "active_provider": "",
            "force_provider": force_provider,
            "session_context": session_context,
        }

    async def run(
        self,
        task: str,
        user_id: str,
        session_id: str,
        approved: bool = False,
        force_provider: str = "",
        session_context: str = "",
    ) -> dict:
        """Spustí kompletní kognitivní smyčku; vrací final_response + provider_log."""
        initial_state = self._make_initial_state(
            task, user_id, session_id, approved, force_provider, session_context
        )
        final_state = await self.graph.ainvoke(initial_state)
        return {
            "response": final_state.get("final_response", "Bez výstupu."),
            "provider_log": final_state.get("provider_log", {}),
            "risk_score": final_state.get("risk_score", 0.0),
        }

    async def run_stream(
        self,
        task: str,
        user_id: str,
        session_id: str,
        approved: bool = False,
        force_provider: str = "",
        session_context: str = "",
    ):
        """
        AsyncGenerator: produkuje progress event po každém LangGraph uzlu.

        Každý event je dict s klíčem "event":
          - "node_completed"  po každém uzlu (node, provider, provider_log)
          - "completed"       finální výsledek (response, provider_log, risk_score)
        """
        initial_state = self._make_initial_state(
            task, user_id, session_id, approved, force_provider, session_context
        )

        accumulated_plog: dict[str, str] = {}
        last_response = ""
        last_risk = 0.0

        async for chunk in self.graph.astream(initial_state):
            for node_name, updates in chunk.items():
                if isinstance(updates, dict):
                    if "provider_log" in updates:
                        accumulated_plog.update(updates["provider_log"])
                    if updates.get("final_response"):
                        last_response = updates["final_response"]
                    if "risk_score" in updates:
                        last_risk = updates["risk_score"]

                node_provider = accumulated_plog.get(node_name, "")
                yield {
                    "event": "node_completed",
                    "node": node_name,
                    "provider": node_provider,
                    "provider_log": dict(accumulated_plog),
                }

        yield {
            "event": "completed",
            "response": last_response or "Bez výstupu.",
            "provider_log": accumulated_plog,
            "risk_score": last_risk,
        }

    def e_stop(self) -> None:
        log.critical("E_STOP_REQUESTED")
