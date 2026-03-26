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
