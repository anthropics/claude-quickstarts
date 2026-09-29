# Sentry triage × Claude Managed Agents

Scheduled deployment: cron → Managed Agents session → Sentry MCP search and
optional Seer RCA → `/mnt/session/outputs/TRIAGE_REPORT.md`. Sentry auth is a
refreshable `mcp_oauth` vault credential; the sandbox never holds a token.

## When the user asks to set this up, get it working, or debug it

1. **Invoke `/claude-api` first.** That skill loads the full Managed Agents API reference (agents, sessions, environments, events, webhooks, deployments, vaults, memory stores). Use it as the source of truth for any SDK call or resource file you edit. Don't guess field names.
2. **Read `./skill.md`** and walk the user through its checklist in order. It has the gotchas (vault always sends `Authorization: Bearer`, `allow_mcp_servers` vs `allowed_hosts`, archive-to-reauthorize, deployment pins an agent version, DST cron semantics, auto-pause) and the debugging table.
3. **Use the installed Sentry plugin** to list the organizations and projects the user can access, and ask them to pick the target. Never guess. If the plugin's `sentry` MCP server is not authenticated, ask the user to run `/mcp` and sign in.
4. **Explain the two OAuth grants** before the second browser window opens: Claude Code's plugin credential serves this conversation; the grant `oauth_setup.py` saves to the vault serves unattended runs. Never inspect or copy Claude Code's credential storage, and never put a Sentry token in `.env`, a shell variable, or the agent prompt.
5. **Run the flow**: `uv sync`, then `./agents/setup.sh --org <slug> --project <slug>` (stop while the user approves in the browser; on Sentry's screen only **Inspect Issues & Events** and **Seer** stay checked), then `uv run python deploy.py`, then `uv run python run_now.py`. Read the `credential: validation status` line from setup and any `session.error` from the run, and inspect the downloaded report.
6. **Recognize the SSO limitation.** If validation says `invalid`, or the first run fails with `mcp_authentication_failed_error` or 403s inside tool results, the organization is rejecting the user-bound MCP OAuth token (SSO enforcement or a similar policy; not specific to any one org). The org-issued token that would work needs `Authorization: Sentry-Bearer`, and the vault can only send `Bearer`. Do not loop on re-authorizing. Show the user the README's "Known limitations" and the `sentry-cli` alternative it points to.
7. **Do not leave the schedule active without asking.** `uv run python teardown.py` removes everything for a disposable evaluation.

Provisioning is `./agents/setup.sh` (ant 1.34 or later, `jq`, `uv`): it records the slugs in ignored `sentry-config.json`, runs `ant apply --yes agents environments vaults`, which creates the agent, environment, and vault and records their IDs in `claude-lock.json`, then runs `oauth_setup.py` when the vault has no credential for `https://mcp.sentry.dev/mcp`. Re-runs publish file edits as a new agent version and re-pin the deployment through `deploy.py`. If `ant apply` prints `refusing to apply`, show the user the reason before reaching for `--force`.

The agent uses `mcp_servers` + a fail-closed `mcp_toolset` with four tools enabled (`search_issues`, `search_events`, `get_sentry_resource`, `analyze_issue_with_seer`). A new resource is one more file (`memory_stores/<name>.yaml`, another `vaults/<name>.yaml`) added to the `ant apply` line in `setup.sh`; its ID lands in `claude-lock.json`, read it with `lockfile_id()` the way `deploy.py` does.
