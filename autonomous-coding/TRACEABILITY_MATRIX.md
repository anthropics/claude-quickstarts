# TRACEABILITY_MATRIX — Consolidated (v3.6.3)

> Concatenation intégrale des matrices existantes, sans altération du contenu source.
> La section `3.6.3` est maintenue directement dans ce fichier consolidé.

---

## Release: `V3.6.3`

# V3.6.3 Traceability Matrix

| Finding ID | Severity | Requirement summary | Files impacted | Implementation action | Test / validation evidence | Final status | Notes / tradeoffs |
|---|---|---|---|---|---|---|---|
| N8-M-01 | P0 | Sécuriser réellement la barrière Bash sans refonte | `security.py`, `test_security.py`, `tests/test_security_hook.py` | Added project-scoped path validation for file commands, restricted init scripts to `./init.sh`, bounded `sleep`, and blocked explicit package installs while preserving the existing allowlist + hook model | `python -m pytest autonomous-coding/tests autonomous-coding/test_security.py -q` | fixed_with_tradeoff | The current allowlist concept is preserved; absolute `--project-dir` support and broad allowed binaries like `git`/`node` remain by design |
| N8-M-02 | P0 | Empêcher le planner de réussir avec des artefacts fictifs | `planner.py`, `autonomous_agent_demo.py`, `tests/test_phase_errors.py` | Replaced silent planner fallbacks with explicit artifact validation failures and taught dry-run mode to emit schema-valid planning artifacts instead of placeholders | `python -m pytest autonomous-coding/tests autonomous-coding/test_security.py -q` | fixed | Planner/builder/evaluator architecture remains unchanged; only failure semantics were made explicit |
| N8-M-03 | P1 | Clarifier durablement le contrat CLI des modes runtime | `autonomous_agent_demo.py`, `agent.py`, `prompts.py`, `AGENTS.md`, `README.md`, `CHANGELOG.md`, `TRACEABILITY_MATRIX.md`, `tests/test_cli.py` | Renamed the public CLI modes to `legacy` and `orchestrated`, removed `v2`, kept temporary `v1`/`v3_1` alias warnings for one release, and aligned runtime-facing strings plus living docs to the canonical names | `pytest autonomous-coding/tests/test_cli.py -q`; dry-run CLI with `--mode legacy` and `--mode orchestrated` | fixed_with_tradeoff | One-release compatibility window is preserved for `v1` and `v3_1`; `v2` now fails fast |
| N8-M-04 | P1 | Rendre explicite et testable la frontière entre dry-run offline et chemins live | `autonomous_agent_demo.py`, `client.py`, `README.md`, `CHANGELOG.md`, `TRACEABILITY_MATRIX.md`, `tests/test_cli.py`, `tests/test_client_auth.py`, `tests/test_dry_run_contract.py`, `tests/test_live_phase_smoke.py`, `.github/workflows/autonomous-coding-audit-tests.yml`, `.github/workflows/autonomous-coding-live-smoke.yml` | Rejected `legacy --dry-run` with a stable non-zero exit, limited browser tools to builder/evaluator/orchestrator, added dedicated offline dry-run contract tests, and introduced a manual live smoke workflow for real SDK/LLM coverage that dry-run cannot provide | `pytest autonomous-coding/tests/test_cli.py autonomous-coding/tests/test_client_auth.py autonomous-coding/tests/test_dry_run_contract.py -q`; `pytest autonomous-coding/tests/test_live_phase_smoke.py -q -m live`; GitHub Actions offline/live smoke workflows | fixed_with_tradeoff | Offline dry-run remains intentionally partial; live verification is manual to keep PR CI deterministic and affordable |
| N8-Q-01 | P1 | Bloquer l’évasion de `--project-dir` tout en gardant la logique `generations/` | `autonomous_agent_demo.py`, `tests/test_cli.py` | Relative paths still normalize under `generations/`, but any path containing `..` now raises an explicit CLI error before directory creation | `python -m pytest autonomous-coding/tests autonomous-coding/test_security.py -q` | fixed | Absolute target paths are still allowed to preserve the historical CLI contract |
| N8-Q-02 | P1 | Rendre `progress.py` robuste face aux JSON valides mais mal structurés | `progress.py`, `tests/test_progress.py` | Added safe shape checks for `feature_list.json` and `run_state.json`, returning deterministic operator-facing fallbacks instead of raising `AttributeError` | `python -m pytest autonomous-coding/tests autonomous-coding/test_security.py -q` | fixed | Behavior intentionally falls back to “not yet created / unexpected structure” instead of attempting schema repair |
| N8-Q-03 | P2 | Rendre la release et la validation statique cohérentes pour `3.6.3` | `agent.py`, `autonomous_agent_demo.py`, `orchestrator.py`, `builder.py`, `planner.py`, `evaluator.py`, `metrics.py`, `prompts/*.md`, `README.md`, `CHANGELOG.md`, `pyrightconfig.json` | Fixed the real local `auth_mode` typing issue, aligned active runtime/docs/prompt version markers to `3.6.3`, and added a local pyright config that resolves the module environment correctly | `ruff check autonomous-coding`; `pyright --pythonpath C:\Python310\python.exe .`; `pip-audit -r autonomous-coding/requirements.txt --ignore-vuln CVE-2026-4539` | fixed | The pyright config is intentionally local to `autonomous-coding` and points at the current interpreter environment |

---

## Source: `V3_6_1_TRACEABILITY_MATRIX.md`

# V3.6.1 Traceability Matrix

| Finding ID | Severity | Requirement summary | Files impacted | Implementation action | Test / validation evidence | Final status | Notes / tradeoffs |
|---|---|---|---|---|---|---|---|
| N7-M-01 | P1 | Forcer Playwright headless par défaut et l’indiquer explicitement | `client.py`, `tests/test_client_auth.py`, `README.md`, `prompts/evaluator_prompt.md`, `prompts/coding_prompt.md`, `CHANGELOG.md`, `TRACEABILITY_MATRIX.md` | Updated browser MCP config to launch Playwright with `--headless` in the default path, added unit coverage, and aligned docs/prompts/changelog on “Playwright headless first, Puppeteer fallback only” | `pytest autonomous-coding/tests/test_client_auth.py -q` | fixed | No phase/security contract changed; only default browser launch policy and traceability/docs wording were updated |
| N7-M-02 | P1 | Permettre la configuration du volume de tests cibles sans modifier la logique métier | `autonomous_agent_demo.py`, `orchestrator.py`, `planner.py`, `agent.py`, `prompts.py`, `prompts/initializer_prompt.md`, `prompts/planner_prompt.md`, `tests/test_cli.py`, `tests/test_prompts.py`, `README.md`, `CHANGELOG.md`, `TRACEABILITY_MATRIX.md` | Added `--target-tests` across modes, threaded value to V1 initializer + V3.1 planner prompt rendering, and enforced explicit default warning (`200`) when unset | `pytest autonomous-coding/tests/test_cli.py -q`; `pytest autonomous-coding/tests/test_prompts.py -q` | fixed | Scope limited to CLI/prompt parameterization; orchestration/phase/security contracts unchanged |

---

## Source: `V3_6_TRACEABILITY_MATRIX.md`

# V3.6 Traceability Matrix

| Finding ID | Severity | Requirement summary | Files impacted | Implementation action | Test / validation evidence | Final status | Notes / tradeoffs |
|---|---|---|---|---|---|---|---|
| N6-M-01 | P1 | Offrir un choix explicite entre API key et credentials Claude CLI | `autonomous_agent_demo.py`, `client.py`, `agent.py`, `README.md`, `tests/test_cli.py`, `tests/test_client_auth.py` | Added `--auth-mode {api_key,cli,auto}`, centralized auth preflight, and threaded auth mode through V3.1 + V1 paths without changing phase/security logic | `pytest autonomous-coding/tests/test_cli.py autonomous-coding/tests/test_client_auth.py -q`; `pytest autonomous-coding/tests -q` | fixed | Default remains `api_key` to preserve historical runtime behavior |
| N6-Q-01 | P2 | Éviter erreurs d’auth tardives et ambiguës | `client.py`, `autonomous_agent_demo.py`, `tests/test_cli.py`, `tests/test_client_auth.py` | Added explicit preflight validation for `api_key`, `cli`, `auto` with user-facing actionable errors | `pytest autonomous-coding/tests/test_cli.py -q`; `pytest autonomous-coding/tests/test_client_auth.py -q` | fixed | SDK stays source of truth at runtime; preflight is best-effort for operator UX |

---

## Source: `V3_1_TRACEABILITY_MATRIX.md`

# V3.1 Traceability Matrix

| Finding ID | Severity | Requirement summary | Files impacted | Implementation action | Test / validation evidence | Final status | Notes / tradeoffs |
|---|---|---|---|---|---|---|---|
| C-01 | P0 | Session continue unique + compaction SDK | `orchestrator.py`, `agent.py`, `planner.py`, `builder.py`, `evaluator.py`, `autonomous_agent_demo.py`, `tests/test_orchestrator_integration.py` | Added shared client injection path; primary path uses one model + one session; compatibility mode for per-phase overrides | `pytest autonomous-coding/tests -q` (`test_continuous_session_shares_client_object`, `test_model_overrides_use_compatibility_mode_without_shared_client`) | fixed_with_tradeoff | Tradeoff: model overrides disable shared context by design and are logged explicitly |
| C-02 | P0 | Contrat de sprint structuré par round | `schemas/sprint_contract.schema.json`, `artifacts.py`, `orchestrator.py`, `builder.py`, `evaluator.py`, prompts, tests | Added sprint contract artifact path/schema/generation/validation and explicit round prompt integration | `pytest autonomous-coding/tests -q` (`test_sprint_contract_schema_validates`, integration checks for generated contract path) | fixed | Contract now persisted per round as schema-backed artifact |
| M-01 | P1 | Evaluator prompt gradué + seuils + few-shot | `prompts/evaluator_prompt.md`, `tests/test_prompts.py` | Rewrote evaluator prompt with graded criteria, hard threshold, skeptical posture, few-shot calibration and pass/fail/blocked semantics | `pytest autonomous-coding/tests -q` (`test_phase_prompts_load`) | fixed | Prompt enforces hard gate and explicit verdict semantics |
| M-02 | P1 | Builder prompt auto-évaluation obligatoire | `prompts/builder_prompt.md`, `tests/test_prompts.py` | Added mandatory self-evaluation flow: server check, browser validation, screenshots, backlog discipline, REFINE/PIVOT | `pytest autonomous-coding/tests -q` (`test_phase_prompts_load`) | fixed | Includes strategy declaration requirement at top of report |
| M-03 | P1 | Planner prompt ambitieux + IA + design skill | `prompts/planner_prompt.md`, `tests/test_prompts.py` | Rewrote planner prompt for ambition, AI feature inclusion, user-deliverable focus, design skill ingestion | `pytest autonomous-coding/tests -q` (`test_phase_prompts_load`) | fixed | Prevents over-specification and keeps user-visible orientation |
| M-04 | P1 | Stratégie modèles cohérente continuité/coût | `autonomous_agent_demo.py`, `README.md`, `orchestrator.py`, tests | Default set to unified Opus model for continuous session; overrides still available in documented compatibility mode | `pytest autonomous-coding/tests -q`; dry-run CLI | fixed_with_tradeoff | Tradeoff vs review suggestion: evaluator Sonnet not default to preserve P0 continuity path |
| M-05 | P1 | Builder: interdire fallback silencieux | `builder.py`, `tests/test_phase_errors.py` | Empty/whitespace builder output now raises explicit `RuntimeError` | `pytest autonomous-coding/tests -q` (`test_builder_empty_response_raises`) | fixed | No fabricated success report remains |
| M-06 | P1 | Orchestrator: checkpoint post-succès | `orchestrator.py`, `tests/test_orchestrator_integration.py` | `current_round` now advances only after successful round completion; no pre-builder increment | `pytest autonomous-coding/tests -q` (`test_builder_checkpoint_only_after_success`) | fixed | Resume no longer skips non-executed round |
| Q-01 | P1 | `pnpm` dans allowlist | `security.py`, `tests/test_security_hook.py` | Added `pnpm` in allowed commands and test coverage | `pytest autonomous-coding/tests -q` (`test_allows_pnpm_command`) | fixed | Security boundary preserved |
| Q-06 | P1 | Robustesse JSON malformé | `artifacts.py`, `evaluator.py`, `tests/test_phase_errors.py` | `read_json` now catches `JSONDecodeError` with deterministic fallback + context message; evaluator fallback blocked behavior | `pytest autonomous-coding/tests -q` (`test_evaluator_invalid_json_uses_blocked_fallback`) | fixed | Deterministic blocker emitted on malformed QA report |
| Q-07 | P1 | `--resume` sur run completed | `orchestrator.py`, `tests/test_orchestrator_integration.py`, `README.md` | Added explicit early return with clear message when resumed run is already completed | `pytest autonomous-coding/tests -q` (`test_resume_completed_run_does_not_restart`) | fixed | Prevents silent restart |
| Q-02 | P2 | Cache schémas statiques | `artifacts.py` | Added `@lru_cache` on schema loader | `pytest autonomous-coding/tests -q` | fixed | Reduces repeated disk reads |
| Q-03 | P2 | Summary max configurable | `orchestrator.py`, `README.md` | Introduced `SUMMARY_MAX_CHARS` via env override `V3_1_SUMMARY_MAX_CHARS` | `pytest autonomous-coding/tests -q` | fixed | Removed magic literal usage |
| Q-04 | P2 | `_normalize_project_dir` robuste | `autonomous_agent_demo.py`, `tests/test_cli.py` | Rewrote normalization to handle `./generations/...` and avoid path duplication | `pytest autonomous-coding/tests -q` (`test_normalize_project_dir_handles_dot_prefix`) | fixed | Supports normalized relative paths safely |
| Q-05 | P2 | Stack trace conservée | `agent.py` | Exception path now emits traceback and returns full error text | `python -m compileall autonomous-coding`; `pytest autonomous-coding/tests -q` | fixed | Better production diagnostics |
| Q-08 | P2 | Écriture conditionnelle `.claude_settings.json` | `client.py` | Only writes settings file when content differs | `pytest autonomous-coding/tests -q` | fixed | Avoids unnecessary disk writes |
| Q-09 | P2 | Métriques durée/coût/tokens exploitables | `orchestrator.py`, `README.md` | Added per-phase timing aggregation and final summary; token/cost explicitly marked unavailable from current runner interface | Dry-run CLI + metrics output | fixed_with_tradeoff | No fake token/cost metrics emitted |
| Q-10 | P2 | Preflight evaluator server/accessibilité | `prompts/evaluator_prompt.md` | Added mandatory preflight/startup attempts and blocked verdict rule when inaccessible | `pytest autonomous-coding/tests -q` (`test_phase_prompts_load`) | fixed | `pass` forbidden when app unreachable |
| Q-11 | P2 | Cohérence `RunStatus` / schéma | `tests/test_artifacts.py` | Added strict unit test comparing enum values with schema enum | `pytest autonomous-coding/tests -q` (`test_run_status_enum_matches_schema`) | fixed | Chosen strict-test approach for maintainability |
| T-01 | Test | `test_resume_skips_planner` robuste | `tests/test_orchestrator_integration.py` | Added `planner_calls` counter and explicit assertion planner is not re-invoked on resume+qa_only | `pytest autonomous-coding/tests -q` (`test_resume_skips_planner`) | fixed | Planner skip now proven directly |
| T-02 | Test | Tests erreurs builder/evaluator | `tests/test_phase_errors.py` | Added explicit tests for builder empty output, evaluator malformed JSON, evaluator missing report | `pytest autonomous-coding/tests -q` (`test_builder_empty_response_raises`, `test_evaluator_invalid_json_uses_blocked_fallback`, `test_evaluator_missing_report_uses_blocked_fallback`) | fixed | Critical failure paths now covered |
| T-03 | Test | Test combinaison invalide planner-only+qa-only | `tests/test_orchestrator_integration.py` | Added assertion of `ValueError` on invalid CLI combination in orchestrator run | `pytest autonomous-coding/tests -q` (`test_invalid_planner_only_and_qa_only_combination`) | fixed | Prevents ambiguous mode invocation |


---

## Source: `V3_2_TRACEABILITY_MATRIX.md`

# V3.2 Traceability Matrix

| Finding ID | Severity | Requirement summary | Files impacted | Implementation action | Test / validation evidence | Final status | Notes / tradeoffs |
|---|---|---|---|---|---|---|---|
| N-M-01 | P1 | Sprint contract negotiation input | `prompts/builder_prompt.md`, `builder.py`, `orchestrator.py`, `tests/test_orchestrator_integration.py` | Added `sprint_proposal_round_XX.md` handoff from builder prompt and orchestrator ingestion for next round contract | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` (`test_round_two_contract_uses_previous_builder_proposal`) | fixed_with_tradeoff | Lightweight proposal handoff; no live multi-turn negotiation loop |
| N-M-02 | P1 | Sprint contract caps + round progression | `orchestrator.py`, `README.md` | Replaced fixed 5/8 caps with configurable defaults (10/12), dedupe, and filtering of attempted features/criteria from previous rounds | `pytest autonomous-coding/tests -q` | fixed | Configurable via `V3_2_SPRINT_MAX_SCOPE_ITEMS` and `V3_2_SPRINT_MAX_ACCEPTANCE_TESTS` |
| N-M-03 | P1 | Shared phase runner typing | `phase_types.py`, `planner.py`, `builder.py`, `evaluator.py`, `orchestrator.py` | Extracted common `PhaseRunner`/`ClientFactory` aliases into a shared module | `python -m compileall autonomous-coding` | fixed | Removes duplicated signatures across phase modules |
| N-M-04 | P1 | CLI mode contract clarity (`--mode v2`) | `autonomous_agent_demo.py`, `tests/test_cli.py` | Added explicit deprecation warning when `v2` alias is used | `pytest autonomous-coding/tests/test_cli.py -q` (`test_main_warns_when_v2_mode_is_used`) | fixed | Backwards-compatible alias retained with explicit warning |
| N-M-05 | P1 | Evaluator schema-invalid QA report handling | `evaluator.py`, `tests/test_phase_errors.py` | Added schema validation guard with deterministic blocked fallback for invalid enum/value payloads | `pytest autonomous-coding/tests/test_phase_errors.py -q` (`test_evaluator_schema_invalid_report_uses_blocked_fallback`) | fixed | Prevents orchestrator crash on schema-invalid evaluator output |
| N-Q-01 | P2 | Avoid fragile shared_client closure capture | `orchestrator.py` | `_run_loop` now takes explicit `client` argument in both shared and non-shared modes | `pytest autonomous-coding/tests -q` | fixed | Safer for refactors |
| N-Q-02 | P2 | Warning on empty planning artifacts | `orchestrator.py` | Added explicit warning when acceptance criteria are empty and fallback contract is used | Dry-run CLI log inspection | fixed | Improves operator visibility |
| N-Q-04 | P2 | Test contract writes must be schema-validated | `tests/test_phase_errors.py` | Replaced ad-hoc JSON writes with `write_validated_json(..., "sprint_contract")` | `pytest autonomous-coding/tests/test_phase_errors.py -q` | fixed | Keeps tests aligned with contract schema changes |
| N-Q-05 | P2 | Round-specific acceptance tests | `orchestrator.py` | Excludes criteria IDs already assigned in previous sprint contracts before selecting current round tests | `pytest autonomous-coding/tests -q` | fixed_with_tradeoff | Uses prior contract assignment proxy (not per-criterion evaluator verdicts) |
| N-Q-06 | P2 | `pytest` import placement | `tests/test_orchestrator_integration.py` | Moved `import pytest` to module top-level | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` | fixed | Conforms to normal Python import style |
| N-Q-07 | P2 | Builder crash checkpoint assertion completeness | `tests/test_orchestrator_integration.py` | Added assertion that status remains `building` when builder crashes before checkpoint advancement | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` (`test_builder_checkpoint_only_after_success`) | fixed | Verifies resumable state consistency |

## Explicit exclusions retained per operator decision

- **N-C-01** (`orchestrator.py` shared client browser tools): excluded from this batch (handled manually by operator).
- **N-Q-03** (`prompts/app_spec.txt` placeholder `{frontend_port}`): excluded from this batch (handled through external process).


---

## Source: `V3_3_TRACEABILITY_MATRIX.md`

# V3.3 Traceability Matrix

| Finding ID | Severity | Requirement summary | Files impacted | Implementation action | Test / validation evidence | Final status | Notes / tradeoffs |
|---|---|---|---|---|---|---|---|
| N2-M-01 | P1 | Restaurer l'historique V3.1 de traçabilité | `V3_1_TRACEABILITY_MATRIX.md` | Restored original V3.1 matrix content from pre-V3.2 history; preserved as immutable historical artifact | `git show e346125:autonomous-coding/V3_1_TRACEABILITY_MATRIX.md` diff check | fixed | V3.1 and V3.2 matrices are now distinct again |
| N2-M-02 | P1 | Ajouter le path de proposition builder au contrat d'artifacts | `artifacts.py`, `orchestrator.py` | Added `ArtifactPaths.sprint_proposal_md()` and migrated orchestrator to use centralized path contract | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` | fixed | Removes path drift risk |
| N2-M-03 | P1 | Empêcher le contournement du filtre `attempted_features` | `orchestrator.py`, `tests/test_orchestrator_integration.py` | Filtered proposed features against attempted set before merging into new sprint scope; added duplicate guard assertion | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` (`test_round_two_contract_uses_previous_builder_proposal`) | fixed | Prevents infinite recycle loops |
| N2-M-04 | P1 | Corriger l'annotation de type `ClaudeSDKClient` manquante en builder | `builder.py` | Added explicit `ClaudeSDKClient` import for runtime/type-hints consistency | `python -m compileall autonomous-coding` | fixed | Aligns builder typing with planner/evaluator |
| N2-M-05 | P1 | Remplacer `XX` littéral dans l'instruction de proposal builder | `builder.py` | Prompt now writes round-specific filename using `round_number` interpolation | `pytest autonomous-coding/tests/test_phase_errors.py -q` | fixed | Proposal naming now deterministic |
| N2-M-06 | P1 | Rendre le parser markdown de proposition robuste | `orchestrator.py` | Parser now resets section on any unknown `##` header and logs missing proposal path for rounds > 1 | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` | fixed | Avoids accidental capture from unrelated sections |
| N2-Q-01 | P2 | Nettoyage import inutilisé evaluator | `evaluator.py` | Removed unused `Awaitable` import | `python -m compileall autonomous-coding` | fixed | Lint/type hygiene |
| N2-Q-02 | P2 | Mettre à jour la version des prompts planner/evaluator | `prompts/planner_prompt.md`, `prompts/evaluator_prompt.md` | Updated prompt headers to V3.3 | `pytest autonomous-coding/tests/test_prompts.py -q` | fixed | Versioning consistency |
| N2-Q-03 | P2 | Warning explicite si backlog vide | `orchestrator.py` | Added deterministic warning when backlog is empty/missing before fallback scope construction | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` | fixed | Better operator observability |
| N2-Q-04 | P2 | Warning explicite si sprint contract précédent absent | `orchestrator.py` | Added INFO log when prior round contract is missing during criteria dedup pass | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` | fixed | Safer resumability diagnostics |
| N2-Q-05 | P2 | Renforcer test round-2 contre duplication de features | `tests/test_orchestrator_integration.py` | Added duplicate detection assertion in round-2 proposal integration test | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` | fixed | Regression guard for N2-M-03 |


---

## Source: `V3_4_TRACEABILITY_MATRIX.md`

# V3.4 Traceability Matrix

| Finding ID | Severity | Requirement summary | Files impacted | Implementation action | Test / validation evidence | Final status | Notes / tradeoffs |
|---|---|---|---|---|---|---|---|
| N3-M-01 | P1 | Implémenter une phase explicite de négociation de contrat sprint | `orchestrator.py`, `artifacts.py`, `schemas/sprint_contract_negotiation.schema.json`, `tests/test_orchestrator_integration.py`, `tests/test_artifacts.py` | Added deterministic proposal review gate that writes `planning/sprint_contract_negotiation_round_XX.json` with `approved|changes_requested`, feedback, approved payload, and turn metadata before contract merge | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` (`test_malformed_proposal_creates_changes_requested_negotiation`), `pytest autonomous-coding/tests/test_artifacts.py -q` | fixed | Negotiation is harness-level deterministic review (not extra model call), preserving reproducibility and resumability |
| N3-M-02 | P1 | Empêcher duplication/contournement des `acceptance_tests` proposés | `orchestrator.py`, `tests/test_orchestrator_integration.py` | Normalized proposal IDs, filtered proposed acceptance against `previous_criteria_ids`, deduped by ID, and retained only unique merged tests | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` (`test_round_two_contract_dedups_proposed_acceptance_ids`) | fixed | Prevents repeated AC IDs across rounds and within same proposal |
| N3-Q-01 | P2 | Harmoniser les marqueurs de version runtime/docs | `orchestrator.py`, `builder.py`, `artifacts.py`, `README.md`, prompt files | Centralized logs to V3.4 markers and updated phase headers/docs | `pytest autonomous-coding/tests/test_prompts.py -q`, manual code inspection | fixed | Keeps audit/log correlation reliable |
| N3-Q-02 | P2 | Mettre à jour `builder_prompt.md` version header | `prompts/builder_prompt.md` | Header bumped to V3.4 | `pytest autonomous-coding/tests/test_prompts.py -q` | fixed | Aligns planner/builder/evaluator prompt versions |
| N3-Q-03 | P2 | Remplacer préfixes logs `[V3.2]` hérités | `orchestrator.py`, `artifacts.py` | Replaced legacy log prefixes with V3.4 constant-based tags | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` | fixed | Simplifies release operations review |
| N3-Q-04 | P2 | Durcir validation parsing proposition markdown | `orchestrator.py`, `tests/test_orchestrator_integration.py` | Added strict parsing diagnostics for malformed test lines and unknown sections; feedback persisted in negotiation artifact | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` | fixed | Parser now deterministic and reviewable |
| N3-Q-05 | P2 | Clarifier déficit de télémétrie coût/tokens | `orchestrator.py`, `README.md` | Added explicit runtime message and README note recommending SDK usage telemetry integration | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` | mitigated | Full token/cost capture still depends on runner API integration |
| N3-Q-06 | P2 | Augmenter couverture de tests sur cas limites propositions | `tests/test_orchestrator_integration.py`, `tests/test_artifacts.py` | Added regression tests for malformed proposals, duplicate acceptance IDs, and new negotiation schema validation | `pytest autonomous-coding/tests -q` | fixed | Strengthens multi-round proposal reliability |


---

## Source: `V3_5_TRACEABILITY_MATRIX.md`

# V3.5.1 Traceability Matrix

| Finding ID | Severity | Requirement summary | Files impacted | Implementation action | Test / validation evidence | Final status | Notes / tradeoffs |
|---|---|---|---|---|---|---|---|
| N4-M-01 | P1 | Intégrer les métriques token/coût par phase dans `run_state` (best-effort) | `orchestrator.py`, `state_models.py`, `schemas/run_state.schema.json`, `metrics.py`, `planner.py`, `builder.py`, `evaluator.py` | Added cumulative `llm_usage` in `RunState`, per-phase usage recording in orchestrator, and lightweight estimation helpers for tokens/cost with configurable rates | `pytest autonomous-coding/tests/test_artifacts.py -q`, `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` | fixed | Estimation is deterministic and resume-safe, but remains approximate until SDK-native usage fields are exposed |
| N4-M-02 | P1 | Afficher la progression coût/tokens pendant le run sans verbosité excessive | `planner.py`, `builder.py`, `evaluator.py`, `orchestrator.py` | Added concise call-level logs (`LLM call <phase> ...`) and phase-end cumulative usage summaries | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` | fixed | One concise line per call + one concise line per phase-end keeps logs actionable without flooding |
| N4-Q-01 | P2 | Préserver `--resume` sans double comptage | `orchestrator.py`, `state_models.py` | Usage counters are loaded from existing `run_state`, then incremented only for newly executed calls after resume | `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` (`test_resume_skips_planner`) | fixed | Existing completed rounds remain untouched; no reset of historical totals |
| N4-Q-02 | P2 | Mettre à jour documentation versionnée sans écraser l'historique | `README.md`, `V3_5_TRACEABILITY_MATRIX.md` | Added dedicated V3.5.1 section and separate traceability matrix file | manual review + test suite | fixed | Keeps prior matrices intact (`V3_1`..`V3_4`) and adds V3.5.1 as additive artifact |


---

## Source: `V3_5_2_TRACEABILITY_MATRIX.md`

# V3.5.2 Traceability Matrix

| Finding ID | Severity | Requirement summary | Files impacted | Implementation action | Test / validation evidence | Final status | Notes / tradeoffs |
|---|---|---|---|---|---|---|---|
| N5-M-01 | P1 | Enrichir le verdict de négociation au-delà du binaire seul | `orchestrator.py`, `schemas/sprint_contract_negotiation.schema.json`, `tests/test_orchestrator_integration.py`, `tests/test_artifacts.py` | Added structured negotiation metadata (`review_mode`, `confidence_score`, `reason_codes`, `actionable_suggestions`) while preserving `approved|changes_requested` status contract | `pytest autonomous-coding/tests/test_artifacts.py -q`; `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` (`test_malformed_proposal_creates_changes_requested_negotiation`) | fixed | Backward-compatible: existing status consumers continue to work |
| N5-M-02 | P1 | Ajouter un enum `negotiation_reason_code` exploitable analytics | `orchestrator.py`, `schemas/sprint_contract_negotiation.schema.json`, `README.md`, `tests/test_artifacts.py` | Introduced typed reason-code set (e.g. `FORMAT_ERROR`, `DUPLICATE_AC`, `OUT_OF_SCOPE`) and deterministic derivation path in negotiation review | `pytest autonomous-coding/tests/test_artifacts.py -q` (`test_sprint_contract_negotiation_rejects_unknown_reason_code`) | fixed | Dashboard intentionally deferred; schema and artifacts now analytics-ready |
| N5-M-03 | P1 | Exposer mode optionnel `--llm-contract-review` pour arbitrage evaluator explicite | `autonomous_agent_demo.py`, `orchestrator.py`, `README.md`, `tests/test_cli.py`, `tests/test_orchestrator_integration.py` | Added CLI flag + optional evaluator-model arbitration call (`contract_reviewer` phase) with deterministic fallback on invalid LLM output | `pytest autonomous-coding/tests/test_cli.py -q`; `pytest autonomous-coding/tests/test_orchestrator_integration.py -q` (`test_llm_contract_review_enriches_negotiation_artifact`) | fixed | Default mode remains deterministic for resumability/cost control; LLM arbitration is opt-in |
