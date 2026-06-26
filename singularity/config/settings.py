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

    # ── Persistence (SQLite) ──────────────────────────────────
    enable_persistence: bool = False   # Fáze 14: SQLite durable storage
    db_path: str = "./data/singularity.db"  # Fáze 14: path to SQLite file

    # ── Scheduler ─────────────────────────────────────────────
    enable_scheduler: bool = True      # Fáze 15: cron-style recurring tasks

    # ── HPC / Apptainer (Fáze 26) ─────────────────────────────────────────────
    hpc_enabled: bool = False
    slurm_partition: str = "gpu_agi"
    apptainer_sif_path: str = "/share/groupname/containers/AGI_Core_Env.sif"
    container_registry: str = "harbor.example.com/agi"
    nccl_ib_hca: str = "mlx5_0"
    burst_buffer_path: str = "/dev/shm/agi"
    cascade_confidence_threshold: float = 0.7
    cascade_draft_provider: str = "gemini"
    cascade_oracle_provider: str = "claude"

    # ── Guardrails / Content Moderation (Fáze 27) ─────────────────────────────
    guardrails_enabled: bool = True
    guardrails_scan_input: bool = True
    guardrails_scan_output: bool = True

    # ── Semantic Cache (Fáze 29) ─────────────────────────────────────────────
    enable_semantic_cache: bool = True
    semantic_cache_threshold: float = 0.95   # cosine similarity threshold for hits
    semantic_cache_max_size: int = 500       # max entries (LRU eviction)
    semantic_cache_ttl_s: float = 300.0     # TTL per entry (seconds)

    # ── Multi-Agent Orchestrator (Fáze 28) ────────────────────────────────────
    orchestrator_max_parallel: int = 8       # max simultaneous sub-tasks per wave
    orchestrator_timeout_s: float = 60.0    # per-task timeout in seconds
    orchestrator_default_aggregation: str = "merge"  # merge | select_best | vote

    # ── Request Pipeline (Fáze 30) ───────────────────────────────────────────
    enable_pipeline: bool = True              # enable request/response pipeline
    pipeline_fail_fast: bool = False          # raise on step error vs. skip
    pipeline_pii_redaction: bool = False      # auto-add PIIRedactionStep

    # ── Output Validator (Fáze 31) ────────────────────────────────────────────
    enable_validator: bool = True             # enable output validation
    validator_max_retries: int = 2            # repair attempts on failure

    # ── Context Window Manager (Fáze 32) ──────────────────────────────────────
    enable_context_manager: bool = True       # enable history trimming
    context_max_tokens: int = 4000            # token budget per conversation
    context_keep_recent: int = 4              # always-keep most recent N turns
    context_trim_strategy: str = "drop_oldest"  # drop_oldest | summarize_oldest | keep_recent

    # ── Consensus Engine (Fáze 33) ────────────────────────────────────────────
    enable_consensus: bool = False            # self-consistency sampling (costly)
    consensus_n_samples: int = 5              # samples per consensus run
    consensus_similarity_threshold: float = 0.9  # cluster grouping similarity
    consensus_agreement_threshold: float = 0.5   # confidence to count as agreement

    # ── Intent Classifier (Fáze 34) ───────────────────────────────────────────
    enable_intent_classifier: bool = True     # content-based intent routing
    intent_min_confidence: float = 0.0        # below this → fall back to general
    intent_default: str = "general"           # fallback intent name

    # ── Citation Tracker (Fáze 35) ────────────────────────────────────────────
    enable_citation_tracker: bool = True      # ground responses in sources
    citation_threshold: float = 0.2           # min Jaccard overlap to cite
    citation_max_per_sentence: int = 3        # max citations per sentence

    # ── Logging ───────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "console"   # Fáze 10: "json" for prod, "console" for dev
    log_buffer_size: int = 500    # Fáze 10: max events in in-memory log ring buffer

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = SingularitySettings()
