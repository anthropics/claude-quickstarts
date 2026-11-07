"""
Singularity — Telemetrie a observabilita.

Strukturované logování (structlog) + Prometheus metriky pro každé volání LLM.
Pokud prometheus_client není dostupný, degraduje na no-op (nikdy nespadne).
"""
from __future__ import annotations

import structlog

log = structlog.get_logger()

try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

    _PROM_AVAILABLE = True

    LLM_REQUESTS = Counter(
        "singularity_llm_requests_total",
        "Celkový počet volání LLM",
        ["provider", "role", "status"],
    )
    LLM_LATENCY = Histogram(
        "singularity_llm_latency_seconds",
        "Latence volání LLM",
        ["provider"],
    )
    PROVIDER_SWITCHES = Counter(
        "singularity_provider_switches_total",
        "Počet failover přepnutí mezi providery",
        ["from_provider", "to_provider"],
    )
    PROVIDER_COOLDOWNS = Counter(
        "singularity_provider_cooldowns_total",
        "Počet aktivací cooldownu providera (self-healing)",
        ["provider"],
    )
except Exception:  # pragma: no cover - prometheus volitelný
    _PROM_AVAILABLE = False
    LLM_REQUESTS = LLM_LATENCY = PROVIDER_SWITCHES = PROVIDER_COOLDOWNS = None  # type: ignore[assignment]
    CONTENT_TYPE_LATEST = "text/plain"


def record_request(provider: str, role: str, status: str, latency_s: float) -> None:
    """Zaznamená jedno volání LLM do logu i Prometheus metrik."""
    log.info(
        "llm_request",
        provider=provider,
        role=role,
        status=status,
        latency_ms=round(latency_s * 1000, 1),
    )
    if _PROM_AVAILABLE:
        LLM_REQUESTS.labels(provider=provider, role=role, status=status).inc()
        LLM_LATENCY.labels(provider=provider).observe(latency_s)


def record_switch(from_provider: str, to_provider: str) -> None:
    """Zaznamená failover přepnutí mezi providery."""
    log.warning("provider_switch", from_provider=from_provider, to_provider=to_provider)
    if _PROM_AVAILABLE:
        PROVIDER_SWITCHES.labels(from_provider=from_provider, to_provider=to_provider).inc()


def record_cooldown(provider: str) -> None:
    """Zaznamená aktivaci cooldownu (self-healing)."""
    log.warning("provider_cooldown", provider=provider)
    if _PROM_AVAILABLE:
        PROVIDER_COOLDOWNS.labels(provider=provider).inc()


def metrics_payload() -> tuple[bytes, str]:
    """Vrátí (telo, content_type) pro GET /metrics endpoint."""
    if _PROM_AVAILABLE:
        return generate_latest(), CONTENT_TYPE_LATEST
    return b"# prometheus_client neni nainstalovan\n", "text/plain"
