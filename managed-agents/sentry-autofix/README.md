# Sentry × Claude Managed Agents: fix production errors with a pull request

A new error lands in [Sentry](https://sentry.io/). A [Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview) session reads the stack trace and [Seer](https://docs.sentry.io/product/ai-in-sentry/seer/)'s root cause analysis through the [Sentry MCP server](https://mcp.sentry.dev/), reproduces the bug with a failing test in a clone of your repository, fixes it, and opens a pull request that says `Fixes SHOP-1A`. You review and merge. Sentry resolves the issue when a release contains the merge commit.

The host is about 600 lines of TypeScript: a webhook route, one `sessions.create` per issue, a loop that answers the agent's one custom tool, and a Sentry OAuth login helper. It stores nothing. A session's metadata says which issue it is for and its event log says how far the fix got. Webhook retries don't start a second fix, and a host that restarted mid-fix picks the session back up the next time the issue is delivered or you run `npm run fix` for it.

`demo-app/` is a small Express checkout service with a real bug to try it on: any cart without a coupon code returns a 500.

## Quickstart

Needs:

- Node 22.9 or later
- The [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart) 1.30 or later (`brew install anthropics/tap/ant`), and Anthropic auth: `ant auth login` once, or an API key from [platform.claude.com](https://platform.claude.com/)
- A Sentry organization. Seer is a paid add-on. Without it the agent works from the stack trace alone and says so in the pull request.
- A GitHub repository whose default branch has a [ruleset](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets) that requires a pull request, and a [fine-grained token](https://github.com/settings/personal-access-tokens) for that one repository with Contents and Pull requests set to read and write

```bash
cd managed-agents/sentry-autofix
npm install
claude "help me set up this Sentry autofix quickstart"   # reads CLAUDE.md and drives the rest
```

Or by hand:

```bash
ant auth login            # or put ANTHROPIC_API_KEY in .env (cp .env.example .env)
./agents/setup.sh         # `ant apply` creates the agent and environment from agents/issue-fixer/*.yaml, then one vault
npm run sentry-login      # signs in to the Sentry MCP server and stores the OAuth tokens in the vault
$EDITOR .env              # GITHUB_REPO_URL, GITHUB_TOKEN, SENTRY_CLIENT_SECRET
npm run fix -- SHOP-1A    # fix one issue by its Sentry short ID, no webhook needed
npm run dev               # or listen on http://localhost:3000/webhooks/sentry for new issues
```

For webhooks, [create an internal integration](https://docs.sentry.io/integrations/integration-platform/) in Sentry (Settings > Developer Settings), subscribe it to the `issue` resource, and set its webhook URL to a tunnel that points at port 3000. Sentry [signs each delivery](https://docs.sentry.io/integrations/integration-platform/webhooks/) with the integration's Client Secret, so copy that to `SENTRY_CLIENT_SECRET`. [`CLAUDE.md`](CLAUDE.md) has the full walkthrough, including publishing `demo-app/` to a repository of your own and connecting it to Sentry.

To change the agent (model, prompt, tools), edit [`agents/issue-fixer/agent.yaml`](agents/issue-fixer/agent.yaml) and re-run `./agents/setup.sh`. [`ant apply`](https://github.com/anthropics/anthropic-cli#readme) updates what changed and records the IDs in `claude-lock.json`, which the app reads. The lockfile is ignored here because its IDs belong to your organization. In your own project, commit it so teammates and CI update the same resources.

## The pull request is the checkpoint

Nobody watches a session that a webhook started at 3am, so the agent's shell runs without per-command approval. The sandbox also reads error text that anyone who can send your service a request can write. Four things bound what an injected instruction could do:

- **A ruleset on the base branch.** The sandbox can push, so the server checks at startup that an active ruleset requires a pull request for `GITHUB_BASE_BRANCH`, and exits if none does. Without it, `git push origin HEAD:main` would skip your review, and Sentry would resolve the issue on the next release. A classic branch protection rule is not accepted: it exempts repository admins by default, and your token is usually an admin's.
- **The host opens the pull request.** `open_pull_request` is a custom tool that this server answers with its own GitHub token. The repository, the base branch, and the `Fixes` line come from the server's config and the webhook. The host checks the agent's text the way Sentry's and GitHub's own parsers read it. A title or body that would close another issue (`Closes #12`, or `Fix the crash` with `BILLING-7` a few words later) is defused, and a branch whose commit messages would do it is refused. Once the pull request is open the host replaces the session's repository token, so the session can't push again. As a backstop it inspects the branch once more when the session ends and closes the pull request if later commits would not pass or the branch can't be read.
- **Credentials stay outside the sandbox.** The GitHub token is injected by a git proxy and the Sentry tokens by the MCP proxy. Code in the session can use both and read neither.
- **No route out.** The environment denies egress except GitHub, package registries, and the Sentry MCP server. The web tools are off. Of Sentry's tools, only the ones that read (plus Seer) are enabled, so the agent can't resolve or reassign issues itself.

Each session also has a hard spend cap (`AUTOFIX_MAX_USD`, default $10 at list prices). A session that reaches it pauses. `AUTOFIX_MAX_ACTIVE` (default 3) limits how many fixes run at once, so a burst of new issues is logged and skipped instead of multiplying that cap.

## Before you deploy

`GET /` lists the fixes this process has started, including the agent's summary of each, and has no auth. The server binds loopback by default for that reason. Expose only `/webhooks/sentry` through your tunnel or proxy, and keep `HOST` on `127.0.0.1` unless you put auth in front of the rest.

## Files

| | |
|---|---|
| `agents/issue-fixer/` | The agent and environment definitions `ant apply` keeps in sync, and the vault definition |
| `src/app.ts` | The webhook route: signature check, filtering, 202 |
| `src/fixer.ts` | One session per issue, the event loop, the `open_pull_request` handler, startup checks |
| `src/github.ts` | Branch protection check, pull request creation |
| `src/sentry.ts` | Webhook signature and payload parsing |
| `src/sentry-login.ts` | MCP OAuth (dynamic registration, PKCE) into an `mcp_oauth` vault credential |
| `demo-app/` | The buggy checkout service, instrumented with `@sentry/node` |
| `CLAUDE.md` | Full setup walkthrough, debugging table, extensions |
