"""
Singularity — FastAPI vrstva.

Endpointy:
  POST /task                   Zadání úkolu (sync, volitelně force_provider)
  POST /task/stream            SSE streaming verze (Fáze 1)
  POST /task/async             Async fronta — vrátí task_id okamžitě (Fáze 3)
  POST /task/compare           Paralelní run na Claude + Gemini (Fáze 3)
  POST /task/batch             Dávkové odeslání úkolů do fronty (Fáze 4)
  GET  /task/{id}/status       Stav async tasku (Fáze 3)
  GET  /task/{id}/result       Výsledek async tasku (Fáze 3)
  GET  /task/{id}/wait         Long-poll čekání na výsledek (Fáze 5)
  GET  /task/{id}/stream       SSE stream lifecycle událostí tasku (Fáze 11)
  GET  /queue/status           Stav fronty (Fáze 4)
  POST /approve                Human-in-the-loop schválení/zamítnutí
  POST /e-stop                 Nouzové zastavení
  GET  /memory/{uid}           Zobrazení paměti uživatele
  GET  /sessions/{uid}         Konverzační historie + náklady (Fáze 1)
  GET  /sessions/{uid}/export  JSON export session (Fáze 3)
  GET  /sessions               Seznam aktivních uživatelů (Fáze 1)
  GET  /providers              Stav providerů
  GET  /health/providers       Okamžitý health check všech providerů (Fáze 2)
  POST /router/strategy        Runtime změna routing strategie
  GET  /metrics                Prometheus metriky
  GET  /tasks/{id}/providers   Který model zpracoval který krok
  GET  /dashboard              Admin dashboard (Fáze 2)
  POST /budget/{uid}           Nastavení cost limitu uživatele (Fáze 4)
  GET  /budget/{uid}           Zobrazení stavu budgetu uživatele (Fáze 4)
  DELETE /budget/{uid}         Odstranění cost limitu uživatele (Fáze 4)
  POST /rate-limits/{uid}      Nastavení RPM limitu uživatele (Fáze 5)
  GET  /rate-limits/{uid}      Stav RPM limitu uživatele (Fáze 5)
  DELETE /rate-limits/{uid}    Odebrání RPM limitu uživatele (Fáze 5)
  GET  /audit-log              Posledních N audit událostí (Fáze 6)
  GET  /dead-letter-queue      Tasky, které vyčerpaly retry pokusy (Fáze 6)
  POST /dead-letter-queue/{id}/retry  Manuální retry DLQ tasku (Fáze 6)
  POST /api-keys               Vytvoří nový API klíč pro uživatele (Fáze 7)
  GET  /api-keys               Vypíše klíče (filtrovatelné user_id) (Fáze 7)
  DELETE /api-keys/{key}       Revokuje API klíč (Fáze 7)
  GET  /health/live            Liveness probe — vždy 200 (Fáze 8)
  GET  /health/ready           Readiness probe — 200 až po inicializaci (Fáze 8)
  GET  /logs/recent            Posledních N strukturovaných log událostí (Fáze 10)
  GET  /cache/stats            Statistiky response cache (Fáze 12)
  DELETE /cache                Vymaže celou response cache (Fáze 12)
  GET  /traces                 Posledních N OTel spanů (Fáze 13)
  GET  /db/status              Stav SQLite persistence (Fáze 14)
  POST /scheduler/jobs         Přidá nový opakovaný úkol (Fáze 15)
  GET  /scheduler/jobs         Vypíše naplánované joby (Fáze 15)
  DELETE /scheduler/jobs/{id}  Odstraní naplánovaný job (Fáze 15)
  POST /experiments            Vytvoří A/B experiment (Fáze 19)
  GET  /experiments            Vypíše experimenty (Fáze 19)
  GET  /experiments/{id}       Detail experimentu + metriky (Fáze 19)
  PATCH /experiments/{id}      Aktualizuje status/split (Fáze 19)
  POST /experiments/{id}/record Zaznamená výsledek varianty (Fáze 19)
  DELETE /experiments/{id}     Smaže experiment (Fáze 19)
  POST /workflows              Vytvoří workflow (Fáze 18)
  GET  /workflows              Vypíše workflows (Fáze 18)
  GET  /workflows/{id}         Detail workflow (Fáze 18)
  POST /workflows/{id}/run     Spustí workflow asynchronně (Fáze 18)
  POST /task/{id}/feedback     Uloží hodnocení tasku 1–5 + thumbs (Fáze 17)
  GET  /task/{id}/feedback     Vrátí hodnocení tasku (Fáze 17)
  GET  /feedback/stats         Agregované statistiky hodnocení (Fáze 17)
  POST /tools                  Registruje HTTP-callback nástroj (Fáze 16)
  GET  /tools                  Vypíše registrované nástroje (Fáze 16)
  DELETE /tools/{name}         Odregistruje nástroj (Fáze 16)
  POST /tools/{name}/invoke    Invokuje nástroj s parametry (Fáze 16)
  WS   /ws/{uid}               Real-time node-level streaming (Fáze 1)
  GET  /health                 Health check (zachováno pro zpětnou kompatibilitu)
  POST /hpc/jobs               Odešle HPC/Slurm job (Fáze 26)
  GET  /hpc/jobs               Vypíše HPC joby (Fáze 26)
  GET  /hpc/jobs/{id}          Detail HPC jobu (Fáze 26)
  GET  /hpc/cluster/status     Stav HPC clusteru + konfigurace (Fáze 26)
  POST /hpc/cascade/route      LLM Cascade routing Draft→Oracle (Fáze 26)
  GET  /hpc/cascade/metrics    Statistiky Cascade routeru (Fáze 26)
  POST /guardrails/rules       Přidá vlastní moderační pravidlo (Fáze 27)
  GET  /guardrails/rules       Vypíše pravidla (filtrovatelné category) (Fáze 27)
  GET  /guardrails/rules/{id}  Detail pravidla (Fáze 27)
  PATCH /guardrails/rules/{id} Zapne/vypne pravidlo (Fáze 27)
  DELETE /guardrails/rules/{id} Smaže vlastní pravidlo (Fáze 27)
  POST /guardrails/scan        Naskenuje text (input/output) (Fáze 27)
  GET  /guardrails/stats       Statistiky skenování (Fáze 27)
  POST /orchestrate            Vytvoří a spustí multi-agent plán (Fáze 28)
  POST /orchestrate/plan       Validuje DAG, vrátí plán bez spuštění (Fáze 28)
  GET  /orchestrate/metrics    Metriky orchestrátoru (Fáze 28)
  POST /orchestrate/metrics/reset  Reset metrik orchestrátoru (Fáze 28)
  GET  /cache/semantic/stats   Statistiky sémantické cache (Fáze 29)
  DELETE /cache/semantic       Vymaže sémantickou cache (Fáze 29)
  POST /cache/semantic/lookup  Testovací dotaz do sémantické cache (Fáze 29)
  GET  /pipeline/steps         Seznam aktivních pipeline kroků (Fáze 30)
  POST /pipeline/steps         Přidá krok do pipeline (Fáze 30)
  DELETE /pipeline/steps/{name} Odstraní krok z pipeline (Fáze 30)
  GET  /pipeline/metrics       Metriky pipeline (Fáze 30)
  POST /validate               Validuje text proti omezením (Fáze 31)
  GET  /validate/metrics       Metriky validátoru (Fáze 31)
  POST /validate/metrics/reset Reset metrik validátoru (Fáze 31)
  POST /context/fit            Ořízne historii na token budget (Fáze 32)
  GET  /context/metrics        Metriky context manageru (Fáze 32)
  POST /consensus              Konsenzus nad vzorky odpovědí (Fáze 33)
  GET  /consensus/metrics      Metriky consensus enginu (Fáze 33)
  POST /intent/classify        Klasifikace záměru dotazu (Fáze 34)
  GET  /intent/list            Seznam registrovaných záměrů (Fáze 34)
  GET  /intent/metrics         Metriky klasifikátoru záměrů (Fáze 34)
  POST /citations/track        Ukotvení odpovědi ve zdrojích (Fáze 35)
  GET  /citations/metrics      Metriky citation trackeru (Fáze 35)
  POST /chunk                  Rozdělí dokument na chunky pro RAG (Fáze 36)
  GET  /chunk/metrics          Metriky document chunkeru (Fáze 36)
  POST /retrieve/index         Zaindexuje dokumenty do BM25 (Fáze 37)
  POST /retrieve/search        Vyhledá top-k relevantních dokumentů (Fáze 37)
  DELETE /retrieve             Vymaže BM25 index (Fáze 37)
  GET  /retrieve/metrics       Metriky BM25 retrieveru (Fáze 37)
  POST /rerank                 Fúze ranked listů (RRF / weighted) (Fáze 38)
  GET  /rerank/metrics         Metriky hybrid rerankeru (Fáze 38)
  POST /anonymize              Reverzibilní anonymizace PII (Fáze 39)
  POST /anonymize/detect       Detekce PII bez úpravy textu (Fáze 39)
  POST /anonymize/restore      Obnoví původní hodnoty z mapy (Fáze 39)
  GET  /anonymize/metrics      Metriky PII anonymizéru (Fáze 39)
  POST /cost/estimate          Odhad ceny requestu pro model (Fáze 40)
  POST /cost/compare           Porovná cenu napříč modely (Fáze 40)
  GET  /cost/models            Ceník modelů (Fáze 40)
  GET  /cost/metrics           Metriky cost estimátoru (Fáze 40)
  POST /compare/responses      Sentence-level diff dvou odpovědí (Fáze 41)
  GET  /compare/responses/metrics  Metriky comparatoru (Fáze 41)
  POST /summarize              Extraktivní sumarizace textu (Fáze 42)
  GET  /summarize/metrics      Metriky summarizéru (Fáze 42)
  POST /language/detect        Detekce jazyka textu (Fáze 43)
  GET  /language/list          Seznam podporovaných jazyků (Fáze 43)
  GET  /language/metrics       Metriky language detektoru (Fáze 43)
  POST /parse/json             Extrakce JSON z textu (Fáze 44)
  POST /parse/key-values       Extrakce key-value párů (Fáze 44)
  POST /parse/list             Extrakce seznamu z textu (Fáze 44)
  GET  /parse/metrics          Metriky output parseru (Fáze 44)
  POST /sentiment              Analýza sentimentu textu (Fáze 45)
  GET  /sentiment/metrics      Metriky sentiment analyzéru (Fáze 45)
  POST /keywords               Extrakce klíčových frází (Fáze 46)
  GET  /keywords/metrics       Metriky keyword extraktoru (Fáze 46)
  POST /readability            Readability metriky textu (Fáze 47)
  GET  /readability/metrics    Metriky readability analyzéru (Fáze 47)
  POST /dedup/check            Kontrola duplicity textu (Fáze 48)
  POST /dedup/batch            Deduplikace seznamu textů (Fáze 48)
  DELETE /dedup                Vymaže dedup index (Fáze 48)
  GET  /dedup/metrics          Metriky deduplikátoru (Fáze 48)
  POST /entities               Extrakce pojmenovaných entit (Fáze 49)
  GET  /entities/metrics       Metriky entity extraktoru (Fáze 49)
  POST /analyze/text           Kompletní NLP analýza textu (Fáze 50)
  GET  /analyze/text/metrics   Metriky text analytics suite (Fáze 50)
  POST /fuzzy/match            Fuzzy match dotazu proti kandidátům (Fáze 51)
  GET  /fuzzy/metrics          Metriky fuzzy matcheru (Fáze 51)
  POST /anomaly/observe        Detekce anomálie v metrice (Fáze 52)
  GET  /anomaly/metrics        Metriky anomaly detektoru (Fáze 52)
  POST /sampler/add            Nabídne položku do reservoiru (Fáze 53)
  GET  /sampler/sample         Vrátí aktuální vzorek (Fáze 53)
  POST /sampler/reset          Vyprázdní reservoir (Fáze 53)
  GET  /sampler/metrics        Metriky sampleru (Fáze 53)
  POST /percentile/observe     Zaznamená hodnotu metriky (Fáze 54)
  GET  /percentile/summary     Distribuce + percentily metriky (Fáze 54)
  GET  /percentile/metrics     Metriky percentile trackeru (Fáze 54)
  POST /webhooks/subscribe     Registruje odběratele webhooku (Fáze 55)
  DELETE /webhooks/{sub_id}    Zruší odběr (Fáze 55)
  GET  /webhooks               Seznam odběratelů (Fáze 55)
  POST /webhooks/dispatch      Rozešle event odběratelům (Fáze 55)
  GET  /webhooks/dead-letters  Dead-letter fronta (Fáze 55)
  GET  /webhooks/metrics       Metriky webhook dispatcheru (Fáze 55)
  POST /flags                  Registruje feature flag (Fáze 56)
  GET  /flags                  Seznam feature flagů (Fáze 56)
  POST /flags/{name}/evaluate  Vyhodnotí flag pro uživatele (Fáze 56)
  PATCH /flags/{name}          Upraví flag (enabled/rollout/override) (Fáze 56)
  DELETE /flags/{name}         Smaže flag (Fáze 56)
  GET  /flags/metrics          Metriky feature flag manageru (Fáze 56)
  GET  /healthz                Agregovaný health všech subsystémů (Fáze 57)
  GET  /health/components      Seznam health komponent (Fáze 57)
  GET  /healthz/metrics        Metriky health agregátoru (Fáze 57)
  POST /slo                     Registruje SLO (Fáze 58)
  POST /slo/{name}/record       Zaznamená SLO událost (Fáze 58)
  GET  /slo/{name}              Report jednoho SLO (Fáze 58)
  GET  /slo                     Reporty všech SLO (Fáze 58)
  DELETE /slo/{name}            Smaže SLO (Fáze 58)
  POST /embeddings              Vektor textu (Fáze 61)
  POST /embeddings/similarity   Kosinová podobnost dvou textů (Fáze 61)
  GET  /embeddings/metrics      Metriky embedding provideru (Fáze 61)
  PUT  /state/{ns}/{key}        Uloží hodnotu do state store (Fáze 62)
  GET  /state/{ns}/{key}        Načte hodnotu (Fáze 62)
  DELETE /state/{ns}/{key}      Smaže hodnotu (Fáze 62)
  GET  /state/{ns}              Klíče v namespace (Fáze 62)
  GET  /state/metrics           Metriky state store (Fáze 62)
  POST /snapshot                Zazálohuje registrované komponenty (Fáze 63)
  POST /snapshot/restore        Obnoví komponenty ze zálohy (Fáze 63)
  GET  /snapshot/metrics        Metriky snapshot manageru (Fáze 63)
  POST /stream/tokens           Token-level SSE stream (Fáze 64)
  GET  /stream/metrics          Metriky token streamingu (Fáze 64)
  POST /tenants                 Vytvoří tenanta (Fáze 65)
  GET  /tenants                 Seznam tenantů (Fáze 65)
  POST /tenants/{id}/principals Přidá principala s rolí (Fáze 65)
  POST /tenants/authorize       Ověří API-key proti permission (Fáze 65)
  GET  /tenants/metrics         Metriky tenancy registru (Fáze 65)
  GET  /coalesce/metrics        Metriky request coalesceru (Fáze 66)
  POST /evals/score             Skóruje expected/actual + gate (Fáze 67)
  POST /vectors/index           Zaindexuje dokumenty (dense) (Fáze 69)
  POST /vectors/search          Sémantické k-NN vyhledávání (Fáze 69)
  DELETE /vectors               Vymaže vektorový index (Fáze 69)
  GET  /vectors/metrics         Metriky vector store (Fáze 69)
"""
from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any


def _resolve_version() -> str:
    """Single source of truth for the app version.

    Prefer pyproject.toml (authoritative when running from source, as in this
    quickstart), fall back to installed package metadata, then a constant.
    Reading pyproject avoids drift when an editable install's metadata is
    stale relative to the declared version.
    """
    try:
        import tomllib
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        return tomllib.loads(pyproject.read_text())["project"]["version"]
    except Exception:
        try:
            from importlib.metadata import version as _pkg_version
            return _pkg_version("singularity")
        except Exception:
            return "1.0.0"


APP_VERSION = _resolve_version()

import structlog
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel

from api.auth import set_manager, verify_api_key
from api.dashboard import get_dashboard_html
from api.middleware import RequestContextMiddleware
from config.settings import settings
from core import telemetry
from core.api_keys import ApiKeyManager
from core.audit_log import AuditLog
from core.budget_manager import BudgetManager
from core.cache import ResponseCache
from core.persistence import Database
from core.ab_test import ABTestManager
from core.alerting import AlertManager
from core.batch import BatchProcessor
from core.prompt_templates import PromptTemplateRegistry
from core.secret_manager import SecretManager
from core.quota_manager import QuotaManager
from core.circuit_breaker import CircuitBreakerRegistry
from core.guardrails import GuardrailManager
from core.orchestrator import MultiAgentOrchestrator, DependencyError as OrcDependencyError
from core.semantic_cache import SemanticCache, HitType as SCHitType
from core.embeddings import build_embedding_provider, cosine_similarity
from core.state_store import build_state_store
from core.snapshot import SnapshotManager
from core.streaming import StreamMetrics, stream_sse
from core.tenancy import TenantRegistry, Role, Permission
from core.coalescer import SingleFlight, make_key
from core.eval_harness import EvalHarness, exact_match, contains, jaccard, numeric_close
from core.vector_store import VectorStore
from core.pipeline import (
    RequestPipeline,
    PIIRedactionStep,
    PromptInjectionStep,
    TruncationStep,
    TokenCounterStep,
)
from core.validator import (
    OutputValidator,
    NonEmptyConstraint,
    JSONConstraint,
    LengthConstraint,
    RegexConstraint,
    BannedWordsConstraint,
)
from core.context_manager import ContextWindowManager, TrimStrategy
from core.consensus import ConsensusEngine
from core.intent_classifier import IntentClassifier, IntentDefinition
from core.citation_tracker import CitationTracker
from core.chunker import DocumentChunker, ChunkStrategy
from core.retriever import BM25Retriever
from core.reranker import HybridReranker, FusionMethod
from core.anonymizer import PIIAnonymizer
from core.cost_estimator import CostEstimator
from core.response_diff import ResponseComparator
from core.summarizer import ExtractiveSummarizer
from core.language_detector import LanguageDetector
from core.output_parser import OutputParser
from core.sentiment import SentimentAnalyzer
from core.keyword_extractor import KeywordExtractor
from core.readability import ReadabilityAnalyzer
from core.deduplicator import Deduplicator
from core.entity_extractor import EntityExtractor
from core.text_analytics import TextAnalyticsSuite
from core.fuzzy_matcher import FuzzyMatcher
from core.anomaly_detector import AnomalyDetector, DetectionMethod
from core.sampler import ReservoirSampler
from core.histogram import PercentileTracker
from core.webhook_dispatcher import WebhookDispatcher
from core.feature_flags import FeatureFlagManager
from core.health_aggregator import HealthAggregator, HealthStatus
from core.slo_monitor import SLOMonitor, SLOKind
from core.feedback import FeedbackStore
from hpc.cascade.cascade_router import CascadeRouter, LLMResponse as CascadeLLMResponse
from core.scheduler import TaskScheduler
from core.workflow import WorkflowEngine
from core.tool_registry import ToolRegistry
from core.tracing import get_finished_spans, setup_tracing
from core.graceful_shutdown import GracefulShutdown
from core.graph import SingularityCore
from core.log_buffer import LogBuffer
from core.logging_config import configure_logging
from core.task_events import TaskEventBus
from core.health_monitor import HealthMonitor
from core.session_store import ConversationTurn, SessionStore, estimate_cost
from core.task_queue import TaskPriority, TaskQueue
from core.user_limiter import UserRateLimiter
from evals.evaluator import OmegaEvaluator

log = structlog.get_logger()

# Singletony (jeden na proces)
core: SingularityCore | None = None
evaluator: OmegaEvaluator | None = None
health_monitor: HealthMonitor | None = None
task_queue: TaskQueue = TaskQueue()
session_store: SessionStore = SessionStore()
budget_manager: BudgetManager = BudgetManager()
user_limiter: UserRateLimiter = UserRateLimiter()
audit_log: AuditLog = AuditLog()
api_key_manager: ApiKeyManager = ApiKeyManager()
log_buffer: LogBuffer = LogBuffer(maxlen=500)
task_event_bus: TaskEventBus = TaskEventBus()
response_cache: ResponseCache = ResponseCache()
db: Database | None = None
scheduler: TaskScheduler = TaskScheduler()
tool_registry: ToolRegistry = ToolRegistry()
feedback_store: FeedbackStore = FeedbackStore()
workflow_engine: WorkflowEngine = WorkflowEngine()
ab_manager: ABTestManager = ABTestManager()
alert_manager: AlertManager = AlertManager()
prompt_registry: PromptTemplateRegistry = PromptTemplateRegistry()
batch_processor: BatchProcessor = BatchProcessor()
secret_manager: SecretManager = SecretManager()
quota_manager: QuotaManager = QuotaManager()
circuit_breakers: CircuitBreakerRegistry = CircuitBreakerRegistry()
guardrails: GuardrailManager = GuardrailManager()

# Embedding Provider (Fáze 61, v2.0) — pluggable, offline feature-hashing
# default with lexical locality; swap for an API-backed provider in production.
_embedding_provider = build_embedding_provider(
    settings.embedding_provider,
    dim=settings.embedding_dim,
    ngram=settings.embedding_ngram,
    cache_size=settings.embedding_cache_size,
)

# State Store (Fáze 62, v2.0) — backend-agnostic shared state; defaults to
# in-memory (identical to today), swappable to Redis for multi-instance.
_state_store = build_state_store(settings.state_backend, redis_url=settings.redis_url)

# Semantic Cache (Fáze 29) — now backed by the embedding provider (Fáze 61),
# so near-duplicate matching reflects real lexical overlap, not whole-text hash.
_semantic_cache: SemanticCache = SemanticCache(
    embed_fn=_embedding_provider.embed,
    threshold=settings.semantic_cache_threshold,
    max_size=settings.semantic_cache_max_size,
    ttl_s=settings.semantic_cache_ttl_s,
)

# Request Pipeline (Fáze 30)
_pipeline: RequestPipeline = RequestPipeline(fail_fast=settings.pipeline_fail_fast)
if settings.pipeline_pii_redaction:
    _pipeline.add_step(PIIRedactionStep())

# Output Validator (Fáze 31)
_validator: OutputValidator = OutputValidator(max_retries=settings.validator_max_retries)

# Context Window Manager (Fáze 32)
_context_manager: ContextWindowManager = ContextWindowManager(
    max_tokens=settings.context_max_tokens,
    keep_recent=settings.context_keep_recent,
    strategy=TrimStrategy(settings.context_trim_strategy),
)

# Consensus Engine (Fáze 33)
_consensus: ConsensusEngine = ConsensusEngine(
    n_samples=settings.consensus_n_samples,
    similarity_threshold=settings.consensus_similarity_threshold,
    agreement_threshold=settings.consensus_agreement_threshold,
)

# Intent Classifier (Fáze 34)
_intent_classifier: IntentClassifier = IntentClassifier(
    min_confidence=settings.intent_min_confidence,
    default_intent=settings.intent_default,
)

# Citation Tracker (Fáze 35)
_citation_tracker: CitationTracker = CitationTracker(
    threshold=settings.citation_threshold,
    max_citations=settings.citation_max_per_sentence,
)

# Document Chunker (Fáze 36)
_chunker: DocumentChunker = DocumentChunker(
    chunk_size=settings.chunk_size,
    overlap=settings.chunk_overlap,
    strategy=ChunkStrategy(settings.chunk_strategy),
)

# BM25 Retriever (Fáze 37)
_retriever: BM25Retriever = BM25Retriever(k1=settings.bm25_k1, b=settings.bm25_b)

# Hybrid Reranker (Fáze 38)
_reranker: HybridReranker = HybridReranker(
    rrf_k=settings.rrf_k,
    default_method=FusionMethod(settings.reranker_method),
)

# PII Anonymizer (Fáze 39)
_anonymizer: PIIAnonymizer = PIIAnonymizer()

# Cost Estimator (Fáze 40)
_cost_estimator: CostEstimator = CostEstimator()

# Response Comparator (Fáze 41)
_comparator: ResponseComparator = ResponseComparator()

# Extractive Summarizer (Fáze 42)
_summarizer: ExtractiveSummarizer = ExtractiveSummarizer(
    ratio=settings.summarizer_ratio,
    max_sentences=settings.summarizer_max_sentences,
)

# Language Detector (Fáze 43)
_language_detector: LanguageDetector = LanguageDetector(
    min_confidence=settings.language_min_confidence,
)

# Output Parser (Fáze 44)
_output_parser: OutputParser = OutputParser()

# Sentiment Analyzer (Fáze 45)
_sentiment: SentimentAnalyzer = SentimentAnalyzer(threshold=settings.sentiment_threshold)

# Keyword Extractor (Fáze 46)
_keyword_extractor: KeywordExtractor = KeywordExtractor(
    max_phrase_words=settings.keyword_max_phrase_words,
    min_word_length=settings.keyword_min_word_length,
)

# Readability Analyzer (Fáze 47)
_readability: ReadabilityAnalyzer = ReadabilityAnalyzer()

# Deduplicator (Fáze 48)
_deduplicator: Deduplicator = Deduplicator(
    threshold=settings.dedup_threshold,
    shingle_k=settings.dedup_shingle_k,
)

# Entity Extractor (Fáze 49)
_entity_extractor: EntityExtractor = EntityExtractor()

# Text Analytics Suite (Fáze 50) — composes the NLP analyzers above
_text_analytics: TextAnalyticsSuite = TextAnalyticsSuite(
    language_detector=_language_detector,
    sentiment_analyzer=_sentiment,
    readability_analyzer=_readability,
    keyword_extractor=_keyword_extractor,
    entity_extractor=_entity_extractor,
    summarizer=_summarizer,
)

# Fuzzy Matcher (Fáze 51)
_fuzzy_matcher: FuzzyMatcher = FuzzyMatcher(threshold=settings.fuzzy_threshold)

# Anomaly Detector (Fáze 52)
_anomaly_detector: AnomalyDetector = AnomalyDetector(
    method=DetectionMethod(settings.anomaly_method),
    window=settings.anomaly_window,
    z_threshold=settings.anomaly_z_threshold,
)

# Reservoir Sampler (Fáze 53)
_sampler: ReservoirSampler = ReservoirSampler(
    capacity=settings.sampler_capacity,
    seed=settings.sampler_seed,
)

# Percentile Tracker (Fáze 54)
_percentile_tracker: PercentileTracker = PercentileTracker(
    window=settings.percentile_window,
)

# Webhook Dispatcher (Fáze 55) — uses an httpx-backed sender at call time
import asyncio as _asyncio


async def _httpx_send(url: str, payload: str, headers: dict) -> int:
    """Default async sender. Imports httpx lazily so the module stays importable
    without the dependency in offline/test contexts (tests inject their own)."""
    import httpx
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, content=payload, headers=headers)
        return resp.status_code


async def _webhook_sleep(seconds: float) -> None:
    await _asyncio.sleep(seconds)


_webhook_dispatcher: WebhookDispatcher = WebhookDispatcher(
    max_retries=settings.webhook_max_retries,
    backoff_base=settings.webhook_backoff_base,
    sleep_fn=_webhook_sleep,
)

# Feature Flag Manager (Fáze 56)
_feature_flags: FeatureFlagManager = FeatureFlagManager()

# Snapshot Manager (Fáze 63, v2.0 #3) — persists stateful subsystems through
# the StateStore so they survive restarts (and, with Redis, are shared).
_snapshot_manager: SnapshotManager = SnapshotManager(_state_store)
_snapshot_manager.register("feature_flags", _feature_flags.export, _feature_flags.import_flags)

# Token streaming metrics (Fáze 64, v2.0 #4)
_stream_metrics: StreamMetrics = StreamMetrics()

# Multi-Tenancy & RBAC (Fáze 65, v2.0 #5)
_tenants: TenantRegistry = TenantRegistry()

# Request Coalescer (Fáze 66, v2.0 #6) — single-flight de-dup of concurrent
# identical work (complements the response/semantic caches for burst load).
_coalescer: SingleFlight = SingleFlight()

# Vector Store (Fáze 69, v2.0 #9) — dense retriever sharing the embedding
# provider (Fáze 61); semantic complement to BM25 (Fáze 37).
_vector_store: VectorStore = VectorStore(embedder=_embedding_provider)

# Health Aggregator (Fáze 57) — composes subsystem checks behind /healthz
_health_aggregator: HealthAggregator = HealthAggregator()


def _register_health_checks() -> None:
    """Wire core subsystems into the aggregator. Optional components degrade
    rather than fail the overall status."""
    _health_aggregator.register(
        "task_queue", lambda: HealthStatus.HEALTHY, required=True,
    )
    _health_aggregator.register(
        "response_cache",
        lambda: HealthStatus.HEALTHY if response_cache is not None else HealthStatus.UNHEALTHY,
        required=False,
    )
    _health_aggregator.register(
        "session_store", lambda: HealthStatus.HEALTHY, required=False,
    )
    _health_aggregator.register(
        "webhooks",
        lambda: (HealthStatus.DEGRADED, "dead-letters present")
        if _webhook_dispatcher.metrics()["dead_letters"] > 0 else HealthStatus.HEALTHY,
        required=False,
    )


_register_health_checks()

# SLO Monitor (Fáze 58)
_slo_monitor: SLOMonitor = SLOMonitor()

# Multi-Agent Orchestrator (Fáze 28)
_orchestrator: MultiAgentOrchestrator = MultiAgentOrchestrator(
    router=None,
    max_parallel=settings.orchestrator_max_parallel,
    timeout_s=settings.orchestrator_timeout_s,
)

# HPC Cascade router (Fáze 26) — initialized lazily on first use
_cascade_router: CascadeRouter | None = None

# Jednoduchý in-memory záznam provider_log per task (v produkci: Redis)
_task_provider_log: dict[str, dict] = {}

_MAX_CONTEXT_TURNS = 3  # kolik posledních turnů vstupuje jako kontext


def _build_session_context(user_id: str) -> str:
    """Sestaví řetězec posledních N turnů z session store pro multi-turn kontext."""
    history = session_store.get_history(user_id)
    turns = history["turns"][-_MAX_CONTEXT_TURNS:]
    if not turns:
        return ""
    return "\n".join(
        f"[Turn {i + 1}]\nTask: {t['task']}\nResponse: {t['response'][:300]}"
        for i, t in enumerate(turns)
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler — inicializace singletonů, health monitoru a task queue."""
    global core, evaluator, health_monitor, response_cache, db, feedback_store
    configure_logging(
        level=settings.log_level,
        log_format=settings.log_format,
        log_buffer=log_buffer,
    )
    if settings.enable_tracing:
        setup_tracing(otlp_endpoint=settings.otlp_endpoint)
    if settings.enable_persistence:
        db = Database(db_path=settings.db_path)
        db.init_schema()
        audit_log.attach_db(db)
        api_key_manager.attach_db(db)
        feedback_store.attach_db(db)
        log.info("persistence_enabled", db_path=settings.db_path)
    response_cache = ResponseCache(
        maxsize=settings.cache_max_size,
        default_ttl_s=settings.cache_ttl_s,
    )
    core = SingularityCore()
    evaluator = OmegaEvaluator()
    health_monitor = HealthMonitor(core.router, interval_s=30.0)
    health_monitor.start()
    set_manager(api_key_manager)
    task_queue.start(core, audit=audit_log, num_workers=settings.task_workers,
                     event_bus=task_event_bus)
    if settings.enable_scheduler:
        scheduler.start(task_queue)
    shutdown = GracefulShutdown(task_queue, timeout_s=30.0)
    shutdown.register()
    log.info("singularity_started", strategy=core.router.strategy,
             task_workers=settings.task_workers, require_api_key=settings.require_api_key)
    yield
    health_monitor.stop()
    scheduler.stop()
    await shutdown.drain()   # waits for in-flight tasks, then stops workers
    log.info("singularity_shutdown")


app = FastAPI(
    title="Singularity API",
    version=APP_VERSION,
    description="Multi-LLM Meta-Cognitive Core (Claude + Gemini)",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # V produkci: omezit na konkrétní domény
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Modely ────────────────────────────────────────────────────────────────────

class TaskRequest(BaseModel):
    task: str
    user_id: str = "default"
    approved: bool = False
    force_provider: str = ""   # "" | "claude" | "gemini"
    callback_url: str = ""     # Fáze 4: webhook po dokončení async tasku
    priority: str = "NORMAL"   # Fáze 5: CRITICAL | HIGH | NORMAL | LOW
    max_retries: int = 0       # Fáze 6: max retry pokusů (0 = žádný retry)


class ApprovalRequest(BaseModel):
    session_id: str
    approved: bool


class StrategyRequest(BaseModel):
    strategy: str


class TaskResponse(BaseModel):
    session_id: str
    response: str
    eval_scores: dict
    provider_log: dict


class BatchTaskRequest(BaseModel):
    tasks: list[TaskRequest]


class BudgetRequest(BaseModel):
    limit_usd: float


class RateLimitRequest(BaseModel):
    rpm: int


class ApiKeyRequest(BaseModel):
    user_id: str


class ScheduledJobRequest(BaseModel):
    task: str
    user_id: str = "default"
    interval_s: float = 60.0
    force_provider: str = ""
    priority: str = "NORMAL"
    max_retries: int = 0


class RegisterToolRequest(BaseModel):
    name: str
    description: str
    params_schema: dict = {}
    callback_url: str = ""  # non-empty → HTTP-callback tool; empty → rejected via API


class InvokeToolRequest(BaseModel):
    params: dict = {}


class FeedbackRequest(BaseModel):
    session_id: str = ""
    rating: int             # 1–5
    thumbs: str = ""        # "up" | "down" | ""
    comment: str = ""


class WorkflowStepRequest(BaseModel):
    task: str
    user_id: str = "workflow"
    force_provider: str = ""
    priority: str = "NORMAL"
    max_retries: int = 0


class CreateWorkflowRequest(BaseModel):
    name: str
    steps: list[WorkflowStepRequest]


class CreateExperimentRequest(BaseModel):
    name: str
    control_provider: str
    treatment_provider: str
    traffic_split: float = 0.5


class UpdateExperimentRequest(BaseModel):
    status: str | None = None
    traffic_split: float | None = None


class RecordOutcomeRequest(BaseModel):
    provider: str
    success: bool
    latency_ms: float = 0.0
    rating: float | None = None


class CreateAlertRequest(BaseModel):
    name: str
    condition: str
    threshold: float
    callback_url: str


class UpdateAlertRequest(BaseModel):
    status: str      # "active" | "muted"


class EvaluateAlertRequest(BaseModel):
    condition: str
    value: float


class RegisterPromptRequest(BaseModel):
    name: str
    template: str
    description: str = ""
    tags: list[str] = []


class RenderPromptRequest(BaseModel):
    variables: dict[str, str] = {}


class BatchTaskInput(BaseModel):
    task: str
    user_id: str
    force_provider: str = ""
    priority: str = "NORMAL"


class SubmitBatchRequest(BaseModel):
    tasks: list[BatchTaskInput]


class StoreSecretRequest(BaseModel):
    name: str
    value: str
    owner: str
    description: str = ""
    tags: list[str] = []
    ttl_s: float | None = None


class RotateSecretRequest(BaseModel):
    new_value: str


class SetQuotaRequest(BaseModel):
    user_id: str
    metric: str
    limit: float
    window: str = "daily"


class RecordQuotaUsageRequest(BaseModel):
    user_id: str
    requests: float = 0.0
    tokens: float = 0.0
    cost_usd: float = 0.0


class CreateBreakerRequest(BaseModel):
    name: str
    failure_threshold: int = 5
    recovery_timeout_s: float = 60.0
    success_threshold: int = 2


class RecordBreakerEventRequest(BaseModel):
    event: str   # "success" | "failure" | "rejected"


# ── REST endpointy ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "version": APP_VERSION}


@app.get("/health/live")
async def health_live() -> dict:
    """Liveness probe — vždy 200, signalizuje že process běží (Fáze 8)."""
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready() -> dict:
    """Readiness probe — 200 až po inicializaci core (Fáze 8)."""
    if core is None:
        raise HTTPException(status_code=503, detail="Initializing")
    return {"status": "ready", "strategy": core.router.strategy}


@app.post("/task", response_model=TaskResponse)
async def submit_task(req: TaskRequest, _auth: str = Depends(verify_api_key)) -> TaskResponse:
    assert core is not None and evaluator is not None
    session_id = str(uuid.uuid4())
    log.info("task_received", user_id=req.user_id, session_id=session_id)

    # Cache lookup (Fáze 12)
    cache_key = ResponseCache.make_key(req.task, req.force_provider, req.approved)
    if settings.enable_cache:
        cached = await response_cache.get(cache_key)
        if cached is not None:
            log.info("cache_hit", session_id=session_id, user_id=req.user_id)
            return TaskResponse(
                session_id=session_id,
                response=cached["response"],
                eval_scores=cached["eval_scores"],
                provider_log=cached["provider_log"],
            )

    session_context = _build_session_context(req.user_id)

    try:
        result = await core.run(
            task=req.task,
            user_id=req.user_id,
            session_id=session_id,
            approved=req.approved,
            force_provider=req.force_provider,
            session_context=session_context,
        )
    except Exception as exc:
        log.error("task_error", error=str(exc), session_id=session_id)
        raise HTTPException(status_code=500, detail=str(exc))

    _task_provider_log[session_id] = result["provider_log"]

    try:
        eval_scores = evaluator.evaluate_response(req.task, result["response"])
    except Exception as exc:
        log.warning("eval_failed", error=str(exc))
        eval_scores = {}

    # Ulož turn do session store (Fáze 3: včetně eval_scores)
    cost = estimate_cost(result["response"], result["provider_log"])
    session_store.add_turn(
        req.user_id,
        ConversationTurn(
            task=req.task,
            response=result["response"],
            provider_log=result["provider_log"],
            risk_score=result.get("risk_score", 0.0),
            cost_usd=cost,
            eval_scores=eval_scores,
        ),
    )

    # Cache store (Fáze 12)
    if settings.enable_cache:
        await response_cache.set(cache_key, {
            "response": result["response"],
            "eval_scores": eval_scores,
            "provider_log": result["provider_log"],
        })

    return TaskResponse(
        session_id=session_id,
        response=result["response"],
        eval_scores=eval_scores,
        provider_log=result["provider_log"],
    )


@app.post("/task/async")
async def submit_task_async(req: TaskRequest, _auth: str = Depends(verify_api_key)) -> dict:
    """Zařadí úkol do fronty a okamžitě vrátí task_id (Fáze 3 + 5)."""
    assert core is not None
    if not budget_manager.is_allowed(req.user_id):
        raise HTTPException(status_code=402, detail="Budget exceeded")
    if not user_limiter.check_and_record(req.user_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    try:
        priority = TaskPriority[req.priority.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Neznámá priorita: {req.priority}")
    session_context = _build_session_context(req.user_id)
    task_id = await task_queue.submit(
        task=req.task,
        user_id=req.user_id,
        approved=req.approved,
        force_provider=req.force_provider,
        session_context=session_context,
        callback_url=req.callback_url,
        priority=priority,
        max_retries=max(0, req.max_retries),
    )
    audit_log.record("task_submitted", req.user_id, task_id=task_id,
                     priority=priority.name, max_retries=req.max_retries)
    return {"task_id": task_id, "status": "queued", "priority": priority.name, "queue_size": task_queue.queue_size()}


@app.get("/task/{task_id}/status")
async def get_task_status(task_id: str) -> dict:
    """Vrátí stav async tasku (Fáze 3)."""
    status = task_queue.get_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Neznámé task_id")
    return status


@app.get("/task/{task_id}/result")
async def get_task_result(task_id: str) -> dict:
    """Vrátí výsledek dokončeného async tasku (Fáze 3)."""
    result = task_queue.get_result(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Neznámé task_id")
    return result


@app.get("/task/{task_id}/wait")
async def wait_for_task(task_id: str, timeout: float = 60.0) -> dict:
    """
    Long-poll: blokuje až do dokončení tasku nebo vypršení timeoutu (Fáze 5).
    timeout: maximální čekání v sekundách (výchozí 60, max 300).
    """
    timeout = min(max(timeout, 1.0), 300.0)
    result = await task_queue.wait(task_id, timeout=timeout)
    if result is None:
        status = task_queue.get_status(task_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Neznámé task_id")
        raise HTTPException(status_code=408, detail="Timeout — task ještě nedoběhl")
    return result


@app.get("/task/{task_id}/stream")
async def stream_task_events(task_id: str) -> StreamingResponse:
    """SSE stream of task lifecycle events (Fáze 11)."""
    status = task_queue.get_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Neznámé task_id")

    async def event_generator():
        if status["status"] in ("completed", "failed", "dlq"):
            result = task_queue.get_result(task_id)
            yield f"data: {json.dumps(result)}\n\n"
            yield "data: [DONE]\n\n"
            return
        q = await task_event_bus.subscribe(task_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=300.0)
                except asyncio.TimeoutError:
                    break
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("status") in ("completed", "failed", "dlq"):
                    break
        finally:
            await task_event_bus.unsubscribe(task_id, q)
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/task/compare")
async def compare_task(req: TaskRequest) -> dict:
    """
    Spustí úkol paralelně na Claude i Gemini a vrátí porovnání (Fáze 3).
    Pokud Gemini není k dispozici, vrátí pouze výsledek Clauda.
    """
    assert core is not None
    session_context = _build_session_context(req.user_id)
    sid_claude = str(uuid.uuid4())
    sid_gemini = str(uuid.uuid4())

    run_kwargs = dict(
        task=req.task,
        user_id=req.user_id,
        approved=req.approved,
        session_context=session_context,
    )

    results = await asyncio.gather(
        core.run(**run_kwargs, session_id=sid_claude, force_provider="claude"),
        core.run(**run_kwargs, session_id=sid_gemini, force_provider="gemini"),
        return_exceptions=True,
    )

    def _fmt(r, sid):
        if isinstance(r, Exception):
            return {"error": str(r), "session_id": sid}
        return {**r, "session_id": sid}

    return {
        "task": req.task,
        "claude": _fmt(results[0], sid_claude),
        "gemini": _fmt(results[1], sid_gemini),
        "gemini_enabled": core.router.gemini_enabled,
    }


@app.post("/task/batch")
async def submit_task_batch(req: BatchTaskRequest) -> dict:
    """
    Dávkové odeslání úkolů do fronty (Fáze 4).
    Maximum 10 úkolů na požadavek.
    """
    assert core is not None
    if len(req.tasks) == 0:
        raise HTTPException(status_code=400, detail="Prázdná dávka")
    if len(req.tasks) > 10:
        raise HTTPException(status_code=400, detail="Maximum je 10 úkolů na dávku")

    task_ids = []
    for t in req.tasks:
        if not budget_manager.is_allowed(t.user_id):
            raise HTTPException(status_code=402, detail=f"Budget exceeded for user {t.user_id}")
        session_context = _build_session_context(t.user_id)
        task_id = await task_queue.submit(
            task=t.task,
            user_id=t.user_id,
            approved=t.approved,
            force_provider=t.force_provider,
            session_context=session_context,
            callback_url=t.callback_url,
        )
        task_ids.append(task_id)

    return {"task_ids": task_ids, "count": len(task_ids), "queue_size": task_queue.queue_size()}


@app.get("/queue/status")
async def queue_status() -> dict:
    """Vrátí aktuální stav fronty (Fáze 4)."""
    return {"queue_size": task_queue.queue_size()}


@app.post("/task/stream")
async def stream_task(req: TaskRequest) -> StreamingResponse:
    """SSE streaming endpoint: posílá progress event po každém uzlu grafu."""
    assert core is not None
    session_id = str(uuid.uuid4())
    log.info("task_stream_received", user_id=req.user_id, session_id=session_id)

    session_context = _build_session_context(req.user_id)

    async def event_generator():
        started = json.dumps({"event": "started", "session_id": session_id})
        yield f"data: {started}\n\n"
        try:
            async for event in core.run_stream(
                task=req.task,
                user_id=req.user_id,
                session_id=session_id,
                approved=req.approved,
                force_provider=req.force_provider,
                session_context=session_context,
            ):
                payload = {**event, "session_id": session_id}
                yield f"data: {json.dumps(payload)}\n\n"

                if event.get("event") == "completed":
                    _task_provider_log[session_id] = event.get("provider_log", {})
                    cost = estimate_cost(
                        event.get("response", ""), event.get("provider_log", {})
                    )
                    session_store.add_turn(
                        req.user_id,
                        ConversationTurn(
                            task=req.task,
                            response=event.get("response", ""),
                            provider_log=event.get("provider_log", {}),
                            risk_score=event.get("risk_score", 0.0),
                            cost_usd=cost,
                        ),
                    )
        except Exception as exc:
            err = json.dumps({"event": "error", "message": str(exc), "session_id": session_id})
            yield f"data: {err}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/approve")
async def approve_task(req: ApprovalRequest) -> dict:
    status = "approved" if req.approved else "rejected"
    log.info("approval_decision", session_id=req.session_id, status=status)
    return {"status": status, "session_id": req.session_id}


@app.post("/e-stop")
async def emergency_stop() -> dict:
    assert core is not None
    core.e_stop()
    log.critical("E_STOP_API_TRIGGERED")
    return {"status": "E_STOP_ACTIVATED"}


@app.get("/memory/{user_id}")
async def get_memory(user_id: str) -> dict:
    assert core is not None
    try:
        memories = core.memory.get_all(user_id=user_id)
        return {"user_id": user_id, "count": len(memories), "memories": memories}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/providers")
async def list_providers() -> dict:
    assert core is not None
    return {
        "strategy": core.router.strategy,
        "gemini_enabled": core.router.gemini_enabled,
        "providers": [p.status() for p in core.router.all_providers()],
    }


@app.post("/router/strategy")
async def set_strategy(req: StrategyRequest) -> dict:
    assert core is not None
    try:
        core.router.set_strategy(req.strategy)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok", "strategy": core.router.strategy}


@app.get("/metrics")
async def metrics() -> Response:
    payload, content_type = telemetry.metrics_payload()
    return Response(content=payload, media_type=content_type)


@app.get("/tasks/{session_id}/providers")
async def task_providers(session_id: str) -> dict:
    plog = _task_provider_log.get(session_id)
    if plog is None:
        raise HTTPException(status_code=404, detail="Neznámé session_id")
    return {"session_id": session_id, "provider_log": plog}


@app.get("/sessions/{user_id}")
async def get_session(user_id: str) -> dict:
    """Vrátí konverzační historii a kumulativní náklady pro uživatele."""
    return session_store.get_history(user_id)


@app.get("/sessions")
async def list_sessions() -> dict:
    """Vrátí seznam uživatelů s aktivními session."""
    return {"users": session_store.list_users()}


@app.get("/sessions/{user_id}/export")
async def export_session(user_id: str) -> Response:
    """JSON export kompletní session historie (Fáze 3)."""
    history = session_store.get_history(user_id)
    payload = json.dumps(history, ensure_ascii=False, indent=2)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="session_{user_id}.json"'},
    )


@app.get("/health/providers")
async def health_check_providers() -> dict:
    """Okamžitý health check všech providerů (Fáze 2)."""
    assert health_monitor is not None
    results = await health_monitor.run_once()
    return {"results": results}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    """Admin dashboard — live přehled providerů, sessionů a metrik (Fáze 2)."""
    return HTMLResponse(content=get_dashboard_html())


# ── Budget endpointy (Fáze 4) ──────────────────────────────────────────────────

@app.post("/budget/{user_id}")
async def set_budget(user_id: str, req: BudgetRequest) -> dict:
    """Nastaví nebo aktualizuje cost limit uživatele (Fáze 4)."""
    budget_manager.set_budget(user_id, req.limit_usd)
    return budget_manager.get_status(user_id)


@app.get("/budget/{user_id}")
async def get_budget(user_id: str) -> dict:
    """Vrátí stav budgetu uživatele (Fáze 4)."""
    return budget_manager.get_status(user_id)


@app.delete("/budget/{user_id}")
async def delete_budget(user_id: str) -> dict:
    """Odstraní cost limit uživatele (nastaví na neomezeno, Fáze 4)."""
    budget_manager.set_budget(user_id, 0.0)  # 0 → None = neomezeno
    return budget_manager.get_status(user_id)


# ── Per-user rate limit endpointy (Fáze 5) ────────────────────────────────────

@app.post("/rate-limits/{user_id}")
async def set_rate_limit(user_id: str, req: RateLimitRequest) -> dict:
    """Nastaví RPM limit pro uživatele (Fáze 5). rpm=0 odebere omezení."""
    user_limiter.set_limit(user_id, req.rpm)
    return user_limiter.get_status(user_id)


@app.get("/rate-limits/{user_id}")
async def get_rate_limit(user_id: str) -> dict:
    """Vrátí stav RPM limitu a počet požadavků za poslední minutu (Fáze 5)."""
    return user_limiter.get_status(user_id)


@app.delete("/rate-limits/{user_id}")
async def delete_rate_limit(user_id: str) -> dict:
    """Odebere RPM limit a resetuje counter uživatele (Fáze 5)."""
    user_limiter.reset(user_id)
    return user_limiter.get_status(user_id)


# ── Audit log + DLQ endpointy (Fáze 6) ────────────────────────────────────────

@app.get("/audit-log")
async def get_audit_log(
    limit: int = 100,
    event_type: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Vrátí posledních N audit událostí (Fáze 6)."""
    limit = min(max(limit, 1), 1000)
    events = audit_log.get_events(limit=limit, event_type=event_type, user_id=user_id)
    return {"count": len(events), "events": events}


@app.get("/dead-letter-queue")
async def get_dlq() -> dict:
    """Vrátí tasky, které vyčerpaly všechny retry pokusy (Fáze 6)."""
    items = task_queue.get_dlq()
    return {"count": len(items), "tasks": items}


@app.post("/dead-letter-queue/{task_id}/retry")
async def retry_dlq_task(task_id: str) -> dict:
    """Manuálně znovu zařadí DLQ task do fronty (Fáze 6)."""
    success = await task_queue.retry_from_dlq(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task není v DLQ")
    audit_log.record("task_dlq_retried", user_id="admin", task_id=task_id)
    return {"status": "requeued", "task_id": task_id}


# ── Structured log endpoint (Fáze 10) ────────────────────────────────────────

@app.get("/logs/recent")
async def get_recent_logs(
    limit: int = 50,
    level: str | None = None,
) -> dict:
    """Vrátí posledních N strukturovaných log událostí z in-memory bufferu (Fáze 10)."""
    limit = min(max(limit, 1), 500)
    events = log_buffer.get_recent(limit=limit, level=level)
    return {"count": len(events), "events": events}


# ── Response cache endpointy (Fáze 12) ────────────────────────────────────────

@app.get("/cache/stats")
async def get_cache_stats() -> dict:
    """Vrátí statistiky response cache: hits, misses, evictions, hit_rate (Fáze 12)."""
    return response_cache.stats()


@app.delete("/cache")
async def clear_cache() -> dict:
    """Vymaže celou response cache (Fáze 12)."""
    cleared = await response_cache.clear()
    log.info("cache_cleared", entries=cleared)
    return {"status": "ok", "cleared": cleared}


# ── Tracing endpoint (Fáze 13) ────────────────────────────────────────────────

@app.get("/traces")
async def get_traces(limit: int = 50) -> dict:
    """Vrátí posledních N OTel spanů z in-memory exporteru (Fáze 13)."""
    limit = min(max(limit, 1), 500)
    spans = get_finished_spans(limit=limit)
    return {"count": len(spans), "spans": spans}


# ── Persistence status (Fáze 14) ─────────────────────────────────────────────

@app.get("/db/status")
async def db_status() -> dict:
    """Vrátí stav SQLite persistence (Fáze 14)."""
    if db is None:
        return {"enabled": False, "db_path": None}
    audit_count = db.fetchone("SELECT COUNT(*) AS n FROM audit_events") or {}
    key_count   = db.fetchone("SELECT COUNT(*) AS n FROM api_keys WHERE revoked=0") or {}
    return {
        "enabled": True,
        "db_path": settings.db_path,
        "audit_events": audit_count.get("n", 0),
        "active_api_keys": key_count.get("n", 0),
    }


# ── Scheduler endpointy (Fáze 15) ────────────────────────────────────────────

@app.post("/scheduler/jobs")
async def create_scheduled_job(req: ScheduledJobRequest) -> dict:
    """Přidá nový opakovaný úkol do scheduleru (Fáze 15)."""
    try:
        job_id = scheduler.add_job(
            task=req.task,
            user_id=req.user_id,
            interval_s=req.interval_s,
            force_provider=req.force_provider,
            priority=req.priority,
            max_retries=req.max_retries,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"job_id": job_id, "status": "scheduled", "interval_s": req.interval_s}


@app.get("/scheduler/jobs")
async def list_scheduled_jobs() -> dict:
    """Vypíše všechny naplánované joby (Fáze 15)."""
    jobs = scheduler.list_jobs()
    return {"count": len(jobs), "jobs": jobs}


@app.get("/scheduler/jobs/{job_id}")
async def get_scheduled_job(job_id: str) -> dict:
    """Vrátí detail konkrétního jobu (Fáze 15)."""
    job = scheduler.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job nenalezen")
    return job


@app.delete("/scheduler/jobs/{job_id}")
async def delete_scheduled_job(job_id: str) -> dict:
    """Odstraní naplánovaný job (Fáze 15)."""
    removed = scheduler.remove_job(job_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Job nenalezen")
    return {"status": "removed", "job_id": job_id}


# ── Alerting (Fáze 20) ───────────────────────────────────────────────────────

@app.post("/alerts")
async def create_alert(req: CreateAlertRequest) -> dict:
    """Vytvoří prahový alert s HTTP-callback (Fáze 20)."""
    try:
        aid = alert_manager.create_alert(
            name=req.name,
            condition=req.condition,
            threshold=req.threshold,
            callback_url=req.callback_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"alert_id": aid, "name": req.name, "condition": req.condition}


@app.get("/alerts")
async def list_alerts() -> dict:
    """Vypíše všechny definované alerty (Fáze 20)."""
    items = alert_manager.list_alerts()
    return {"count": len(items), "alerts": items}


@app.get("/alerts/{alert_id}")
async def get_alert(alert_id: str) -> dict:
    """Vrátí detail alertu včetně fire_count (Fáze 20)."""
    a = alert_manager.get_alert(alert_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Alert nenalezen")
    return a


@app.patch("/alerts/{alert_id}")
async def update_alert_status(alert_id: str, req: UpdateAlertRequest) -> dict:
    """Ztlumí nebo aktivuje alert (Fáze 20)."""
    try:
        ok = alert_manager.set_status(alert_id, req.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Alert nenalezen")
    return {"status": "updated", "alert_id": alert_id, "new_status": req.status}


@app.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str) -> dict:
    """Smaže alert (Fáze 20)."""
    if not alert_manager.delete_alert(alert_id):
        raise HTTPException(status_code=404, detail="Alert nenalezen")
    return {"status": "deleted", "alert_id": alert_id}


@app.post("/alerts/evaluate")
async def evaluate_alerts(req: EvaluateAlertRequest) -> dict:
    """Ručně spustí evaluaci alertů pro daný condition + value (Fáze 20)."""
    fired = await alert_manager.evaluate(req.condition, req.value)
    return {"condition": req.condition, "value": req.value, "fired_count": len(fired), "fired": fired}


# ── A/B Testing (Fáze 19) ────────────────────────────────────────────────────

@app.post("/experiments")
async def create_experiment(req: CreateExperimentRequest) -> dict:
    """Vytvoří A/B experiment pro dva providery (Fáze 19)."""
    try:
        eid = ab_manager.create_experiment(
            name=req.name,
            control_provider=req.control_provider,
            treatment_provider=req.treatment_provider,
            traffic_split=req.traffic_split,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"experiment_id": eid, "name": req.name}


@app.get("/experiments")
async def list_experiments() -> dict:
    """Vypíše A/B experimenty (Fáze 19)."""
    items = ab_manager.list_experiments()
    return {"count": len(items), "experiments": items}


@app.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str) -> dict:
    """Vrátí detail A/B experimentu včetně metrik (Fáze 19)."""
    exp = ab_manager.get_experiment(experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment nenalezen")
    return exp


@app.patch("/experiments/{experiment_id}")
async def update_experiment(experiment_id: str, req: UpdateExperimentRequest) -> dict:
    """Aktualizuje status nebo traffic_split experimentu (Fáze 19)."""
    kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
    try:
        ok = ab_manager.update_experiment(experiment_id, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Experiment nenalezen")
    return {"status": "updated", "experiment_id": experiment_id}


@app.post("/experiments/{experiment_id}/record")
async def record_experiment_outcome(experiment_id: str, req: RecordOutcomeRequest) -> dict:
    """Zaznamená výsledek požadavku pro daný variant (Fáze 19)."""
    ok = ab_manager.record_outcome(
        experiment_id=experiment_id,
        provider=req.provider,
        success=req.success,
        latency_ms=req.latency_ms,
        rating=req.rating,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Experiment nebo provider nenalezen")
    return {"status": "recorded"}


@app.delete("/experiments/{experiment_id}")
async def delete_experiment(experiment_id: str) -> dict:
    """Smaže A/B experiment (Fáze 19)."""
    if not ab_manager.delete_experiment(experiment_id):
        raise HTTPException(status_code=404, detail="Experiment nenalezen")
    return {"status": "deleted", "experiment_id": experiment_id}


# ── Workflow Engine (Fáze 18) ─────────────────────────────────────────────────

@app.post("/workflows")
async def create_workflow(req: CreateWorkflowRequest) -> dict:
    """Vytvoří nový workflow (Fáze 18)."""
    try:
        wid = workflow_engine.create_workflow(
            name=req.name,
            steps=[s.model_dump() for s in req.steps],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"workflow_id": wid, "name": req.name, "step_count": len(req.steps)}


@app.get("/workflows")
async def list_workflows() -> dict:
    """Vypíše všechny workflows (Fáze 18)."""
    items = workflow_engine.list_workflows()
    return {"count": len(items), "workflows": items}


@app.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str) -> dict:
    """Vrátí detail workflow (Fáze 18)."""
    wf = workflow_engine.get_workflow(workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow nenalezen")
    return wf


@app.post("/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str) -> dict:
    """Spustí workflow asynchronně (Fáze 18). Vrátí okamžitě."""
    wf = workflow_engine.get_workflow(workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow nenalezen")
    if wf["status"] == "running":
        raise HTTPException(status_code=409, detail="Workflow již běží")

    async def _run():
        try:
            await workflow_engine.run_workflow(workflow_id, task_queue)
        except Exception as exc:
            log.error("workflow_run_error", workflow_id=workflow_id, error=str(exc))

    asyncio.create_task(_run(), name=f"workflow_{workflow_id}")
    return {"status": "started", "workflow_id": workflow_id}


# ── Human Feedback (Fáze 17) ─────────────────────────────────────────────────

@app.post("/task/{task_id}/feedback")
async def submit_feedback(task_id: str, req: FeedbackRequest) -> dict:
    """Uloží hodnocení pro daný task (Fáze 17)."""
    try:
        fid = feedback_store.record(
            task_id=task_id,
            session_id=req.session_id,
            user_id="user",
            rating=req.rating,
            thumbs=req.thumbs,
            comment=req.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"feedback_id": fid, "task_id": task_id}


@app.get("/task/{task_id}/feedback")
async def get_task_feedback(task_id: str) -> dict:
    """Vrátí všechna hodnocení pro daný task (Fáze 17)."""
    entries = feedback_store.get_by_task(task_id)
    return {"task_id": task_id, "count": len(entries), "feedback": entries}


@app.get("/feedback/stats")
async def get_feedback_stats() -> dict:
    """Agregované statistiky hodnocení (Fáze 17)."""
    return feedback_store.get_stats()


# ── Tool Registry (Fáze 16) ───────────────────────────────────────────────────

@app.post("/tools")
async def register_tool(req: RegisterToolRequest) -> dict:
    """Registruje HTTP-callback tool (Fáze 16). callback_url je povinný pro API registraci."""
    if not req.callback_url:
        raise HTTPException(status_code=422, detail="callback_url je povinný pro API registraci")
    try:
        tool_registry.register_http(
            name=req.name,
            description=req.description,
            params_schema=req.params_schema,
            callback_url=req.callback_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit_log.record("tool_registered", user_id="admin", tool_name=req.name)
    return {"status": "registered", "name": req.name, "tool_type": "http"}


@app.get("/tools")
async def list_tools() -> dict:
    """Vypíše všechny registrované nástroje (Fáze 16)."""
    tools = tool_registry.list_tools()
    return {"count": len(tools), "tools": tools}


@app.delete("/tools/{name}")
async def unregister_tool(name: str) -> dict:
    """Odregistruje nástroj dle jména (Fáze 16)."""
    removed = tool_registry.unregister(name)
    if not removed:
        raise HTTPException(status_code=404, detail="Nástroj nenalezen")
    audit_log.record("tool_unregistered", user_id="admin", tool_name=name)
    return {"status": "unregistered", "name": name}


@app.post("/tools/{name}/invoke")
async def invoke_tool(name: str, req: InvokeToolRequest) -> dict:
    """Invokuje registrovaný nástroj s danými parametry (Fáze 16)."""
    try:
        result = await tool_registry.invoke(name, **req.params)
    except KeyError:
        raise HTTPException(status_code=404, detail="Nástroj nenalezen")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Chyba nástroje: {exc}") from exc
    return {"name": name, "result": result}


# ── Prompt Template Registry (Fáze 21) ───────────────────────────────────────

@app.post("/prompts")
async def register_prompt(req: RegisterPromptRequest) -> dict:
    """Registruje pojmenovanou prompt šablonu s {{proměnnými}} (Fáze 21)."""
    try:
        tid = prompt_registry.register(
            name=req.name,
            template=req.template,
            description=req.description,
            tags=req.tags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    t = prompt_registry.get(tid)
    return {"template_id": tid, "name": req.name, "version": t["version"],
            "variables": t["variables"]}


@app.get("/prompts")
async def list_prompts(tag: str | None = None) -> dict:
    """Vypíše všechny prompt šablony; volitelně filtrovat dle tagu (Fáze 21)."""
    items = prompt_registry.list_templates(tag=tag)
    return {"count": len(items), "templates": items}


@app.get("/prompts/{template_id}")
async def get_prompt(template_id: str) -> dict:
    """Vrátí detail prompt šablony (Fáze 21)."""
    t = prompt_registry.get(template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Šablona nenalezena")
    return t


@app.delete("/prompts/{template_id}")
async def delete_prompt(template_id: str) -> dict:
    """Smaže prompt šablonu (Fáze 21)."""
    if not prompt_registry.delete(template_id):
        raise HTTPException(status_code=404, detail="Šablona nenalezena")
    return {"status": "deleted", "template_id": template_id}


@app.post("/prompts/{template_id}/render")
async def render_prompt(template_id: str, req: RenderPromptRequest) -> dict:
    """Renderuje prompt šablonu s danými proměnnými (Fáze 21)."""
    try:
        result = prompt_registry.render(template_id, **req.variables)
    except KeyError:
        raise HTTPException(status_code=404, detail="Šablona nenalezena")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"template_id": template_id, "rendered": result}


# ── Batch Processor (Fáze 22) ────────────────────────────────────────────────

@app.post("/batch")
async def submit_batch(req: SubmitBatchRequest) -> dict:
    """Registruje dávku tasků; vrátí batch_id (Fáze 22)."""
    try:
        bid = batch_processor.submit([t.model_dump() for t in req.tasks])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    b = batch_processor.get_batch(bid)
    return {"batch_id": bid, "total": b["total"], "status": b["status"]}


@app.get("/batch")
async def list_batches() -> dict:
    """Vypíše všechny dávky (Fáze 22)."""
    items = batch_processor.list_batches()
    return {"count": len(items), "batches": items}


@app.get("/batch/{batch_id}")
async def get_batch(batch_id: str) -> dict:
    """Vrátí stav a výsledky dávky (Fáze 22)."""
    b = batch_processor.get_batch(batch_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Dávka nenalezena")
    return b


@app.delete("/batch/{batch_id}")
async def cancel_batch(batch_id: str) -> dict:
    """Zruší čekající dávku (Fáze 22)."""
    if not batch_processor.cancel(batch_id):
        raise HTTPException(status_code=404, detail="Dávka nenalezena nebo již spuštěna")
    return {"status": "cancelled", "batch_id": batch_id}


@app.post("/batch/{batch_id}/run")
async def run_batch(batch_id: str) -> dict:
    """Odešle všechny tasky dávky do fronty a čeká na dokončení (Fáze 22)."""
    try:
        result = await batch_processor.run_batch(batch_id, task_queue)
    except KeyError:
        raise HTTPException(status_code=404, detail="Dávka nenalezena")
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result


# ── Secret Manager (Fáze 23) ─────────────────────────────────────────────────

@app.post("/secrets")
async def store_secret(req: StoreSecretRequest) -> dict:
    """Uloží pojmenované tajemství s volitelným TTL (Fáze 23)."""
    try:
        sid = secret_manager.store(
            req.name, req.value,
            owner=req.owner, description=req.description,
            tags=req.tags, ttl_s=req.ttl_s,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"secret_id": sid, "name": req.name, "owner": req.owner}


@app.get("/secrets")
async def list_secrets(owner: str, tag: str | None = None) -> dict:
    """Vypíše tajemství daného vlastníka (hodnoty zamaskované) (Fáze 23)."""
    items = secret_manager.list_secrets(owner=owner, tag=tag)
    return {"count": len(items), "secrets": items}


@app.get("/secrets/{secret_id}")
async def get_secret(secret_id: str, owner: str) -> dict:
    """Vrátí metadata tajemství (hodnota zamaskovaná) (Fáze 23)."""
    s = secret_manager.get(secret_id, owner=owner)
    if s is None:
        raise HTTPException(status_code=404, detail="Tajemství nenalezeno nebo přístup odepřen")
    return s


@app.get("/secrets/{secret_id}/reveal")
async def reveal_secret(secret_id: str, owner: str) -> dict:
    """Vrátí plaintext hodnotu tajemství (Fáze 23)."""
    value = secret_manager.reveal(secret_id, owner=owner)
    if value is None:
        raise HTTPException(status_code=404, detail="Tajemství nenalezeno, vypršelo nebo přístup odepřen")
    return {"secret_id": secret_id, "value": value}


@app.post("/secrets/{secret_id}/rotate")
async def rotate_secret(secret_id: str, req: RotateSecretRequest, owner: str) -> dict:
    """Nahradí hodnotu tajemství (Fáze 23)."""
    try:
        ok = secret_manager.rotate(secret_id, req.new_value, owner=owner)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Tajemství nenalezeno, vypršelo nebo přístup odepřen")
    return {"status": "rotated", "secret_id": secret_id}


@app.delete("/secrets/{secret_id}")
async def delete_secret(secret_id: str, owner: str) -> dict:
    """Smaže tajemství (Fáze 23)."""
    if not secret_manager.delete(secret_id, owner=owner):
        raise HTTPException(status_code=404, detail="Tajemství nenalezeno nebo přístup odepřen")
    return {"status": "deleted", "secret_id": secret_id}


# ── Quota Manager (Fáze 24) ──────────────────────────────────────────────────

@app.post("/quotas")
async def set_quota(req: SetQuotaRequest) -> dict:
    """Nastaví kvótu pro uživatele (requests/tokens/cost_usd × okno) (Fáze 24)."""
    try:
        rid = quota_manager.set_quota(
            req.user_id, req.metric, req.limit, window=req.window
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"rule_id": rid, "user_id": req.user_id,
            "metric": req.metric, "limit": req.limit, "window": req.window}


@app.get("/quotas")
async def list_quotas(user_id: str | None = None) -> dict:
    """Vypíše kvóty; volitelně filtrovat dle user_id (Fáze 24)."""
    items = quota_manager.list_quotas(user_id=user_id)
    return {"count": len(items), "quotas": items}


@app.get("/quotas/{rule_id}")
async def get_quota(rule_id: str) -> dict:
    """Vrátí kvótu podle rule_id (Fáze 24)."""
    r = quota_manager.get_quota(rule_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Kvóta nenalezena")
    return r


@app.delete("/quotas/{rule_id}")
async def delete_quota(rule_id: str) -> dict:
    """Smaže kvótu (Fáze 24)."""
    if not quota_manager.delete_quota(rule_id):
        raise HTTPException(status_code=404, detail="Kvóta nenalezena")
    return {"status": "deleted", "rule_id": rule_id}


@app.post("/quotas/usage")
async def record_quota_usage(req: RecordQuotaUsageRequest) -> dict:
    """Zaznamená spotřebu pro daného uživatele (Fáze 24)."""
    quota_manager.record_usage(
        req.user_id,
        requests=req.requests,
        tokens=req.tokens,
        cost_usd=req.cost_usd,
    )
    return {"status": "recorded", "user_id": req.user_id}


@app.get("/quotas/check/{user_id}")
async def check_quota(user_id: str, metric: str = "requests") -> dict:
    """Zkontroluje, zda uživatel nepřekročil kvótu pro danou metriku (Fáze 24)."""
    try:
        return quota_manager.check_quota(user_id, metric)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/quotas/usage/{user_id}")
async def get_quota_usage(user_id: str) -> dict:
    """Vrátí přehled spotřeby uživatele přes všechna okna (Fáze 24)."""
    return quota_manager.get_usage_summary(user_id)


# ── Circuit Breakers (Fáze 25) ───────────────────────────────────────────────

@app.post("/circuit-breakers")
async def create_breaker(req: CreateBreakerRequest) -> dict:
    """Vytvoří nebo vrátí existující circuit breaker (Fáze 25)."""
    try:
        circuit_breakers.get_or_create(
            req.name,
            failure_threshold=req.failure_threshold,
            recovery_timeout_s=req.recovery_timeout_s,
            success_threshold=req.success_threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return circuit_breakers.get_state(req.name)


@app.get("/circuit-breakers")
async def list_breakers() -> dict:
    """Vypíše všechny circuit breakers a jejich stav (Fáze 25)."""
    items = circuit_breakers.list_breakers()
    return {"count": len(items), "breakers": items}


@app.get("/circuit-breakers/{name}")
async def get_breaker(name: str) -> dict:
    """Vrátí stav konkrétního circuit breakeru (Fáze 25)."""
    s = circuit_breakers.get_state(name)
    if s is None:
        raise HTTPException(status_code=404, detail="Circuit breaker nenalezen")
    return s


@app.post("/circuit-breakers/{name}/event")
async def record_breaker_event(name: str, req: RecordBreakerEventRequest) -> dict:
    """Zaznamená success/failure/rejected do circuit breakeru (Fáze 25)."""
    if name not in {cb["name"] for cb in circuit_breakers.list_breakers()}:
        raise HTTPException(status_code=404, detail="Circuit breaker nenalezen")
    if req.event == "success":
        circuit_breakers.record_success(name)
    elif req.event == "failure":
        circuit_breakers.record_failure(name)
    elif req.event == "rejected":
        circuit_breakers.record_rejected(name)
    else:
        raise HTTPException(status_code=422, detail="event musí být success/failure/rejected")
    return circuit_breakers.get_state(name)


@app.post("/circuit-breakers/{name}/reset")
async def reset_breaker(name: str) -> dict:
    """Resetuje circuit breaker do stavu CLOSED (Fáze 25)."""
    if not circuit_breakers.reset(name):
        raise HTTPException(status_code=404, detail="Circuit breaker nenalezen")
    return circuit_breakers.get_state(name)


# ── API key management (Fáze 7) ───────────────────────────────────────────────

@app.post("/api-keys")
async def create_api_key(req: ApiKeyRequest) -> dict:
    """Vytvoří nový API klíč pro uživatele (Fáze 7)."""
    raw_key = api_key_manager.create_key(req.user_id)
    audit_log.record("api_key_created", req.user_id)
    return {"key": raw_key, "user_id": req.user_id}


@app.get("/api-keys")
async def list_api_keys(user_id: str | None = None) -> dict:
    """Vypíše API klíče; volitelně filtrovat dle user_id (Fáze 7)."""
    keys = api_key_manager.list_keys(user_id=user_id)
    return {"count": len(keys), "keys": keys}


@app.delete("/api-keys/{key}")
async def revoke_api_key(key: str) -> dict:
    """Revokuje API klíč (Fáze 7)."""
    success = api_key_manager.revoke_key(key)
    if not success:
        raise HTTPException(status_code=404, detail="Klíč nenalezen")
    audit_log.record("api_key_revoked", user_id="admin", key_prefix=key[:12])
    return {"status": "revoked"}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str) -> None:
    """
    Node-level streaming (Fáze 1): klient dostane event po každém uzlu grafu.

    Protokol:
      ← {"event": "started",        "session_id": "..."}
      ← {"event": "node_completed", "node": "plan", "provider": "gemini", ...}
      ← {"event": "node_completed", "node": "execute", ...}
      ...
      ← {"event": "completed",      "response": "...", "provider_log": {...}}
    """
    assert core is not None
    await websocket.accept()
    log.info("ws_connected", user_id=user_id)

    try:
        while True:
            data = await websocket.receive_json()
            task = data.get("task", "")
            session_id = str(uuid.uuid4())

            await websocket.send_json({"event": "started", "session_id": session_id})

            try:
                async for event in core.run_stream(
                    task=task,
                    user_id=user_id,
                    session_id=session_id,
                    approved=data.get("approved", False),
                    force_provider=data.get("force_provider", ""),
                ):
                    await websocket.send_json({**event, "session_id": session_id})

                    if event.get("event") == "completed":
                        _task_provider_log[session_id] = event.get("provider_log", {})
                        cost = estimate_cost(
                            event.get("response", ""), event.get("provider_log", {})
                        )
                        session_store.add_turn(
                            user_id,
                            ConversationTurn(
                                task=task,
                                response=event.get("response", ""),
                                provider_log=event.get("provider_log", {}),
                                risk_score=event.get("risk_score", 0.0),
                                cost_usd=cost,
                            ),
                        )
            except Exception as exc:
                await websocket.send_json({"event": "error", "message": str(exc)})
    except WebSocketDisconnect:
        log.info("ws_disconnected", user_id=user_id)


# ── HPC (Fáze 26) ─────────────────────────────────────────────────────────────


class HpcJobRequest(BaseModel):
    script: str = "submit_ddp_agi.sh"
    nodes: int = 1
    gpus_per_node: int = 8
    partition: str = ""
    sif_path: str = ""
    extra_args: dict = {}


class HpcJobResponse(BaseModel):
    job_id: str
    status: str
    script: str
    nodes: int
    gpus_per_node: int
    partition: str
    submitted_at: str


class CascadeRouteRequest(BaseModel):
    messages: list[dict]
    confidence_threshold: float = 0.7


class CascadeRouteResponse(BaseModel):
    content: str
    provider: str
    confidence: float
    latency_ms: float
    tokens_used: int
    metadata: dict


# In-memory HPC job store (production: use Slurm REST API / DB)
_hpc_jobs: dict[str, dict] = {}


@app.post("/hpc/jobs", tags=["HPC"])
async def hpc_submit_job(req: HpcJobRequest):
    """Submit a simulated HPC job (Slurm sbatch). In production, calls sbatch directly."""
    import uuid
    from datetime import datetime, timezone
    job_id = f"hpc-{uuid.uuid4().hex[:8]}"
    partition = req.partition or settings.slurm_partition
    sif_path = req.sif_path or settings.apptainer_sif_path
    record = {
        "job_id": job_id,
        "status": "submitted",
        "script": req.script,
        "nodes": req.nodes,
        "gpus_per_node": req.gpus_per_node,
        "partition": partition,
        "sif_path": sif_path,
        "extra_args": req.extra_args,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    _hpc_jobs[job_id] = record
    log.info("hpc_job_submitted", job_id=job_id, nodes=req.nodes, partition=partition)
    return record


@app.get("/hpc/jobs", tags=["HPC"])
async def hpc_list_jobs():
    """List all submitted HPC jobs."""
    return {"jobs": list(_hpc_jobs.values()), "total": len(_hpc_jobs)}


@app.get("/hpc/jobs/{job_id}", tags=["HPC"])
async def hpc_get_job(job_id: str):
    """Get status of a specific HPC job."""
    job = _hpc_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@app.get("/hpc/cluster/status", tags=["HPC"])
async def hpc_cluster_status():
    """Return HPC cluster configuration status."""
    return {
        "hpc_enabled": settings.hpc_enabled,
        "slurm_partition": settings.slurm_partition,
        "apptainer_sif_path": settings.apptainer_sif_path,
        "container_registry": settings.container_registry,
        "nccl_ib_hca": settings.nccl_ib_hca,
        "burst_buffer_path": settings.burst_buffer_path,
        "cascade_confidence_threshold": settings.cascade_confidence_threshold,
        "cascade_draft_provider": settings.cascade_draft_provider,
        "cascade_oracle_provider": settings.cascade_oracle_provider,
        "jobs_submitted": len(_hpc_jobs),
    }


def _get_or_create_cascade_router() -> CascadeRouter:
    """Return or create the global cascade router using the main LLM providers."""
    global _cascade_router
    if _cascade_router is None and core is not None:
        router = core.router
        draft = (router._gemini if router._gemini else router._claude)
        oracle = router._claude
        _cascade_router = CascadeRouter(
            draft_provider=draft,
            oracle_provider=oracle,
            confidence_threshold=settings.cascade_confidence_threshold,
        )
    if _cascade_router is None:
        raise HTTPException(
            status_code=503,
            detail="Core not initialized — cascade router unavailable",
        )
    return _cascade_router


@app.post("/hpc/cascade/route", tags=["HPC"])
async def hpc_cascade_route(req: CascadeRouteRequest):
    """Route a prompt through the LLM Cascade (Draft → Oracle)."""
    router = _get_or_create_cascade_router()
    if req.confidence_threshold != router.confidence_threshold:
        router.confidence_threshold = req.confidence_threshold
    resp: CascadeLLMResponse = await router.route(req.messages)
    return CascadeRouteResponse(
        content=resp.content,
        provider=resp.provider,
        confidence=resp.confidence,
        latency_ms=resp.latency_ms,
        tokens_used=resp.tokens_used,
        metadata=resp.metadata,
    )


@app.get("/hpc/cascade/metrics", tags=["HPC"])
async def hpc_cascade_metrics():
    """Return LLM Cascade routing statistics."""
    global _cascade_router
    if _cascade_router is None:
        return {"message": "Cascade router not yet initialized", "metrics": None}
    return {"metrics": _cascade_router.metrics()}


# ── Guardrails / Content Moderation (Fáze 27) ─────────────────────────────────


class GuardrailRuleRequest(BaseModel):
    name: str
    pattern: str
    action: str          # allow | flag | redact | block
    category: str = "custom"
    placeholder: str = "[REDACTED]"


class GuardrailToggleRequest(BaseModel):
    enabled: bool


class GuardrailScanRequest(BaseModel):
    text: str
    direction: str = "input"   # input | output


@app.post("/guardrails/rules", tags=["Guardrails"])
async def guardrails_add_rule(req: GuardrailRuleRequest):
    """Register a custom content-moderation rule."""
    try:
        rule_id = guardrails.add_rule(
            name=req.name,
            pattern=req.pattern,
            action=req.action,
            category=req.category,
            placeholder=req.placeholder,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"rule_id": rule_id, "rule": guardrails.get_rule(rule_id)}


@app.get("/guardrails/rules", tags=["Guardrails"])
async def guardrails_list_rules(category: str | None = None):
    """List moderation rules, optionally filtered by category."""
    return {"rules": guardrails.list_rules(category=category)}


@app.get("/guardrails/rules/{rule_id}", tags=["Guardrails"])
async def guardrails_get_rule(rule_id: str):
    """Get a specific moderation rule."""
    rule = guardrails.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return rule


@app.patch("/guardrails/rules/{rule_id}", tags=["Guardrails"])
async def guardrails_toggle_rule(rule_id: str, req: GuardrailToggleRequest):
    """Enable or disable a moderation rule."""
    if not guardrails.set_enabled(rule_id, req.enabled):
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return guardrails.get_rule(rule_id)


@app.delete("/guardrails/rules/{rule_id}", tags=["Guardrails"])
async def guardrails_delete_rule(rule_id: str):
    """Delete a custom moderation rule (built-ins cannot be deleted)."""
    try:
        deleted = guardrails.delete_rule(rule_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return {"deleted": rule_id}


@app.post("/guardrails/scan", tags=["Guardrails"])
async def guardrails_scan(req: GuardrailScanRequest):
    """Scan text against all enabled moderation rules."""
    result = guardrails.scan(req.text, direction=req.direction)
    return result.to_dict()


@app.get("/guardrails/stats", tags=["Guardrails"])
async def guardrails_stats():
    """Return guardrail scanning statistics."""
    return guardrails.stats()


# ── Orchestrator (Fáze 28) ────────────────────────────────────────────────────

class OrchestrateTaskRequest(BaseModel):
    task_id: str | None = None
    prompt: str
    provider: str | None = None
    depends_on: list[str] = []


class OrchestrateRequest(BaseModel):
    tasks: list[OrchestrateTaskRequest]
    aggregation: str = "merge"


@app.post("/orchestrate", tags=["Orchestrator"])
async def orchestrate_run(req: OrchestrateRequest):
    """Create and immediately execute a multi-agent plan. Returns OrchestrationResult."""
    raw_tasks = [
        {
            "task_id": t.task_id or str(uuid.uuid4()),
            "prompt": t.prompt,
            "provider": t.provider,
            "depends_on": t.depends_on,
        }
        for t in req.tasks
    ]
    try:
        plan = _orchestrator.create_plan(raw_tasks, aggregation=req.aggregation)
    except (ValueError, OrcDependencyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    result = await _orchestrator.execute(plan)
    return result.to_dict()


@app.post("/orchestrate/plan", tags=["Orchestrator"])
async def orchestrate_validate_plan(req: OrchestrateRequest):
    """Validate a task DAG and return the execution plan without running it."""
    raw_tasks = [
        {
            "task_id": t.task_id or str(uuid.uuid4()),
            "prompt": t.prompt,
            "provider": t.provider,
            "depends_on": t.depends_on,
        }
        for t in req.tasks
    ]
    try:
        plan = _orchestrator.create_plan(raw_tasks, aggregation=req.aggregation)
    except (ValueError, OrcDependencyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return plan.to_dict()


@app.get("/orchestrate/metrics", tags=["Orchestrator"])
async def orchestrate_metrics():
    """Return orchestrator execution metrics."""
    return _orchestrator.metrics()


@app.post("/orchestrate/metrics/reset", tags=["Orchestrator"])
async def orchestrate_metrics_reset():
    """Reset orchestrator metrics counters."""
    _orchestrator.reset_metrics()
    return {"reset": True}


# ── Semantic Cache (Fáze 29) ──────────────────────────────────────────────────

class SemanticLookupRequest(BaseModel):
    text: str


class SemanticPutRequest(BaseModel):
    text: str
    response: str


@app.get("/cache/semantic/stats", tags=["Semantic Cache"])
async def semantic_cache_stats():
    """Return semantic cache statistics (queries, hit rates, entry count)."""
    return _semantic_cache.stats()


@app.delete("/cache/semantic", tags=["Semantic Cache"])
async def semantic_cache_clear():
    """Clear all semantic cache entries. Returns number of entries removed."""
    n = _semantic_cache.clear()
    return {"cleared": n}


@app.post("/cache/semantic/lookup", tags=["Semantic Cache"])
async def semantic_cache_lookup(req: SemanticLookupRequest):
    """
    Test a similarity lookup against the semantic cache.
    Returns the matched entry or a miss indicator — does NOT call the LLM.
    """
    result = _semantic_cache.get(req.text)
    if result is None:
        return {"hit": False, "hit_type": "miss"}
    return {"hit": True, **result.to_dict()}


@app.post("/cache/semantic/put", tags=["Semantic Cache"])
async def semantic_cache_put(req: SemanticPutRequest):
    """Store a text→response pair in the semantic cache. Returns entry_id."""
    entry_id = _semantic_cache.put(req.text, req.response)
    return {"entry_id": entry_id}


# ── Request Pipeline (Fáze 30) ─────────────────────────────────────────────────

class PipelineStepAddRequest(BaseModel):
    name: str  # "prompt_injection" | "pii_redaction" | "truncation" | "token_counter"
    config: dict = {}


@app.get("/pipeline/steps", tags=["Pipeline"])
async def pipeline_list_steps():
    """List all active pipeline steps in execution order."""
    return {"steps": _pipeline.list_steps()}


@app.post("/pipeline/steps", tags=["Pipeline"])
async def pipeline_add_step(req: PipelineStepAddRequest):
    """Add a built-in step to the pipeline. Supported names: prompt_injection, pii_redaction, truncation, token_counter."""
    name = req.name
    cfg = req.config
    if name == "prompt_injection":
        step = PromptInjectionStep(
            injection=cfg.get("injection", ""),
            role=cfg.get("role", "system"),
        )
    elif name == "pii_redaction":
        step = PIIRedactionStep()
    elif name == "truncation":
        step = TruncationStep(
            max_chars=cfg.get("max_chars", 2000),
            suffix=cfg.get("suffix", "…"),
        )
    elif name == "token_counter":
        step = TokenCounterStep()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown step name: {name!r}")
    _pipeline.add_step(step)
    return {"steps": _pipeline.list_steps()}


@app.delete("/pipeline/steps/{step_name}", tags=["Pipeline"])
async def pipeline_remove_step(step_name: str):
    """Remove a step from the pipeline by name. Returns 404 if not found."""
    removed = _pipeline.remove_step(step_name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Step '{step_name}' not found")
    return {"steps": _pipeline.list_steps()}


@app.get("/pipeline/metrics", tags=["Pipeline"])
async def pipeline_metrics():
    """Pipeline execution metrics: total runs, abort count, per-step latency."""
    return _pipeline.metrics()


# ── Output Validator (Fáze 31) ─────────────────────────────────────────────────

class ValidateRequest(BaseModel):
    text: str
    constraints: list[dict] = []
    # Each constraint dict: {"type": "json"|"non_empty"|"length"|"regex"|"banned_words", ...config}


def _build_constraint(spec: dict):
    ctype = spec.get("type")
    if ctype == "non_empty":
        return NonEmptyConstraint()
    if ctype == "json":
        return JSONConstraint(spec.get("required_keys"))
    if ctype == "length":
        return LengthConstraint(
            min_len=spec.get("min_len", 0),
            max_len=spec.get("max_len"),
        )
    if ctype == "regex":
        return RegexConstraint(
            spec["pattern"],
            should_match=spec.get("should_match", True),
        )
    if ctype == "banned_words":
        return BannedWordsConstraint(
            spec.get("words", []),
            case_sensitive=spec.get("case_sensitive", False),
        )
    raise HTTPException(status_code=400, detail=f"Unknown constraint type: {ctype!r}")


@app.post("/validate", tags=["Validator"])
async def validate_text(req: ValidateRequest):
    """Validate a text against an ad-hoc list of constraints (no LLM call)."""
    try:
        constraints = [_build_constraint(s) for s in req.constraints]
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    v = OutputValidator(constraints, max_retries=0)
    results = v.validate(req.text)
    return {
        "valid": all(r.passed for r in results),
        "constraint_results": [r.to_dict() for r in results],
    }


@app.get("/validate/metrics", tags=["Validator"])
async def validate_metrics():
    """Output validator metrics: success/repair/failure rates."""
    return _validator.metrics()


@app.post("/validate/metrics/reset", tags=["Validator"])
async def validate_metrics_reset():
    """Reset the output validator metrics."""
    _validator.reset_metrics()
    return {"status": "reset"}


# ── Context Window Manager (Fáze 32) ───────────────────────────────────────────

class ContextFitRequest(BaseModel):
    messages: list[dict]
    max_tokens: int | None = None
    keep_recent: int | None = None
    strategy: str | None = None  # drop_oldest | summarize_oldest | keep_recent


@app.post("/context/fit", tags=["Context"])
async def context_fit(req: ContextFitRequest):
    """Trim a conversation history to fit a token budget. Returns the fitted messages."""
    # Use a per-request manager if overrides are supplied, else the singleton.
    if req.max_tokens is not None or req.keep_recent is not None:
        try:
            cm = ContextWindowManager(
                max_tokens=req.max_tokens or settings.context_max_tokens,
                keep_recent=req.keep_recent
                if req.keep_recent is not None
                else settings.context_keep_recent,
                strategy=TrimStrategy(req.strategy or settings.context_trim_strategy),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        cm = _context_manager

    strat = None
    if req.strategy is not None:
        try:
            strat = TrimStrategy(req.strategy)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown strategy: {req.strategy!r}")

    result = cm.fit(req.messages, strategy=strat)
    return result.to_dict()


@app.get("/context/metrics", tags=["Context"])
async def context_metrics():
    """Context window manager metrics: trim rate, dropped/summarized counts."""
    return _context_manager.metrics()


# ── Consensus Engine (Fáze 33) ─────────────────────────────────────────────────

class ConsensusRequest(BaseModel):
    samples: list[str]
    similarity_threshold: float | None = None
    agreement_threshold: float | None = None


@app.post("/consensus", tags=["Consensus"])
async def consensus(req: ConsensusRequest):
    """Compute self-consistency consensus over a list of candidate answers."""
    if req.similarity_threshold is not None or req.agreement_threshold is not None:
        try:
            engine = ConsensusEngine(
                n_samples=max(1, len(req.samples)),
                similarity_threshold=req.similarity_threshold
                or settings.consensus_similarity_threshold,
                agreement_threshold=req.agreement_threshold
                or settings.consensus_agreement_threshold,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        engine = _consensus
    result = engine.from_samples(req.samples)
    return result.to_dict()


@app.get("/consensus/metrics", tags=["Consensus"])
async def consensus_metrics():
    """Consensus engine metrics: agreement rate, average confidence."""
    return _consensus.metrics()


# ── Intent Classifier (Fáze 34) ────────────────────────────────────────────────

class IntentClassifyRequest(BaseModel):
    text: str


@app.post("/intent/classify", tags=["Intent"])
async def intent_classify(req: IntentClassifyRequest):
    """Classify a query into an intent with confidence and a provider hint."""
    return _intent_classifier.classify(req.text).to_dict()


@app.get("/intent/list", tags=["Intent"])
async def intent_list():
    """List all registered intent names."""
    return {"intents": _intent_classifier.list_intents()}


@app.get("/intent/metrics", tags=["Intent"])
async def intent_metrics():
    """Intent classifier metrics: per-intent counts, fallback rate."""
    return _intent_classifier.metrics()


# ── Citation Tracker (Fáze 35) ──────────────────────────────────────────────────

class CitationTrackRequest(BaseModel):
    response: str
    sources: list[dict]   # [{"source_id"/"id": str, "text": str}]
    threshold: float | None = None


@app.post("/citations/track", tags=["Citations"])
async def citations_track(req: CitationTrackRequest):
    """Annotate response sentences with supporting sources; flag unsupported claims."""
    if req.threshold is not None:
        try:
            tracker = CitationTracker(
                threshold=req.threshold,
                max_citations=settings.citation_max_per_sentence,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        tracker = _citation_tracker
    return tracker.track(req.response, req.sources).to_dict()


@app.get("/citations/metrics", tags=["Citations"])
async def citations_metrics():
    """Citation tracker metrics: overall grounding score across reports."""
    return _citation_tracker.metrics()


# ── Document Chunker (Fáze 36) ──────────────────────────────────────────────────

class ChunkRequest(BaseModel):
    text: str
    chunk_size: int | None = None
    overlap: int | None = None
    strategy: str | None = None  # character | sentence | paragraph


@app.post("/chunk", tags=["Chunker"])
async def chunk_document(req: ChunkRequest):
    """Split a document into overlapping chunks for RAG ingestion."""
    if req.chunk_size is not None or req.overlap is not None:
        try:
            chunker = DocumentChunker(
                chunk_size=req.chunk_size or settings.chunk_size,
                overlap=req.overlap if req.overlap is not None else settings.chunk_overlap,
                strategy=ChunkStrategy(req.strategy or settings.chunk_strategy),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        chunker = _chunker

    strat = None
    if req.strategy is not None:
        try:
            strat = ChunkStrategy(req.strategy)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown strategy: {req.strategy!r}")

    return chunker.chunk(req.text, strategy=strat).to_dict()


@app.get("/chunk/metrics", tags=["Chunker"])
async def chunk_metrics():
    """Document chunker metrics: total docs/chunks, avg chunks per doc."""
    return _chunker.metrics()


# ── BM25 Retriever (Fáze 37) ────────────────────────────────────────────────────

class RetrieveIndexRequest(BaseModel):
    documents: list[dict]   # [{"doc_id"/"id", "text", "metadata"?}]


class RetrieveSearchRequest(BaseModel):
    query: str
    top_k: int | None = None


@app.post("/retrieve/index", tags=["Retriever"])
async def retrieve_index(req: RetrieveIndexRequest):
    """Index documents into the BM25 retriever. Returns counts."""
    added = _retriever.add_many(req.documents)
    return {"added": added, "indexed_documents": _retriever.size}


@app.post("/retrieve/search", tags=["Retriever"])
async def retrieve_search(req: RetrieveSearchRequest):
    """Search the BM25 index for the top-k most relevant documents."""
    try:
        hits = _retriever.search(req.query, top_k=req.top_k or settings.retriever_top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"query": req.query, "hits": [h.to_dict() for h in hits]}


@app.delete("/retrieve", tags=["Retriever"])
async def retrieve_clear():
    """Clear the BM25 index. Returns number of documents removed."""
    return {"removed": _retriever.clear()}


@app.get("/retrieve/metrics", tags=["Retriever"])
async def retrieve_metrics():
    """BM25 retriever metrics: index size, vocabulary, search counts."""
    return _retriever.metrics()


# ── Hybrid Reranker (Fáze 38) ───────────────────────────────────────────────────

class RerankRequest(BaseModel):
    ranked_lists: list[list[dict]]   # each list: [{doc_id/id, score?, text?, metadata?}]
    method: str | None = None        # reciprocal_rank | weighted_score
    weights: list[float] | None = None
    top_k: int | None = None


@app.post("/rerank", tags=["Reranker"])
async def rerank(req: RerankRequest):
    """Fuse multiple ranked result lists into one consensus ranking."""
    method = None
    if req.method is not None:
        try:
            method = FusionMethod(req.method)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown method: {req.method!r}")
    try:
        fused = _reranker.fuse(
            req.ranked_lists,
            method=method,
            weights=req.weights,
            top_k=req.top_k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"results": [f.to_dict() for f in fused]}


@app.get("/rerank/metrics", tags=["Reranker"])
async def rerank_metrics():
    """Hybrid reranker metrics: fusion counts, average output size."""
    return _reranker.metrics()


# ── PII Anonymizer (Fáze 39) ────────────────────────────────────────────────────

class AnonymizeRequest(BaseModel):
    text: str


class RestoreRequest(BaseModel):
    text: str
    mapping: dict[str, str]


@app.post("/anonymize", tags=["Anonymizer"])
async def anonymize_text(req: AnonymizeRequest):
    """Reversibly replace PII with stable placeholders; returns text + mapping."""
    return _anonymizer.anonymize(req.text).to_dict()


@app.post("/anonymize/detect", tags=["Anonymizer"])
async def anonymize_detect(req: AnonymizeRequest):
    """Detect PII entities without modifying the text."""
    return {"entities": _anonymizer.detect(req.text)}


@app.post("/anonymize/restore", tags=["Anonymizer"])
async def anonymize_restore(req: RestoreRequest):
    """Re-insert original values from a placeholder mapping."""
    return {"restored_text": PIIAnonymizer.restore(req.text, req.mapping)}


@app.get("/anonymize/metrics", tags=["Anonymizer"])
async def anonymize_metrics():
    """PII anonymizer metrics: entity counts by type."""
    return _anonymizer.metrics()


# ── Cost Estimator (Fáze 40) ────────────────────────────────────────────────────

class CostEstimateRequest(BaseModel):
    model: str
    prompt: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    budget: float | None = None


class CostCompareRequest(BaseModel):
    prompt: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    budget: float | None = None
    models: list[str] | None = None


@app.post("/cost/estimate", tags=["Cost"])
async def cost_estimate(req: CostEstimateRequest):
    """Project the USD cost of a request for a given model."""
    try:
        est = _cost_estimator.estimate(
            req.model,
            input_tokens=req.input_tokens,
            output_tokens=req.output_tokens,
            prompt=req.prompt,
            expected_output_tokens=settings.cost_default_output_tokens,
            budget=req.budget,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return est.to_dict()


@app.post("/cost/compare", tags=["Cost"])
async def cost_compare(req: CostCompareRequest):
    """Compare projected cost across models; reports cheapest/most expensive."""
    try:
        result = _cost_estimator.compare(
            input_tokens=req.input_tokens,
            output_tokens=req.output_tokens,
            prompt=req.prompt,
            expected_output_tokens=settings.cost_default_output_tokens,
            budget=req.budget,
            models=req.models,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.to_dict()


@app.get("/cost/models", tags=["Cost"])
async def cost_models():
    """List models with known pricing."""
    return {"models": _cost_estimator.list_models()}


@app.get("/cost/metrics", tags=["Cost"])
async def cost_metrics():
    """Cost estimator metrics: total/avg projected cost."""
    return _cost_estimator.metrics()


# ── Response Comparator (Fáze 41) ───────────────────────────────────────────────

class CompareResponsesRequest(BaseModel):
    text_a: str
    text_b: str


@app.post("/compare/responses", tags=["Comparator"])
async def compare_responses(req: CompareResponsesRequest):
    """Sentence-level diff between two responses with similarity scores."""
    return _comparator.compare(req.text_a, req.text_b).to_dict()


@app.get("/compare/responses/metrics", tags=["Comparator"])
async def compare_responses_metrics():
    """Response comparator metrics: avg similarity, identical rate."""
    return _comparator.metrics()


# ── Extractive Summarizer (Fáze 42) ─────────────────────────────────────────────

class SummarizeRequest(BaseModel):
    text: str
    ratio: float | None = None
    max_sentences: int | None = None
    top_keywords: int = 5


@app.post("/summarize", tags=["Summarizer"])
async def summarize_text(req: SummarizeRequest):
    """Extractively summarize a text by selecting the most salient sentences."""
    try:
        result = _summarizer.summarize(
            req.text,
            ratio=req.ratio,
            max_sentences=req.max_sentences,
            top_keywords=req.top_keywords,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.to_dict()


@app.get("/summarize/metrics", tags=["Summarizer"])
async def summarize_metrics():
    """Summarizer metrics: overall compression across calls."""
    return _summarizer.metrics()


# ── Language Detector (Fáze 43) ─────────────────────────────────────────────────

class LanguageDetectRequest(BaseModel):
    text: str


@app.post("/language/detect", tags=["Language"])
async def language_detect(req: LanguageDetectRequest):
    """Detect the dominant language of a text with confidence + per-language scores."""
    return _language_detector.detect(req.text).to_dict()


@app.get("/language/list", tags=["Language"])
async def language_list():
    """List supported language codes."""
    return {"languages": _language_detector.list_languages()}


@app.get("/language/metrics", tags=["Language"])
async def language_metrics():
    """Language detector metrics: per-language counts, unknown rate."""
    return _language_detector.metrics()


# ── Output Parser (Fáze 44) ─────────────────────────────────────────────────────

class ParseRequest(BaseModel):
    text: str


@app.post("/parse/json", tags=["Parser"])
async def parse_json(req: ParseRequest):
    """Extract JSON from free-form text (fences, balanced spans, light repair)."""
    return _output_parser.extract_json(req.text).to_dict()


@app.post("/parse/key-values", tags=["Parser"])
async def parse_key_values(req: ParseRequest):
    """Extract 'key: value' pairs from text into a dict."""
    return _output_parser.extract_key_values(req.text).to_dict()


@app.post("/parse/list", tags=["Parser"])
async def parse_list(req: ParseRequest):
    """Extract bullet / numbered list items from text."""
    return _output_parser.extract_list(req.text).to_dict()


@app.get("/parse/metrics", tags=["Parser"])
async def parse_metrics():
    """Output parser metrics: success/repair rates."""
    return _output_parser.metrics()


# ── Sentiment Analyzer (Fáze 45) ────────────────────────────────────────────────

class SentimentRequest(BaseModel):
    text: str


@app.post("/sentiment", tags=["Sentiment"])
async def analyze_sentiment(req: SentimentRequest):
    """Lexicon-based sentiment: polarity + normalized score with negation handling."""
    return _sentiment.analyze(req.text).to_dict()


@app.get("/sentiment/metrics", tags=["Sentiment"])
async def sentiment_metrics():
    """Sentiment analyzer metrics: polarity distribution."""
    return _sentiment.metrics()


# ── Keyword Extractor (Fáze 46) ─────────────────────────────────────────────────

class KeywordRequest(BaseModel):
    text: str
    top_k: int = 10


@app.post("/keywords", tags=["Keywords"])
async def extract_keywords(req: KeywordRequest):
    """Extract top keyphrases from text via RAKE-style scoring."""
    try:
        result = _keyword_extractor.extract(req.text, top_k=req.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.to_dict()


@app.get("/keywords/metrics", tags=["Keywords"])
async def keywords_metrics():
    """Keyword extractor metrics: average keywords per extraction."""
    return _keyword_extractor.metrics()


# ── Readability Analyzer (Fáze 47) ──────────────────────────────────────────────

class ReadabilityRequest(BaseModel):
    text: str


@app.post("/readability", tags=["Readability"])
async def analyze_readability(req: ReadabilityRequest):
    """Compute Flesch readability metrics (ease, grade, syllables, averages)."""
    return _readability.analyze(req.text).to_dict()


@app.get("/readability/metrics", tags=["Readability"])
async def readability_metrics():
    """Readability analyzer metrics: average reading ease and grade level."""
    return _readability.metrics()


# ── Deduplicator (Fáze 48) ──────────────────────────────────────────────────────

class DedupCheckRequest(BaseModel):
    text: str
    add: bool = True   # register the text if not a duplicate


class DedupBatchRequest(BaseModel):
    texts: list[str]


@app.post("/dedup/check", tags=["Dedup"])
async def dedup_check(req: DedupCheckRequest):
    """Check a text for exact/near duplicates; optionally register it."""
    if req.add:
        entry_id, check = _deduplicator.add(req.text)
        return {"entry_id": entry_id, **check.to_dict()}
    return _deduplicator.check(req.text).to_dict()


@app.post("/dedup/batch", tags=["Dedup"])
async def dedup_batch(req: DedupBatchRequest):
    """Deduplicate a list of texts, keeping first occurrences."""
    return _deduplicator.deduplicate(req.texts)


@app.delete("/dedup", tags=["Dedup"])
async def dedup_clear():
    """Clear the deduplication index."""
    return {"removed": _deduplicator.clear()}


@app.get("/dedup/metrics", tags=["Dedup"])
async def dedup_metrics():
    """Deduplicator metrics: exact/near counts, duplicate rate."""
    return _deduplicator.metrics()


# ── Entity Extractor (Fáze 49) ──────────────────────────────────────────────────

class EntityRequest(BaseModel):
    text: str


@app.post("/entities", tags=["Entities"])
async def extract_entities(req: EntityRequest):
    """Extract typed named entities (date, money, email, phone, proper noun, …)."""
    return _entity_extractor.extract(req.text).to_dict()


@app.get("/entities/metrics", tags=["Entities"])
async def entities_metrics():
    """Entity extractor metrics: counts by entity type."""
    return _entity_extractor.metrics()


# ── Text Analytics Suite (Fáze 50) ──────────────────────────────────────────────

class TextAnalyticsRequest(BaseModel):
    text: str
    language: bool = True
    sentiment: bool = True
    readability: bool = True
    keywords: bool = True
    entities: bool = True
    summary: bool = True
    top_keywords: int = 8


@app.post("/analyze/text", tags=["Analytics"])
async def analyze_text(req: TextAnalyticsRequest):
    """One-shot composed NLP report: language, sentiment, readability, keywords, entities, summary."""
    report = _text_analytics.analyze(
        req.text,
        language=req.language,
        sentiment=req.sentiment,
        readability=req.readability,
        keywords=req.keywords,
        entities=req.entities,
        summary=req.summary,
        top_keywords=req.top_keywords,
    )
    return report.to_dict()


@app.get("/analyze/text/metrics", tags=["Analytics"])
async def analyze_text_metrics():
    """Text analytics suite metrics: total analyses, per-section counts."""
    return _text_analytics.metrics()


# ── Fuzzy Matcher (Fáze 51) ─────────────────────────────────────────────────────

class FuzzyMatchRequest(BaseModel):
    query: str
    candidates: list[str]
    top_k: int = 5


@app.post("/fuzzy/match", tags=["Fuzzy"])
async def fuzzy_match(req: FuzzyMatchRequest):
    """Fuzzy-match a query against candidates via Levenshtein similarity."""
    try:
        result = _fuzzy_matcher.match(req.query, req.candidates, top_k=req.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.to_dict()


@app.get("/fuzzy/metrics", tags=["Fuzzy"])
async def fuzzy_metrics():
    """Fuzzy matcher metrics: hit rate across queries."""
    return _fuzzy_matcher.metrics()


# ── Anomaly Detector (Fáze 52) ──────────────────────────────────────────────────

class AnomalyObserveRequest(BaseModel):
    metric: str
    value: float
    method: str | None = None   # z_score | iqr


@app.post("/anomaly/observe", tags=["Anomaly"])
async def anomaly_observe(req: AnomalyObserveRequest):
    """Record a metric value and report whether it is anomalous vs. recent history."""
    method = None
    if req.method is not None:
        try:
            method = DetectionMethod(req.method)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown method: {req.method!r}")
    return _anomaly_detector.observe(req.metric, req.value, method=method).to_dict()


@app.get("/anomaly/metrics", tags=["Anomaly"])
async def anomaly_metrics():
    """Anomaly detector metrics: anomaly rate, tracked metric streams."""
    return _anomaly_detector.metrics()


# ── Reservoir Sampler (Fáze 53) ─────────────────────────────────────────────────

class SamplerAddRequest(BaseModel):
    item: Any


@app.post("/sampler/add", tags=["Sampler"])
async def sampler_add(req: SamplerAddRequest):
    """Offer an item to the reservoir; returns whether it is currently retained."""
    kept = _sampler.add(req.item)
    return {"kept": kept, "seen": _sampler.seen}


@app.get("/sampler/sample", tags=["Sampler"])
async def sampler_sample():
    """Return the current reservoir sample and state."""
    return _sampler.state().to_dict()


@app.post("/sampler/reset", tags=["Sampler"])
async def sampler_reset():
    """Empty the reservoir."""
    _sampler.reset()
    return {"status": "reset"}


@app.get("/sampler/metrics", tags=["Sampler"])
async def sampler_metrics():
    """Reservoir sampler metrics: seen, sample size, replacements, fill ratio."""
    return _sampler.metrics()


# ── Percentile Tracker (Fáze 54) ────────────────────────────────────────────────

class PercentileObserveRequest(BaseModel):
    metric: str
    value: float


@app.post("/percentile/observe", tags=["Percentile"])
async def percentile_observe(req: PercentileObserveRequest):
    """Record a value for a metric's rolling distribution."""
    _percentile_tracker.observe(req.metric, req.value)
    return {"metric": req.metric, "observed": req.value}


@app.get("/percentile/summary", tags=["Percentile"])
async def percentile_summary(metric: str):
    """Return count/min/max/mean + percentiles (p50/p90/p95/p99) for a metric."""
    summary = _percentile_tracker.summary(metric)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"No data for metric {metric!r}")
    return summary.to_dict()


@app.get("/percentile/metrics", tags=["Percentile"])
async def percentile_metrics():
    """Percentile tracker metrics: total observations, tracked metrics."""
    return _percentile_tracker.metrics()


# ── Webhook Dispatcher (Fáze 55) ────────────────────────────────────────────────

class WebhookSubscribeRequest(BaseModel):
    url: str
    secret: str
    events: list[str] | None = None


class WebhookDispatchRequest(BaseModel):
    event_type: str
    data: dict


@app.post("/webhooks/subscribe", tags=["Webhooks"])
async def webhooks_subscribe(req: WebhookSubscribeRequest):
    """Register an outbound webhook subscriber (HMAC-signed deliveries)."""
    try:
        sid = _webhook_dispatcher.subscribe(req.url, req.secret, events=req.events)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"sub_id": sid}


@app.delete("/webhooks/{sub_id}", tags=["Webhooks"])
async def webhooks_unsubscribe(sub_id: str):
    """Remove a webhook subscriber."""
    if not _webhook_dispatcher.unsubscribe(sub_id):
        raise HTTPException(status_code=404, detail=f"Unknown subscriber {sub_id!r}")
    return {"status": "unsubscribed", "sub_id": sub_id}


@app.get("/webhooks", tags=["Webhooks"])
async def webhooks_list():
    """List registered webhook subscribers."""
    return {"subscriptions": _webhook_dispatcher.list_subscriptions()}


@app.post("/webhooks/dispatch", tags=["Webhooks"])
async def webhooks_dispatch(req: WebhookDispatchRequest):
    """Dispatch an event to all matching subscribers; returns delivery result."""
    result = await _webhook_dispatcher.dispatch(req.event_type, req.data, _httpx_send)
    return result.to_dict()


@app.get("/webhooks/dead-letters", tags=["Webhooks"])
async def webhooks_dead_letters():
    """List failed deliveries in the dead-letter queue."""
    return {"dead_letters": _webhook_dispatcher.dead_letters()}


@app.get("/webhooks/metrics", tags=["Webhooks"])
async def webhooks_metrics():
    """Webhook dispatcher metrics: delivery rate, dead-letter count."""
    return _webhook_dispatcher.metrics()


# ── Feature Flag Manager (Fáze 56) ──────────────────────────────────────────────

class FlagRegisterRequest(BaseModel):
    name: str
    enabled: bool = False
    rollout: int = 0
    description: str = ""


class FlagUpdateRequest(BaseModel):
    enabled: bool | None = None
    rollout: int | None = None
    override_user: str | None = None
    override_state: bool | None = None  # True=on, False=off, None=clear (with override_user)


@app.post("/flags", tags=["Flags"])
async def flags_register(req: FlagRegisterRequest):
    """Register a feature flag."""
    try:
        flag = _feature_flags.register(
            req.name, enabled=req.enabled, rollout=req.rollout,
            description=req.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return flag.to_dict()


@app.get("/flags", tags=["Flags"])
async def flags_list():
    """List all feature flags."""
    return {"flags": _feature_flags.list_flags()}


@app.post("/flags/{name}/evaluate", tags=["Flags"])
async def flags_evaluate(name: str, user: str | None = None):
    """Evaluate whether a flag is enabled for a given user."""
    return {"name": name, "user": user, "enabled": _feature_flags.is_enabled(name, user)}


@app.patch("/flags/{name}", tags=["Flags"])
async def flags_update(name: str, req: FlagUpdateRequest):
    """Update a flag: master switch, rollout percentage, or a user override."""
    if _feature_flags.get(name) is None:
        raise HTTPException(status_code=404, detail=f"Unknown flag {name!r}")
    if req.enabled is not None:
        _feature_flags.set_enabled(name, req.enabled)
    if req.rollout is not None:
        try:
            _feature_flags.set_rollout(name, req.rollout)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    if req.override_user is not None:
        _feature_flags.set_user_override(name, req.override_user, req.override_state)
    return _feature_flags.get(name)


@app.delete("/flags/{name}", tags=["Flags"])
async def flags_delete(name: str):
    """Delete a feature flag."""
    if not _feature_flags.delete(name):
        raise HTTPException(status_code=404, detail=f"Unknown flag {name!r}")
    return {"status": "deleted", "name": name}


@app.get("/flags/metrics", tags=["Flags"])
async def flags_metrics():
    """Feature flag manager metrics: evaluations, enabled rate."""
    return _feature_flags.metrics()


# ── Health Aggregator (Fáze 57) ─────────────────────────────────────────────────

@app.get("/healthz", tags=["Health"])
async def healthz():
    """Aggregated health across all registered subsystems.

    Returns 200 when healthy/degraded, 503 when unhealthy (a required
    component is down) so orchestrators can gate traffic."""
    report = await _health_aggregator.check()
    if report.status == HealthStatus.UNHEALTHY:
        raise HTTPException(status_code=503, detail=report.to_dict())
    return report.to_dict()


@app.get("/health/components", tags=["Health"])
async def health_components():
    """List registered health-check component names."""
    return {"components": _health_aggregator.list_components()}


@app.get("/healthz/metrics", tags=["Health"])
async def healthz_metrics():
    """Health aggregator metrics: report status distribution."""
    return _health_aggregator.metrics()


# ── SLO Monitor (Fáze 58) ───────────────────────────────────────────────────────

class SLORegisterRequest(BaseModel):
    name: str
    kind: str = "availability"   # availability | latency
    target: float = 0.99
    window: int = 1000
    threshold_ms: float | None = None


class SLORecordRequest(BaseModel):
    outcome: str | None = None   # "success" | "failure" (availability)
    latency_ms: float | None = None  # (latency)


@app.post("/slo", tags=["SLO"])
async def slo_register(req: SLORegisterRequest):
    """Register a Service-Level Objective (availability or latency)."""
    try:
        _slo_monitor.register(
            req.name, kind=SLOKind(req.kind), target=req.target,
            window=req.window, threshold_ms=req.threshold_ms,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "registered", "name": req.name}


@app.post("/slo/{name}/record", tags=["SLO"])
async def slo_record(name: str, req: SLORecordRequest):
    """Record an SLO event: success/failure (availability) or latency_ms (latency)."""
    try:
        if req.latency_ms is not None:
            _slo_monitor.record_latency(name, req.latency_ms)
        elif req.outcome == "success":
            _slo_monitor.record_success(name)
        elif req.outcome == "failure":
            _slo_monitor.record_failure(name)
        else:
            raise HTTPException(status_code=400,
                                detail="provide outcome=success/failure or latency_ms")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "recorded", "name": name}


@app.get("/slo/{name}", tags=["SLO"])
async def slo_report(name: str):
    """Report a single SLO: SLI, error budget, burn rate, status."""
    try:
        return _slo_monitor.report(name).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/slo", tags=["SLO"])
async def slo_report_all():
    """Report all registered SLOs."""
    return {"slos": _slo_monitor.report_all()}


@app.delete("/slo/{name}", tags=["SLO"])
async def slo_delete(name: str):
    """Delete an SLO."""
    if not _slo_monitor.delete(name):
        raise HTTPException(status_code=404, detail=f"Unknown SLO {name!r}")
    return {"status": "deleted", "name": name}


# ── Embedding Provider (Fáze 61, v2.0) ──────────────────────────────────────────

class EmbedRequest(BaseModel):
    text: str


class SimilarityRequest(BaseModel):
    text_a: str
    text_b: str


@app.post("/embeddings", tags=["Embeddings"])
async def embeddings_embed(req: EmbedRequest):
    """Embed text into a vector (offline feature-hashing provider by default)."""
    vec = _embedding_provider.embed(req.text)
    return {"dim": _embedding_provider.dim, "embedding": vec}


@app.post("/embeddings/similarity", tags=["Embeddings"])
async def embeddings_similarity(req: SimilarityRequest):
    """Cosine similarity between two texts' embeddings."""
    a = _embedding_provider.embed(req.text_a)
    b = _embedding_provider.embed(req.text_b)
    return {"similarity": round(cosine_similarity(a, b), 6)}


@app.get("/embeddings/metrics", tags=["Embeddings"])
async def embeddings_metrics():
    """Embedding provider metrics (incl. cache hit-rate when caching)."""
    return _embedding_provider.metrics()


# ── State Store (Fáze 62, v2.0) ─────────────────────────────────────────────────

class StateSetRequest(BaseModel):
    value: Any
    ttl_s: float | None = None


@app.put("/state/{namespace}/{key}", tags=["State"])
async def state_set(namespace: str, key: str, req: StateSetRequest):
    """Store a JSON value under namespace:key, optionally with a TTL."""
    try:
        _state_store.set(namespace, key, req.value, ttl_s=req.ttl_s)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok", "namespace": namespace, "key": key}


@app.get("/state/{namespace}/{key}", tags=["State"])
async def state_get(namespace: str, key: str):
    """Fetch a value; 404 if absent or expired."""
    val = _state_store.get(namespace, key)
    if val is None and not _state_store.exists(namespace, key):
        raise HTTPException(status_code=404, detail="not found")
    return {"namespace": namespace, "key": key, "value": val}


@app.delete("/state/{namespace}/{key}", tags=["State"])
async def state_delete(namespace: str, key: str):
    """Delete a value; 404 if absent."""
    if not _state_store.delete(namespace, key):
        raise HTTPException(status_code=404, detail="not found")
    return {"status": "deleted", "namespace": namespace, "key": key}


@app.get("/state/metrics", tags=["State"])
async def state_metrics():
    """State store metrics (backend, key count, hit rate)."""
    return _state_store.metrics()


@app.get("/state/{namespace}", tags=["State"])
async def state_keys(namespace: str):
    """List live keys within a namespace."""
    return {"namespace": namespace, "keys": _state_store.keys(namespace)}


# ── Snapshot Manager (Fáze 63, v2.0 #3) ─────────────────────────────────────────

class SnapshotRequest(BaseModel):
    component: str | None = None   # None = all registered components


@app.post("/snapshot", tags=["Snapshot"])
async def snapshot_create(req: SnapshotRequest):
    """Persist registered components to the state store."""
    try:
        return {"result": _snapshot_manager.snapshot(req.component)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/snapshot/restore", tags=["Snapshot"])
async def snapshot_restore(req: SnapshotRequest):
    """Restore registered components from the state store."""
    try:
        return {"result": _snapshot_manager.restore(req.component)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/snapshot/metrics", tags=["Snapshot"])
async def snapshot_metrics():
    """Snapshot manager metrics: components, snapshot/restore counts."""
    return _snapshot_manager.metrics()


# ── Token Streaming (Fáze 64, v2.0 #4) ──────────────────────────────────────────

class TokenStreamRequest(BaseModel):
    text: str
    by_sentence: bool = False


@app.post("/stream/tokens", tags=["Streaming"])
async def stream_tokens(req: TokenStreamRequest):
    """Stream text back token-by-token as SSE.

    Demonstrates the end-to-end token-streaming path with a whitespace
    tokenizer as the source; in production the source is a provider's
    ``astream``. Emits ``token`` (or ``sentence``) frames then a ``done`` frame.
    """
    async def _source():
        for i, word in enumerate((req.text or "").split()):
            yield (word if i == 0 else " " + word)

    return StreamingResponse(
        stream_sse(_source(), metrics=_stream_metrics, by_sentence=req.by_sentence),
        media_type="text/event-stream",
    )


@app.get("/stream/metrics", tags=["Streaming"])
async def stream_metrics():
    """Token streaming metrics: stream count, tokens, avg per stream."""
    return _stream_metrics.snapshot()


# ── Multi-Tenancy & RBAC (Fáze 65, v2.0 #5) ─────────────────────────────────────

class TenantCreateRequest(BaseModel):
    tenant_id: str
    name: str


class PrincipalCreateRequest(BaseModel):
    principal_id: str
    role: str            # admin | user | readonly
    api_key: str | None = None


class AuthorizeRequest(BaseModel):
    api_key: str
    permission: str      # read | write | admin


@app.post("/tenants", tags=["Tenancy"])
async def tenants_create(req: TenantCreateRequest):
    """Create a tenant."""
    try:
        return _tenants.create_tenant(req.tenant_id, req.name).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/tenants", tags=["Tenancy"])
async def tenants_list():
    """List tenants (principals shown without API keys)."""
    return {"tenants": _tenants.list_tenants()}


@app.post("/tenants/{tenant_id}/principals", tags=["Tenancy"])
async def tenants_add_principal(tenant_id: str, req: PrincipalCreateRequest):
    """Add a principal to a tenant; returns the (one-time) API key."""
    try:
        role = Role(req.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid role {req.role!r}")
    try:
        p = _tenants.add_principal(tenant_id, req.principal_id, role, api_key=req.api_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"principal_id": p.principal_id, "tenant_id": p.tenant_id,
            "role": p.role.value, "api_key": p.api_key}


@app.post("/tenants/authorize", tags=["Tenancy"])
async def tenants_authorize(req: AuthorizeRequest):
    """Authorize an API key against a permission (read/write/admin)."""
    try:
        perm = Permission(req.permission)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid permission {req.permission!r}")
    return _tenants.authorize(req.api_key, perm).to_dict()


@app.get("/tenants/metrics", tags=["Tenancy"])
async def tenants_metrics():
    """Tenancy metrics: tenants, principals, authz deny rate."""
    return _tenants.metrics()


# ── Request Coalescer (Fáze 66, v2.0 #6) ────────────────────────────────────────

@app.get("/coalesce/metrics", tags=["Coalescer"])
async def coalesce_metrics():
    """Request coalescer metrics: calls, executions, coalesce rate."""
    return _coalescer.metrics()


# ── Eval Harness (Fáze 67, v2.0 #7) ─────────────────────────────────────────────

class EvalScoreRequest(BaseModel):
    cases: list[dict]          # [{name, expected, actual}]
    scorer: str = "exact_match"  # exact_match | contains | jaccard | numeric_close
    threshold: float = 0.8
    pass_score: float = 1.0
    tolerance: float = 0.01    # for numeric_close


_SCORERS = {
    "exact_match": exact_match,
    "contains": contains,
    "jaccard": jaccard,
}


@app.post("/evals/score", tags=["Evals"])
async def evals_score(req: EvalScoreRequest):
    """Score pre-computed expected/actual pairs and return a pass/fail gate.

    A CI regression gate — fail the build when mean score < threshold."""
    if req.scorer == "numeric_close":
        scorer = numeric_close(tolerance=req.tolerance)
    elif req.scorer in _SCORERS:
        scorer = _SCORERS[req.scorer]
    else:
        raise HTTPException(status_code=400, detail=f"unknown scorer {req.scorer!r}")

    harness = EvalHarness()
    actuals: dict[str, Any] = {}
    for i, c in enumerate(req.cases):
        name = c.get("name", f"case{i}")
        harness.add_case(name, input=name, expected=c.get("expected"))
        actuals[name] = c.get("actual")

    try:
        report = await harness.run(
            lambda name: actuals.get(name),
            scorer=scorer, threshold=req.threshold, pass_score=req.pass_score,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return report.to_dict()


# ── Vector Store / Dense Retriever (Fáze 69, v2.0 #9) ───────────────────────────

class VectorIndexRequest(BaseModel):
    documents: list[dict]   # [{doc_id/id, text, metadata?}]


class VectorSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    min_score: float = 0.0


@app.post("/vectors/index", tags=["Vectors"])
async def vectors_index(req: VectorIndexRequest):
    """Index documents into the dense vector store (embedded on ingest)."""
    added = _vector_store.add_many(req.documents)
    return {"added": added, "indexed": _vector_store.size}


@app.post("/vectors/search", tags=["Vectors"])
async def vectors_search(req: VectorSearchRequest):
    """Semantic cosine k-NN search over the vector store."""
    try:
        hits = _vector_store.search(req.query, top_k=req.top_k, min_score=req.min_score)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"query": req.query, "hits": [h.to_dict() for h in hits]}


@app.delete("/vectors", tags=["Vectors"])
async def vectors_clear():
    """Clear the vector index."""
    return {"removed": _vector_store.clear()}


@app.get("/vectors/metrics", tags=["Vectors"])
async def vectors_metrics():
    """Vector store metrics: index size, dim, search counts."""
    return _vector_store.metrics()
