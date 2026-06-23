"""
Singularity — Google Gemini provider.
Vyžaduje GEMINI_API_KEY a balíček langchain-google-genai.
"""
from __future__ import annotations

import time

import structlog
from langchain_core.messages import BaseMessage, HumanMessage

from providers.base import AbstractLLMProvider, LLMResponse

log = structlog.get_logger()


class GeminiProvider(AbstractLLMProvider):
    """Wraps ChatGoogleGenerativeAI do AbstractLLMProvider rozhraní."""

    name = "gemini"
    cost_per_1k = 0.0005         # Flash je výrazně levnější (orientační)
    typical_latency_ms = 900.0   # Flash je rychlejší
    quality_rank = 2

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__()
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise ImportError(
                "Gemini provider vyžaduje: pip install langchain-google-genai"
            ) from exc

        self._model_id = model
        self._llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0.3,
        )

    async def ainvoke(self, messages: list[BaseMessage]) -> LLMResponse:
        start = time.monotonic()
        response = await self._llm.ainvoke(messages)
        latency_ms = (time.monotonic() - start) * 1000

        content = response.content if isinstance(response.content, str) else str(response.content)
        usage = getattr(response, "usage_metadata", None)
        tokens = usage.get("total_tokens", 0) if isinstance(usage, dict) else 0

        return LLMResponse(
            content=content,
            provider=self.name,
            model=self._model_id,
            tokens_used=tokens,
            latency_ms=round(latency_ms, 1),
        )

    async def health_check(self) -> bool:
        try:
            result = await self._llm.ainvoke([HumanMessage(content="ping")])
            return bool(result.content)
        except Exception as exc:
            log.warning("gemini_health_check_failed", error=str(exc))
            return False
