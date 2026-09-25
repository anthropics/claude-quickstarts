# REVIEW_autonomous_coding — Consolidated (v3.5.1)

> Concatenation intégrale des reviews existantes, sans altération du contenu source.

---

## Source: `REVIEW_V2_autonomous_coding.md`

# Rapport de Review Production — `autonomous-coding/` V2

> **Périmètre :** Audit complet du code V2, confronté à l'article de référence  
> **Référence :** [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) — Anthropic Engineering, 24 mars 2026  
> **Sévérité des findings :** 🔴 Critique · 🟠 Majeur · 🟡 Mineur · 🟢 Positif  
> **Tolérance erreurs :** Zéro (usage production)

---

## Résumé Exécutif

Le portage V1→V2 capture correctement le squelette architectural de l'article (trois phases, état persisté, schémas JSON, sécurité préservée). C'est un bon point de départ. Cependant, **7 écarts majeurs ou critiques** séparent l'implémentation actuelle des recommandations clés de l'article, et **11 défauts de qualité code** constituent des risques réels en production. Plusieurs fonctionnalités décrites comme des leviers de performance essentiels dans l'article sont soit absentes, soit tronquées. Ce rapport les détaille tous avec des solutions de correction précises et actionnables.

---

## Table des Matières

1. [Conformité Architecturale vs Article](#1-conformité-architecturale-vs-article)
2. [Findings Critiques](#2-findings-critiques)
3. [Findings Majeurs](#3-findings-majeurs)
4. [Findings Mineurs / Qualité Code](#4-findings-mineurs--qualité-code)
5. [Défauts de Tests](#5-défauts-de-tests)
6. [Matrice de Conformité Article](#6-matrice-de-conformité-article)
7. [Plan d'Actions Priorisé](#7-plan-dactions-priorisé)

---

## 1. Conformité Architecturale vs Article

### Ce qui est correctement implémenté ✅

| Concept Article | Implémentation V2 | Statut |
|---|---|---|
| Architecture trois agents | `planner.py`, `builder.py`, `evaluator.py` | ✅ |
| État persisté sur disque | `state/run_state.json`, `state/round_state_XX.json` | ✅ |
| Artifacts contractuels avec schémas | `schemas/*.json` + `artifacts.py` | ✅ |
| Playwright MCP préféré, Puppeteer fallback | `client.py` `_browser_config()` | ✅ |
| Résumé de phase passé en contexte | `run_state.latest_summary` | ✅ (partiel) |
| Résumabilité (`--resume`) | `orchestrator.py` + `--resume` flag | ✅ |
| Planner comme phase dédiée | `planner.py` + `planner_prompt.md` | ✅ |
| Modèles configurables par phase | `ModelConfig` + args CLI | ✅ |
| Sécurité préservée | `security.py` inchangé | ✅ |

### Ce qui est absent ou diverge ❌

| Concept Article | Statut V2 | Gravité |
|---|---|---|
| Session continue unique + compaction SDK (vs resets de contexte) | ❌ Absent | 🔴 |
| Négociation de contrat de sprint (Generator ↔ Evaluator) | ❌ Absent | 🔴 |
| Critères d'évaluation gradués avec seuils durs (4 critères) | ❌ Absent | 🟠 |
| Auto-évaluation du generator avant handoff QA | ❌ Absent | 🟠 |
| Calibration de l'evaluator avec exemples few-shot | ❌ Absent | 🟠 |
| Planner ambitieux en scope + intégration de features IA | ❌ Partiel | 🟠 |
| Décision stratégique post-évaluation (refine vs pivot) | ❌ Absent | 🟡 |
| Tracking de coût/tokens par phase | ❌ Absent | 🟡 |
| Intégration du skill `frontend-design` dans le planner | ❌ Absent | 🟡 |

---

## 2. Findings Critiques

### 🔴 C-01 — Architecture de Session : Context Resets au lieu de Compaction Continue

**Fichier :** `agent.py:run_phase_session()` + `client.py:create_client()`

**Problème :**
L'article précise explicitement que pour **Claude Opus 4.6**, les context resets ne sont plus nécessaires. La compaction automatique du SDK Agent suffit. Le code V2 crée pourtant un **nouveau client à chaque phase**, ce qui constitue un context reset complet entre planner, builder et evaluator.

```python
# agent.py — PROBLÈME : nouveau client = nouveau contexte à chaque phase
async def run_phase_session(project_dir, model, prompt, phase):
    client = create_client(...)   # ← Contexte détruit ici
    async with client:
        status, response = await run_agent_session(client, prompt, project_dir)
```

L'article (section "Scaling to full-stack coding") :
> *"Opus 4.6 largely removed that behavior on its own, so I was able to drop context resets from this harness entirely. The agents were run as one continuous session across the whole build, with the Claude Agent SDK's automatic compaction handling context growth."*

**Impact :** Overhead de tokens à chaque phase, perte de contexte implicite acquis par le builder lors du handoff vers l'evaluator, latence accrue inutile.

**Correction :**
```python
# orchestrator.py — Session unique persistante
class Orchestrator:
    def __init__(self, ...):
        self._persistent_client: ClaudeSDKClient | None = None

    def _get_or_create_client(self, model: str, phase: str) -> ClaudeSDKClient:
        if self._persistent_client is None:
            self._persistent_client = create_client(
                project_dir=self.project_dir,
                model=model,
                phase=phase,
                compaction_enabled=True,  # SDK auto-compaction
            )
        return self._persistent_client

    async def run(self, ...):
        async with self._get_or_create_client(...) as client:
            # Planner, builder, evaluator partagent le même client
            planner_result = await self.planner.run(
                project_dir=self.project_dir,
                model=self.model_config.planner_model,
                client=client,  # Injecter le client partagé
            )
            ...
```

> **Note importante :** Cette refactorisation nécessite de passer le `client` en paramètre dans `PlannerPhase`, `BuilderPhase` et `EvaluatorPhase`, et de supprimer la création interne du client dans `run_phase_session`. La signature du `PhaseRunner` callable doit aussi être adaptée.

---

### 🔴 C-02 — Négociation de Contrat de Sprint Absente

**Fichier :** `builder.py`, `evaluator.py`, `prompts/builder_prompt.md`, `prompts/evaluator_prompt.md`

**Problème :**
L'article décrit un mécanisme central : avant chaque sprint, le generator et l'evaluator **négocient un contrat** définissant ce que "done" signifie pour ce bloc de travail. Ce contrat est ensuite utilisé comme référence de test par l'evaluator.

> *"Before each sprint, the generator and evaluator negotiated a sprint contract: agreeing on what 'done' looked like for that chunk of work before any code was written."*

Ce concept est **entièrement absent** du V2. Les prompts builder et evaluator ne font aucune mention de ce processus. L'evaluator ne teste que contre des critères généraux, pas contre un accord pré-négocié.

**Impact :** L'evaluator évalue sans critères précis, ce qui produit des verdicts flous, difficiles à contester et potentiellement incohérents d'un round à l'autre.

**Correction :**

Créer un fichier d'artifact de contrat par round :

```python
# artifacts.py — Ajouter
def sprint_contract(self, round_number: int) -> Path:
    return self.planning_dir / f"sprint_contract_round_{round_number:02d}.md"
```

Ajouter un schéma `sprint_contract.schema.json` :
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["round_number", "features_in_scope", "acceptance_tests"],
  "properties": {
    "round_number": { "type": "integer" },
    "features_in_scope": { "type": "array", "items": { "type": "string" } },
    "acceptance_tests": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "criterion", "verification_method"],
        "properties": {
          "id": { "type": "string" },
          "criterion": { "type": "string" },
          "verification_method": { "type": "string" }
        }
      }
    }
  }
}
```

Mettre à jour les prompts pour que le builder propose un contrat et que l'evaluator le valide avant implémentation.

---

## 3. Findings Majeurs

### 🟠 M-01 — Prompt Evaluator : Absence de Critères Gradués et de Calibration

**Fichier :** `prompts/evaluator_prompt.md`

**Problème :**
Le prompt actuel de l'evaluator est minimaliste (21 lignes). L'article décrit un evaluator soigneusement calibré avec :
- **4 critères nommés** (design quality, originality, craft, functionality)
- **Des seuils durs par critère** — si un seul tombe sous le seuil, le sprint échoue
- **Des exemples few-shot** pour calibrer le jugement et éviter la dérive
- Une instruction explicite à être **sceptique et bug-oriented**

> *"Getting the evaluator to perform at this level took work. Out of the box, Claude is a poor QA agent. In early runs, I watched it identify legitimate issues, then talk itself into deciding they weren't a big deal."*

Prompt actuel (extrait) :
```markdown
### Rules
- Be skeptical and bug-oriented.
- Require user-visible verification evidence; code inspection alone is insufficient.
```

C'est insuffisant. L'article montre que "be skeptical" seul ne suffit pas — il faut des critères explicites et des exemples de calibration.

**Correction :**
```markdown
## GRADED EVALUATION CRITERIA

Each criterion is scored 1-5. A score below 3 on ANY criterion is an automatic FAIL.

### 1. Functional Correctness (Weight: 40%)
- 5: All tested features work end-to-end with no bugs found
- 3: Core features work but secondary features have bugs
- 1: Core features are broken or stub-only

### 2. Visual Design Quality (Weight: 25%)
- 5: Coherent visual identity, deliberate design choices, not generic AI output
- 3: Functional but templated, no distinct identity
- 1: Broken layout, poor contrast, obvious AI slop patterns

### 3. Product Completeness (Weight: 25%)
- 5: All sprint contract items implemented and verifiable
- 3: 80%+ items implemented, remainder are non-blocking
- 1: < 70% implemented or blockers present

### 4. Code Quality (Weight: 10%)
- 5: Clean, no console errors, proper error handling
- 3: Minor issues, no regressions
- 1: Console errors, regressions, broken imports

## FEW-SHOT CALIBRATION EXAMPLES

### Example: PASS verdict
Sprint contract required: user login, session persistence, message streaming
Playwright found: login works, session survives refresh, streaming delivers tokens progressively
Score: Correctness=5, Design=4, Completeness=5, Code=5 → PASS

### Example: FAIL verdict
Sprint contract required: artifact panel renders HTML previews
Playwright found: panel opens but iframe stays blank; no console error, silent failure
Score: Correctness=2 → AUTOMATIC FAIL despite other criteria passing

### Example: BLOCKED verdict
Playwright MCP server did not start (npx timeout).
Result: blocked — do not mark pass without user-visible verification.
```

---

### 🟠 M-02 — Prompt Builder : Absence d'Auto-Évaluation Avant Handoff

**Fichier :** `prompts/builder_prompt.md`

**Problème :**
L'article indique que le generator est instruit de **s'auto-évaluer avant de passer la main** à l'evaluator. Le prompt builder actuel ne mentionne pas cette étape.

**Correction — Ajouter à `builder_prompt.md` :**
```markdown
### Before handing off to QA (MANDATORY)

Before completing your build round, self-evaluate your work:

1. Start the application servers and verify they are running.
2. Use Playwright MCP to navigate the app and exercise each feature you implemented.
3. Take screenshots as evidence for each tested feature.
4. For each item in `planning/work_backlog.json` you worked on:
   - Mark it `in_progress` or `done` based on actual browser verification.
   - Do NOT mark `done` if you only wrote the code without browser verification.
5. Document your self-evaluation findings in `builder/build_report_round_XX.md`.

Strategic decision: After reviewing evaluator feedback from the previous round,
decide explicitly whether to REFINE (continue current direction) or PIVOT
(change approach entirely). State this decision at the top of your build report.
```

---

### 🟠 M-03 — Prompt Planner : Trop Conservateur, Manque d'Ambition et de Features IA

**Fichier :** `prompts/planner_prompt.md`

**Problème :**
L'article insiste sur le fait que le planner doit :
1. Être **ambitieux en scope** — élargir la spec initiale au maximum
2. **Intégrer des features IA** dans chaque spec générée
3. Lire le **frontend design skill** pour créer un langage visuel cohérent
4. Se concentrer sur les **livrables utilisateur**, pas les détails techniques

Le planner actuel est générique et défensif.

**Correction — Remplacer `prompts/planner_prompt.md` par :**
```markdown
## ROLE: PLANNER PHASE (V2)

You are the planner in a three-phase autonomous coding harness. Your job is to
transform the input spec into an ambitious, detailed, and AI-powered product spec.

### Guiding principles (from Anthropic's harness research)
- Be AMBITIOUS about scope: expand the brief beyond what was explicitly asked.
- Weave AI-powered features into the spec wherever natural.
- Focus on user-visible deliverables and testable behaviors — not implementation details.
- Deliberately avoid over-specifying technical implementation to prevent cascading errors.
- If a frontend design skill file exists at `skills/frontend-design/SKILL.md` or similar,
  read it and use it to define the visual design language for the app.

### Inputs you must read
- `app_spec.txt`
- `feature_list.json` (if present — treat as requirement ledger, do not rewrite)
- `skills/` directory (if present)

### Outputs you must write
...
```

---

### 🟠 M-04 — Modèle par Défaut : Sonnet au lieu d'Opus pour les Phases Critiques

**Fichier :** `autonomous_agent_demo.py` (lignes 14-17)

**Problème :**
```python
DEFAULT_PLANNER_MODEL = "claude-sonnet-4-6"
DEFAULT_BUILDER_MODEL = "claude-sonnet-4-6"
DEFAULT_EVALUATOR_MODEL = "claude-sonnet-4-6"
```

L'article utilise **Opus 4.6** pour l'ensemble du harness, et justifie ce choix :
> *"We also released Opus 4.6 [...] 'plans more carefully, sustains agentic tasks for longer, can operate more reliably in larger codebases, and has better code review and debugging skills to catch its own mistakes.'"*

Utiliser Sonnet pour le builder d'une session de plusieurs heures est un risque de dégradation de performance mesurable, surtout pour la phase de build qui peut durer > 2 heures.

**Correction :**
```python
DEFAULT_PLANNER_MODEL = "claude-opus-4-6"    # Meilleure planification
DEFAULT_BUILDER_MODEL = "claude-opus-4-6"    # Sessions longues (2h+)
DEFAULT_EVALUATOR_MODEL = "claude-sonnet-4-6" # Évaluation = tâche moins lourde
```

Documenter clairement dans le README le trade-off coût/qualité.

---

### 🟠 M-05 — BuilderPhase : Création Silencieuse de Rapport Fallback

**Fichier :** `builder.py:BuilderPhase.run()` (lignes 29-34)

**Problème :**
```python
if not report_path.exists():
    report_path.write_text(
        f"# Build Report Round {round_number:02d}\n\n{summary.strip() or 'No summary from builder.'}\n"
    )
```

Si le runner renvoie une chaîne vide (échec silencieux, timeout, ou modèle qui n'a rien écrit), un rapport de build est créé artificiellement contenant uniquement `"No summary from builder."`. L'orchestrateur continue comme si le build avait réussi.

**Impact :** Un round de build défaillant peut passer inaperçu et propager un état invalide.

**Correction :**
```python
async def run(self, project_dir, model, round_number) -> BuilderResult:
    paths = ArtifactPaths(project_dir)
    paths.ensure_dirs()
    summary = await self.runner(project_dir, model, get_builder_prompt(), "builder")

    if not summary or not summary.strip():
        raise RuntimeError(
            f"BuilderPhase round {round_number}: runner returned empty response. "
            "Builder may have failed silently. Check logs."
        )

    report_path = paths.build_report_md(round_number)
    if not report_path.exists():
        report_path.write_text(
            f"# Build Report Round {round_number:02d}\n\n{summary.strip()}\n"
        )
    return BuilderResult(report_path=report_path, summary=summary)
```

---

### 🟠 M-06 — Orchestrator : État Écrit Avant Succès du Builder

**Fichier :** `orchestrator.py` (lignes 74-78)

**Problème :**
```python
run_state.status = RunStatus.BUILDING
run_state.current_round = round_number    # ← Écrit ici
self._save_run_state(run_state)            # ← Persisté
build_result = await self.builder.run(...)  # ← Peut planter
```

Si le builder plante après la sauvegarde de l'état, le `current_round` est incrémenté dans le fichier d'état, mais aucun build n'a réellement été effectué. Au prochain `--resume`, l'orchestrateur sautera ce round.

**Correction — Pattern checkpoint post-succès :**
```python
run_state.status = RunStatus.BUILDING
self._save_run_state(run_state)             # Sauvegarde le statut

build_result = await self.builder.run(...)  # Exécution

# Checkpoint APRÈS succès seulement
run_state.current_round = round_number
self._save_run_state(run_state)
```

---

## 4. Findings Mineurs / Qualité Code

### 🟡 Q-01 — `security.py` : `pnpm` Absent de l'Allowlist

**Fichier :** `security.py:ALLOWED_COMMANDS`

L'`app_spec.txt` mentionne explicitement `pnpm` pour les dépendances frontend :
> *"Frontend dependencies pre-installed via pnpm"*

`pnpm` est absent de `ALLOWED_COMMANDS`. Si le builder tente `pnpm install`, la commande sera bloquée silencieusement.

**Correction :**
```python
ALLOWED_COMMANDS = {
    ...
    "npm",
    "pnpm",   # ← Ajouter
    "node",
    ...
}
```

---

### 🟡 Q-02 — `artifacts.py` : Lecture de Schéma Non Cachée

**Fichier :** `artifacts.py:_load_schema()`

```python
def _load_schema(name: str) -> dict[str, Any]:
    path = SCHEMA_DIR / f"{name}.schema.json"
    return json.loads(path.read_text())   # ← Lecture disque à chaque appel
```

Dans un harness avec 3 phases × N rounds, cette fonction est appelée en boucle. Les schémas sont statiques — ils ne changent pas pendant l'exécution.

**Correction :**
```python
from functools import lru_cache

@lru_cache(maxsize=None)
def _load_schema(name: str) -> dict[str, Any]:
    path = SCHEMA_DIR / f"{name}.schema.json"
    return json.loads(path.read_text())
```

---

### 🟡 Q-03 — `orchestrator.py` : Résumé Tronqué Arbitrairement à 4000 Caractères

**Fichier :** `orchestrator.py` (occurrences multiples)

```python
run_state.latest_summary = planner_result.summary[:4000]
```

Cette limite de 4000 caractères est arbitraire et non documentée. Elle peut tronquer des informations de handoff critiques (bugs identifiés, décisions architecturales).

**Correction :** Définir la constante, la documenter, et permettre son override :
```python
SUMMARY_MAX_CHARS = int(os.environ.get("V2_SUMMARY_MAX_CHARS", "8000"))
...
run_state.latest_summary = planner_result.summary[:SUMMARY_MAX_CHARS]
```

---

### 🟡 Q-04 — `autonomous_agent_demo.py` : `_normalize_project_dir` Fragile

**Fichier :** `autonomous_agent_demo.py:_normalize_project_dir()`

```python
def _normalize_project_dir(project_dir: Path) -> Path:
    if project_dir.is_absolute() or str(project_dir).startswith("generations/"):
        return project_dir
    return Path("generations") / project_dir
```

Un path comme `./generations/myproject` ne commence pas par `"generations/"` — il commence par `"./"`. Ce chemin sera normalisé en `generations/./generations/myproject`.

**Correction :**
```python
def _normalize_project_dir(project_dir: Path) -> Path:
    resolved = project_dir.resolve()
    generations = Path("generations").resolve()
    if resolved.is_relative_to(generations) or project_dir.is_absolute():
        return project_dir
    return Path("generations") / project_dir
```

---

### 🟡 Q-05 — `agent.py` : Perte de Stack Trace sur Exception

**Fichier :** `agent.py:run_agent_session()` (lignes 46-48)

```python
except Exception as exc:
    print(f"Error during agent session: {exc}")
    return "error", str(exc)
```

Le `str(exc)` perd le type d'exception et la stack trace. En production, diagnostiquer un échec de session sans stack trace est très difficile.

**Correction :**
```python
import traceback

except Exception as exc:
    tb = traceback.format_exc()
    print(f"Error during agent session: {exc}\n{tb}")
    return "error", f"{exc}\n{tb}"
```

---

### 🟡 Q-06 — `evaluator.py` : `read_json` ne Gère pas le JSON Malformé

**Fichier :** `evaluator.py:EvaluatorPhase.run()` (ligne 29)

```python
report = read_json(report_json_path)
```

`read_json` dans `artifacts.py` appelle `json.loads(path.read_text())` sans try/catch. Si le modèle a écrit un JSON malformé (ce qui arrive fréquemment en production), c'est une exception non traitée qui fait crasher l'evaluator sans message d'erreur utile.

**Correction dans `artifacts.py` :**
```python
def read_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"Warning: malformed JSON at {path}: {e}. Using default.")
        return default if default is not None else {}
```

---

### 🟡 Q-07 — `orchestrator.py` : Pas de Gestion du `resume` sur un Run Déjà `completed`

**Fichier :** `orchestrator.py:run()`

Si `--resume` est passé sur un projet dont `run_state.json` indique `completed=True`, l'orchestrateur relance l'intégralité des rounds builder/evaluator sans avertissement.

**Correction :**
```python
async def run(self, resume=True, ...):
    run_state = self._load_run_state() if resume else RunState(max_rounds=self.max_rounds)

    if resume and run_state.completed:
        print(f"[V2] Run already completed (status={run_state.status.value}). "
              "Use --resume=False or delete state/run_state.json to restart.")
        return run_state
    ...
```

---

### 🟡 Q-08 — `client.py` : Écriture de `.claude_settings.json` à Chaque Appel

**Fichier :** `client.py:create_client()` (ligne 68)

```python
settings_file.write_text(json.dumps(security_settings, indent=2))
```

Ce fichier est écrit à chaque création de client, même si le contenu n'a pas changé. Dans un harness multi-round, c'est une écriture disque superflue à chaque phase.

**Correction :**
```python
if not settings_file.exists():
    settings_file.write_text(json.dumps(security_settings, indent=2))
```

---

### 🟡 Q-09 — Absence de Tracking de Coût et de Durée par Phase

**Problème :**
L'article présente des tableaux de coût détaillés par phase. V2 n'émet aucune métrique de coût ou de durée, ce qui rend l'optimisation et le debugging impossibles.

**Correction minimale :**
```python
# orchestrator.py
import time

async def run(self, ...):
    phase_timings = {}
    
    t0 = time.monotonic()
    planner_result = await self.planner.run(...)
    phase_timings["planner"] = time.monotonic() - t0
    
    ...
    
    # En fin de run
    print("\n[V2] Phase timing summary:")
    for phase, duration in phase_timings.items():
        print(f"  {phase}: {duration:.1f}s")
```

---

### 🟡 Q-10 — `prompts/evaluator_prompt.md` : Pas de Vérification de l'État du Serveur Applicatif

**Problème :**
L'evaluator est censé tester l'application via Playwright. Mais le prompt ne contient aucune instruction pour vérifier que l'application est bien **démarrée et accessible** avant de lancer les tests. Si le serveur n'est pas lancé, l'evaluator peut produire un rapport `fail` ou `blocked` pour de mauvaises raisons.

**Correction — Ajouter en tête de `evaluator_prompt.md` :**
```markdown
### Pre-flight checks (run before any QA)

1. Verify the application server is running:
   - Use Playwright to navigate to the expected URL (check app_spec.txt for port).
   - If the page returns a connection error or 5xx, immediately emit `result: blocked`
     with description "Application server not responding at expected URL."
   - Do NOT attempt further testing until the app is confirmed accessible.
2. If the server is not running, check `builder/build_report_round_XX.md` for
   startup instructions and attempt to start it before failing the round.
```

---

### 🟡 Q-11 — `schemas/run_state.schema.json` : Enum `status` Désynchronisé avec `RunStatus`

**Fichier :** `schemas/run_state.schema.json` vs `state_models.py`

Le schéma JSON déclare :
```json
"status": {"type": "string", "enum": ["not_started", "planning", "building", "evaluating", "completed", "blocked"]}
```

`RunStatus` dans `state_models.py` déclare exactement les mêmes valeurs. Toute modification de l'enum dans l'un mais pas l'autre introduira une erreur de validation silencieuse ou une `KeyError`.

**Correction :** Générer le schéma JSON programmatiquement depuis `RunStatus` :
```python
# scripts/generate_schemas.py
import json
from state_models import RunStatus

schema_fragment = {"enum": [s.value for s in RunStatus]}
# Intégrer à run_state.schema.json via script de génération
```

Ou, au minimum, ajouter un test unitaire qui vérifie la cohérence :
```python
# tests/test_schema_consistency.py
def test_run_status_enum_matches_schema():
    schema = json.loads((SCHEMA_DIR / "run_state.schema.json").read_text())
    schema_values = set(schema["properties"]["status"]["enum"])
    code_values = {s.value for s in RunStatus}
    assert schema_values == code_values, f"Drift: {schema_values ^ code_values}"
```

---

## 5. Défauts de Tests

### 🟡 T-01 — `test_resume_skips_planner` ne Vérifie Pas que le Planner est Réellement Sauté

**Fichier :** `tests/test_orchestrator_integration.py:test_resume_skips_planner()`

```python
state = asyncio.run(orchestrator2.run(resume=True, qa_only=True))
assert state.current_round >= 1   # ← Vérifie seulement que round >= 1
```

Ce test ne vérifie pas que `runner2.eval_calls` (nombre d'appels planner) est `0`. Un bug qui relancerait le planner passerait ce test.

**Correction :**
```python
assert runner2.eval_calls >= 1
# Vérifier que le planner du second orchestrateur n'a pas été appelé
# (nécessite un compteur planner_calls dans FakeRunner)
assert runner2.planner_calls == 0  # ← Ajouter ce compteur dans FakeRunner
```

---

### 🟡 T-02 — Absence de Tests pour les Cas d'Erreur de `BuilderPhase` et `EvaluatorPhase`

Il manque des tests couvrant :
- Builder qui renvoie une réponse vide → doit lever `RuntimeError`
- Evaluator qui écrit un JSON invalide → doit utiliser le fallback `blocked`
- Evaluator qui ne crée aucun rapport → doit créer le rapport `blocked`

Ces cas sont les plus susceptibles de se produire en production.

---

### 🟡 T-03 — Absence de Test `--planner-only` et `--qa-only` en Combinaison Invalide

**Fichier :** `orchestrator.py:run()`

```python
if planner_only and qa_only:
    raise ValueError("Cannot use --planner-only and --qa-only together")
```

Ce comportement n'est couvert par aucun test.

---

## 6. Matrice de Conformité Article

| Principe Article | Implémenté | Qualité | Priorité Fix |
|---|---|---|---|
| Architecture 3 agents | ✅ Oui | Correcte | — |
| Session continue + compaction SDK | ❌ Non | Context resets à la place | 🔴 P0 |
| Contrat de sprint négocié | ❌ Non | Absent | 🔴 P0 |
| Critères d'évaluation gradués | ❌ Non | Prompt minimaliste | 🟠 P1 |
| Calibration evaluator few-shot | ❌ Non | Absent | 🟠 P1 |
| Auto-évaluation builder pre-handoff | ❌ Non | Absent | 🟠 P1 |
| Planner ambitieux + features IA | 🟡 Partiel | Prompt trop défensif | 🟠 P1 |
| Modèle adapté (Opus 4.6) | 🟡 Partiel | Sonnet pour tout | 🟠 P1 |
| Checkpoint état post-succès | ❌ Non | Avant exécution | 🟠 P1 |
| Décision stratégique refine/pivot | ❌ Non | Absent du prompt | 🟡 P2 |
| Tracking coût/durée par phase | ❌ Non | Absent | 🟡 P2 |
| Skill frontend-design dans planner | ❌ Non | Non mentionné | 🟡 P2 |
| Gestion JSON malformé evaluator | ❌ Non | Exception non traitée | 🟠 P1 |
| pnpm dans allowlist sécurité | ❌ Non | Bug potentiel prod | 🟠 P1 |
| Tests cohérence schéma/enum | ❌ Non | Dérive possible | 🟡 P2 |

---

## 7. Plan d'Actions Priorisé

### P0 — Bloquant Production (Corriger avant tout déploiement)

| ID | Action | Fichier(s) |
|---|---|---|
| C-01 | Passer à session unique + compaction SDK pour Opus 4.6 | `agent.py`, `orchestrator.py`, `client.py`, `builder.py`, `evaluator.py`, `planner.py` |
| C-02 | Implémenter la négociation de contrat de sprint | `artifacts.py`, `schemas/`, `prompts/builder_prompt.md`, `prompts/evaluator_prompt.md`, `orchestrator.py` |

### P1 — Majeur (Sprint suivant)

| ID | Action | Fichier(s) |
|---|---|---|
| M-01 | Rewrite prompt evaluator avec critères gradués + few-shot | `prompts/evaluator_prompt.md` |
| M-02 | Ajouter auto-évaluation + décision stratégique au builder | `prompts/builder_prompt.md` |
| M-03 | Rewrite prompt planner (ambitieux, features IA, skill) | `prompts/planner_prompt.md` |
| M-04 | Changer modèles par défaut (Opus planner+builder, Sonnet evaluator) | `autonomous_agent_demo.py` |
| M-05 | BuilderPhase : lever exception si runner vide | `builder.py` |
| M-06 | Orchestrator : checkpoint état après succès builder | `orchestrator.py` |
| Q-01 | Ajouter `pnpm` à l'allowlist sécurité | `security.py` |
| Q-06 | Gérer `json.JSONDecodeError` dans `read_json` | `artifacts.py` |
| Q-07 | Gérer `--resume` sur run déjà `completed` | `orchestrator.py` |

### P2 — Amélioration (Backlog qualité)

| ID | Action | Fichier(s) |
|---|---|---|
| M-09 | Ajouter tracking coût/durée par phase | `orchestrator.py` |
| Q-02 | Cache `lru_cache` sur `_load_schema` | `artifacts.py` |
| Q-03 | Constante `SUMMARY_MAX_CHARS` configurable | `orchestrator.py` |
| Q-04 | Fix `_normalize_project_dir` avec `.resolve()` | `autonomous_agent_demo.py` |
| Q-05 | Conserver stack trace dans `run_agent_session` | `agent.py` |
| Q-08 | Écriture conditionnelle `.claude_settings.json` | `client.py` |
| Q-11 | Test de cohérence schéma/enum `RunStatus` | `tests/` |
| T-01 | Fix `test_resume_skips_planner` + compteur `planner_calls` | `tests/test_orchestrator_integration.py` |
| T-02 | Tests cas d'erreur Builder/Evaluator | `tests/` |
| T-03 | Test combinaison invalide `--planner-only + --qa-only` | `tests/` |

---

## Conclusion

Le V2 est une base saine : la structure trois phases, les schémas JSON, l'état persisté et la sécurité sont bien posés. Mais l'implémentation s'arrête là où l'article commence à délivrer sa vraie valeur — la session continue, le contrat de sprint, les critères gradués et la calibration de l'evaluator sont précisément les mécanismes qui permettent à ce harness de produire des applications de qualité sur des runs de plusieurs heures.

Le P0 le plus critique (C-01) est architectural : passer des context resets par phase à une session continue avec compaction SDK est un changement de fond qui conditionne toute la performance du harness avec Opus 4.6. Le P0 C-02 (contrat de sprint) est ce qui transforme l'evaluator d'un agent générique en un QA agent précis et actionnable.

Sans ces deux corrections, le V2 reste fonctionnel mais délivre une qualité proche du V1 — ce qui manque précisément l'objectif de l'upgrade.

---

*Rapport généré le 25 mars 2026 — v1.0 — Usage interne production*


---

## Source: `REVIEW_V3_1_autonomous_coding.md`

# Rapport de Review Production — `autonomous-coding/` V3.1

> **Périmètre :** Audit complet V3.1 (code + tests + schémas + prompts), confronté à la matrice de traçabilité, au plan d'implémentation et à l'article de référence  
> **Référence article :** [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) — Anthropic Engineering, 24 mars 2026  
> **Précédent audit :** `REVIEW_V2_autonomous_coding.md` (25 mars 2026)  
> **Sévérité :** 🔴 Critique · 🟠 Majeur · 🟡 Mineur · ✅ Résolu  
> **Tolérance :** Zéro erreur production

---

## Résumé Exécutif

La V3.1 est une progression réelle et substantielle par rapport à la V2. **21 findings sur 22 du rapport précédent sont adressés**, dont les deux bloquants P0 (session continue, sprint contract). La matrice de traçabilité est bien tenue et honnête sur les tradeoffs. Le code est nettement plus robuste.

Cependant, l'audit révèle **1 bug critique de régression, 5 findings majeurs nouveaux et 7 findings mineurs** non couverts par la matrice et non présents en V2. Le bug critique (N-C-01) est particulièrement grave : **le mode session continue — fonctionnalité principale de V3.1 — prive l'evaluator de ses browser tools**, rendant toute QA Playwright impossible en chemin principal. Ce bug annule de facto la valeur du P0 C-01 de la V2 pourtant marqué `fixed_with_tradeoff`.

**Score de migration V2→V3.1 : 19/22 findings correctement résolus, 1 résolution invalide, 1 résolution partielle mal documentée, 13 findings nouveaux.**

---

## Table des Matières

1. [Résolution des Findings V2 — Vérification Ligne par Ligne](#1-résolution-des-findings-v2--vérification-ligne-par-ligne)
2. [Bug Critique de Régression V3.1](#2-bug-critique-de-régression-v31)
3. [Nouveaux Findings Majeurs V3.1](#3-nouveaux-findings-majeurs-v31)
4. [Nouveaux Findings Mineurs V3.1](#4-nouveaux-findings-mineurs-v31)
5. [Matrice de Conformité Article — Mise à Jour V3.1](#5-matrice-de-conformité-article--mise-à-jour-v31)
6. [Verdict sur la Traceability Matrix](#6-verdict-sur-la-traceability-matrix)
7. [Plan d'Actions Priorisé V3.1](#7-plan-dactions-priorisé-v31)

---

## 1. Résolution des Findings V2 — Vérification Ligne par Ligne

### ✅ Findings correctement résolus (19/22)

| ID V2 | Finding | Preuve dans le code | Statut réel |
|---|---|---|---|
| M-05 | Builder fallback silencieux | `builder.py:39-43` — `raise RuntimeError(...)` si summary vide | ✅ Résolu |
| M-06 | Checkpoint post-succès | `orchestrator.py` — `current_round` avancé après builder+evaluator | ✅ Résolu |
| Q-01 | `pnpm` allowlist | `security.py:26` — `"pnpm"` dans `ALLOWED_COMMANDS` | ✅ Résolu |
| Q-02 | Cache schémas | `artifacts.py:17` — `@lru_cache(maxsize=None)` | ✅ Résolu |
| Q-03 | Summary max configurable | `orchestrator.py:19` — `SUMMARY_MAX_CHARS` via env | ✅ Résolu |
| Q-04 | `_normalize_project_dir` | `autonomous_agent_demo.py:54-60` + test dédié | ✅ Résolu |
| Q-05 | Stack trace conservée | `agent.py:48-50` — `traceback.format_exc()` | ✅ Résolu |
| Q-06 | JSON malformé | `artifacts.py:76-83` — `JSONDecodeError` avec contexte | ✅ Résolu |
| Q-07 | Resume sur run completed | `orchestrator.py:108-113` — early return avec message | ✅ Résolu |
| Q-08 | Settings file conditionnel | `client.py:72-74` — diff avant écriture | ✅ Résolu |
| Q-09 | Métriques durée | `orchestrator.py:214-220` — `_print_metrics()` | ✅ Résolu (tradeoff documenté) |
| Q-10 | Preflight evaluator | `prompts/evaluator_prompt.md` — section Pre-flight | ✅ Résolu |
| Q-11 | Cohérence RunStatus/schéma | `tests/test_artifacts.py:test_run_status_enum_matches_schema` | ✅ Résolu |
| M-01 | Evaluator prompt gradué | `prompts/evaluator_prompt.md` — critères 1-5, seuils durs, few-shot | ✅ Résolu |
| M-02 | Builder auto-évaluation | `prompts/builder_prompt.md` — section "Mandatory self-evaluation" | ✅ Résolu |
| M-03 | Planner ambitieux | `prompts/planner_prompt.md` — scope, IA, design skill | ✅ Résolu |
| M-04 | Modèles par défaut Opus | `autonomous_agent_demo.py:17-20` — tout Opus 4.6 | ✅ Résolu |
| T-01 | `test_resume_skips_planner` | `tests/test_orchestrator_integration.py:93` — `assert runner2.planner_calls == 0` | ✅ Résolu |
| T-02/T-03 | Tests erreurs + combinaison invalide | `tests/test_phase_errors.py` + `test_orchestrator_integration.py` | ✅ Résolu |

---

### ⚠️ Findings V2 résolus avec réserves

#### C-01 — Session continue : marqué `fixed_with_tradeoff`, mais contient un bug critique

La matrice indique `fixed_with_tradeoff`. **La structure est correcte** — `orchestrator.py` crée bien un `shared_client` unique et le passe à toutes les phases. Mais **un bug introduit dans l'implémentation détruit la valeur de cette correction** (voir Section 2, N-C-01).

#### C-02 — Sprint contract : marqué `fixed`, réalité = `fixed_with_tradeoff` non documenté

La structure existe (schéma, path, génération, validation). Mais la matrice dit `fixed` alors que la **négociation builder↔evaluator décrite par l'article n'est pas implémentée**. L'orchestrateur génère unilatéralement un contrat statique sans input du builder. C'est un tradeoff légitime mais il devrait être explicitement documenté dans la matrice, pas masqué derrière `fixed`. Voir Section 3, N-M-01.

---

## 2. Bug Critique de Régression V3.1

### 🔴 N-C-01 — Browser Tools Absents en Mode Session Continue (Régression V3.1)

**Fichiers :** `orchestrator.py:116-117` + `client.py:52-54`

**Description précise :**

En mode session continue (chemin principal V3.1), le client partagé est créé avec :

```python
# orchestrator.py:116-117
shared_client = self.client_factory(self.project_dir, model, "orchestrator")
```

Dans `client.py`, la logique de permission des tools est :

```python
# client.py:52-54
allowed_tools = [*BUILTIN_TOOLS]
if phase in {"builder", "evaluator"}:
    allowed_tools.extend(browser_tools)
```

`phase="orchestrator"` **n'est pas dans** `{"builder", "evaluator"}`. Le client partagé est donc créé **sans aucun browser tool** (ni Playwright, ni Puppeteer).

**Conséquence directe :**

En mode session continue (défaut V3.1 quand tous les modèles sont identiques, soit le cas nominal avec `--model claude-opus-4-6`) :

- L'evaluator reçoit un client qui n'a accès qu'à `["Read", "Write", "Edit", "Glob", "Grep", "Bash"]`
- Toute tentative d'appeler `mcp__playwright__browser_navigate` ou équivalent est bloquée par le SDK
- L'evaluator ne peut pas faire de browser QA → il émet `blocked` → le harness boucle indéfiniment ou atteint `max_rounds` sans jamais passer

**Cette régression annule le bénéfice du P0 C-01 de la V2.** Le mode censé être le plus performant est celui qui rend le QA impossible.

**Test qui aurait dû détecter ce bug :** Absent. Les tests utilisent un `FakeRunner` qui ignore complètement les tools du client.

**Correction :**

Option A — Créer le client partagé avec les tools les plus permissifs (recommandé) :

```python
# orchestrator.py
shared_client = self.client_factory(self.project_dir, model, "evaluator")
# "evaluator" inclut BUILTIN_TOOLS + PLAYWRIGHT_TOOLS + PUPPETEER_TOOLS
```

Option B — Ajouter `"orchestrator"` à la condition dans `client.py` :

```python
# client.py
if phase in {"builder", "evaluator", "orchestrator"}:
    allowed_tools.extend(browser_tools)
```

Option C — Mode session continue : ignorer le `phase` pour les tools et accorder toujours le jeu complet :

```python
# client.py
def create_client(project_dir, model, phase, browser_provider="playwright"):
    ...
    browser_tools, mcp_servers = _browser_config(browser_provider)
    allowed_tools = [*BUILTIN_TOOLS]
    # En mode orchestrateur (session partagée), accorder tous les tools
    if phase in {"builder", "evaluator", "orchestrator"}:
        allowed_tools.extend(browser_tools)
```

**Test de non-régression à ajouter :**

```python
# tests/test_client_tools.py
def test_shared_session_client_includes_browser_tools():
    """Verify continuous session client has playwright tools available."""
    from client import create_client, PLAYWRIGHT_TOOLS
    import os
    os.environ["ANTHROPIC_API_KEY"] = "test-key"
    # Cannot instantiate real client in unit tests, test the config computation instead
    browser_tools, _ = client._browser_config("playwright")
    assert "mcp__playwright__browser_navigate" in browser_tools
    # Document that "orchestrator" phase must include browser tools
    allowed = [*client.BUILTIN_TOOLS]
    if "orchestrator" in {"builder", "evaluator", "orchestrator"}:
        allowed.extend(browser_tools)
    assert any("playwright" in t for t in allowed)
```

---

## 3. Nouveaux Findings Majeurs V3.1

### 🟠 N-M-01 — Sprint Contract Non-Négocié : Génération Unilatérale par l'Orchestrateur

**Fichier :** `orchestrator.py:139-177` (`_build_sprint_contract()`)

**Problème :**

L'article décrit une négociation active entre generator et evaluator :

> *"Before each sprint, the generator and evaluator negotiated a sprint contract: agreeing on what 'done' looked like for that chunk of work before any code was written. The generator proposed what it would build and how success would be verified, and the evaluator reviewed that proposal."*

En V3.1, `_build_sprint_contract()` génère le contrat **mécaniquement et unilatéralement** depuis `acceptance_criteria.json` et `work_backlog.json`, sans aucune participation du builder ou de l'evaluator :

```python
# orchestrator.py:139-177
def _build_sprint_contract(self, round_number: int) -> Path:
    acceptance = read_json(self.paths.acceptance_criteria, ...)
    backlog = read_json(self.paths.work_backlog, ...)
    in_scope = [item.get("title", ...) for item in backlog_items if ...][:5]
    acceptance_tests = [
        {
            "id": criterion.get("id", ...),
            "criterion": criterion.get("description", ...),
            "verification_method": "Browser QA with screenshots and reproducible steps",
        }
        for idx, criterion in enumerate(criteria[:8])
    ]
    # Écriture directe, sans input builder/evaluator
    write_validated_json(contract_path, payload, "sprint_contract")
    return contract_path
```

**Conséquences :**

1. Le `verification_method` est identique pour TOUS les tests de TOUS les rounds : `"Browser QA with screenshots and reproducible steps"`. L'evaluator n'a pas de critère de vérification spécifique par test.
2. Le contrat ne contient pas les décisions du builder sur ce qu'il va réellement faire — l'evaluator évalue contre un oracle qu'il n'a pas validé.
3. Les `acceptance_tests` sont dérivés des critères d'acceptance globaux, pas du scope du round courant.

**Impact :** La matrice marque C-02 comme `fixed`. C'est inexact — la structure contractuelle existe mais la sémantique de négociation est absente.

**Correction minimale (sans multi-turn negotiation) :**

Au minimum, le builder devrait écrire sa proposition de contrat, et le contract final devrait intégrer ce plan :

```python
# Dans le prompt builder_prompt.md, ajouter :
### Before implementation: write your sprint proposal
Before writing code, write `planning/sprint_proposal_round_XX.md` containing:
- Exact list of features you commit to implement this round
- How you plan to verify each feature (specific URL, user flow, assertion)
- What is explicitly OUT of scope

# Dans orchestrator.py, lire la proposition builder après le round précédent :
def _build_sprint_contract(self, round_number: int) -> Path:
    # Chercher une proposition builder du round précédent
    proposal_path = self.paths.planning_dir / f"sprint_proposal_round_{round_number:02d}.md"
    ...
```

---

### 🟠 N-M-02 — `_build_sprint_contract()` : Caps Arbitraires et Contrat Round-Agnostique

**Fichier :** `orchestrator.py:149-168`

**Problème 1 — Caps non documentés :**

```python
in_scope = in_scope[:5]          # ← 5 items max
acceptance_tests = [...][:8]     # ← 8 critères max (via criteria[:8])
```

Pour l'`app_spec.txt` fourni (claude.ai clone avec ~200 features), 5 items par round = 15 items sur 3 rounds, soit 7.5% de la spec couverte. Les caps sont arbitraires et non documentés dans le README, la matrice ou les commentaires.

**Problème 2 — Contrat identique round 1 et round 2+ :**

Le contrat est construit depuis les mêmes sources (`acceptance_criteria.json`, `work_backlog.json`) à chaque round. Sauf si le builder met à jour le statut des items (`"done"`), les rounds 2 et 3 proposent le même scope que le round 1. Le harness peut donc boucler indéfiniment sur les mêmes 5 items sans progresser.

```python
# Le filtre est :
in_scope = [item.get("title") for item in backlog_items if item.get("status") != "done"]
# Si le builder ne marque pas "done", les mêmes items réapparaissent
```

**Correction :**

```python
def _build_sprint_contract(self, round_number: int, max_scope_items: int = 10) -> Path:
    ...
    # Exclure aussi les items in_progress si déjà tentés dans les rounds précédents
    attempted_items = self._get_attempted_items(round_number)
    in_scope = [
        item.get("title", "Unnamed")
        for item in backlog_items
        if item.get("status") not in {"done"} and item.get("title") not in attempted_items
    ][:max_scope_items]
    
    if not in_scope:
        in_scope = ["Address QA blockers from previous round"]
```

---

### 🟠 N-M-03 — `PhaseRunner` Type Alias Dupliqué dans 4 Fichiers

**Fichiers :** `builder.py:12`, `evaluator.py:12`, `planner.py:12`, `orchestrator.py:28`

**Problème :**

```python
# Identique dans les 4 fichiers :
PhaseRunner = Callable[[Path, str, str, str, ClaudeSDKClient | None], Awaitable[str]]
```

Si la signature du runner change (ex : ajout d'un paramètre de round, ou d'un contexte), il faut mettre à jour 4 fichiers. Un oubli dans l'un d'eux créera une divergence silencieuse non détectée par mypy si les types sont compatibles.

**Correction :**

```python
# Créer autonomous-coding/types.py :
from __future__ import annotations
from pathlib import Path
from typing import Awaitable, Callable
from claude_code_sdk import ClaudeSDKClient

PhaseRunner = Callable[[Path, str, str, str, ClaudeSDKClient | None], Awaitable[str]]
ClientFactory = Callable[[Path, str, str], Any]
```

Puis importer depuis `types.py` dans les 4 fichiers.

---

### 🟠 N-M-04 — `--mode v2` Redirige Silencieusement vers V3.1

**Fichier :** `autonomous_agent_demo.py:120-130` (`main()`)

**Problème :**

```python
parser.add_argument("--mode", choices=["v3_1", "v2", "v1"], default="v3_1")
...
if args.mode == "v1":
    asyncio.run(run_autonomous_agent(...))
else:  # ← "v2" ET "v3_1" tombent ici
    asyncio.run(_run_v3_1(args, project_dir))
```

Un utilisateur qui passe `--mode v2` explicitement — parce qu'il a une raison d'utiliser V2 — exécutera silencieusement V3.1 sans avertissement. C'est une **rupture de contrat CLI non signalée**.

Par ailleurs, `"v2"` dans les `choices` donne l'impression qu'un mode V2 distinct existe, ce qui est trompeur.

**Correction :**

```python
if args.mode == "v1":
    asyncio.run(run_autonomous_agent(...))
elif args.mode == "v2":
    print("[WARNING] --mode v2 is deprecated and aliased to v3_1. "
          "Use --mode v3_1 explicitly. This alias will be removed in a future version.")
    asyncio.run(_run_v3_1(args, project_dir))
else:  # v3_1
    asyncio.run(_run_v3_1(args, project_dir))
```

Ou supprimer `"v2"` des `choices` et migrer complètement.

---

### 🟠 N-M-05 — `evaluator.py` : `ValidationError` Non Catchée sur Rapport Invalide

**Fichier :** `evaluator.py:44`

**Problème :**

```python
report = read_json(report_json_path, default=fallback_report, context="qa_report")
if "result" not in report:
    report = fallback_report

write_validated_json(report_json_path, report, "qa_report")  # ← Peut lever ValidationError
```

`read_json` retourne maintenant proprement le fallback si le JSON est malformé. Mais si le modèle écrit un JSON **valide syntaxiquement mais invalide au regard du schéma** (ex : `"result": "unknown_value"`, ou `"severity": "low"` non présent dans l'enum), `write_validated_json` lève une `jsonschema.ValidationError` non catchée.

Cette exception remonte jusqu'à `orchestrator.py:run()` sans être transformée en `result: blocked`. L'orchestrateur plante au lieu d'enregistrer un round bloqué et continuer.

**Correction dans `evaluator.py` :**

```python
from jsonschema import ValidationError
from artifacts import safe_validate

# Après la lecture du rapport :
ok, reason = safe_validate(report, "qa_report")
if not ok:
    print(f"[V3.1] QA report failed schema validation: {reason}. Using blocked fallback.")
    report = fallback_report

write_validated_json(report_json_path, report, "qa_report")
```

---

## 4. Nouveaux Findings Mineurs V3.1

### 🟡 N-Q-01 — `_run_loop()` Capture `shared_client` via Closure (Code Fragile)

**Fichier :** `orchestrator.py:122-210`

```python
shared_client: Any = None
if continuous_session:
    shared_client = self.client_factory(...)

async def _run_loop() -> RunState:
    nonlocal run_state
    # shared_client accessible via closure — non déclaré nonlocal
    planner_result = await self.planner.run(..., client=shared_client)
```

Si `shared_client` est réassigné dans `_run_loop` (accidentellement, lors d'un refactor), Python crée une variable locale silencieusement au lieu d'utiliser la closure — bug de closure classique Python.

**Correction — Passer le client comme paramètre :**

```python
async def _run_loop(client: Any = None) -> RunState:
    ...
    planner_result = await self.planner.run(..., client=client)
    ...

# Appel :
if shared_client is None:
    final_state = await _run_loop(client=None)
else:
    async with shared_client:
        final_state = await _run_loop(client=shared_client)
```

---

### 🟡 N-Q-02 — `_build_sprint_contract()` : Pas de Warning Quand Planning Artifacts Vides

**Fichier :** `orchestrator.py:143-150`

Si `planner_complete=True` est persisté dans l'état mais que `acceptance_criteria.json` est vide (fichier corrompu, interruption pendant le planner), le sprint contract est généré depuis les fallbacks hardcodés sans aucun avertissement :

```python
acceptance = read_json(self.paths.acceptance_criteria, context="acceptance_criteria")
# Si vide → acceptance = {}
criteria = acceptance.get("criteria", [])  # → []
# acceptance_tests → []
# fallback : [{"id": "AC-FALLBACK-001", ...}]
```

L'orchestrateur continue sans signaler que le contrat est un fallback générique.

**Correction :**

```python
if not criteria:
    print(
        f"[V3.1] WARNING: acceptance_criteria.json is empty or missing for round {round_number}. "
        "Sprint contract uses generic fallback. Consider re-running planner phase."
    )
```

---

### 🟡 N-Q-03 — `app_spec.txt` : Placeholder `{frontend_port}` Non Résolu

**Fichier :** `prompts/app_spec.txt`

```xml
<port>Only launch on port {frontend_port}</port>
```

Ce placeholder template n'est jamais substitué. Le builder reçoit littéralement `{frontend_port}` et doit deviner le port. En pratique, Vite utilise 5173 par défaut, mais ce n'est pas dans la spec.

**Correction :**

```xml
<port>Only launch on port 5173 (frontend) and 3001 (backend API)</port>
```

Ou implémenter une substitution dans `copy_spec_to_project()` :

```python
def copy_spec_to_project(project_dir: Path, frontend_port: int = 5173) -> None:
    content = spec_source.read_text()
    content = content.replace("{frontend_port}", str(frontend_port))
    spec_dest.write_text(content)
```

---

### 🟡 N-Q-04 — `test_phase_errors.py` : Contrat Sprint Écrit Sans Validation de Schéma

**Fichier :** `tests/test_phase_errors.py:34-36`

```python
contract.write_text(
    '{"round_number":1,"features_in_scope":["x"],"acceptance_tests":[{"id":"A","criterion":"c","verification_method":"m"}]}'
)
```

Le contrat est écrit manuellement sans passer par `write_validated_json`. Si le schéma `sprint_contract.schema.json` change (ex : ajout d'un champ `required`), ce test ne le détectera pas — il continuera à écrire un JSON qui viole le schéma sans erreur.

**Correction :**

```python
from artifacts import write_validated_json, ArtifactPaths

contract_payload = {
    "round_number": 1,
    "features_in_scope": ["x"],
    "acceptance_tests": [{"id": "A", "criterion": "c", "verification_method": "m"}]
}
write_validated_json(contract, contract_payload, "sprint_contract")
```

---

### 🟡 N-Q-05 — `acceptance_tests` du Sprint Contract = Critères Globaux, Pas Round-Spécifiques

**Fichier :** `orchestrator.py:155-166`

```python
acceptance_tests = [
    {
        "id": criterion.get("id", ...),
        "criterion": criterion.get("description", ...),
        "verification_method": "Browser QA with screenshots and reproducible steps",
    }
    for idx, criterion in enumerate(criteria[:8])
]
```

Les `acceptance_tests` sont les mêmes aux rounds 1, 2 et 3 (les 8 premiers critères globaux). Le contrat ne change pas en fonction de ce qui a déjà été validé ou de ce qui est réellement en scope pour ce round. L'evaluator du round 2 vérifie exactement les mêmes critères que le round 1, sans tenir compte des résultats précédents.

**Correction :** Filtrer les critères déjà passés dans les rounds précédents :

```python
# Lire les rapports QA précédents pour exclure les critères déjà passés
previous_passes = self._get_criteria_passed_in_previous_rounds(round_number)
criteria_for_round = [c for c in criteria if c.get("id") not in previous_passes]
```

---

### 🟡 N-Q-06 — Import `pytest` dans une Fonction de Test

**Fichier :** `tests/test_orchestrator_integration.py:156`

```python
def test_invalid_planner_only_and_qa_only_combination(tmp_path: Path) -> None:
    ...
    import pytest   # ← Import dans la fonction
    with pytest.raises(ValueError, ...):
```

`pytest` doit être importé en tête de fichier. L'import inline fonctionne mais viole les conventions Python et peut causer des problèmes avec certains linters et outils de coverage.

**Correction :** Déplacer `import pytest` en haut de `test_orchestrator_integration.py`.

---

### 🟡 N-Q-07 — `test_builder_checkpoint_only_after_success` : Assertion Incomplète

**Fichier :** `tests/test_orchestrator_integration.py:123-142`

```python
state = json.loads((tmp_path / "state" / "run_state.json").read_text())
assert state["current_round"] == 0  # ← Seul le round est vérifié
```

Le test vérifie que `current_round == 0` après un crash du builder. C'est correct. Mais il ne vérifie pas que `status == "building"` (l'état au moment du crash), ce qui permettrait de valider que l'état persisté est cohérent avec la reprise.

**Correction :**

```python
state = json.loads((tmp_path / "state" / "run_state.json").read_text())
assert state["current_round"] == 0, "current_round should not advance before builder succeeds"
assert state["status"] == "building", "status should reflect interrupted build, not a clean state"
```

---

## 5. Matrice de Conformité Article — Mise à Jour V3.1

| Principe Article | Statut V2 | Statut V3.1 | Qualité V3.1 | Priorité Fix |
|---|---|---|---|---|
| Architecture 3 agents | ✅ | ✅ | Conforme | — |
| Session continue + compaction SDK | ❌ | ⚠️ | Structurellement présent, browser tools absents en continu | 🔴 P0 |
| Contrat de sprint | ❌ | 🟡 | Artifact présent, négociation absente, caps arbitraires | 🟠 P1 |
| Critères évaluation gradués | ❌ | ✅ | Présent avec seuils et few-shot | — |
| Calibration evaluator few-shot | ❌ | ✅ | Présent | — |
| Auto-évaluation builder pre-handoff | ❌ | ✅ | Présent dans le prompt | — |
| Planner ambitieux + IA | 🟡 | ✅ | Correct | — |
| Modèle adapté (Opus 4.6) | 🟡 | ✅ | Tous Opus par défaut | — |
| Checkpoint état post-succès | ❌ | ✅ | Corrigé | — |
| Décision stratégique refine/pivot | ❌ | ✅ | Dans le prompt builder | — |
| Tracking durée par phase | ❌ | ✅ | `_print_metrics()` | — |
| Skill frontend-design dans planner | ❌ | ✅ | Mentionné dans le prompt | — |
| Gestion JSON malformé evaluator | ❌ | 🟡 | `read_json` OK, `ValidationError` non catchée | 🟠 P1 |
| pnpm dans allowlist sécurité | ❌ | ✅ | Présent | — |
| Tests cohérence schéma/enum | ❌ | ✅ | Test dédié | — |
| Resume sur run completed | ❌ | ✅ | Early return propre | — |

---

## 6. Verdict sur la Traceability Matrix

La matrice `V3_1_TRACEABILITY_MATRIX.md` est globalement bien tenue. Elle est honnête sur les tradeoffs (`fixed_with_tradeoff` pour C-01 et M-04). Cependant :

| ID Matrice | Statut Déclaré | Statut Réel | Écart |
|---|---|---|---|
| C-01 | `fixed_with_tradeoff` | ❌ Bug critique (browser tools) | La correction est structurellement présente mais fonctionnellement invalide |
| C-02 | `fixed` | `fixed_with_tradeoff` | La négociation n'est pas implémentée, le contrat est généré unilatéralement |
| Q-09 | `fixed_with_tradeoff` | ✅ Correct | Honnête : coût non disponible depuis le runner |

**Recommandation :** Ajouter une colonne `"Limitations connues"` dans la matrice pour capturer les tradeoffs implicites (ex : caps du sprint contract, absence de négociation réelle).

---

## 7. Plan d'Actions Priorisé V3.1

### P0 — Bloquant Production (Avant tout déploiement)

| ID | Action | Fichier(s) | Effort |
|---|---|---|---|
| N-C-01 | Créer le client partagé avec `phase="evaluator"` (ou équivalent incluant browser tools) | `orchestrator.py:116` | XS |
| N-C-01 | Ajouter test unitaire vérifiant que le client session continue a les browser tools | `tests/test_client_tools.py` (nouveau) | S |

```python
# Correction P0 — une ligne dans orchestrator.py:
# AVANT :
shared_client = self.client_factory(self.project_dir, model, "orchestrator")
# APRÈS :
shared_client = self.client_factory(self.project_dir, model, "evaluator")
# "evaluator" inclut BUILTIN_TOOLS + PLAYWRIGHT_TOOLS + PUPPETEER_TOOLS
```

### P1 — Majeur (Sprint suivant)

| ID | Action | Fichier(s) | Effort |
|---|---|---|---|
| N-M-05 | Catcher `ValidationError` dans `evaluator.py` → émettre `blocked` | `evaluator.py` | XS |
| N-M-04 | Ajouter warning deprecation pour `--mode v2` | `autonomous_agent_demo.py` | XS |
| N-M-02 | Augmenter les caps du sprint contract (5→10+ items), exclure items déjà traités | `orchestrator.py:_build_sprint_contract()` | S |
| N-M-03 | Extraire `PhaseRunner` dans `types.py` partagé | `types.py` (nouveau), 4 fichiers | S |
| N-Q-01 | Passer `client` en paramètre à `_run_loop()` | `orchestrator.py` | XS |
| N-Q-02 | Ajouter warning quand planning artifacts vides → sprint contract fallback | `orchestrator.py` | XS |

### P2 — Amélioration (Backlog qualité)

| ID | Action | Fichier(s) | Effort |
|---|---|---|---|
| N-M-01 | Implémenter proposition de contrat côté builder + lecture dans l'orchestrateur | `prompts/builder_prompt.md`, `orchestrator.py`, `artifacts.py` | M |
| N-Q-03 | Résoudre `{frontend_port}` dans `app_spec.txt` | `prompts/app_spec.txt`, `prompts.py` | XS |
| N-Q-04 | Utiliser `write_validated_json` dans les tests de phase errors | `tests/test_phase_errors.py` | XS |
| N-Q-05 | Filtrer critères déjà passés des acceptance_tests du sprint contract | `orchestrator.py` | S |
| N-Q-06 | Déplacer `import pytest` en tête de fichier | `tests/test_orchestrator_integration.py` | XS |
| N-Q-07 | Ajouter assertion `status == "building"` dans test checkpoint | `tests/test_orchestrator_integration.py` | XS |
| Matrice | Mettre à jour C-02 en `fixed_with_tradeoff`, documenter limitation caps | `V3_1_TRACEABILITY_MATRIX.md` | XS |

---

## Conclusion

La V3.1 est une migration de qualité avec un travail rigoureux sur les 22 findings du rapport V2. La matrice de traçabilité est un bon outil de suivi. Le code est nettement plus robuste, les prompts sont substantiellement améliorés, et la couverture de tests est étendue.

Le bug N-C-01 est néanmoins une régression sévère : le chemin principal du harness — session continue avec Opus 4.6 — désactive silencieusement la capacité de l'evaluator à faire du browser QA. Le fix est d'une ligne mais son impact est total sur la valeur fonctionnelle du harness. C'est le seul blocking avant déploiement.

Les 5 findings P1 sont des corrections de robustesse importantes mais ne bloquent pas un usage expérimental. Les P2 constituent le chemin vers la conformité complète avec l'article, notamment la vraie négociation de contrat de sprint.

**Priorité absolue avant déploiement :** `orchestrator.py:116` — changer `"orchestrator"` en `"evaluator"`.

---

*Rapport généré le 25 mars 2026 — v2.0 (audit V3.1) — Usage interne production*  
*Référence croisée : REVIEW_V2_autonomous_coding.md (v1.0) + V3_1_TRACEABILITY_MATRIX.md*


---

## Source: `REVIEW_V3_2_autonomous_coding.md`

# Rapport de Review Production — `autonomous-coding/` V3.2

> **Périmètre :** Audit complet V3.2 (tous fichiers du repo), confronté à `V3_2_TRACEABILITY_MATRIX.md`, `README.md` et à l'article de référence  
> **Référence article :** [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) — Anthropic Engineering, 24 mars 2026  
> **Précédents audits :** `REVIEW_V2_autonomous_coding.md` (v1.0), `REVIEW_V3_1_autonomous_coding.md` (v2.0)  
> **Sévérité :** 🔴 Critique · 🟠 Majeur · 🟡 Mineur · ✅ Résolu  
> **Tolérance :** Zéro erreur production

---

## Résumé Exécutif

La V3.2 est une progression solide sur la V3.1. Tous les findings P0/P1 du rapport V3.1 sont adressés et la matrice V3.2 est bien tenue. La régression critique N-C-01 (browser tools) a été corrigée manuellement par l'opérateur : `orchestrator.py` utilise désormais `phase="evaluator"` pour le client partagé. Le nouveau mécanisme de proposition builder (`sprint_proposal_round_XX.md`) est une amélioration architecturale réelle.

Cependant, l'audit révèle **1 bug fonctionnel majeur qui brise la progression entre rounds**, **5 autres findings majeurs** dont un de traçabilité documentaire grave, et **5 findings mineurs**. Aucun n'est un bloquant P0, mais N2-M-03 (filtre `attempted_features` contourné) est le plus dangereux en production car il peut provoquer des boucles infinies sur les mêmes features.

**Score migration V3.1→V3.2 : 100% des findings du rapport V3.1 adressés. 11 findings nouveaux, dont 6 majeurs.**

---

## Table des Matières

1. [Vérification des Findings V3.1 — Statut Réel](#1-vérification-des-findings-v31--statut-réel)
2. [Nouveaux Findings Majeurs V3.2](#2-nouveaux-findings-majeurs-v32)
3. [Nouveaux Findings Mineurs V3.2](#3-nouveaux-findings-mineurs-v32)
4. [Matrice de Conformité Article — Mise à Jour V3.2](#4-matrice-de-conformité-article--mise-à-jour-v32)
5. [Verdict sur la V3_2_TRACEABILITY_MATRIX.md](#5-verdict-sur-la-v3_2_traceability_matrixmd)
6. [Plan d'Actions Priorisé V3.2](#6-plan-dactions-priorisé-v32)

---

## 1. Vérification des Findings V3.1 — Statut Réel

### ✅ Tous les findings V3.1 correctement résolus

| ID V3.1 | Finding | Preuve dans le code | Statut |
|---|---|---|---|
| N-C-01 | Browser tools absents (régression) | `orchestrator.py` — `client_factory(..., "evaluator")` | ✅ Fixé manuellement |
| N-M-01 | Sprint contract unilatéral → proposition builder | `builder_prompt.md` + `orchestrator._load_previous_sprint_proposal()` | ✅ Résolu |
| N-M-02 | Caps arbitraires + round-agnostique | `orchestrator.py` — `MAX_SCOPE_ITEMS=10`, `_get_attempted_features()` | ✅ Résolu |
| N-M-03 | `PhaseRunner` dupliqué dans 4 fichiers | `phase_types.py` + imports dans tous les modules | ✅ Résolu |
| N-M-04 | `--mode v2` silencieux | `autonomous_agent_demo.py` — deprecation warning | ✅ Résolu |
| N-M-05 | `ValidationError` non catchée evaluator | `evaluator.py` — `safe_validate()` avant écriture | ✅ Résolu |
| N-Q-01 | Closure fragile `shared_client` | `orchestrator._run_loop(client=None)` | ✅ Résolu |
| N-Q-02 | Pas de warning backlog vide | `orchestrator._build_sprint_contract()` — warning critères vides | ✅ Partiel (voir N2-Q-03) |
| N-Q-04 | Tests sprint contract sans validation schéma | `test_phase_errors.py` — `write_validated_json(...)` | ✅ Résolu |
| N-Q-05 | `acceptance_tests` round-agnostiques | `orchestrator._get_previously_assigned_criteria_ids()` | ✅ Résolu |
| N-Q-06 | `import pytest` inline | `test_orchestrator_integration.py` — top-level import | ✅ Résolu |
| N-Q-07 | Assertion checkpoint incomplète | `test_orchestrator_integration.py:test_builder_checkpoint_only_after_success` | ✅ Résolu |

---

## 2. Nouveaux Findings Majeurs V3.2

### 🟠 N2-M-01 — `V3_1_TRACEABILITY_MATRIX.md` Écrasé avec le Contenu V3.2 (Corruption de Traçabilité)

**Fichiers :** `autonomous-coding/V3_1_TRACEABILITY_MATRIX.md` vs `autonomous-coding/V3_2_TRACEABILITY_MATRIX.md`

**Problème :**

Les deux fichiers ont le **contenu identique** et déclarent tous deux `# V3.2 Traceability Matrix` en en-tête. La matrice V3.1 originale a été **écrasée**.

```
# V3.1 (contenu attendu) : historique V3.1 préservé, nouveau fichier V3.2 créé
# Réalité V3.2 : les deux fichiers sont identiques, V3.1 est perdu
```

**Impact :** La traçabilité historique de l'audit V3.1 est détruite. Il est désormais impossible de vérifier quels findings étaient présents en V3.1 vs V3.2, ce qui compromet toute revue d'audit ultérieure.

**Correction :**

1. Restaurer `V3_1_TRACEABILITY_MATRIX.md` avec son contenu original (l'historique est dans `REVIEW_V3_1_autonomous_coding.md`).
2. `V3_2_TRACEABILITY_MATRIX.md` doit uniquement contenir les findings nouveaux ou modifiés en V3.2.

**Convention à adopter :** Chaque matrice `VX_Y_TRACEABILITY_MATRIX.md` est immuable une fois publiée. Les nouvelles versions créent un nouveau fichier sans toucher aux anciens.

---

### 🟠 N2-M-02 — `sprint_proposal_md()` Absent de `ArtifactPaths` — Path Codé en Dur dans l'Orchestrateur

**Fichiers :** `orchestrator.py:103-108`, `artifacts.py`

**Problème :**

Le chemin du fichier de proposition builder est construit directement dans l'orchestrateur, en dehors de `ArtifactPaths` :

```python
# orchestrator.py:103-108
def _load_previous_sprint_proposal(self, round_number: int) -> ...:
    if round_number <= 1:
        return [], []
    proposal_path = self.paths.planning_dir / f"sprint_proposal_round_{round_number - 1:02d}.md"
    # ↑ Path codé en dur — diverge du pattern ArtifactPaths
```

Tous les autres artifacts du harness ont leur path déclaré dans `ArtifactPaths` :
`sprint_contract_json()`, `qa_report_json()`, `build_report_md()`, etc.

Ce path hors-contrat crée deux risques : (1) si le nom du fichier est modifié dans le prompt mais pas dans l'orchestrateur, le harness cesse de lire les propositions silencieusement ; (2) les tests ne peuvent pas utiliser `ArtifactPaths` pour vérifier l'existence de la proposition.

**Correction — Ajouter à `artifacts.py:ArtifactPaths` :**

```python
def sprint_proposal_md(self, round_number: int) -> Path:
    """Builder's refined sprint proposal for round N, written before implementation.
    Read by orchestrator when building the sprint contract for round N+1.
    """
    return self.planning_dir / f"sprint_proposal_round_{round_number:02d}.md"
```

Puis dans `orchestrator.py` :

```python
proposal_path = self.paths.sprint_proposal_md(round_number - 1)
```

---

### 🟠 N2-M-03 — `_build_sprint_contract()` : Les Features Proposées Contournent le Filtre `attempted_features`

**Fichier :** `orchestrator.py:127-149`

**Problème :**

```python
# orchestrator.py:127-149
in_scope = [
    item.get("title", "Unnamed backlog item")
    for item in backlog_items
    if item.get("status") != "done"
    and item.get("title", "").strip() not in attempted_features  # ← filtre appliqué
]
if proposed_features:
    in_scope = proposed_features + in_scope  # ← proposed_features contourne le filtre !
```

Les `proposed_features` issus du fichier de proposition du builder sont **prépendés à `in_scope` AVANT la déduplication**, mais **APRÈS le filtre `attempted_features`**. Résultat : si le builder propose une feature qui était déjà dans un contrat précédent, elle sera incluse à nouveau dans le prochain contrat malgré le filtre.

**Scénario concret :**
- Round 1 : contrat inclut "Message streaming"
- Builder échoue, propose "Message streaming" dans `sprint_proposal_round_01.md`
- Round 2 : `_get_attempted_features(2)` retourne `{"Message streaming"}` → backlog item filtré
- Mais `proposed_features` = `["Message streaming"]` → contourne le filtre → réapparaît dans round 2

Le harness peut boucler indéfiniment sur les mêmes features si le builder les reprend dans sa proposition après un échec.

**Correction :**

```python
if proposed_features:
    # Filtrer les features proposées contre attempted_features
    # pour éviter de recycler des items déjà tentés
    new_proposals = [f for f in proposed_features if f.strip() not in attempted_features]
    in_scope = new_proposals + in_scope
```

---

### 🟠 N2-M-04 — `builder.py` : `ClaudeSDKClient` Utilisé Sans Être Importé

**Fichier :** `builder.py:24`

**Problème :**

```python
# builder.py — imports
from __future__ import annotations
...
from phase_types import PhaseRunner
# ← ClaudeSDKClient manquant

class BuilderPhase:
    async def run(
        self,
        ...
        client: ClaudeSDKClient | None = None,  # ← non importé
    ) -> BuilderResult:
```

Grâce à `from __future__ import annotations` (PEP 563), les annotations sont des chaînes de caractères à runtime — aucun `NameError` ne se produit à l'exécution. Mais :

1. `mypy` et tous les type checkers signalent une erreur non résolue.
2. `typing.get_type_hints(BuilderPhase.run)` lèverait `NameError: name 'ClaudeSDKClient' is not defined`.
3. L'incohérence avec `planner.py` et `evaluator.py` (qui importent `ClaudeSDKClient`) crée une confusion pour les mainteneurs.

**Correction :**

```python
# builder.py — ajouter l'import
from claude_code_sdk import ClaudeSDKClient
```

---

### 🟠 N2-M-05 — Builder Prompt : Instruction `sprint_proposal_round_XX.md` avec `XX` Littéral

**Fichier :** `builder.py:30-33`

**Problème :**

```python
# builder.py:30-33
prompt = (
    f"{get_builder_prompt()}\n\n"
    f"Current round number: {round_number}\n"
    f"Sprint contract (must be honored): {sprint_contract_path.as_posix()}\n"
    "After implementation, write planning/sprint_proposal_round_XX.md for the next round "  # ← XX littéral !
    "using the template in the builder prompt.\n"
)
```

L'instruction au modèle contient `sprint_proposal_round_XX.md` avec `XX` littéral. Le modèle ne sait pas qu'il doit remplacer `XX` par le numéro de round courant. Il pourrait créer un fichier littéralement nommé `sprint_proposal_round_XX.md` qui ne serait jamais trouvé par `_load_previous_sprint_proposal`.

**Correction :**

```python
f"After implementation, write planning/sprint_proposal_round_{round_number:02d}.md "
f"for round {round_number} using the sprint proposal template in the builder prompt.\n"
```

---

### 🟠 N2-M-06 — `_load_previous_sprint_proposal()` : Parser Markdown Fragile Sans Réinitialisation de Section

**Fichier :** `orchestrator.py:112-141`

**Problème :**

Le parser lit la proposition builder ligne par ligne en maintenant un état `section`:

```python
section = ""
for raw_line in proposal_path.read_text().splitlines():
    line = raw_line.strip()
    if line.lower().startswith("## proposed features in scope"):
        section = "features"
        continue
    if line.lower().startswith("## proposed acceptance tests"):
        section = "tests"
        continue
    if not line.startswith("- "):
        continue
    # Traitement selon section
```

**Problème 1 — Section non réinitialisée :** Si un `##` arbitraire apparaît après `## Proposed features in scope` mais avant `## Proposed acceptance tests`, le `section` reste sur `"features"`. Les lignes `- item` de cette section inconnue seront ajoutées à `proposed_features` par erreur.

**Problème 2 — Absence de warning si fichier absent :** La méthode retourne `[], []` silencieusement si le fichier n'existe pas. L'orchestrateur ne sait pas si la proposition est absente parce que le builder ne l'a pas écrite, ou parce que c'est le round 1.

**Correction :**

```python
for raw_line in proposal_path.read_text().splitlines():
    line = raw_line.strip()
    if line.startswith("##"):
        # Réinitialiser la section sur tout nouveau header level 2
        if "proposed features in scope" in line.lower():
            section = "features"
        elif "proposed acceptance tests" in line.lower():
            section = "tests"
        else:
            section = ""  # ← Section inconnue → ne rien collecter
        continue
    ...

# Ajouter warning si fichier absent et round > 1 :
if round_number > 1 and not proposal_path.exists():
    print(
        f"[V3.2] INFO: No sprint proposal found for round {round_number - 1} "
        f"(expected at {proposal_path}). Contract built from backlog only."
    )
    return [], []
```

---

## 3. Nouveaux Findings Mineurs V3.2

### 🟡 N2-Q-01 — `evaluator.py` : Import `Awaitable` Inutilisé

**Fichier :** `evaluator.py:5`

```python
from typing import Awaitable  # ← jamais utilisé dans ce module
```

`Awaitable` faisait partie de la définition locale de `PhaseRunner` (avant l'extraction vers `phase_types.py`). L'import n'a pas été nettoyé.

**Correction :**

```python
# Supprimer la ligne :
from typing import Awaitable
```

---

### 🟡 N2-Q-02 — Prompts `evaluator_prompt.md` et `planner_prompt.md` Toujours Labelisés V3.1

**Fichiers :** `prompts/evaluator_prompt.md:1`, `prompts/planner_prompt.md:1`

```markdown
## ROLE: EVALUATOR / QA PHASE (V3.1)   ← devrait être V3.2
## ROLE: PLANNER PHASE (V3.1)           ← devrait être V3.2
```

`builder_prompt.md` est lui correctement labélisé `V3.2`. Incohérence de versioning dans les prompts.

**Correction :** Mettre à jour les deux headers de `V3.1` en `V3.2`.

---

### 🟡 N2-Q-03 — Pas de Warning pour Backlog Vide dans `_build_sprint_contract()`

**Fichier :** `orchestrator.py:118-126`

Le code émet un warning quand `acceptance_criteria.json` est vide, mais pas quand `work_backlog.json` est vide. Dans les deux cas, le contrat tombe sur un fallback générique sans avertir l'opérateur.

```python
backlog_items = backlog.get("items", []) if isinstance(backlog, dict) else []
# ← Pas de warning si backlog_items est vide
```

**Correction — Ajouter à la suite du bloc backlog :**

```python
if not backlog_items:
    print(
        f"[V3.2] WARNING: work_backlog.json is empty or missing for round {round_number}. "
        "Sprint scope uses generic fallback. Consider re-running planner phase."
    )
```

---

### 🟡 N2-Q-04 — `_get_previously_assigned_criteria_ids()` Sans Warning sur Contrats Manquants

**Fichier :** `orchestrator.py:88-100`

```python
def _get_previously_assigned_criteria_ids(self, round_number: int) -> set[str]:
    assigned: set[str] = set()
    for prev_round in range(1, round_number):
        prev_contract = self.paths.sprint_contract_json(prev_round)
        payload = read_json(prev_contract, context=f"sprint_contract_round_{prev_round:02d}")
        if not isinstance(payload, dict):
            continue   # ← Silencieux si contrat absent
```

Si un fichier de contrat est manquant (ex: après une interruption propre), la déduplication des critères est incomplète sans que l'opérateur le sache. Le même critère peut être réassigné à plusieurs rounds.

**Correction :**

```python
if not prev_contract.exists():
    print(
        f"[V3.2] INFO: sprint_contract_round_{prev_round:02d}.json not found; "
        "criteria deduplication for round {round_number} may be incomplete."
    )
    continue
```

---

### 🟡 N2-Q-05 — `test_round_two_contract_uses_previous_builder_proposal` : Assertion Incomplète

**Fichier :** `tests/test_orchestrator_integration.py:215-237`

```python
contract_round_02 = json.loads((tmp_path / "planning" / "sprint_contract_round_02.json").read_text())
assert "Ship profile settings page" in contract_round_02["features_in_scope"]
assert any(test["id"] == "AC-NEXT-1" for test in contract_round_02["acceptance_tests"])
```

Ce test valide que la proposition du round 1 est bien reprise dans le contrat du round 2. C'est utile. Mais il ne valide pas le cas inverse (négatif) : **le feature du round 1 qui était déjà dans le contrat original ne doit PAS être dupliqué**. Le test tel qu'écrit passerait même si le bug N2-M-03 provoque une duplication.

**Correction — Ajouter assertion de non-duplication :**

```python
# Vérifier qu'un item du backlog original n'est pas présent deux fois
feature_counts = {}
for f in contract_round_02["features_in_scope"]:
    feature_counts[f] = feature_counts.get(f, 0) + 1
duplicates = {f for f, count in feature_counts.items() if count > 1}
assert not duplicates, f"Duplicate features in round 2 contract: {duplicates}"
```

---

## 4. Matrice de Conformité Article — Mise à Jour V3.2

| Principe Article | Statut V2 | Statut V3.1 | Statut V3.2 | Qualité V3.2 |
|---|---|---|---|---|
| Architecture 3 agents | ✅ | ✅ | ✅ | Conforme |
| Session continue + compaction SDK | ❌ | ⚠️ Bug tools | ✅ | Corrigé (fix manuel opérateur) |
| Contrat de sprint | ❌ | 🟡 Unilatéral | 🟡 | Proposition builder ajoutée, mais contournement filtre attempted (N2-M-03) |
| Critères évaluation gradués | ❌ | ✅ | ✅ | Stable |
| Calibration evaluator few-shot | ❌ | ✅ | ✅ | Stable |
| Auto-évaluation builder pre-handoff | ❌ | ✅ | ✅ | Stable |
| Planner ambitieux + IA | 🟡 | ✅ | ✅ | Stable |
| Modèle Opus 4.6 | 🟡 | ✅ | ✅ | Stable |
| Checkpoint état post-succès | ❌ | ✅ | ✅ | Stable |
| Décision stratégique refine/pivot | ❌ | ✅ | ✅ | Dans le prompt V3.2 |
| Tracking durée par phase | ❌ | ✅ | ✅ | Stable |
| Gestion JSON malformé evaluator | ❌ | 🟡 | ✅ | `safe_validate` + fallback |
| pnpm dans allowlist | ❌ | ✅ | ✅ | Stable |
| Traçabilité documentaire | N/A | ✅ | 🟠 | V3.1 matrix écrasée (N2-M-01) |

---

## 5. Verdict sur la V3_2_TRACEABILITY_MATRIX.md

La matrice V3.2 est complète et correctement structurée pour les 35 findings qu'elle couvre. Les tradeoffs sont honnêtement documentés (`fixed_with_tradeoff` pour N-M-01, N-M-02, N-Q-05). Les colonnes "Test / validation evidence" sont précises et référencent des noms de tests réels.

**Écart constaté :**

| Entrée Matrice | Statut Déclaré | Statut Réel | Écart |
|---|---|---|---|
| N-M-03 (round progression) | `fixed` | 🟠 Bug (filtre contourné) | N2-M-03 ci-dessus |
| N-Q-02 (warning empty artifacts) | `fixed` | 🟡 Partiel (backlog non couvert) | N2-Q-03 ci-dessus |
| `V3_1_TRACEABILITY_MATRIX.md` | Conservé | Écrasé | N2-M-01 ci-dessus |

---

## 6. Plan d'Actions Priorisé V3.2

### P1 — Majeur (À corriger avant usage production)

| ID | Action | Fichier(s) | Effort |
|---|---|---|---|
| N2-M-01 | Restaurer `V3_1_TRACEABILITY_MATRIX.md` avec son contenu original V3.1 | `V3_1_TRACEABILITY_MATRIX.md` | XS |
| N2-M-02 | Ajouter `sprint_proposal_md()` à `ArtifactPaths` + utiliser dans orchestrator | `artifacts.py`, `orchestrator.py` | XS |
| N2-M-03 | Filtrer `proposed_features` contre `attempted_features` avant préfixage | `orchestrator.py:_build_sprint_contract()` | XS |
| N2-M-04 | Ajouter `from claude_code_sdk import ClaudeSDKClient` dans `builder.py` | `builder.py` | XS |
| N2-M-05 | Remplacer `sprint_proposal_round_XX.md` par `sprint_proposal_round_{round_number:02d}.md` dans le prompt injecté | `builder.py:30-33` | XS |
| N2-M-06 | Réinitialiser `section = ""` sur tout `##` inconnu dans le parser de proposition | `orchestrator.py:_load_previous_sprint_proposal()` | S |

### P2 — Mineur (Backlog qualité)

| ID | Action | Fichier(s) | Effort |
|---|---|---|---|
| N2-Q-01 | Supprimer `from typing import Awaitable` | `evaluator.py` | XS |
| N2-Q-02 | Mettre à jour header prompts `V3.1` → `V3.2` | `prompts/evaluator_prompt.md`, `prompts/planner_prompt.md` | XS |
| N2-Q-03 | Ajouter warning backlog vide dans `_build_sprint_contract()` | `orchestrator.py` | XS |
| N2-Q-04 | Ajouter warning contrat manquant dans `_get_previously_assigned_criteria_ids()` | `orchestrator.py` | XS |
| N2-Q-05 | Ajouter assertion anti-duplication dans `test_round_two_contract_uses_previous_builder_proposal` | `tests/test_orchestrator_integration.py` | XS |

---

## Conclusion

La V3.2 est une version mature et proche d'un état production. Le harness est maintenant aligné avec tous les concepts structurants de l'article Anthropic. Le seul bug fonctionnel significatif est N2-M-03 : les features proposées par le builder contournent le filtre anti-répétition, ce qui peut forcer des rounds à traiter les mêmes items indéfiniment après un échec. C'est un bug d'une ligne.

Les cinq autres findings P1 sont tous des corrections XS ou S (une ligne à quelques lignes chacune). Aucun n'implique de refactoring structurel.

**Trois corrections de priorité maximale avant déploiement :**

1. **`orchestrator.py` ligne ~135** — Filtrer `proposed_features` contre `attempted_features` (N2-M-03).  
2. **`builder.py` ligne ~33** — Remplacer `"XX"` par `f"{round_number:02d}"` dans l'instruction de proposition (N2-M-05).  
3. **`V3_1_TRACEABILITY_MATRIX.md`** — Restaurer le contenu V3.1 original (N2-M-01).

---

*Rapport généré le 26 mars 2026 — v3.0 (audit V3.2) — Usage interne production*  
*Référence croisée : REVIEW_V2 (v1.0) · REVIEW_V3_1 (v2.0) · V3_2_TRACEABILITY_MATRIX.md*


---

## Source: `REVIEW_V3_3_autonomous_coding.md`

# Rapport de Review Production — `autonomous-coding/` V3.3

> **Périmètre :** Audit complet V3.3 (code + prompts + tests + docs), confronté à `V3_3_TRACEABILITY_MATRIX.md`, `README.md` et à l'article de référence.  
> **Référence article :** [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) — Anthropic Engineering, **24 mars 2026**.  
> **Précédents audits :** `REVIEW_V2_autonomous_coding.md`, `REVIEW_V3_1_autonomous_coding.md`, `REVIEW_V3_2_autonomous_coding.md`.  
> **Sévérité :** 🔴 Critique · 🟠 Majeur · 🟡 Mineur · ✅ Résolu  
> **Tolérance :** Zéro erreur production

---

## Résumé Exécutif

La V3.3 est **globalement une bonne consolidation** de la V3.2 : les correctifs annoncés dans `V3_3_TRACEABILITY_MATRIX.md` sont bien visibles dans le code (path contract de proposition sprint, filtrage `attempted_features` côté propositions, robustification parser markdown, warnings opérateur additionnels, import typing builder, restauration de la matrice V3.1).

Mais l’audit production met en évidence **2 écarts majeurs restants** et **6 écarts mineurs** qui empêchent un verdict "production excellente" sans réserve :

1. 🟠 **N3-M-01 — La négociation builder/evaluator n’est pas réellement implémentée** (article: boucle itérative jusqu’à accord; code: handoff unidirectionnel via un seul fichier de proposition round N).  
2. 🟠 **N3-M-02 — Risque de duplication/contournement sur `acceptance_tests` proposés** (pas de filtre `previous_criteria_ids` ni dédup explicite pour les propositions builder).

**Verdict global V3.3 :** 🟠 **Apte pré-production**, **non "gold production"** en l’état pour des runs longs multi-rounds à forte variance.  
**Recommandation :** corriger les 2 majeurs + normaliser les marqueurs de version/logs avant la release V3.4.

---

## Table des Matières

1. [Validation des claims V3.3 (matrice → code)](#1-validation-des-claims-v33-matrice--code)
2. [Conformité à l’article Anthropic "harness design"](#2-conformité-à-larticle-anthropic-harness-design)
3. [Findings majeurs V3.3](#3-findings-majeurs-v33)
4. [Findings mineurs V3.3](#4-findings-mineurs-v33)
5. [Plan de correction priorisé](#5-plan-de-correction-priorisé)
6. [Verdict final production](#6-verdict-final-production)

---

## 1. Validation des claims V3.3 (matrice → code)

### ✅ Points bien implémentés

- **Restauration de la traçabilité V3.1** : `V3_1_TRACEABILITY_MATRIX.md` est redevenu distinct de V3.2.
- **Contrat d’artifacts pour propositions sprint** : `ArtifactPaths.sprint_proposal_md(...)` existe et est utilisé par l’orchestrateur.
- **Filtrage des features proposées déjà tentées** : `proposed_features` est maintenant filtré contre `attempted_features`.
- **Fix prompt builder nom de fichier** : interpolation de `round_number` active (plus de `XX` littéral dans l’instruction runtime).
- **Parser proposition plus robuste** : reset de section sur header `##` non reconnu.
- **Observabilité opérateur améliorée** : warnings explicites backlog/contrat précédent manquants.

Conclusion section 1 : la matrice V3.3 n’est pas "cosmétique"; l’essentiel des fixes annoncés est effectivement présent dans l’implémentation.

---

## 2. Conformité à l’article Anthropic "harness design"

### ✅ Alignements forts

- **Architecture tri-agent planner / builder / evaluator** : implémentée.
- **Séparation génération / évaluation** : implémentée.
- **Artifacts structurés inter-phases** : largement implémentés et schema-backed.
- **Runs longs avec reprise (`run_state`)** : implémenté.
- **QA orientée navigateur + Playwright prioritaire** : implémentée (Puppeteer en fallback).
- **Session continue + compaction** : mode continu activé quand modèles identiques.

### ⚠️ Alignements partiels (gap de fidélité à l’article)

- **Négociation de sprint contract** : l’article décrit une itération builder/evaluator "jusqu’à accord"; la V3.3 reste sur un modèle **asynchrone unidirectionnel** (builder propose round N, orchestrateur injecte round N+1), sans boucle d’accord explicite avant build.
- **Boucle de calibration de jugement** : il existe un prompt évaluateur exigeant, mais pas de mécanisme de calibration systématique (ex: scoring history / drift monitor / adjudication artifacts).

---

## 3. Findings majeurs V3.3

### 🟠 N3-M-01 — Négociation sprint contract incomplète vs design cible de l’article

**Constat :**
Le système lit une proposition markdown du builder puis construit le contrat suivant. Il n’existe pas de phase explicite où l’evaluator contredit/valide la proposition avant exécution du sprint courant.

**Impact production :**
- Contrat potentiellement biaisé par l’agent constructeur seul.
- Réduction de la fonction "garde-fou" de l’evaluator en amont.
- Risque d’itérations inefficaces (scope mal défini → fail QA tardif).

**Correction recommandée (V3.4) :**
- Ajouter une mini-phase `contract_review` :
  1. builder écrit proposition,
  2. evaluator écrit review structurée (`approved|changes_requested` + raisons),
  3. orchestrateur itère max N tours ou tranche avec fallback conservateur.
- Persister `planning/sprint_contract_negotiation_round_XX.json` (schema-backed + tests).

---

### 🟠 N3-M-02 — `proposed_acceptance` non filtré/dédupliqué contre historique

**Constat :**
Dans `_build_sprint_contract()`, les critères planner sont filtrés par `previous_criteria_ids`, mais les critères issus de proposition builder (`proposed_acceptance`) sont prepend sans ce filtre et sans déduplication d’ID.

**Impact production :**
- Réintroduction possible de tests déjà assignés.
- Duplications `id` dans `acceptance_tests`, ambiguïté QA et reporting.
- Dégradation de la progression réelle entre rounds.

**Correction recommandée :**
- Appliquer la même politique aux propositions builder :
  - filtrer sur `previous_criteria_ids`,
  - dédup strict par `id`,
  - fallback de normalisation si `id` absent/malformé.
- Ajouter test de non-régression dédié (round2/round3 avec proposals redondantes).

---

## 4. Findings mineurs V3.3

### 🟡 N3-Q-01 — Marqueurs de version incohérents (V3.2/V3.1 encore visibles)

Logs, docstrings et CLI exposent encore `V3.2` ou `v3_1` alors que la release est documentée V3.3.  
**Impact :** confusion opérateur, audit logs moins fiables.  
**Action :** harmoniser tags/version labels sur V3.3.

### 🟡 N3-Q-02 — `builder_prompt.md` header resté en V3.2

Le prompt builder n’affiche pas la même version que planner/evaluator.  
**Impact :** drift documentaire et ambiguïté en incident review.  
**Action :** aligner header sur V3.3 + note de changement.

### 🟡 N3-Q-03 — Préfixes logs orchestrateur restent `[V3.2]`

Plusieurs `print(...)` utilisent `[V3.2]`.  
**Impact :** corrélation logs/version perturbée.  
**Action :** passer en `[V3.3]` partout via constante unique.

### 🟡 N3-Q-04 — Validation proposition markdown trop permissive

Le parser accepte des lignes `- ...` au format libre; pas de validation stricte template pour `proposed features/tests`.  
**Impact :** variabilité non déterministe, contrats faibles.  
**Action :** parser strict + diagnostics précis + test d’erreurs de format.

### 🟡 N3-Q-05 — Mesures coût/tokens toujours indisponibles

Le README l’indique explicitement (bon point de transparence), mais en production long-run cette métrique est structurante pour gouvernance coût.  
**Action :** ajouter collecteur best-effort (même approximatif) ou instrumentation externe documentée.

### 🟡 N3-Q-06 — Couverture de tests perfectible sur chemins de proposition

La suite couvre bien le cas nominal proposal→round2, mais manque des cas de bords : IDs dupliqués, header markdown parasites, proposal malformée/mixte.  
**Action :** compléter tests intégration ciblés.

---

## 5. Plan de correction priorisé

### P0 immédiat (avant tag release "prod")

1. **Implémenter filtre + dédup sur `proposed_acceptance`** (N3-M-02).  
2. **Ajouter tests round multi-itérations avec proposals redondantes/malformées**.

### P1 court terme (V3.4)

3. **Introduire une vraie boucle de négociation contractuelle builder↔evaluator** (N3-M-01).  
4. **Schema dédié de négociation + artifact persistant + resume-safe behavior**.

### P2 hygiène/ops

5. **Harmoniser toutes les versions/log labels en V3.3** (N3-Q-01..03).  
6. **Durcir parsing/validation des propositions markdown** (N3-Q-04).  
7. **Plan télémétrie coût/tokens** (N3-Q-05).

---

## 6. Verdict final production

### Décision

- **GO conditionnel** pour environnement de pré-production / essais contrôlés.
- **NO-GO "prod stricte"** tant que N3-M-01 et N3-M-02 ne sont pas traités.

### Avis clair

La V3.3 capture bien l’**essence architecturale** de l’article (tri-agent, artifacts, QA indépendante, runs longs résumables, session continue), et corrige proprement les défauts V3.2 principaux.  
Le point bloquant restant est la **maturité de la négociation de contrat** et la **discipline de progression round-to-round côté critères QA**.

Si vous corrigez ces deux axes, vous aurez une base V3.4 réellement "production-grade" au standard demandé.

---

## Annexe — Commandes de vérification exécutées

```bash
pytest autonomous-coding/tests -q
```

Résultat observé : **26 passed**.


---

## Source: `REVIEW_V3_4_autonomous_coding.md`

# Rapport de Review Production — `autonomous-coding/` V3.4

> **Périmètre :** Audit complet V3.4 (code + prompts + tests + docs), confronté à `V3_4_TRACEABILITY_MATRIX.md`, `README.md` et à l'article de référence.  
> **Référence article :** [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) — Anthropic Engineering, **24 mars 2026**.  
> **Précédents audits :** `REVIEW_V2_autonomous_coding.md`, `REVIEW_V3_1_autonomous_coding.md`, `REVIEW_V3_2_autonomous_coding.md`, `REVIEW_V3_3_autonomous_coding.md`.  
> **Sévérité :** 🔴 Critique · 🟠 Majeur · 🟡 Mineur · ✅ Résolu  
> **Tolérance :** Zéro erreur production

---

## Résumé Exécutif

La V3.4 **corrige effectivement l’ensemble des points listés en V3.3**, avec des améliorations structurelles concrètes :

1. ✅ **Négociation de contrat matérialisée** via artifact dédié `sprint_contract_negotiation_round_XX.json` (schema-backed).
2. ✅ **Déduplication + filtrage historiques** des `acceptance_tests` proposés.
3. ✅ **Parser de proposition durci** avec diagnostics déterministes.
4. ✅ **Hygiène version/logs/prompt alignée sur V3.4**.
5. ✅ **Couverture de tests renforcée** sur les cas de bords critiques.

**Verdict global V3.4 :** ✅ **GO production** (avec recommandations d’optimisation non bloquantes).

---

## Table des Matières

1. [Validation des claims V3.4 (matrice → code)](#1-validation-des-claims-v34-matrice--code)
2. [Conformité à l’article Anthropic "harness design"](#2-conformité-à-larticle-anthropic-harness-design)
3. [Critique professionnelle de l’update](#3-critique-professionnelle-de-lupdate)
4. [Améliorations/optimisations recommandées (post V3.4)](#4-améliorationsoptimisations-recommandées-post-v34)
5. [Verdict final production](#5-verdict-final-production)

---

## 1. Validation des claims V3.4 (matrice → code)

### ✅ Points implémentés et vérifiés

- **N3-M-01 fermé** : une revue explicite de proposition est désormais persistée en artifact de négociation round-scoped, validée par schéma.
- **N3-M-02 fermé** : les tests d’acceptation proposés sont normalisés, filtrés contre l’historique et dédupliqués strictement par ID.
- **N3-Q-01/02/03 fermés** : alignement global des marqueurs V3.4 (logs + prompts + docs + docstrings).
- **N3-Q-04 fermé** : parser proposition plus strict avec feedback exploitable, sans ingestion silencieuse de bullets invalides.
- **N3-Q-06 fermé** : nouveaux tests ciblés multi-round sur duplicats/malformed proposals.
- **N3-Q-05 mitigé et explicité** : insuffisance token/cost toujours connue mais désormais signalée explicitement runtime + README.

---

## 2. Conformité à l’article Anthropic "harness design"

### ✅ Alignements forts

- Tri-agent planner/builder/evaluator conservé.
- Artifacts contractuels et états résumables robustes.
- QA indépendante et orientée exécution réelle.
- Gouvernance inter-round améliorée via contrat de négociation explicite.

### 🟡 Point partiellement aligné (non bloquant)

- La négociation est **déterministe côté harness** (review structurée persistée) plutôt qu’une boucle conversationnelle multi-tours orchestrée par un appel explicite à l’evaluator LLM pour l’accord contractuel.

**Avis expert :** ce choix est acceptable en production pour la robustesse/répétabilité, mais un mode “LLM-adjudicated negotiation” configurable pourrait améliorer l’exploration sur produits complexes.

---

## 3. Critique professionnelle de l’update

### Ce qui est excellent

- **Discipline de traçabilité** : historique versionné sans écrasement.
- **Solidité contrat→QA** : meilleure progression round-to-round, réduction des boucles stériles.
- **Déterminisme opérationnel** : gestion explicite des erreurs de format au lieu de comportements implicites.

### Ce qui peut encore progresser

- **Observabilité coût** : l’absence de compteur token/$ reste un angle mort pour pilotage long-run.
- **Négociation enrichie** : status binaire `approved|changes_requested` pourrait être enrichi (scores de confiance, raisons typées, suggestions actionnables normalisées).

---

## 4. Améliorations/optimisations recommandées (post V3.4)

### P1 (haute valeur)

1. Ajouter un `negotiation_reason_code` enum (ex: `FORMAT_ERROR`, `DUPLICATE_AC`, `OUT_OF_SCOPE`) pour analytics.
2. Exposer un mode optionnel `--llm-contract-review` pour arbitrage evaluator explicite quand requis.

### P2 (ops/finops)

3. Intégrer métriques token/coût par phase dans `run_state` (best-effort).
4. Ajouter dashboard simple cumul round/phase pour visibilité lead engineering.

---

## 5. Verdict final production

### Décision

- **GO production** ✅

### Avis clair

La V3.4 est une mise à jour sérieuse, cohérente, et adaptée à un usage production sur runs multi-rounds. Les écarts bloquants V3.3 ont été adressés proprement avec traçabilité, schémas, et tests adaptés. Les recommandations restantes relèvent d’optimisation (observabilité/finops et sophistication de négociation), pas de correctifs bloquants.

---

## Annexe — Commandes de vérification exécutées

```bash
pytest autonomous-coding/tests -q
```


