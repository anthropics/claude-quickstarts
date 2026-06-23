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

    # ── Logging ───────────────────────────────────────────────
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = SingularitySettings()
