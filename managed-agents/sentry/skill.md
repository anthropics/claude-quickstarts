# Setup tips & tricks: scheduled Sentry triage with an MCP OAuth vault credential

Things that aren't obvious from the docs and tend to cost debugging time. Use
the checklist at the bottom when walking someone through the quickstart.

---

## Mental model

### Two Sentry authorizations, on purpose

```
./start.sh
  ├─ installs/updates the Sentry plugin for Claude Code (.claude/settings.json)
  └─ launches this guided setup
       │
       ├─ plugin MCP (Claude Code's own OAuth; /mcp to sign in):
       │    list orgs and projects, confirm the target with the user
       │
       └─ ./agents/setup.sh --org <slug> --project <slug>
            ├─ sentry-config.json: the two non-secret slugs
            ├─ ant apply: agent + environment + vault → claude-lock.json
            └─ oauth_setup.py: browser grant → mcp_oauth credential in the vault
                               → mcp-oauth-validate probe

cron → deployment → session ──(vault injects token)──▶ mcp.sentry.dev
                                                        issues + optional Seer RCA
                                                        └── TRIAGE_REPORT.md
```

Claude Code owns the plugin's credential and does not expose it; the vault owns
the scheduled agent's credential and Anthropic refreshes it. Never inspect or
copy Claude Code's credential files, and never put a Sentry token in `.env`,
the shell environment, or the agent prompt.

### Where the token lives

An `mcp_oauth` credential is keyed by `mcp_server_url`. When a session's agent
declares an `mcp_servers` entry with exactly that URL, Anthropic attaches the
token to the connection outside the sandbox. The container never holds it, so
there is nothing for a prompt injection to read. Two things must match
character for character: the agent's `mcp_servers[].url` and the credential's
`auth.mcp_server_url`, both `https://mcp.sentry.dev/mcp`.

What this doesn't give you: the agent can do anything the grant and the
enabled tools allow. Both are read-only here. The grant is what the user
approved on Sentry's consent screen (**Inspect Issues & Events** and **Seer**
only) and the `mcp_toolset` is fail-closed with four tools enabled, so tools
Sentry adds later do not appear.

### A deployment is the whole host process

A **deployment** bundles the agent, environment, vault, and initial user
message with a cron schedule. Sessions start themselves on Anthropic infra.
Nothing runs on your machine after `deploy.py`.

---

## Gotchas

### The vault always sends `Authorization: Bearer`

Both MCP credential types (`mcp_oauth`, `static_bearer`) present the token as
`Authorization: Bearer <token>`; there is no field for another scheme. On
Sentry's hosted MCP server, `Bearer` means a token from its own OAuth flow,
which is bound to the approving user and inherits that user's standing in the
org. SSO-enforced or otherwise policy-restricted organizations can reject that
token on every call (seen as 403s on Sentry's own org; assume any SSO org may
behave this way until a manual run proves otherwise). The fix those orgs
expect, an org auth token or internal integration token, reaches the server
only as `Authorization: Sentry-Bearer <token>`, a fixed scheme of
`mcp.sentry.dev` that no org can change and the vault cannot send. The consent
completes and the credential saves either way, so `oauth_setup.py` runs
`mcp-oauth-validate` right after create to catch it when the probe can. There
is no in-vault workaround; the README's "Known limitations" has the details and
the `sentry-cli` alternative.

### `allow_mcp_servers` is separate from `allowed_hosts`

Under `networking.type: limited`, the sandbox's `allowed_hosts` gates what
shell commands can reach, and `allow_mcp_servers: true` is the separate opt-in
for the platform's own connection to declared MCP servers. This environment
keeps `allowed_hosts: []`, so `bash` has no network and Sentry is reachable
only through the MCP tools. Drop `allow_mcp_servers` and the session fails with
`mcp_egress_blocked_error`.

### The credential is created once, and archiving is how you re-authorize

`setup.sh` lists the vault's credentials and skips OAuth if one already
matches the MCP URL. Archived credentials are not listed, so the re-auth path
is: archive, re-run `setup.sh`, approve in the browser. The vault ID is in
`claude-lock.json` under `./vaults/sentry-triage.yaml`:

```bash
ant beta:vaults:credentials list --vault-id <vault-id>
ant beta:vaults:credentials archive --vault-id <vault-id> --credential-id <credential-id>
./agents/setup.sh
```

`mcp_server_url`, `token_endpoint`, and `client_id` are immutable on a
credential, which is why replacement rather than update is the path.

### The deployment pins an agent version

An agent update writes a new agent version, and sessions you start by hand use
the latest. The deployment doesn't: it keeps the version it pinned at create
time, so a prompt edit alone never reaches scheduled runs. Re-running
`./agents/setup.sh` does both halves: `ant apply` publishes the change, then
`deploy.py` (which setup runs when `.env` has a deployment ID) calls
`deployments.update` to re-pin to the latest. The bare agent ID means "latest
version". The same call sends the environment ID, `vault_ids`, and the first
message, because the deployment also keeps the ones it was created with. That
matters after you recreate a vault or environment, or change the org or project
in `sentry-config.json`.

### Cron is wall-clock, with DST edges

`0 9 * * 1-5` in `America/New_York` fires at 9:00 AM Eastern regardless of
DST. Times that don't exist on spring-forward day are skipped, and times that
occur twice on fall-back day fire twice. If that matters, schedule outside 1-3
AM local or use UTC. Runs may start up to 10 seconds late, granularity is
per-minute, and an org can have up to 1,000 deployments.

After `deployments.create`, check `schedule.upcoming_runs_at` in the response
to confirm the expression fires when you expect (`deploy.py` prints it).

### Permanent failures auto-pause the deployment

`vault_not_found_error`, `agent_archived_error`, and
`environment_archived_error` pause the deployment and set `paused_reason`, so a
misconfigured deployment doesn't keep failing on schedule indefinitely.
Transient failures (rate limits, backend errors) don't pause. `runs.py` lists
both: every trigger writes a deployment run record with `error.type` when no
session was produced.

### `pause` is not `archive`

`pause` stops future scheduled triggers. In-flight sessions keep running, and
manual runs still work while paused. `unpause` resumes from the next occurrence
(missed runs are not backfilled). `archive` is terminal.

### Report files lag the session by a few seconds

The agent writes to `/mnt/session/outputs/`, which the Files API captures
automatically. Indexing can lag 1-3 seconds after the session goes idle, so
`run_now.py` retries the empty list a few times before giving up.

### Seer unavailable is not an auth failure

Seer may be unavailable because the organization has not enabled it, the plan
does not include it, repository/code mappings are absent, or the issue category
is not supported. The agent tries once per run, then labels the rest **Model
hypothesis** instead of retrying. A Seer result is evidence-backed advice, not
permission to run Autofix or open a pull request.

---

## Setup checklist

1. Confirm `uv`, `ant` 1.34+, `jq`, and Claude Code are installed. Sign in
   once with [`ant auth login`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart)
   or put only `ANTHROPIC_API_KEY` in `.env`. The `ant` CLI and the SDK share
   the login.
2. Use the Sentry plugin's MCP tools to list the organizations and projects the
   user can access. If the plugin's `sentry` server is not authenticated, ask
   the user to run `/mcp` and sign in. Ask them to choose the target; do not
   infer a production project.
3. `uv sync`.
4. `./agents/setup.sh --org <organization-slug> --project <project-slug>` →
   writes `sentry-config.json`, `ant apply` creates the agent, environment, and
   vault and writes `claude-lock.json`, then `oauth_setup.py` opens the
   browser. Explain the second consent before it opens and stop while the user
   completes it. Read back the `credential: validation status` line; `invalid`
   means the SSO/custom-scheme limitation above.
5. `uv run python deploy.py` → reads the three IDs from `claude-lock.json`,
   creates the deployment, appends `CLAUDE_DEPLOYMENT_ID` to `.env`. Check the
   printed upcoming runs.
6. `uv run python run_now.py` → streams a manual run and downloads
   `TRIAGE_REPORT.md` to `reports/<session_id>/`. Watch for `session.error`,
   especially `mcp_authentication_failed_error`.
7. Verify the report: searches are constrained to the selected org and project,
   top issues are ranked by users affected, Seer status is explicit, each top
   issue labels either **Seer RCA** or **Model hypothesis**, and no issue state,
   code, or pull request was changed.
8. Ask before leaving the cron deployment active. `uv run python runs.py` shows
   history.

To change the prompt or model later, edit `agents/sentry-triage.md` and re-run
`./agents/setup.sh`. It publishes the change and re-pins the deployment (see
the gotcha above).

To stop: `uv run python teardown.py` archives the deployment and everything in
`claude-lock.json` (the vault's credential goes with it), then removes the
deployment ID from `.env` and deletes the lockfile. Skip it to leave the
schedule running. Afterwards `./agents/setup.sh` and `deploy.py` start from
scratch. If teardown fails partway, fix the cause and run it again.

## Debugging a failed run

| Symptom | Likely cause |
|---|---|
| `mcp_authentication_failed_error` on the first run, or `mcp-oauth-validate` says `invalid` right after setup | The organization rejects the user-bound MCP OAuth token (SSO enforcement or a similar policy). The org-issued token it would accept needs `Sentry-Bearer`, which the vault cannot send. See the README's "Known limitations" |
| `mcp_authentication_failed_error` after runs that used to work | Refresh failed: grant revoked or upstream session lapsed. `mcp-oauth-validate` shows the failing step. Archive the credential and re-run `./agents/setup.sh` |
| `mcp_egress_blocked_error` | `allow_mcp_servers: true` missing from the environment's `networking`. Restore it and re-run setup |
| Session runs but never calls a Sentry tool | `mcp_toolset` missing or its `mcp_server_name` does not match the `mcp_servers` entry, or the tools were disabled in the Console after an agent update |
| Session parks waiting for a confirmation | A tool's `permission_policy` is `always_ask`. Scheduled runs have no one to answer; set it back to `always_allow` and re-pin |
| 403 from Sentry inside a tool result | The grant lacks the skill (approve **Inspect Issues & Events** and **Seer**), or the organization rejects user-bound OAuth tokens (see the first row) |
| `runs.py` shows `vault_not_found_error` or `vault_archived_error` | Vault deleted or archived while the deployment still references it. `ant apply` notices too and refuses to guess: run `ant apply --force --yes vaults` to create a replacement, then `./agents/setup.sh`, which adds the credential to the new vault and points the deployment's `vault_ids` at it. The failure paused the deployment, so finish with `ant beta:deployments unpause --deployment-id $CLAUDE_DEPLOYMENT_ID` |
| `ant apply` prints `refusing to apply` | A resource in `claude-lock.json` was changed, archived, or deleted in the Console. The plan says which and why. `--force` overwrites the edit or creates a replacement |
| Scheduled time passed, no run record | Deployment paused (check `paused_reason`), or you're checking before the up-to-10s jitter |
| `run_now.py` finds no files | Report indexing lag. The script retries, but if it still comes up empty, check the streamed transcript for whether the agent wrote the file |

---

## Production notes

- Keep the grant read-only. A prompt injection in an issue title can at worst
  read what the on-call engineer could; with **Triage Issues** approved it
  could resolve or reassign issues.
- The report lands in the session's files, not your inbox. For delivery,
  register a `session.status_idled` webhook, download the report, and post it
  to Slack (the [`../slack`](../slack) quickstart has the webhook pattern).
  Subscribe to `vault_credential.refresh_failed` on the same webhook to hear
  about a lapsed grant before the next morning's run fails.
