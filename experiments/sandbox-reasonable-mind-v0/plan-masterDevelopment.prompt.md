# 🦅 CLAUDE-QUICKSTARTS: Master Development Plan
## Bird's-Eye View - December 2025

---

## Vision Statement

> **"Logic is the skeleton, AI is the muscles, User agency is the soul."**

A neuro-symbolic AI agent framework combining deterministic formal logic with neural LLM capabilities to create trustworthy, auditable, and trainable AI systems—with Watson-Glaser critical thinking methodology as the proving ground.

---

## Project Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         CLAUDE-QUICKSTARTS ECOSYSTEM                        │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    LAYER 4: USER INTERFACES                         │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────────┐   │  │
│  │  │ watson-glaser-  │  │   agents/ui/    │  │  Anthropic        │   │  │
│  │  │ trainer (Web)   │  │   cli.py ❌     │  │  computer-use     │   │  │
│  │  │ ✅ Complete     │  │   MISSING       │  │  ✅ Original      │   │  │
│  │  └─────────────────┘  └─────────────────┘  └───────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    ▲                                       │
│                                    │                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    LAYER 3: AGENT ORCHESTRATION                     │  │
│  │  ┌───────────────────────────────────────────────────────────────┐ │  │
│  │  │  agents/core/ (40+ modules) - Phase 2 Enhancements           │ │  │
│  │  │  ├─ self_consistency.py    ├─ debate_system.py               │ │  │
│  │  │  ├─ hallucination_*.py     ├─ calibration_system.py          │ │  │
│  │  │  ├─ planning_system.py     ├─ memory_*.py                    │ │  │
│  │  │  ├─ tool_arbitration.py    ├─ curriculum_system.py           │ │  │
│  │  │  └─ 246 tests passing      └─ 70% coverage target            │ │  │
│  │  └───────────────────────────────────────────────────────────────┘ │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    ▲                                       │
│                                    │                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    LAYER 2: REASONING ENGINE                        │  │
│  │  ┌─────────────────────┐  ┌─────────────────────────────────────┐  │  │
│  │  │   agents/logic/     │  │   agents/tools/extended_thinking    │  │  │
│  │  │  ├─ knowledge_base  │  │   8-Layer Chain-of-Thought:         │  │  │
│  │  │  ├─ decision_model  │  │   L1: Pattern Perception            │  │  │
│  │  │  ├─ reasoning_agent │  │   L2: Semantic Analysis             │  │  │
│  │  │  └─ epistemic.py    │  │   L3: Deductive (75% weight) ⭐     │  │  │
│  │  └─────────────────────┘  │   L4: Inductive (75% weight) ⭐     │  │  │
│  │                           │   L5: Critical Evaluation           │  │  │
│  │                           │   L6: Counterfactual Analysis       │  │  │
│  │                           │   L7: Strategic Synthesis           │  │  │
│  │                           │   L8: Meta-Cognition                │  │  │
│  │                           └─────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    ▲                                       │
│                                    │ ⚠️ INVERSION NEEDED                   │
│                                    │ (Logic should be PRIMARY)             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    LAYER 1: DETERMINISTIC FOUNDATION               │  │
│  │  ┌─────────────────────────────────────────────────────────────┐   │  │
│  │  │  agents/core/categorical_engine.py  - Syllogistic Logic     │   │  │
│  │  │    ✅ Barbara (AAA-1)    ✅ Celarent (EAE-1)                │   │  │
│  │  │    ✅ Darii (AII-1)      ✅ Ferio (EIO-1)                   │   │  │
│  │  │    ⏳ Figures 2-4 (16 more forms)                           │   │  │
│  │  ├─────────────────────────────────────────────────────────────┤   │  │
│  │  │  agents/core/fallacy_detector.py - 25+ Patterns             │   │  │
│  │  │    Relevance(7) | Presumption(8) | Ambiguity(3) | Formal(7) │   │  │
│  │  ├─────────────────────────────────────────────────────────────┤   │  │
│  │  │  agents/core/inference_engine.py - Rule Application         │   │  │
│  │  │    Modus Ponens | Modus Tollens | Syllogistic | Transitive  │   │  │
│  │  ├─────────────────────────────────────────────────────────────┤   │  │
│  │  │  ❌ MISSING: proof_engine.py, logic_orchestrator.py         │   │  │
│  │  │  ❌ MISSING: data/argument_forms.json, data/fallacies.json  │   │  │
│  │  └─────────────────────────────────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Phased Development Roadmap

### Phase 1: Deterministic Foundation 🔴 40% → 60%
**Status: CRITICAL GAP BEING ADDRESSED**

| Component | Status | Owner | Priority |
|-----------|--------|-------|----------|
| `categorical_engine.py` | ✅ 4/24 syllogisms | Copilot | P1 |
| `fallacy_detector.py` | ✅ 25+ patterns | Claude Code | P1 |
| `inference_engine.py` | ⚠️ Partial | Copilot | P1 |
| `proof_engine.py` | ❌ Missing | TBD | P1 |
| `logic_orchestrator.py` | ❌ Missing | TBD | P1 |
| `ui/cli.py` (Rich) | ❌ Missing | Claude Code | P2 |
| `data/*.json` | ❌ Missing | TBD | P2 |

**Goal**: Logic can derive answers **before** AI is consulted

---

### Phase 2: Intelligence Layer ✅ 75% Complete
**Status: STRONG - Neural capabilities mature**

| Component | Status | Lines | Tests |
|-----------|--------|-------|-------|
| Self-consistency voting | ✅ | 855 | ✅ |
| Debate system | ✅ | 400+ | ✅ |
| Hallucination mitigation | ✅ | 500+ | ✅ |
| Calibration system | ✅ | 300+ | ✅ |
| Tool arbitration | ✅ | 400+ | ✅ |
| Memory persistence | ✅ | 863 | ✅ |
| Planning system | ✅ | 600+ | ✅ |
| Curriculum learning | ✅ | 599 | ✅ |
| Extended thinking | ✅ | 509 | ✅ |

**Total**: 40+ modules, 246 tests passing, 70%+ coverage

---

### Phase 3: Evolution & Adaptation 🟡 60% Complete
**Status: IN PROGRESS**

| Feature | Web (WGT) | Python | Integration |
|---------|-----------|--------|-------------|
| Neural pattern bank | ✅ | ❌ | ❌ |
| Strategy weights | ✅ | ✅ | ⚠️ |
| Error tracking | ⚠️ | ❌ | ❌ |
| Growth metrics | ⚠️ | ⚠️ | ❌ |
| Agent profiles (8) | ✅ | ❌ | ❌ |

**Gap**: Watson-Glaser frontend and Python backend are **completely disconnected**

---

### Phase 4: Platform Features 🔵 30% Complete
**Status: PLANNED**

| Feature | Status | Priority |
|---------|--------|----------|
| Web UI (advanced.html) | ✅ Complete | - |
| Formal 80-item assessment | ❌ Missing | P3 |
| Analytics dashboard | ❌ Missing | P3 |
| API layer (FastAPI) | ❌ Missing | P2 |
| Multi-user support | ❌ Missing | P4 |
| Local LLM support | ❌ Missing | P3 |

---

## Decision Model: Utility Function

```
U(option) = Σᵢ wᵢ × vᵢ(option) - C(option) - R(option)

Where:
  wᵢ = weight for value dimension i
  vᵢ = value score for dimension i (0-1)
  C  = cost (tokens, latency, API calls)
  R  = risk penalty (uncertainty, potential harm)

Constraints:
  - Hard: Must satisfy (reject if violated)
  - Soft: Should satisfy (penalize if violated)
  
Risk Bands:
  Low (0-0.3)    → Standard evidence
  Medium (0.3-0.6) → Additional verification
  High (0.6-1.0)  → Human escalation
```

---

## 8-Layer Extended Thinking Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              EXTENDED THINKING CONFIGURATIONS               │
├─────────────────────────────────────────────────────────────┤
│  Config │ Layers │ Time    │ Accuracy │ Recommended Use     │
├─────────────────────────────────────────────────────────────┤
│  4x     │ 1-4    │ ~250ms  │ Baseline │ Quick decisions     │
│  8x ⭐  │ 1-8    │ ~450ms  │ +12%     │ Standard reasoning  │
│  16x    │ 1-8×2  │ ~850ms  │ +18%     │ Complex analysis    │
│  32x    │ 1-8×4  │ ~1600ms │ +22%     │ Critical decisions  │
├─────────────────────────────────────────────────────────────┤
│  Layer Weight Distribution:                                 │
│    Layers 3-4 (Logic): 75%                                 │
│    Layers 1-2, 5-8:    25%                                 │
│    → Logic is intentionally prioritized                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Success Metrics Dashboard

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Tests Passing | 246 | 300+ | 🟢 |
| Code Coverage | ~70% | 70% | 🟢 |
| Syllogism Forms | 4/24 | 24/24 | 🟡 |
| Fallacy Patterns | 25 | 60+ | 🟡 |
| Proof Generation | None | Full | 🔴 |
| CLI Interface | None | Complete | 🔴 |
| API Bridge | None | REST+WS | 🔴 |
| WGT Integration | 0% | 100% | 🔴 |

---

## Integration Architecture (Current vs Target)

### Current State ❌
```
┌──────────────────┐         ┌──────────────────┐
│ watson-glaser-   │         │    agents/       │
│ trainer          │   NO    │    (Python)      │
│ (JavaScript)     │◄──────►│                  │
│                  │ BRIDGE  │                  │
└──────────────────┘         └──────────────────┘
       │                              │
       ▼                              ▼
   Browser                      Claude API
   (Local)                      (Remote)
```

### Target State ✅
```
┌──────────────────┐         ┌──────────────────┐
│ watson-glaser-   │         │    agents/       │
│ trainer          │   API   │    (Python)      │
│ (JavaScript)     │◄═══════►│                  │
│                  │ BRIDGE  │                  │
└────────┬─────────┘         └────────┬─────────┘
         │                            │
         │     ┌──────────────┐       │
         └────►│  api/server  │◄──────┘
               │  (FastAPI)   │
               └──────────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
    Claude API   Local LLM    Offline Mode
```

---

## Developer Priority Queue

### Immediate (This Sprint)
1. ⬜ Complete remaining 20 syllogism forms (Figures 2-4)
2. ⬜ Create `proof_engine.py` for step-by-step derivations
3. ⬜ Create `logic_orchestrator.py` for logic-first routing
4. ⬜ Build `ui/cli.py` with Rich library

### Short-Term (2-4 Weeks)
5. ⬜ Create `api/server.py` FastAPI bridge
6. ⬜ Refactor `inference_engine.py` (744 lines → 3 files)
7. ⬜ Add model profiles (Sonnet/Opus/Aurora configs)
8. ⬜ Connect WGT frontend to Python backend

### Medium-Term (1-3 Months)
9. ⬜ Implement formal 80-item WG assessment
10. ⬜ Build analytics dashboard
11. ⬜ Add local LLM support (Ollama)
12. ⬜ Create teaching mode (system explains reasoning)

---

## File Distribution: Core 10

```
📁 ESSENTIAL FILES FOR PROJECT FUNCTION
├── agents/core/inference_engine.py      # Central reasoning (744 lines)
├── agents/core/categorical_engine.py    # Formal syllogisms (300+ lines)
├── agents/logic/knowledge_base.py       # Fact storage (466 lines)
├── agents/core/decision_model.py        # Utility scoring
├── agents/core/planning_system.py       # Task execution
├── agents/core/hallucination_mitigation.py  # Safety layer
├── agents/core/self_consistency.py      # Multi-sample voting (855 lines)
├── agents/core/memory_persistence.py    # State persistence (863 lines)
├── watson-glaser-trainer/advanced.html  # Web interface (1394 lines)
└── pyproject.toml                       # Project configuration
```

---

## The One-Line Mission

> **Build the deterministic logic foundation underneath the excellent neural upper layers, then wire them so logic is primary and AI fills gaps only.**

---

*Document Version: 1.0*
*Last Updated: December 4, 2025*
*Branch: wgt-test-dev*
*Tests: 246 passing*
*Coverage: ~70%*
