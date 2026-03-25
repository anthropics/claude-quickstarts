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
