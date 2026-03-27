# Changelog

Toutes les évolutions notables du module `autonomous-coding` sont listées ici.

## [3.6.0] - 2026-03-27

### Added
- Nouveau flag CLI `--auth-mode {api_key,cli,auto}` pour choisir explicitement la méthode d’authentification.
- Détection best-effort des credentials Claude CLI (session/token/fichier credentials) pour préflight explicite.
- Couverture de tests dédiée à la validation auth (`tests/test_client_auth.py`) et au parsing/erreurs CLI.

### Changed
- Préflight d’authentification centralisé dans `client.py` (`validate_auth_configuration`) avec messages d’erreur actionnables.
- Intégration de l’auth mode dans les chemins V3.1 (orchestrator) et V1 compat (`run_autonomous_agent`).
- Documentation mise à jour pour inclure les modes `cli` et `auto`.

## [3.5.2] - 2026-03-26

### Added
- Enrichissement de l’artefact de négociation (`reason_codes`, `confidence_score`, `actionable_suggestions`, `review_mode`).
- Option `--llm-contract-review` pour arbitrage de contrat assisté modèle.

### Changed
- Alignement des marqueurs de version runtime/télémetrie sur V3.5.2.
- Conservation de compatibilité des statuts historiques (`approved|changes_requested`).

## [3.5.0] - 2026-03-26

### Added
- Télémétrie best-effort token/coût consolidée dans `state/run_state.json`.
- Résumé d’usage LLM au niveau appel et phase.

### Changed
- Reprise (`--resume`) compatible avec cumul de métriques existantes.
- Schéma `schemas/run_state.schema.json` étendu pour valider `llm_usage`.

## [3.4.0] - 2026-03-26

### Added
- Artefact de négociation de sprint `planning/sprint_contract_negotiation_round_XX.json`.

### Changed
- Durcissement progression des tests d’acceptation (normalisation, filtrage, déduplication).
- Validation plus stricte des propositions malformed.

## [3.3.0] - 2026-03-26

### Added
- Matrice de traçabilité dédiée à la version 3.3.
- Contrat de chemin des artefacts de proposition sprint.

### Changed
- Filtrage des features déjà tentées lors de la progression des rounds.
- Correctifs de prompts/typing et robustesse du parser de proposition.

## [3.2.0] - 2026-03-26

### Added
- Contrats de sprint par round avec cap/filtrage configurable.
- Intégration explicite des propositions builder dans la préparation du round suivant.

### Changed
- Fallback déterministe `blocked` si rapport QA non conforme au schéma.
- Avertissement explicite pour `--mode v2` déprécié.

## [3.1.0] - 2026-03-26

### Added
- Chemin principal en session continue (planner/builder/evaluator).
- Artefacts de contrat de sprint obligatoires.

### Changed
- Suppression du fallback silencieux builder vide (erreur explicite).
- Reprise renforcée (pas de redémarrage implicite d’un run terminé).

---

## Notes
- Les dates exactes historiques antérieures peuvent être affinées si vous souhaitez un changelog “calendaire” précis basé sur l’historique Git.
