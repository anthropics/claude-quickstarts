# Sentry triage × Claude Managed Agents

A scheduled [Managed Agent](https://platform.claude.com/docs/en/managed-agents/overview)
that uses Sentry's hosted MCP server to rank the last 24 hours of issues and,
when available, ask Seer for root-cause analysis and remediation guidance. It
writes a one-page `TRIAGE_REPORT.md`. No host process stays running: the cron
schedule and the refreshable Sentry OAuth credential both live on Anthropic's
platform.

```
cron (0 9 * * 1-5) ──▶ deployment ──▶ Managed Agents session
                                         │  Sentry MCP tools:
                                         │  search + issue context
                                         │  + Seer RCA when available
                                         ▼
                        vault: mcp_oauth credential injected
                        on the connection to mcp.sentry.dev
                                         ▼
                        TRIAGE_REPORT.md in /mnt/session/outputs/
```

The Sentry credential is an `mcp_oauth` vault credential keyed to
`https://mcp.sentry.dev/mcp`. Anthropic attaches it to the agent's connection
to that server and refreshes it with the stored refresh token. The sandbox
never holds a token, and the model never sees one.

## Quickstart

You need:

- [Claude Code](https://docs.claude.com/en/docs/claude-code)
- [uv](https://docs.astral.sh/uv/)
- the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart)
  1.34 or later (`brew install anthropics/tap/ant`) and `jq`
- Anthropic auth: `ant auth login` once, or `ANTHROPIC_API_KEY` in `.env`
- a Sentry account with access to the organization and project to triage

```bash
cd managed-agents/sentry
./start.sh
```

`start.sh` installs or updates [Sentry's Agent Plugin for Claude
Code](https://docs.sentry.io/ai/agent-plugin/) at project scope
(`.claude/settings.json` records it), then starts Claude with this repository's
walkthrough. The plugin gives the setup conversation an authenticated Sentry MCP
connection, so Claude can list your organizations and projects and confirm the
target with you instead of guessing. If Claude reports the plugin's `sentry`
server as unauthenticated, run `/mcp` inside Claude Code and sign in; that is
the first of two browser authorizations.

The second opens during `./agents/setup.sh`, and it is expected: Claude Code
owns the plugin's OAuth session and does not share it, while scheduled Managed
Agents sessions need their own credential in an Anthropic vault.
`oauth_setup.py` obtains that grant with PKCE and writes the access and refresh
tokens straight to the vault. No Sentry token goes into `.env`, a command-line
argument, or the agent prompt. On Sentry's approval screen, leave only
**Inspect Issues & Events** and **Seer** checked; untick **Triage Issues** and
**Manage Projects & Teams**. The agent independently allowlists only four MCP
tools (`search_issues`, `search_events`, `get_sentry_resource`,
`analyze_issue_with_seer`), so the grant and the tool list are both read-only.

The guide provisions the resources, creates the schedule, runs it once,
downloads the report, and asks whether to leave the schedule active.

## By hand

The same steps, without Claude Code:

```bash
ant auth login                                     # or put ANTHROPIC_API_KEY in .env
uv sync
./agents/setup.sh --org <org-slug> --project <project-slug>   # omit the flags to be prompted
uv run python deploy.py                            # schedules it: weekday mornings, 9 AM Eastern
uv run python run_now.py                           # manual run: streams the session, downloads TRIAGE_REPORT.md to reports/<session_id>/
```

`setup.sh` records the two non-secret slugs in ignored `sentry-config.json`,
then runs [`ant apply`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/apply)
on three files: the agent in [`agents/sentry-triage.md`](agents/sentry-triage.md),
whose frontmatter is the configuration and whose prose is the system prompt,
the environment in [`environments/sentry-triage.yaml`](environments/sentry-triage.yaml),
and the vault in [`vaults/sentry-triage.yaml`](vaults/sentry-triage.yaml).
`ant apply` creates them and records their IDs in `claude-lock.json`, which
`deploy.py` reads. The one thing it never touches is a secret, so `setup.sh`
then runs `oauth_setup.py`, which opens the browser authorization, creates the
credential with `ant beta:vaults:credentials create`, and probes it with
`ant beta:vaults:credentials mcp-oauth-validate`. Re-running `setup.sh` reuses
the credential, publishes any file edits as a new agent version, and re-pins
the deployment to it. This repository ignores `claude-lock.json`, since every
reader creates their own resources. In a project of your own, commit it.

## What a run does

1. Search the selected project for unresolved issues seen in the last 24 hours.
2. Pull representative events, stack traces, release and trace context for the
   highest-impact candidates.
3. Classify issues as new, regression, escalating, or ongoing and rank by users
   affected.
4. Call `analyze_issue_with_seer` for the top issues. If Seer is unavailable
   for the organization, stop retrying and continue with clearly labeled model
   hypotheses.
5. Write a one-page report with explicit Seer availability, evidence, root
   cause, and remediation guidance.

The agent treats all Sentry content and Seer output as untrusted data. It does
not resolve issues, modify code, run Autofix, or open pull requests.

## Files

| | |
|---|---|
| `start.sh` | Installs or updates the Claude Code Sentry plugin, then launches the guided setup |
| `.claude/settings.json` | Enables the plugin at project scope (written by `start.sh`) |
| `agents/sentry-triage.md`, `environments/sentry-triage.yaml`, `vaults/sentry-triage.yaml` | The agent, environment, and vault, as files for `ant apply` |
| `agents/setup.sh` | Records the slugs, `ant apply`, then the OAuth credential if the vault has none, and the deployment sync on re-runs |
| `oauth_setup.py` | Browser OAuth with PKCE; creates and validates the `mcp_oauth` credential |
| `managed_agents.py` | Shared client, env and `sentry-config.json` loading, `claude-lock.json` lookup, event streaming |
| `deploy.py` | `deployments.create` with a cron schedule, or `update` to re-pin an existing one |
| `run_now.py` | Manual trigger, stream the session, download the report |
| `runs.py` | Run history and failures |
| `teardown.py` | Archive everything, clear the deployment ID from `.env`, remove `claude-lock.json` |
| `skill.md` | Mental model, gotchas, setup checklist, debugging |

Requires `anthropic` ≥ 1.9.0.

## Credential lifecycle and re-authentication

The vault credential holds Sentry MCP's access token and refresh token. Before
a session connects, Anthropic re-resolves the credential and, if the access
token has expired, exchanges the refresh token at the token endpoint recorded
in the credential. No user action is involved as long as that exchange
succeeds.

Re-authentication is needed when the exchange stops succeeding: the grant was
revoked in Sentry, the upstream Sentry session behind it lapsed, or the refresh
token was rejected. The next run then fails with
`mcp_authentication_failed_error`, and `vault_credential.refresh_failed` is
emitted to any webhook you have registered. Archive the credential and re-run
setup; the vault no longer lists an active credential for the MCP URL, so
`setup.sh` opens the browser again:

```bash
ant beta:vaults:credentials list --vault-id <vault-id>      # find the credential ID
ant beta:vaults:credentials archive --vault-id <vault-id> --credential-id <credential-id>
./agents/setup.sh
```

The vault ID is in `claude-lock.json` under `./vaults/sentry-triage.yaml`. To
check credential health at any time:

```bash
ant beta:vaults:credentials mcp-oauth-validate \
  --vault-id <vault-id> --credential-id <credential-id>
# status: valid | invalid | unknown, with the failing refresh or MCP step
```

## Known limitations

### SSO-enforced organizations, and any org that rejects user-bound OAuth tokens

The Managed Agents vault presents every MCP credential, `mcp_oauth` and
`static_bearer` alike, as `Authorization: Bearer <token>`. Neither credential
type has a field for a different scheme.

On Sentry's hosted MCP server, `Bearer` always means a token minted by the
server's own OAuth flow. That token is bound to the user who approved it and
inherits that user's standing in the organization: SSO link, 2FA, membership.
Organizations with enforced SSO or similar identity policies can reject such
tokens on every API call. Testing against Sentry's own organization showed
this as HTTP 403 on all calls after a successful consent; the exact response
depends on the organization's configuration, so treat any SSO-enforced or
policy-restricted org as potentially affected until a manual run proves
otherwise. The symptoms are `mcp_authentication_failed_error` on the session,
403 from Sentry inside the MCP tool results, or an `invalid` verdict from the
`mcp-oauth-validate` probe that `oauth_setup.py` runs right after saving the
credential.

The standard answer for unattended automation in such organizations is an
organization-issued token (an org auth token or an internal integration
token), which is not tied to a user's session. The hosted MCP server accepts
those only as `Authorization: Sentry-Bearer <token>`. That scheme name is a
fixed property of `mcp.sentry.dev`, the same for every organization, and it is
the only way to hand an org-issued token to the remote server; it is not
something an org configures. Since the vault cannot send anything but `Bearer`,
this quickstart cannot serve those organizations until the platform adds an
authorization-scheme option to `static_bearer`. The same gap applies to any
MCP server that uses a non-`Bearer` scheme for pre-issued tokens.

The interactive plugin path is unaffected, because Claude Code holds that OAuth
session itself. If you need a scheduled triage for such an organization now,
the previous revision of this quickstart works: it ran `sentry-cli` in the
sandbox against Sentry's REST API, which accepts `Bearer` for org auth tokens,
with an `environment_variable` vault credential instead of MCP. Read it with
`git show 97c825e:managed-agents/sentry/README.md`.

### MCP tool permissions after agent updates

After `ant apply` publishes a new agent version, check in the Managed Agents
Console that the four Sentry MCP tools are still enabled with **always allow**
and that the rest remain disabled. A scheduled run has no one to answer an
`always_ask` prompt, so a permission that drifts back to the platform default
parks the session instead of writing the report.
