"""
Singularity — Google Gemini provider.
Vyžaduje GEMINI_API_KEY; pokud není k dispozici, selže při inicializaci.
"""
from __future__ import annotations

import structlog
from langchain_core.messages import BaseMessage

from providers.base import AbstractLLMProvider, LLMResponse

log = structlog.get_logger()


class GeminiProvider(AbstractLLMProvider):
    """Wraps ChatGoogleGenerativeAI do AbstractLLMProvider rozhraní."""

    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
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
        response = await self._llm.ainvoke(messages)
        content = response.content if isinstance(response.content, str) else str(response.content)
        usage = getattr(response, "usage_metadata", None)
        tokens = (usage.get("total_tokens", 0) if isinstance(usage, dict) else 0)
        log.debug("gemini_invoked", model=self._model_id, tokens=tokens)
        return LLMResponse(
            content=content,
            provider=self.name,
            model=self._model_id,
            tokens_used=tokens,
        )

    async def health_check(self) -> bool:
        try:
            from langchain_core.messages import HumanMessage
            result = await self._llm.ainvoke([HumanMessage(content="ping")])
            return bool(result.content)
        except Exception as exc:
            log.warning("gemini_health_check_failed", error=str(exc))
            return False
