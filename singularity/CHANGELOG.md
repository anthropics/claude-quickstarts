# Changelog — Singularity

All notable changes to the Singularity quickstart are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/);
versioning is [SemVer](https://semver.org/).

## [Unreleased]

### Added
- `GET /ui` — simple task-submission web interface served by the app (mirrors
  the `/dashboard` pattern). Same-origin form posts to `POST /task` and renders
  the response, provider log, eval scores, and readable error details.
- `TaskQueue.submit()` accepts optional `backoff_base` / `max_backoff` / `jitter`
  for per-task retry tuning (defaults unchanged — production behaviour identical).

### Changed
- Retry unit tests use a near-zero backoff, cutting `test_retry.py` from ~8 s to
  ~0.2 s (no product behaviour change).
- Maintainability refactor (start): shared runtime singletons moved to
  `api/state.py`; the Vectors endpoints extracted into `api/routers/vectors.py`
  as an `APIRouter`. Routes and behaviour are identical; `api/main.py` shrinks
  from 3743 to 3702 lines. Establishes the pattern for splitting the monolith.
- Maintainability refactor (cont.): Embeddings, State, Streaming, Tenancy,
  Coalescer, and Evals endpoints extracted into `api/routers/*` (singletons in
  `api/state.py`). Routes and behaviour identical (all verified live);
  `api/main.py` shrinks from 3702 to 3479 lines. Snapshot stays in main.py for
  now (coupled to the feature-flags singleton).

## [1.0.0] — 2026-06-29

First stable release. Singularity is a production-ready, multi-LLM
meta-cognitive AI platform (Claude + Gemini) with a dependency-light core:
every module is offline-testable and ships with its own unit suite.

**1259 tests passing** across 63 core modules and an end-to-end integration
suite. Built incrementally over 60 development phases (Fáze 1–60).

### Multi-LLM & Orchestration
- Provider abstraction (`AbstractLLMProvider`) for Claude + Gemini with
  cost/latency/quality metadata and self-healing cooldown
- LLM Router — 6 strategies (static, failover, round-robin, cost/latency/
  quality-optimized) plus a cascade (draft → oracle) strategy
- Multi-Agent Orchestrator — DAG supervisor-worker execution with topological
  waves, dependency injection, and merge/select-best/vote aggregation
- Swarm, workflow engine, scheduler, task queue (priority + multi-worker)

### Retrieval (RAG)
- Document Chunker (character / sentence / paragraph, overlap-aware)
- BM25 Retriever (Okapi BM25, incremental index)
- Semantic Cache (cosine similarity, LRU, TTL)
- Hybrid Reranker (Reciprocal Rank Fusion + weighted score)
- Citation Tracker (sentence-level grounding, hallucination signal)

### NLP toolkit
- Extractive Summarizer, Language Detector, Output Parser, Sentiment
  Analyzer, Keyword Extractor (RAKE), Readability (Flesch), Entity Extractor,
  Deduplicator (SimHash), Fuzzy Matcher (Levenshtein)
- Text Analytics Suite — one-shot composed report over all of the above

### Safety & privacy
- Guardrails (content moderation rules), Output Validator (constraint +
  repair loop), PII Anonymizer (reversible), Request Pipeline (PII redaction,
  truncation, token counting), Audit Log, API-key auth

### Observability & operations
- structlog + Prometheus telemetry, OpenTelemetry tracing, log ring buffer
- Percentile Tracker, Anomaly Detector (z-score / IQR), SLO Monitor
  (error budgets + burn rate), Health Aggregator (`/healthz`)
- Rate limiting, circuit breakers, quota/budget managers, Cost Estimator,
  Reservoir/Rate Sampler, graceful shutdown, persistence (SQLite)

### Integration & control plane
- Webhook Dispatcher (HMAC-signed, retry/backoff, dead-letter queue)
- Feature Flag Manager (runtime toggles, % rollout, per-user overrides)
- Context Window Manager, Consensus Engine, Intent Classifier,
  Response Comparator, Prompt Templates, Tool Registry

### Enterprise / HPC
- Apptainer definitions, Slurm DDP submission, PyTorch Lightning preemption
  handling, cascade routing, monitoring & AppArmor hardening (`hpc/`)

### API
- ~190 FastAPI endpoints with lifespan management, request-context
  middleware, CORS, SSE streaming, and a WebSocket node-stream
