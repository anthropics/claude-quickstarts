"""
Singularity — Retry policy a dead-letter queue (Fáze 6).

Neúspěšné tasky jsou automaticky znovu zařazeny do fronty
s exponenciálním backoffem + jitter. Po vyčerpání pokusů
přejdou do dead-letter queue (DLQ) pro manuální analýzu.
"""
from __future__ import annotations

import dataclasses
import random


@dataclasses.dataclass(frozen=True)
class RetryPolicy:
    """Immutable konfigurace retry logiky per task."""

    max_attempts: int = 3        # celkový počet pokusů (1 = žádný retry)
    backoff_base: float = 2.0    # základ exponenciálního backoffu [s]
    max_backoff: float = 30.0    # strop backoffu [s]
    jitter: bool = True          # přidat náhodný jitter (×0.5–1.0)

    def delay_for_attempt(self, attempt: int) -> float:
        """Vrátí počet sekund čekání před attempt-tým pokusem."""
        raw = self.backoff_base ** attempt
        capped = min(raw, self.max_backoff)
        if self.jitter:
            capped *= 0.5 + random.random() * 0.5
        return capped


DEFAULT_POLICY = RetryPolicy()
NO_RETRY = RetryPolicy(max_attempts=1)
