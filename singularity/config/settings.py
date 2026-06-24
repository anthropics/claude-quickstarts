"""
Singularity — Centrální konfigurace.
Rozšiřuje Omega nastavení o Gemini API a routing strategii.
"""
from pydantic import SecretStr
from pydantic_settings import BaseSettings


class SingularitySettings(BaseSettings):
    # ── Claude (Anthropic) ────────────────────────────────────
    anthropic_api_key: SecretStr = SecretStr("sk-ant-placeholder")
    primary_cloud_model: str = "claude-sonnet-4-6"

    # ── Google Gemini ─────────────────────────────────────────
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.0-flash"
    enable_gemini: bool = True

    # ── LLM Routing ───────────────────────────────────────────
    # Strategie: "static" | "round_robin" | "failover"
    routing_strategy: str = "static"

    # ── Lokální LLM (fallback) ────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # ── Paměť ─────────────────────────────────────────────────
    openai_api_key: SecretStr | None = None
    mem0_api_key: SecretStr | None = None
    chroma_persist_dir: str = "./data/chroma"

    # ── Bezpečnost ────────────────────────────────────────────
    max_iterations: int = 10
    require_human_approval: bool = True
    risk_threshold: float = 0.7
    require_api_key: bool = False   # Fáze 7: True = endpointy vyžadují X-API-Key

    # ── Task queue ────────────────────────────────────────────
    task_workers: int = 1           # Fáze 7: počet paralelních workerů

    # ── Response cache ────────────────────────────────────────
    enable_cache: bool = True      # Fáze 12: LRU response cache
    cache_ttl_s: float = 300.0    # Fáze 12: TTL per cache entry (seconds)
    cache_max_size: int = 1000    # Fáze 12: max cached entries (LRU eviction)

    # ── Distributed tracing (OpenTelemetry) ──────────────────
    enable_tracing: bool = True    # Fáze 13: OTel tracing
    otlp_endpoint: str = ""        # Fáze 13: gRPC OTLP collector (empty = in-memory)

    # ── Logging ───────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "console"   # Fáze 10: "json" for prod, "console" for dev
    log_buffer_size: int = 500    # Fáze 10: max events in in-memory log ring buffer

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = SingularitySettings()
