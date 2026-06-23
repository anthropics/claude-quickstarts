# Singularity — Multi-LLM Meta-Cognitive Core

> Externí nástavba na **Claude AI** a **Google Gemini**.
> Rozšiřuje architekturu Omega Exoskeleton o simultánní orchestraci dvou LLM
> providerů s inteligentním routerem, rate limitingem, telemetrií a self-healingem.

## Co Singularity přidává oproti Omega

| Vrstva | Přínos |
|--------|--------|
| **Provider abstrakce** | Unifikované rozhraní `AbstractLLMProvider` — Claude i Gemini, snadné přidání dalších |
| **LLM Router** | 6 strategií + self-healing (cooldown po opakovaných selháních) |
| **Rate limiting** | Token bucket per provider (`aiolimiter`) |
| **Telemetrie** | structlog + Prometheus metriky na `/metrics` |
| **Failover** | Automatické přepnutí na druhý provider při selhání |

## Architektura

```
Operátor
  └─► FastAPI (api/main.py)
        └─► SingularityCore (core/graph.py)         ← LangGraph stavový automat
              ├─► LLMRouter (core/router.py)         ← Claude ↔ Gemini routing
              │     ├─► ClaudeProvider               (providers/claude_provider.py)
              │     └─► GeminiProvider               (providers/gemini_provider.py)
              ├─► SingularitySwarm (agents/swarm.py) ← 5 agentů + retry + failover
              │     ├─► Badatel → Claude
              │     ├─► Programátor → Gemini
              │     ├─► Kritik → Claude
              │     ├─► Plánovač → Gemini
              │     └─► Komunikátor → Claude
              ├─► OmegaMemory (memory/mem0_store.py) ← 3-vrstvá paměť
              ├─► OmegaEvaluator (evals/evaluator.py)
              ├─► ProviderRateLimiter (core/limiter.py)
              └─► Telemetry (core/telemetry.py)
```

### Kognitivní smyčka

```
PLAN → EXECUTE → CRITIQUE → [AWAIT_APPROVAL?] → SYNTHESIZE → REFLECT
         ↑                        |
         └────────────────────────┘  (re-plán po zamítnutí)
```

## Routing strategie

| Strategie | Chování |
|-----------|---------|
| `static` | Pevné přiřazení role → provider (default) |
| `failover` | Primary; při selhání přepne na druhý |
| `round_robin` | Střídá dostupné providery |
| `cost_optimized` | Nejlevnější dostupný provider |
| `latency_optimized` | Nejrychlejší dostupný provider |
| `quality_first` | Nejvýše hodnocený dostupný provider |

Výchozí `static` přiřazení využívá silné stránky modelů: Claude pro hluboké
uvažování a kritiku, Gemini pro velký kontext a strukturování.

## Rychlý start

```bash
cp .env.example .env
# Vyplň ANTHROPIC_API_KEY (a volitelně GEMINI_API_KEY)

pip install -e ".[test,dev]"
uvicorn api.main:app --reload --port 8001
```

### Bez Gemini

Pokud `GEMINI_API_KEY` chybí nebo `ENABLE_GEMINI=false`, router automaticky
degraduje na čistě Claude režim — všechny role běží na Claude.

## API endpointy

| Metoda | Endpoint | Popis |
|--------|----------|-------|
| GET | `/health` | Health check |
| POST | `/task` | Zadání úkolu (volitelně `force_provider`) |
| POST | `/approve` | Human-in-the-loop schválení |
| POST | `/e-stop` | 🔴 Nouzové zastavení |
| GET | `/memory/{uid}` | Paměť uživatele |
| GET | `/providers` | Stav providerů (health, cost, latency, cooldown) |
| POST | `/router/strategy` | Runtime změna routing strategie |
| GET | `/metrics` | Prometheus metriky |
| GET | `/tasks/{id}/providers` | Který model zpracoval který krok |
| WS | `/ws/{uid}` | Real-time streaming |

### Příklady

```bash
curl http://localhost:8001/providers

curl -X POST http://localhost:8001/router/strategy \
  -H "Content-Type: application/json" \
  -d '{"strategy": "cost_optimized"}'

curl -X POST http://localhost:8001/task \
  -H "Content-Type: application/json" \
  -d '{"task": "Vysvětli kvantové provázání", "user_id": "test"}'
```

## Testy

```bash
bash scripts/run_tests.sh unit          # rychlé, plně offline (mock provideři)
bash scripts/run_tests.sh chaos         # odolnost vůči výpadkům
bash scripts/run_tests.sh perf          # výkon routingu
bash scripts/run_tests.sh all           # vše
bash scripts/run_tests.sh cov           # s coverage reportem
```

Unit, chaos a perf testy běží **bez API klíčů** díky mock providerům.
Integrační testy s reálnými klíči vyžadují `ANTHROPIC_API_KEY`.

## Stack

| Vrstva | Nástroj |
|--------|---------|
| Orchestrace | LangGraph |
| LLM cloud | Claude API + Gemini API |
| Paměť | Mem0 / lokální ChromaDB |
| RAG | LlamaIndex (volitelné) |
| Evaluace | DeepEval / heuristika |
| Rate limiting | aiolimiter |
| Observabilita | structlog + prometheus-client |
| API | FastAPI + WebSocket |
| Retry | Tenacity |

## Zachované kritické opravy z Omega

Všech 8 kritických oprav z Omega je zachováno: lazy DeepEval init, lokální
paměť bez API klíčů, offline hash embeddings (128-dim), `ASGITransport`,
keyword-only `user_id`, tenacity retry, degraded fallback v `_plan_node`,
`lifespan` handler místo `on_event`.
