"""
Singularity — Abstraktní LLM provider protokol.

Každý provider (Claude, Gemini, …) implementuje toto rozhraní a nese metadata
pro cost/latency/quality-aware routing a self-healing stav (cooldown).
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    tokens_used: int = 0
    latency_ms: float = 0.0


class AbstractLLMProvider(ABC):
    """Společné rozhraní pro všechny LLM providery."""

    name: str = "abstract"

    # Metadata pro routing strategie (přepiš v podtřídě)
    cost_per_1k: float = 0.0       # USD / 1k tokenů — pro COST_OPTIMIZED
    typical_latency_ms: float = 0.0  # baseline — pro LATENCY_OPTIMIZED
    quality_rank: int = 99         # 1 = nejvyšší — pro QUALITY_FIRST

    # Self-healing stav
    COOLDOWN_THRESHOLD: int = 3    # počet selhání před cooldownem
    COOLDOWN_SECONDS: float = 60.0

    def __init__(self) -> None:
        self.consecutive_failures: int = 0
        self.cooldown_until: float = 0.0

    @abstractmethod
    async def ainvoke(self, messages: list) -> LLMResponse:
        """Odešle zprávy do LLM a vrátí strukturovanou odpověď."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Ověří dostupnost providera (lehký ping)."""
        ...

    # ── Self-healing ──────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """False, pokud je provider v cooldownu po opakovaných selháních."""
        return time.monotonic() >= self.cooldown_until

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.cooldown_until = 0.0

    def record_failure(self) -> bool:
        """
        Zaznamená selhání. Vrátí True, pokud tím byl spuštěn cooldown.
        """
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.COOLDOWN_THRESHOLD:
            self.cooldown_until = time.monotonic() + self.COOLDOWN_SECONDS
            return True
        return False

    def status(self) -> dict:
        """Snapshot stavu providera pro GET /providers."""
        return {
            "name": self.name,
            "cost_per_1k": self.cost_per_1k,
            "typical_latency_ms": self.typical_latency_ms,
            "quality_rank": self.quality_rank,
            "available": self.is_available(),
            "consecutive_failures": self.consecutive_failures,
            "cooldown_remaining_s": max(0.0, round(self.cooldown_until - time.monotonic(), 1)),
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
