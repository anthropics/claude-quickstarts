# IMPLEMENTATION PLAN V3.1

## 1) Résumé de l'état V2 observé

- Le harness V2 est structuré en 3 phases (`planner`, `builder`, `evaluator`) avec état persistant (`state/run_state.json`) et schémas JSON validés.
- Le chemin principal V2 crée un nouveau client SDK par phase (`run_phase_session`), ce qui réinitialise le contexte.
- Il n'existe pas de contrat de sprint formel par round.
- Les prompts planner/builder/evaluator sont minimalistes et ne couvrent pas les exigences de calibration, auto-évaluation et préflight exigées.
- Plusieurs défauts de robustesse existent (fallback builder silencieux, checkpoint round prématuré, JSON malformé non géré explicitement).

## 2) Cible V3.1

- Chemin principal **session continue unique** avec client SDK partagé et compaction SDK.
- Contrat de sprint structuré par round (artifact + schéma + validation + intégration prompts).
- Orchestrateur strictement résumable, sans faux progrès d'état.
- Prompts planner/builder/evaluator réalignés sur les exigences du rapport.
- Robustesse runtime renforcée (JSON fallback contrôlé, erreurs explicites, traçabilité métriques).

## 3) Risques structurants

- Le SDK ne supporte pas le changement de modèle en cours de session.
- Les runners de tests existants sont basés sur l'ancienne signature de phase runner.
- Les tests d'intégration doivent être adaptés pour couvrir les nouveaux artifacts et la logique resume.

## 4) Stratégie de migration

1. Introduire la session partagée dans l'orchestrateur et l'injection de client dans les phases.
2. Ajouter le contrat de sprint (pathing, schéma, génération, lecture, validation).
3. Corriger les comportements P1 bloquants (builder empty, checkpoint post-success, resume completed, JSON robustesse).
4. Ajouter les améliorations P2 (cache schéma, limite résumé configurable, métriques, cohérence enum/schema).
5. Étendre les tests unitaires/intégration.

## 5) Stratégie de compatibilité

- **Chemin principal**: modèle unifié + session continue.
- **Mode compatibilité**: si overrides par phase différents, exécution multi-session explicitement signalée.
- Le support V1 reste intact (`--mode v1`).

## 6) Stratégie de tests

- Ajouter/mettre à jour tests unitaires pour:
  - session continue vs mode compatibilité,
  - génération/validation sprint contract,
  - builder vide,
  - evaluator JSON invalide / rapport manquant,
  - resume sur run completed,
  - combinaison invalide `--planner-only` + `--qa-only`,
  - cohérence `RunStatus` vs schéma.
- Exécuter `pytest autonomous-coding/tests` et un dry-run e2e CLI.

## 7) Ordre réel d'implémentation

1. Ajouter plan/matrice.
2. Refactor P0 session continue.
3. Implémenter sprint contract.
4. Implémenter P1 runtime + prompts + sécurité + defaults.
5. Implémenter P2 robustesse/metrics/docs.
6. Ajuster et exécuter tests.
7. Finaliser README + matrice.

## 8) Hypothèses validées par inspection

- `run_phase_session` crée actuellement un client neuf par phase.
- `orchestrator.run` persiste `current_round` avant succès builder.
- `builder.py` crée un rapport fallback silencieux sur résumé vide.
- `read_json` ne gère pas explicitement `JSONDecodeError`.
- `run_state.schema.json` et `RunStatus` peuvent dériver sans garde-fou test.
