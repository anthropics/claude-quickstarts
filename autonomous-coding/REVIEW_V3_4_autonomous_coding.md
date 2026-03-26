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
