# Daily brief on Claude Managed Agents

A scheduled deployment, not an app: there is no long-running process in this quickstart. `agents/daily-brief/` holds six resource files that `ant apply` reconciles (agent, environment, two memory stores, vault, deployment). `ant apply` manages the vault container but never its contents, so `agents/setup.sh` adds the two credentials with `ant beta:vaults:credentials create` and writes the vault's ID into `deployment.md`'s `vault_ids` (a deployment takes vault IDs, not a file reference). Each scheduled run is a fresh session: it reads `/mnt/memory/preferences/preferences.md` (read-only store), reads and writes `/mnt/memory/state/` (bookmarks, ledger, notes, run records), calls Slack with `curl` and a vault-substituted `$SLACK_BOT_TOKEN`, and reads GitHub through the MCP server with a read-only token from the same vault.

```
cron (deployment.md) ──▶ session ──▶ agent.md run steps
                           │  resources: preferences (ro), state (rw)
                           │  vault: SLACK_BOT_TOKEN (env var, slack.com only), GitHub static_bearer
                           │  budget: $5 per run
                           ▼
        Slack conversations.history / chat.postMessage (curl)     GitHub MCP (read-only)
```

Needs `ant` 1.34 or later (the first release whose `ant apply` manages vaults) and `jq`.

## When the user asks to set this up, get it working, or debug it

1. **Invoke `/claude-api` first.** It loads the Managed Agents reference (deployments, memory stores, vaults, webhooks, permission policies). Use it as the source of truth for any field you edit. Don't guess field names.
2. **Walk the README's Quickstart in order.** Slack app (the one-click link) and its bot token, GitHub read-only token, `.env`, `agents/setup.sh`, `preferences.md` plus `scripts/seed-preferences.sh`, `scripts/run.sh`, unpause.
3. **Check a run with `scripts/run.sh`**, not by waiting for the schedule. It prints `session.error` events (an unreadable source shows up there, e.g. `mcp_authentication_failed_error` naming `github`), the agent's last message, and the run records in the state store. `ant beta:sessions connect <id>` follows a run live.
4. **Common failures and what they mean:**
   - `mcp_egress_blocked_error` when a run starts: `environment.yaml` lost `allow_mcp_servers: true`.
   - `400 invalid value for string field amount`: the budget amount must be a quoted string, in cents.
   - `ant apply` plans 3 resources instead of 5: memory stores in `deployment.md` must be `- path: ./memory_store_x.yaml` entries, not `memory_store_id: ./...`.
   - Slack `not_authed`: no vault attached (`vault_ids` empty in `deployment.md`; re-run `agents/setup.sh`) or the credential's `allowed_hosts` does not include `slack.com`. `invalid_auth`: wrong token. `not_in_channel`: invite the bot.
   - `ant apply` says it cannot tell what kind of resource `vault.yaml` is: the file lost its `type: vault` line, or `ant` is older than 1.34.
   - Run record says `status: held`: the post could not reach the destination. Nothing else in state changed, by design.
   - The agent starts hunting for tokens or writes workarounds into `notes.md`: the run steps forbid both. If you edit the steps, keep those two rules.
   - Keep `web_search` and `web_fetch` disabled in `agent.md`: they run outside the sandbox, so `environment.yaml`'s allowlist does not apply to them.
5. **Keep the deployment paused while testing** (`agents/setup.sh` pauses it on creation; manual runs work while paused). `scripts/reset-state.sh` empties the state store afterwards; `scripts/teardown.sh` removes all six resources.

## Conventions

- Resource files are commented for a first-time reader. Keep the comments in sync when you change a field.
- The "Create the Slack app" link in README.md is `slack/manifest.yaml` URL-encoded. After editing the manifest, regenerate it with the one-liner in the HTML comment above the link in README.md and paste it in.
