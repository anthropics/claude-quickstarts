"""
Singularity — Abstraktní LLM provider protokol.
Každý provider (Claude, Gemini) implementuje toto rozhraní.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    tokens_used: int = 0


class AbstractLLMProvider(ABC):
    """Společné rozhraní pro všechny LLM providery."""

    name: str

    @abstractmethod
    async def ainvoke(self, messages: list) -> LLMResponse:
        """Odešle zprávy do LLM a vrátí strukturovanou odpověď."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Ověří dostupnost providera."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
