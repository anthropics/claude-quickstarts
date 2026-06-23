"""
Singularity — SingularitySwarm.
Multi-LLM orchestrátor s retry logikou z Omega (stop=3, wait=exponential).
"""
from __future__ import annotations

import asyncio
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langchain_core.messages import SystemMessage, HumanMessage

from agents.base import AgentRole, AgentOutput
from config.settings import settings
from core.router import LLMRouter

log = structlog.get_logger()

AGENT_SYSTEM_PROMPTS: dict[AgentRole, str] = {
    AgentRole.RESEARCHER: (
        "Jsi specializovany Badatel v systemu Singularity. "
        "Sbiras, overujes a strukturujes informace. "
        "Vystup: FINDINGS | CONFIDENCE: x.x | GAPS: ..."
    ),
    AgentRole.PROGRAMMER: (
        "Jsi specializovany Programator v systemu Singularity. "
        "Pis produktni, testovatelny kod s typovymi anotacemi. "
        "Hodnot riziko deploymentu (0-1)."
    ),
    AgentRole.CRITIC: (
        "Jsi specializovany Kritik v systemu Singularity. "
        "Hledej chyby, edge cases, bezpecnostni rizika. "
        "Vystup: ISSUES | RISK_SCORE: 0.0-1.0 | RECOMMENDATION."
    ),
    AgentRole.PLANNER: (
        "Jsi specializovany Planovac v systemu Singularity. "
        "Rozkladaš komplexni cile na atomicke, meritelne kroky."
    ),
    AgentRole.COMMUNICATOR: (
        "Jsi specializovany Komunikator v systemu Singularity. "
        "Syntetizujes vystupy agentu do srozumitelne odpovedi pro operatora."
    ),
}


class SingularitySwarm:
    """Multi-agentni orchestrator s LLM routerem (Claude + Gemini)."""

    def __init__(self, router: LLMRouter, rag=None) -> None:
        self.router = router
        self.rag = rag

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.1, min=0.1, max=1.0),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True,
    )
    async def run_agent(self, role: AgentRole, task: str, context: str = "") -> AgentOutput:
        provider = self.router.get_provider(role)

        rag_context = ""
        if self.rag and role == AgentRole.RESEARCHER:
            try:
                rag_context = f"\n\nRAG KONTEXT:\n{self.rag.query(task)}"
            except Exception as exc:
                log.warning("rag_query_failed", error=str(exc))

        messages = [
            SystemMessage(content=AGENT_SYSTEM_PROMPTS[role]),
            HumanMessage(content=f"KONTEXT: {context}{rag_context}\n\nUKOL: {task}"),
        ]

        try:
            llm_response = await provider.ainvoke(messages)
        except Exception as exc:
            log.warning("primary_provider_failed", provider=provider.name, error=str(exc))
            fallback = self.router.get_fallback(provider)
            if fallback:
                llm_response = await fallback.ainvoke(messages)
            else:
                raise

        content = llm_response.content
        risk_score = 0.2
        if role == AgentRole.CRITIC and "RISK_SCORE:" in content:
            try:
                risk_score = float(content.split("RISK_SCORE:")[1].split()[0])
            except (IndexError, ValueError):
                pass

        log.info("agent_completed", role=role.value, provider=llm_response.provider, risk=risk_score)

        return AgentOutput(
            role=role,
            content=content,
            confidence=0.8,
            risk_score=risk_score,
            requires_approval=(risk_score >= settings.risk_threshold or role == AgentRole.PROGRAMMER),
            provider_used=llm_response.provider,
            metadata={"task": task[:100], "model": llm_response.model},
        )

    async def orchestrate(
        self,
        task: str,
        roles: list[AgentRole] | None = None,
        context: str = "",
    ) -> dict[AgentRole, AgentOutput]:
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
