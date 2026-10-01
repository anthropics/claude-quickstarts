# Autonomous Coding Harness (V3.7.0)

Harness d’automatisation de développement basé sur un cycle **Planner → Builder → Evaluator**, avec artefacts JSON validés par schéma, reprise de session (`--resume`) et garde-fous QA/sécurité.

> 📌 Le détail des évolutions par version est désormais dans `CHANGELOG.md` (et **plus** dans ce README).

## 1) Objectif du projet

Ce projet sert à piloter un cycle de développement autonome sur un dossier cible (`--project-dir`) en :
- planifiant le travail,
- implémentant des changements,
- évaluant les résultats avec critères d’acceptation,
- conservant un état durable pour reprendre sans perdre le contexte.

Le flux est pensé pour des itérations multi-rounds avec contrats de sprint explicites et reporting QA structuré.

## 2) Schéma de fonctionnement

```mermaid
flowchart LR
    A[app_spec.txt] --> B[Planner]
    B --> C[Artifacts planning/*]
    C --> D[Sprint contract round XX]
    D --> E[Builder]
    E --> F[build_report_round_XX.md]
    E --> G[Code changes in project-dir]
    D --> H[Evaluator]
    F --> H
    G --> H
    H --> I[qa_report_round_XX.json/.md]
    I --> J[state/round_state_XX.json]
    J --> K[state/run_state.json]
    K -->|resume| B
```

## 3) Architecture (modules clés)

- `autonomous_agent_demo.py` : point d’entrée CLI (modes, flags, orchestration runtime).  
- `orchestrator.py` : boucle de rounds, reprise, progression, création contrats de sprint.  
- `planner.py` : production des artefacts de planification.  
- `builder.py` : exécution implémentation + rapport de build.  
- `evaluator.py` : QA finale, statut pass/fail/blocked.  
- `artifacts.py` : chemins d’artefacts + validation de schémas JSON.  
- `client.py` et `security.py` : configuration SDK, sandbox, permissions outils, hooks Bash.  
- `state_models.py` : modèles de l’état d’exécution.

## 4) Prérequis obligatoires

## 4.1 Linux

- Python **3.10+** recommandé.
- `pip` disponible.
- `npx` (Node.js) recommandé pour les outils MCP navigateur (Playwright/Puppeteer).
- Authentification au choix :
  - `ANTHROPIC_API_KEY` (mode `api_key`),
  - ou credentials Claude CLI détectables (mode `cli`/`auto`).

Vérification rapide :

```bash
python3 --version
pip --version
npx --version
```

## 4.2 Windows (PowerShell)

- Python **3.10+** recommandé.
- `pip` fonctionnel.
- Node.js (pour `npx`) recommandé.
- Authentification au choix :
  - variable `ANTHROPIC_API_KEY` (mode `api_key`),
  - ou credentials Claude CLI détectables (mode `cli`/`auto`).

Vérification rapide :

```powershell
python --version
pip --version
npx --version
```

## 5) Installation

Depuis la racine du repo :

```bash
pip install -r autonomous-coding/requirements.txt
```

Dépendances principales :
- `claude-code-sdk`
- `jsonschema`
- `pytest`

## 6) Configuration

> Etat actuel du support provider :
> - `--provider claude` utilise le runtime Claude existant.
> - `--provider openai` utilise aujourd'hui le transport **Codex CLI** en mode non interactif.
> - Le provider OpenAI ne passe pas encore par une intégration API OpenAI Python directe dans ce harness.

### 6.1 Variables d’environnement / credentials

Linux/macOS :

```bash
export ANTHROPIC_API_KEY="votre_cle"
```

Windows PowerShell :

```powershell
$env:ANTHROPIC_API_KEY="votre_cle"
```

Credentials CLI (optionnels) :
- Session CLI (`claude login`) détectée automatiquement.
- Ou token via une variable d’environnement compatible CLI (`CLAUDE_CODE_AUTH_TOKEN`, `CLAUDE_AUTH_TOKEN`, `ANTHROPIC_AUTH_TOKEN`).

Credentials OpenAI/Codex :
- API key non interactive : `CODEX_API_KEY` ou `OPENAI_API_KEY`.
- Session CLI persistée : `codex login`, avec cache local attendu dans `~/.codex/auth.json`.
- Le provider OpenAI nécessite un projet cible dans un dépôt Git pour l'exécution Codex CLI.

### 6.2 Fichiers importants à connaître

- `prompts/app_spec.txt` : spec applicative de base copiée dans le projet cible pour initialiser le contexte produit.
- `artifacts/qa_report_template.json` : exemple/template de structure de rapport QA.
- `schemas/*.schema.json` : contrats JSON officiels (run state, backlog, contrat sprint, QA, etc.).
- `.claude_settings.json` (généré dans `--project-dir`) : sandbox + permissions outils autorisés.

> Le “fichier JSON pour commencer” auquel on pense souvent est en pratique le couple :
> - `planning/work_backlog.json` (généré par le Planner),
> - et les schémas dans `schemas/` qui imposent la structure.

## 7) Utilisation détaillée

Commande de base :

```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project
```

Le dossier effectif est normalisé sous `generations/` quand un chemin relatif est fourni. Les chemins relatifs contenant `..` sont rejetés pour empêcher une sortie de périmètre.

### 7.1 Commandes principales

- Exécution standard :

```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project
```

- Reprise d’un run existant :

```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project --resume
```

- Dry-run orchestrated (sans appel LLM distant) :

```bash
python autonomous-coding/autonomous_agent_demo.py --mode orchestrated --project-dir ./my_project --dry-run
```

- `legacy --dry-run` :

  non supporté intentionnellement. Le runtime V1 ne valide pas un run offline complet et la CLI échoue vite avec un code non nul stable.

- Planification uniquement :

```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project --planner-only
```

- QA uniquement :

```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project --qa-only
```

- Activer la revue de contrat assistée LLM :

```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project --llm-contract-review
```

- Forcer l’authentification via Claude CLI :

```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project --auth-mode cli
```

- Exécuter explicitement avec le provider OpenAI via session Codex CLI :

```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project --provider openai --auth-mode cli
```

- Exécuter explicitement avec le provider OpenAI via API key pour Codex CLI :

```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project --provider openai --auth-mode api_key
```

- Mode auto (essaye CLI puis API key) :

```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project --auth-mode auto
```

- Mode `legacy` avec cible de tests personnalisée :

```bash
python autonomous-coding/autonomous_agent_demo.py --mode legacy --project-dir ./my_project --target-tests 300
```

- Mode `orchestrated` avec cible de backlog planifiée :

```bash
python autonomous-coding/autonomous_agent_demo.py --mode orchestrated --project-dir ./my_project --target-tests 300
```

- `orchestrated` est le mode par défaut. Les alias `v1` et `v3_1` restent acceptés temporairement avec warning de dépréciation. `v2` n'est plus reconnu.

### 7.2 Flags CLI (résumé)

- `--project-dir` : dossier du projet cible.
- `--mode {legacy,orchestrated}` : runtime public. `v1` et `v3_1` restent acceptés temporairement comme alias avec warning ; `v2` est retiré.
- `--model` : même modèle pour toutes les phases.
- `--planner-model` / `--builder-model` / `--evaluator-model` : override par phase.
- `--max-rounds` : nombre max de rounds.
- `--max-iterations` : uniquement mode `legacy`.
- `--target-tests` : nombre cible minimum de tests appliqué aux prompts de planification/initialisation (défaut explicite: 200 avec warning).
- `--resume` : reprendre sur l’état existant.
- `--dry-run` : smoke test offline du mode `orchestrated`. Ne valide ni auth réelle, ni client SDK réel, ni appels LLM/outils réels.
- `--planner-only` / `--qa-only` : exécution partielle.
- `--provider {claude,openai}` : sélection explicite du provider runtime.
- `--auth-mode {api_key,cli,auto}` : stratégie d’authentification du provider sélectionné.
- `--llm-contract-review` : arbitrage modèle côté négociation de contrat.
- `legacy --dry-run` : rejet explicite avec code de sortie non nul, pour éviter un faux sentiment de couverture V1.

## 8) Artefacts produits

Dans `--project-dir` (souvent `generations/<nom>`):

- `planning/expanded_spec.md`
- `planning/architecture.md`
- `planning/acceptance_criteria.json`
- `planning/work_backlog.json`
- `planning/sprint_contract_round_XX.json`
- `planning/sprint_contract_negotiation_round_XX.json`
- `builder/build_report_round_XX.md`
- `qa/qa_report_round_XX.json`
- `qa/qa_report_round_XX.md`
- `state/round_state_XX.json`
- `state/run_state.json`

## 9) Fonctionnalités couvertes

- Orchestration multi-phase (planner/builder/evaluator).
- Contrats de sprint explicites par round.
- Négociation de contrat avec raison structurée (`reason_codes`, etc.).
- Validation schéma JSON des artefacts.
- Reprise de run robuste via état persistant.
- Telemetry token/coût (estimation best-effort).
- Garde-fous sécurité (sandbox + permissions + hooks Bash).
- Support outillage navigateur MCP (**Playwright prioritaire en mode headless par défaut**, Puppeteer fallback).

## 10) Tests et validation efficaces

Exécuter les tests unitaires/intégration locale :

```bash
pytest autonomous-coding/tests autonomous-coding/test_security.py -q
```

Tester la tuyauterie offline du mode orchestrated sans coûts API :

```bash
python autonomous-coding/autonomous_agent_demo.py --mode orchestrated --project-dir ./smoke_demo --dry-run --max-rounds 2 --llm-contract-review
```

Vérifier la cohérence des artefacts JSON :
- inspecter les fichiers sous `state/`, `planning/`, `qa/`,
- confirmer l’alignement avec `schemas/*.schema.json`.

Tester les chemins réels que le dry-run ne couvre pas :
- utiliser le workflow live manuel GitHub Actions `autonomous-coding-live-smoke`,
- ou lancer `pytest autonomous-coding/tests/test_live_phase_smoke.py -q -m live` avec `ANTHROPIC_API_KEY` et `AUTONOMOUS_CODING_ENABLE_LIVE_TESTS=1`.

## 11) Dépannage rapide

- **Auth en échec** :
  - mode `api_key` : `ANTHROPIC_API_KEY` requis,
  - mode `cli` : credentials/session CLI requis,
  - mode `auto` : au moins une méthode doit être disponible.
- **Erreurs de schéma JSON** : valider les artefacts contre `schemas/*.schema.json`.
- **Run bloqué en reprise** : vérifier `state/run_state.json` et le dernier `state/round_state_XX.json`.
- **QA navigateur indisponible** : vérifier Node.js/`npx` et l’exécution MCP.

## 12) Bonnes pratiques d’exploitation

- Toujours démarrer par une spec claire dans `app_spec.txt`.
- Garder `work_backlog.json` et critères d’acceptation concis et testables.
- Favoriser `orchestrated --dry-run` pour valider la tuyauterie offline avant run live.
- Ne pas utiliser `legacy --dry-run` comme signal de validation : la combinaison est rejetée explicitement.
- Utiliser le workflow live manuel quand il faut vérifier auth SDK, appels LLM réels, QA réelle et revue de contrat LLM.
- Utiliser `--resume` plutôt que relancer de zéro pour préserver la traçabilité.
