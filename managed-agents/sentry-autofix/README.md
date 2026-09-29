# Sentry × Claude Managed Agents: fix production errors with a pull request

A new error lands in [Sentry](https://sentry.io/). A [Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview) session reads the stack trace and [Seer](https://docs.sentry.io/product/ai-in-sentry/seer/)'s root cause analysis through the [Sentry MCP server](https://mcp.sentry.dev/), reproduces the bug with a failing test in a clone of your repository, fixes it, and opens a pull request that says `Fixes SHOP-1A`. You review and merge. Sentry resolves the issue when a release contains the merge commit.

The host is about 600 lines of TypeScript: a webhook route, one `sessions.create` per issue, a loop that answers the agent's one custom tool, and a Sentry OAuth login helper. It stores nothing. A session's metadata says which issue it is for and its event log says how far the fix got. Webhook retries don't start a second fix, and a host that restarted mid-fix picks the session back up the next time the issue is delivered or you run `npm run fix` for it.

`demo-app/` is a small Express checkout service with a real bug to try it on: any cart without a coupon code returns a 500.

## Quickstart

Needs:

- [Claude Code](https://docs.claude.com/en/docs/claude-code), for the guided setup
- Node 22.9 or later
- The [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart) 1.34 or later (`brew install anthropics/tap/ant`), `jq`, and Anthropic auth: `ant auth login` once, or an API key from [platform.claude.com](https://platform.claude.com/)
- A Sentry organization. Seer is a paid add-on. Without it the agent works from the stack trace alone and says so in the pull request.
- A GitHub repository whose default branch has a [ruleset](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets) that requires a pull request, and a [fine-grained token](https://github.com/settings/personal-access-tokens) for that one repository with Contents and Pull requests set to read and write

```bash
cd managed-agents/sentry-autofix
./start.sh
```

`start.sh` installs or updates [Sentry's Agent Plugin for Claude Code](https://docs.sentry.io/ai/agent-plugin/) at project scope (`.claude/settings.json` records it), then starts Claude with the walkthrough in [`CLAUDE.md`](CLAUDE.md). The plugin gives the setup conversation an authenticated Sentry MCP connection. Claude lists your organizations and projects for you to choose from, and later finds the demo issue's short ID.

You authorize Sentry twice, because two clients hold separate credentials:

1. **The plugin.** If Claude reports the plugin's `sentry` server as unauthenticated, run `/mcp` inside Claude Code and sign in. Claude Code owns that OAuth session and doesn't share it.
2. **The vault.** Sessions that a webhook starts need their own credential. `./agents/setup.sh` runs `npm run sentry-login`, which prints a URL, obtains a grant with PKCE, and writes the access and refresh tokens to an Anthropic vault. No Sentry token goes into `.env`, a command-line argument, or the agent prompt.

On Sentry's approval screen for the second one, leave only **Inspect Issues & Events** and **Seer** checked. `sentry-login` requests three of the five scopes the server offers (`org:read`, `project:write`, `event:write`) and refuses to store a token that reports a scope outside them. The agent separately allowlists five MCP tools: `get_sentry_resource`, `find_organizations`, `search_issues`, `search_events`, and `analyze_issue_with_seer`.

### By hand

```bash
ant auth login            # or put ANTHROPIC_API_KEY in .env (cp .env.example .env)
npm install
./agents/setup.sh         # `ant apply` creates the agent, environment, and vault, then `npm run sentry-login` stores the OAuth credential
$EDITOR .env              # GITHUB_REPO_URL, GITHUB_TOKEN, SENTRY_CLIENT_SECRET
npm run fix -- SHOP-1A    # fix one issue by its Sentry short ID, no webhook needed
npm run dev               # or listen on http://localhost:3000/webhooks/sentry for new issues
```

For webhooks, [create an internal integration](https://docs.sentry.io/integrations/integration-platform/) in Sentry (Settings > Developer Settings), subscribe it to the `issue` resource, and set its webhook URL to a tunnel that points at port 3000. Sentry [signs each delivery](https://docs.sentry.io/integrations/integration-platform/webhooks/) with the integration's Client Secret, so copy that to `SENTRY_CLIENT_SECRET`. [`CLAUDE.md`](CLAUDE.md) has the full walkthrough, including publishing `demo-app/` to a repository of your own and connecting it to Sentry.

To change the agent (model, prompt, tools), edit [`agents/issue-fixer/agent.yaml`](agents/issue-fixer/agent.yaml) and re-run `./agents/setup.sh`. [`ant apply`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/apply) updates what changed and records the IDs in `claude-lock.json`, which the app reads. A re-run keeps the Sentry credential the vault already has. The lockfile is ignored here because its IDs belong to your organization. In your own project, commit it so teammates and CI update the same resources.

## The pull request is the checkpoint

Nobody watches a session that a webhook started at 3am, so the agent's shell runs without per-command approval. The sandbox also reads error text that anyone who can send your service a request can write. Four things bound what an injected instruction could do:

- **A ruleset on the base branch.** The sandbox can push, so the server checks at startup that an active ruleset requires a pull request for `GITHUB_BASE_BRANCH`, and exits if none does. Without it, `git push origin HEAD:main` would skip your review, and Sentry would resolve the issue on the next release. A classic branch protection rule is not accepted: it exempts repository admins by default, and your token is usually an admin's.
- **The host opens the pull request.** `open_pull_request` is a custom tool that this server answers with its own GitHub token. The repository, the base branch, and the `Fixes` line come from the server's config and the webhook. The host checks the agent's text the way Sentry's and GitHub's own parsers read it. A title or body that would close another issue (`Closes #12`, or `Fix the crash` with `BILLING-7` a few words later) is defused, and a branch whose commit messages would do it is refused. Once the pull request is open the host replaces the session's repository token, so the session can't push again. As a backstop it inspects the branch once more when the session ends and closes the pull request if later commits would not pass or the branch can't be read.
- **Credentials stay outside the sandbox.** The GitHub token is injected by a git proxy and the Sentry tokens by the MCP proxy. Code in the session can use both and read neither.
- **No route out.** The environment denies egress except GitHub, package registries, and the Sentry MCP server. The web tools are off. Of Sentry's tools, only the ones that read (plus Seer) are enabled, so the agent can't resolve or reassign issues itself.

Each session also has a hard spend cap (`AUTOFIX_MAX_USD`, default $10 at list prices). A session that reaches it pauses. `AUTOFIX_MAX_ACTIVE` (default 3) limits how many fixes run at once, so a burst of new issues is logged and skipped instead of multiplying that cap.

## Credential lifecycle and re-authentication

Anthropic refreshes the Sentry token for you. You sign in again only when the refresh fails.

The vault credential holds the Sentry MCP server's access token and refresh token. Before a session connects, Anthropic checks the access token. If it has expired, Anthropic exchanges the refresh token at the token endpoint recorded in the credential.

That exchange stops working when someone revokes the grant in Sentry, the Sentry session behind it lapses, or Sentry rejects the refresh token. The next session then fails with `mcp_authentication_failed_error`, and any webhook you have registered receives `vault_credential.refresh_failed`. `npm run sentry-login` archives the old credential and stores a new one:

```bash
npm run sentry-login
```

To check the credential at any time (the vault ID is in `claude-lock.json` under `./agents/issue-fixer/vault.yaml`):

```bash
ant beta:vaults:credentials list --vault-id <vault-id>      # find the credential ID
ant beta:vaults:credentials mcp-oauth-validate \
  --vault-id <vault-id> --credential-id <credential-id>
# status: valid | invalid | unknown, with the failing refresh or MCP step
```

`sentry-login` runs the same probe right after it stores the credential and prints `credential: validation status <status>`.

## Known limitations

### Organizations that enforce SSO or reject user-bound OAuth tokens

This quickstart can't read issues from an organization that rejects user-bound OAuth tokens, and signing in again doesn't help.

The vault presents every MCP credential, `mcp_oauth` and `static_bearer` alike, as `Authorization: Bearer <token>`. Neither type has a field for a different scheme. On Sentry's hosted MCP server, `Bearer` means a token minted by the server's own OAuth flow. That token is bound to the user who approved it and inherits that user's standing in the organization: SSO link, 2FA, membership. Organizations with enforced SSO or similar identity policies can reject such tokens on every API call.

Consent completes and the credential saves. The failure shows up later as one of:

- an `invalid` status from the probe `sentry-login` runs
- `mcp_authentication_failed_error` on the session
- 403 from Sentry inside the MCP tool results

Those organizations expect unattended automation to use an organization-issued token (an org auth token or an internal integration token), which isn't tied to a user's session. The hosted MCP server accepts those only as `Authorization: Sentry-Bearer <token>`. That scheme is a fixed property of `mcp.sentry.dev`, not something an organization configures, and the vault can't send it. The [Sentry triage quickstart](../sentry#known-limitations) has the same limitation and records the test that showed it.

The plugin in Claude Code is unaffected, because Claude Code holds that OAuth session itself. Sentry's REST API does accept `Bearer` for org auth tokens, so an agent can reach it from the sandbox with an `environment_variable` vault credential instead of MCP, once `sentry.io` is in the environment's `allowed_hosts`. That agent has no MCP tools, so no Seer. An earlier revision of the triage quickstart shows that pattern: `git show 97c825e:managed-agents/sentry/README.md`.

### MCP tool permissions after agent updates

A tool permission that drifts to `always_ask` parks the session, because nobody is there to answer, and no pull request opens. After `ant apply` publishes a new agent version, check in the Managed Agents Console that the five Sentry MCP tools are still enabled with **always allow** and that the rest remain disabled.

## Before you deploy

`GET /` lists the fixes this process has started, including the agent's summary of each, and has no auth. The server binds loopback by default for that reason. Expose only `/webhooks/sentry` through your tunnel or proxy, and keep `HOST` on `127.0.0.1` unless you put auth in front of the rest.

## Files

| | |
|---|---|
| `start.sh` | Installs or updates the Claude Code Sentry plugin, then launches the guided setup |
| `.claude/settings.json` | Enables the plugin at project scope |
| `agents/issue-fixer/` | The agent, environment, and vault definitions `ant apply` keeps in sync |
| `agents/setup.sh` | `ant apply`, then `npm run sentry-login` if the vault has no Sentry credential |
| `src/app.ts` | The webhook route: signature check, filtering, 202 |
| `src/fixer.ts` | One session per issue, the event loop, the `open_pull_request` handler, startup checks |
| `src/github.ts` | Branch protection check, pull request creation |
| `src/sentry.ts` | Webhook signature and payload parsing |
| `src/sentry-login.ts` | MCP OAuth (discovery, dynamic registration, PKCE) into an `mcp_oauth` vault credential, then a validation probe |
| `demo-app/` | The buggy checkout service, instrumented with `@sentry/node` |
| `CLAUDE.md` | Full setup walkthrough, debugging table, extensions |
