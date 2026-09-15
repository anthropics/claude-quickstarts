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

Needs [uv](https://docs.astral.sh/uv/), the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart) 1.19 or later (`brew install anthropics/tap/ant`), a Sentry auth token, and Anthropic auth: `ant auth login` once, or an API key from [platform.claude.com](https://platform.claude.com/).

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
./agents/setup.sh             # creates the vault + credential, environment, and agent, writes their IDs to .env
uv run python deploy.py       # schedules it: weekday mornings, 9 AM Eastern
uv run python run_now.py      # manual run: streams the session and downloads TRIAGE_REPORT.md to reports/<session_id>/
```

To change the agent (model, prompt, tools), edit [`agents/sentry-triage/agent.yaml`](agents/sentry-triage/agent.yaml) and re-run `./agents/setup.sh`. It pushes a new agent version and re-pins the deployment to it.

## Files

| | |
|---|---|
| `agents/sentry-triage/` | The vault, environment, and agent definitions `setup.sh` provisions |
| `agents/setup.sh` | Vault + credential + environment + agent, and the deployment sync on re-runs |
| `managed_agents.py` | Shared client, env loading, event streaming |
| `deploy.py` | `deployments.create` with a cron schedule |
| `run_now.py` | Manual trigger, stream the session, download the report |
| `runs.py` | Run history and failures |
| `teardown.py` | Archive everything and clear the IDs from `.env` |
| `skill.md` | Mental model, gotchas, setup checklist, debugging |

Requires `anthropic` ≥ 0.109.0.
