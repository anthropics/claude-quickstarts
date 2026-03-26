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
