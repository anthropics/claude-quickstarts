# Sentry triage × Claude Managed Agents

Scheduled deployment: cron → Managed Agents session with `sentry-cli` and a vault env-var credential → triage report in `/mnt/session/outputs/`.

## When the user asks to set this up, get it working, or debug it

1. **Invoke `/claude-api` first.** That skill loads the full Managed Agents API reference (agents, sessions, environments, events, webhooks, deployments, vaults, memory stores). Use it as the source of truth for any SDK call you write or edit. Don't guess field names.
2. **Read `./skill.md`** and walk the user through it step by step. It has the ordered checklist, every gotcha (two separate host allowlists, immutable `secret_name`, replace-only `allowed_hosts`, DST cron semantics, auto-pause on permanent failures), and the debugging table.
3. **After the base schedule works, offer extensions.** Ask the user which (if any) they want, then edit `agents/sentry-triage.md`, `environments/sentry-triage.yaml`, or `vaults/sentry-triage.yaml` and re-run `./agents/setup.sh`, whose `ant apply` publishes the edit as a new agent version and whose last step re-pins the deployment, and/or edit `deploy.py` for the deployment side. A new resource is one more file (`memory_stores/<name>.yaml`, another `vaults/<name>.yaml`) added to the `ant apply` line in `setup.sh`; its ID lands in `claude-lock.json`, read it with `lockfile_id()` the way `deploy.py` does.
   - **Deliver the report** instead of leaving it in the sandbox: a `session.status_idled` webhook that downloads the report and posts to Slack (see [`../slack`](../slack) for the bridge pattern)
   - **More CLIs**: add other env-var-authenticated CLIs as additional vault credentials, one credential per token with its own host allowlist (another `ant beta:vaults:credentials create` block in `setup.sh`)
   - **Outcomes**: rubric-graded iterate loop (`user.define_outcome` event instead of `user.message` in `initial_events`)
   - **Memory store**: track issue history across runs so the agent can flag regressions it has seen before (add `memory_stores/<name>.yaml` and `memory_stores` to the `ant apply` line in `setup.sh`, then `resources: [{type: "memory_store", ...}]` on the deployment in `deploy.py`)

   Pull exact shapes from the `/claude-api` skill's `shared/managed-agents-*.md` docs.

Provisioning is `./agents/setup.sh` (ant 1.34 or later, `jq`): it runs `ant apply --yes agents environments vaults`, which creates the agent, environment, and vault from those directories and records their IDs in `claude-lock.json`, then adds the Sentry token to the vault as an `environment_variable` credential (skipped when the vault already has one), and on re-runs publishes file edits onto the same resources and re-pins the deployment through `deploy.py`. If `ant apply` prints `refusing to apply`, a resource was changed or archived in the Console: show the user the reason before reaching for `--force`. Schedule with `uv run python deploy.py`. Smoke-test with `uv run python run_now.py`.
