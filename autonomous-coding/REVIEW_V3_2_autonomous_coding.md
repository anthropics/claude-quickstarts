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
