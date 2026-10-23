"""
Singularity — SingularitySwarm.

Multi-LLM orchestrátor: každý agent běží na Claude nebo Gemini dle routeru.
Integruje rate limiting, telemetrii, self-healing a tenacity retry (z Omega).
"""
from __future__ import annotations

import asyncio
import time

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from agents.base import AgentOutput, AgentRole
from config.settings import settings
from core import telemetry
from core.limiter import ProviderRateLimiter
from core.router import LLMRouter

log = structlog.get_logger()

AGENT_SYSTEM_PROMPTS: dict[AgentRole, str] = {
    AgentRole.RESEARCHER: (
        "Jsi specializovaný Badatel v systému Singularity. "
        "Sbíráš, ověřuješ a strukturuješ informace. Vždy uveď zdroj a jistotu. "
        "Výstup: FINDINGS | CONFIDENCE: x.x | GAPS: ..."
    ),
    AgentRole.PROGRAMMER: (
        "Jsi specializovaný Programátor v systému Singularity. "
        "Píšeš produkční, testovatelný kód s typovými anotacemi a ošetřením výjimek. "
        "Hodnoť riziko deploymentu (0-1)."
    ),
    AgentRole.CRITIC: (
        "Jsi specializovaný Kritik v systému Singularity — devil's advocate. "
        "Hledej chyby, edge cases, bezpečnostní a etická rizika. "
        "Výstup: ISSUES | RISK_SCORE: 0.0-1.0 | RECOMMENDATION."
    ),
    AgentRole.PLANNER: (
        "Jsi specializovaný Plánovač v systému Singularity. "
        "Rozkládáš komplexní cíle na atomické, měřitelné kroky se závislostmi."
    ),
    AgentRole.COMMUNICATOR: (
        "Jsi specializovaný Komunikátor v systému Singularity. "
        "Syntetizuješ výstupy agentů do srozumitelné odpovědi pro operátora."
    ),
}


class SingularitySwarm:
    """Multi-agentní orchestrátor s LLM routerem (Claude + Gemini)."""

    def __init__(
        self,
        router: LLMRouter,
        limiter: ProviderRateLimiter | None = None,
        rag=None,
    ) -> None:
        self.router = router
        self.limiter = limiter or ProviderRateLimiter()
        self.rag = rag

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.1, min=0.1, max=1.0),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True,
    )
    async def run_agent(
        self,
        role: AgentRole,
        task: str,
        context: str = "",
    ) -> AgentOutput:
        """Spustí agenta přes router; rate-limited, s failoverem a telemetrií."""
        provider = self.router.get_provider(role)

        rag_context = ""
        if self.rag and role == AgentRole.RESEARCHER:
            try:
                rag_context = f"\n\nRAG KONTEXT:\n{self.rag.query(task)}"
            except Exception as exc:
                log.warning("rag_query_failed", error=str(exc))

        messages = [
            SystemMessage(content=AGENT_SYSTEM_PROMPTS[role]),
            HumanMessage(content=f"KONTEXT: {context}{rag_context}\n\nÚKOL: {task}"),
        ]

        llm_response = await self._invoke_with_failover(provider, role, messages)
        content = llm_response.content

        risk_score = 0.2
        if role == AgentRole.CRITIC and "RISK_SCORE:" in content:
            try:
                risk_score = float(content.split("RISK_SCORE:")[1].split()[0])
            except (IndexError, ValueError):
                pass

        requires_approval = (
            risk_score >= settings.risk_threshold or role == AgentRole.PROGRAMMER
        )

        return AgentOutput(
            role=role,
            content=content,
            confidence=0.8,
            risk_score=risk_score,
            requires_approval=requires_approval,
            provider_used=llm_response.provider,
            metadata={
                "task": task[:100],
                "model": llm_response.model,
                "latency_ms": llm_response.latency_ms,
            },
        )

    async def _invoke_with_failover(self, provider, role, messages):
        """Zavolá provider; při výjimce zkusí failover a aktualizuje self-healing stav."""
        try:
            return await self._invoke_once(provider, role, messages)
        except Exception as exc:
            log.warning("primary_provider_failed", provider=provider.name, error=str(exc))
            if provider.record_failure():
                telemetry.record_cooldown(provider.name)
            fallback = self.router.get_fallback(provider)
            if fallback is None:
                raise
            return await self._invoke_once(fallback, role, messages)

    async def _invoke_once(self, provider, role, messages):
        """Jedno volání s rate-limit gate, měřením latence a telemetrií."""
        start = time.monotonic()
        try:
            async with self.limiter.acquire(provider.name):
                response = await provider.ainvoke(messages)
            provider.record_success()
            telemetry.record_request(
                provider.name, role.value, "ok", time.monotonic() - start
            )
            return response
        except Exception:
            telemetry.record_request(
                provider.name, role.value, "error", time.monotonic() - start
            )
            raise

    async def orchestrate(
        self,
        task: str,
        roles: list[AgentRole] | None = None,
        context: str = "",
    ) -> dict[AgentRole, AgentOutput]:
        """Paralelně spustí agenty; selhání jednoho neblokuje ostatní."""
        active_roles = roles or [AgentRole.RESEARCHER, AgentRole.PLANNER, AgentRole.CRITIC]

        raw_results = await asyncio.gather(
            *[self.run_agent(r, task, context) for r in active_roles],
            return_exceptions=True,
        )

        outputs: dict[AgentRole, AgentOutput] = {}
        for role, result in zip(active_roles, raw_results):
            if isinstance(result, Exception):
                log.error("agent_failed", role=role.value, error=str(result))
            else:
                outputs[role] = result  # type: ignore[assignment]
        return outputs
