# Changelog

Toutes les évolutions notables du module `autonomous-coding` sont listées ici.

## [3.6.3] - 2026-03-28

### Added

- Couverture de régression dédiée pour la barrière Bash, l’échec explicite du planner, la traversée `--project-dir` et la robustesse de `progress.py`.
- Configuration locale `pyrightconfig.json` pour rendre le type-check du module `autonomous-coding` exécutable dans l’environnement de développement courant.
- Nouvelle couverture hybride du contrat `--dry-run` : tests offline dédiés, smoke CLI orchestrated, et workflow live manuel pour les chemins SDK/LLM réels.

### Changed

- Durcissement réel de `security.py` sans changer le concept actuel : chemins hors projet bloqués, `./init.sh` uniquement, `sleep` borné, et installations explicites de paquets refusées.
- `PlannerPhase` échoue désormais explicitement si les artefacts obligatoires sont absents, invalides ou restent en placeholder ; le dry-run génère des artefacts de planification valides.
- Les chemins relatifs `--project-dir` conservent la normalisation sous `generations/` mais refusent désormais toute évasion via `..`.
- `progress.py` retombe proprement sur un fallback sûr quand `feature_list.json` ou `run_state.json` ont une structure inattendue.
- Alignement des marqueurs de version runtime, prompts actifs et documentation utilisateur sur `V3.6.3`.
- Contrat CLI des modes clarifié : `v2` est retiré, `v1` devient `legacy`, `v3_1` devient `orchestrated`, et `orchestrated` devient le mode par défaut. Les alias `v1`/`v3_1` restent acceptés temporairement avec warning.
- `legacy --dry-run` est maintenant rejeté explicitement avec code de sortie stable ; seul `orchestrated --dry-run` reste vendu comme smoke test offline.
- `create_client()` n’autorise plus les outils navigateur dans le contrat planner/contract-reviewer ; ils restent limités à builder/evaluator/orchestrator.

## [3.6.1] - 2026-03-27

### Added

- Nouveau flag CLI `--target-tests` pour définir explicitement le volume cible de tests dans les prompts de planification/initialisation (tous modes).

### Changed
- Priorité renforcée sur Playwright MCP en mode **headless par défaut** dans la configuration client (`client.py`).
- Clarification des consignes QA/prompts pour imposer Playwright headless en chemin principal, avec Puppeteer seulement en fallback.
- Mise à jour de la documentation versionnée (README + traceability consolidée) pour refléter cette politique navigateur.
- Si `--target-tests` n’est pas fourni, le runtime affiche un warning explicite et applique la valeur par défaut `200`.

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
