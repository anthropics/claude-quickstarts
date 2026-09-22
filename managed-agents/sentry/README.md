# Sentry triage × Claude Managed Agents

A scheduled [Managed Agent](https://platform.claude.com/docs/en/managed-agents/overview) that pulls the last 24 hours of Sentry issues with `sentry-cli` and writes a prioritized triage report. No host process: the cron schedule lives server-side as a deployment.

```
cron (0 9 * * 1-5) ──▶ deployment ──▶ session (sandbox)
                                         │  sentry-cli / curl with
                                         │  placeholder token
                                         ▼
                          egress proxy: placeholder → real token,
                              Sentry API hosts only
                                         ▼
                        TRIAGE_REPORT.md in /mnt/session/outputs/
```

The Sentry token is an `environment_variable` vault credential. The sandbox holds an opaque placeholder, and the egress proxy substitutes the real token only on requests to Sentry's API hosts (`sentry.io`, `us.sentry.io`, `de.sentry.io`). The model never sees the secret. The same pattern works for `gh`, `twilio`, `vercel`, or any other CLI that authenticates via an env var.

## Quickstart

Needs [uv](https://docs.astral.sh/uv/), the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart) 1.34 or later (`brew install anthropics/tap/ant`), `jq`, a Sentry auth token, and Anthropic auth: `ant auth login` once, or an API key from [platform.claude.com](https://platform.claude.com/).

```bash
cd managed-agents/sentry
uv sync
claude "walk me through setting this up"   # reads skill.md and drives the rest
```

Claude walks through the Sentry token, the vault, agent, and environment, the cron deployment, then a manual test run.

Or by hand:

```bash
ant auth login                # or put ANTHROPIC_API_KEY in .env
cp .env.example .env          # fill in SENTRY_AUTH_TOKEN, SENTRY_ORG, SENTRY_PROJECT
./agents/setup.sh             # `ant apply` creates the agent, environment, and vault; then the token goes into the vault
uv run python deploy.py       # schedules it: weekday mornings, 9 AM Eastern
uv run python run_now.py      # manual run: streams the session and downloads TRIAGE_REPORT.md to reports/<session_id>/
```

`setup.sh` runs [`ant apply`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/apply) on three files: the agent in [`agents/sentry-triage.md`](agents/sentry-triage.md), whose frontmatter is the configuration and whose prose is the system prompt, the environment in [`environments/sentry-triage.yaml`](environments/sentry-triage.yaml), and the vault in [`vaults/sentry-triage.yaml`](vaults/sentry-triage.yaml). `ant apply` creates them and records their IDs in `claude-lock.json`, which `deploy.py` reads. The one thing it never touches is a secret, so `setup.sh` then puts the Sentry token into the vault as a credential with `ant beta:vaults:credentials create`. To change the agent (model, prompt, tools), edit its file and re-run `./agents/setup.sh`: apply publishes a new version of the same agent, and setup re-pins the deployment to it. This repository ignores `claude-lock.json`, since every reader creates their own resources. In a project of your own, commit it.

## Files

| | |
|---|---|
| `agents/sentry-triage.md`, `environments/sentry-triage.yaml`, `vaults/sentry-triage.yaml` | The agent, environment, and vault, as files for `ant apply` |
| `agents/setup.sh` | `ant apply`, then the token credential, and the deployment sync on re-runs |
| `managed_agents.py` | Shared client, env loading, `claude-lock.json` lookup, event streaming |
| `deploy.py` | `deployments.create` with a cron schedule, or `update` to re-pin an existing one |
| `run_now.py` | Manual trigger, stream the session, download the report |
| `runs.py` | Run history and failures |
| `teardown.py` | Archive everything, clear the deployment ID from `.env`, remove `claude-lock.json` |
| `skill.md` | Mental model, gotchas, setup checklist, debugging |

Requires `anthropic` ≥ 0.109.0.
