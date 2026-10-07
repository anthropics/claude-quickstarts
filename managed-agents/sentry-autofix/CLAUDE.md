# Sentry autofix on Claude Managed Agents

Long-running Node server (Hono). Sentry posts a signed `issue` / `created` webhook → `src/app.ts` verifies it and hands the issue to `src/fixer.ts` → one Managed Agents session per issue, with the repository mounted as a `github_repository` resource, the Sentry MCP credential attached through a vault, a dollar budget, the kickoff message in `initial_events`, and `metadata.sentry_short_id` as the dedupe key → the agent reads the issue and Seer's analysis through the Sentry MCP server, reproduces, fixes, pushes `autofix/<short-id>` → it calls the `open_pull_request` custom tool, which this host answers with the GitHub API. `npm run fix -- SHOP-1A` runs the same path without a webhook.

```
Sentry ──POST /webhooks/sentry──▶ app.ts (HMAC check, issue.created only)
                                     │ onIssue
                                     ▼
                                 fixer.ts ──sessions.create──▶ session ─────────────▶ issue fixer (opus)
                                     ▲        resources: github_repository            bash, read, edit, grep
                                     │        vault_ids: Sentry mcp_oauth             sentry MCP: get_sentry_resource,
                                     │        budget, metadata                          search_*, analyze_issue_with_seer
                                     │
   GitHub REST ◀── open_pull_request ┘◀── agent.custom_tool_use {branch, title, body}
   (host token, host-chosen repo/base,     user.custom_tool_result {PR URL | error}
    host-written "Fixes SHOP-1A")
```

Needs `@anthropic-ai/sdk` ≥ 0.125.0, `jq`, and `ant` ≥ 1.34 (the first release whose `ant apply` manages vaults).

## When the user asks to set this up, get it working, or debug it

1. **Invoke `/claude-api` first.** It loads the Managed Agents API reference (agents, sessions, environments, events, vaults, MCP, permission policies). Use it as the source of truth for any SDK call you write or edit. Don't guess field names.
2. **Use the installed Sentry plugin** (`./start.sh` installs it) to list the organizations and projects the user can access, and ask them to pick the target. Never pick a project for them. If the plugin's `sentry` MCP server is not authenticated, ask the user to run `/mcp` and sign in.
3. **Explain the two OAuth grants** before the second sign-in: Claude Code's plugin credential serves this conversation, and the grant `npm run sentry-login` saves to the vault serves sessions that webhooks start. Never inspect or copy Claude Code's credential storage, and never put a Sentry API token in `.env`, a shell variable, or the agent prompt.
4. **Walk the setup in this order.** Each step depends on the one before it.
   1. **A repository to fix.** To use the demo: copy `demo-app/` out of this checkout, make it its own repository, and push it.
      ```bash
      cp -r demo-app ~/sentry-autofix-demo && cd ~/sentry-autofix-demo
      git init -b main && git add -A && git commit -m "Checkout service"
      gh repo create sentry-autofix-demo --private --source . --push
      ```
   2. **Protect the base branch.** In the repository: Settings > Rules > Rulesets > New branch ruleset, target the default branch, enable "Require a pull request before merging" and "Block force pushes", set enforcement to Active, and leave the bypass list empty. The server refuses to start without it. A classic branch protection rule does not pass: it exempts repository admins unless "Do not allow bypassing the above settings" is ticked, and the token usually belongs to an admin. If rulesets are not offered on a private repository under the user's GitHub plan, make the demo repository public.
   3. **A GitHub token.** Fine-grained, that one repository only, Contents: read and write, Pull requests: read and write. It goes in `.env` as `GITHUB_TOKEN`.
   4. **Sentry.** Have the user pick the organization through the plugin. Create a Node project in it (or pick an existing one), put its slug in `.env` as `SENTRY_PROJECT`, and put its DSN in the demo app's environment as `SENTRY_DSN`. Add the GitHub integration to the Sentry organization and add the repository to it: that is what makes `Fixes SHOP-1A` link the pull request to the issue.
   5. **Managed Agents resources.** `ant auth login`, `npm install`, then `./agents/setup.sh`. It runs `ant apply --yes agents/issue-fixer`, which creates or updates the agent, environment, and vault and writes their IDs to `claude-lock.json` (the app reads them from there), then runs step 6 when the vault has no credential for `https://mcp.sentry.dev/mcp`. That first run waits on the user's browser consent, so give the command a long timeout or have the user run it in their own terminal. If `ant apply` prints `refusing to apply`, show the user the reason before reaching for `--force`. The lockfile records the organization and workspace, so check `ant auth status` first: applying under a different profile is refused rather than silently creating copies.
   6. **Sentry credential.** `npm run sentry-login` (setup runs it the first time) prints a URL. Stop while the user opens it and approves the organization. On Sentry's screen only **Inspect Issues & Events** and **Seer** stay checked. The script stores an `mcp_oauth` credential in the vault and probes it. Read back the `credential: validation status` line: `invalid` means the SSO limitation (step 5). On a remote machine the browser's redirect to `localhost:8976` fails to load: the user pastes that final URL back into the terminal.
   7. **Try it.** Start the demo app with `npm start`, run `npm run break` in it, find the new issue's short ID with the plugin (or in Sentry), then `npm run fix -- <SHORT-ID>` here. A fix takes a few minutes. Seer alone can take five.
   8. **Webhooks.** Only after the CLI path works. Sentry: Settings > Developer Settings > New Internal Integration, webhook URL `<tunnel>/webhooks/sentry`, then check `issue` under Webhooks. If that checkbox is disabled, the integration lacks read permission on issues and events: grant it under Permissions first. Client Secret goes in `.env` as `SENTRY_CLIENT_SECRET`. Then `npm run dev`.
5. **Recognize the SSO limitation.** If validation says `invalid`, or the first fix fails with `mcp_authentication_failed_error` or 403s inside tool results, the organization is rejecting the user-bound MCP OAuth token (SSO enforcement or a similar policy). The org-issued token that would work needs `Authorization: Sentry-Bearer`, and the vault can only send `Bearer`. Do not loop on `npm run sentry-login`. Show the user "Known limitations" in the README.
6. **After the base loop works, offer extensions.** Ask which the user wants.
   - **Outcomes**: kick off with `user.define_outcome` and a rubric (new test fails before the fix, whole suite passes after, diff touches only what the root cause needs) instead of `user.message`, so a grader sends weak fixes back for another iteration.
   - **Seer webhooks**: subscribe the integration to the `seer` resource and start the session on `seer.root_cause_completed`, passing `data.root_cause` in the kickoff, so the agent starts from Seer's finished analysis instead of waiting on it. The delivery goes through the same signature check in `src/app.ts` before anything reads it. Seer's text is derived from error data that outsiders can write, so fence it in the kickoff as untrusted data the way `kickoff()` fences the issue title.
   - **`SessionToolRunner`**: `client.beta.sessions.events.toolRunner(sessionId, {tools})` replaces the hand-written loop in `drive()`. It reconnects dropped streams. It does not report `budget_reached` or `retries_exhausted` stops or the agent's final message, which is why this quickstart reads the stream itself.
   - **Hear about a lapsed grant**: register a webhook for `vault_credential.refresh_failed`, so a failed refresh reaches a person before the next issue's session fails on it.
   - **Tell the team**: post the pull request URL to Slack from the `pr_opened` branch in `handleCustomTool`. The host posts it, with text the host writes. Don't give the session a Slack tool.
   - **A feature flag instead of a wait**: give the agent a second custom tool that asks to turn off a LaunchDarkly flag for the broken code path while the pull request waits for review. Keep it host-side like `open_pull_request`, with the flag key fixed in config, and have the host wait for a person to approve (a Slack button, a CLI prompt) before it calls LaunchDarkly. Anyone who can trigger an error can start a session, so an unapproved flag flip would let an outsider switch off a feature by sending bad requests. A pull request has a reviewer in front of it. A flag change does not unless you put one there.
   - **Schedule instead of webhooks**: a scheduled deployment that runs `search_issues` for new unresolved issues each hour. See `/claude-api`, scheduled deployments.

## Design rules to keep when editing

- The agent's shell is `always_allow` and reads attacker-writable text. Anything that could widen what it reaches (a new `allowed_hosts` entry, an enabled web tool, `update_issue`, `execute_sentry_tool`) needs the same scrutiny as handing a stranger that capability.
- Host-side tools decide the repository, the base branch, and the issue link. Never take those from tool input.
- `drive()` is one code path for a first connect, a reconnect, and a restarted host: open the stream, replay `events.list`, tail. Keep new event handling idempotent against replay, the way the `answered` set keeps a tool call from being answered twice.
- Log tool names, never tool inputs. Inputs are derived from production error data.
- `hasClosingReference` in `src/github.ts` mirrors Sentry's parser (`src/sentry/utils/groupreference.py` in getsentry/sentry) and GitHub's keyword rule. Sentry's reference span runs through plain words and newlines until punctuation, so text the host writes into a pull request uses the verbs fix, close, and resolve exactly once, in `Fixes <SHORT-ID>.`, and that line ends with a period.
- `mcp_servers[].url` in `agent.yaml`, `SENTRY_MCP_URL` in `src/fixer.ts` (which `src/sentry-login.ts` imports), and the URL `agents/setup.sh` greps for must be the same string. The platform matches credentials to servers by URL.
- `SCOPES` in `src/sentry-login.ts` is narrower than what the server advertises, and the script refuses a token that reports more. The tool allow-list in `agent.yaml` can drift in the Console, so it is not the only bound on what the credential can do.

## Debugging

| Symptom | Cause | Fix |
|---|---|---|
| Server exits: "is not protected" or "classic branch protection rule but no ruleset" | No active ruleset requires a pull request for `GITHUB_BASE_BRANCH`. A ruleset in Evaluate mode does not count, and neither does a classic rule | Step 4.2, with enforcement set to Active |
| `ant apply` cannot tell what kind of resource `vault.yaml` is | The file lost its `type: vault` line, or `ant` is older than 1.34 | Restore the line, or upgrade `ant` |
| Startup says `claude-lock.json` is missing or has no agent | `./agents/setup.sh` has not run in this directory, or the lockfile was deleted | Run it. If the resources still exist, `ant apply` would create new ones: archive the old ones in the Console |
| Server exits: "no Sentry credential" | `npm run sentry-login` never ran, or ran against a different vault | Run it again. It replaces the old credential |
| `mcp_authentication_failed_error` on the first fix, or `sentry-login` prints `validation status invalid` | The organization rejects the user-bound MCP OAuth token (SSO enforcement or a similar policy), or the credential URL does not match `agent.yaml` | Check the URLs match. If they do, signing in again will not help: see "Known limitations" in the README |
| `mcp_authentication_failed_error` after fixes that used to work | Refresh failed: the grant was revoked or the Sentry session behind it lapsed. `ant beta:vaults:credentials mcp-oauth-validate` shows the failing step | `npm run sentry-login` |
| 403 from Sentry inside a tool result | The grant lacks the skill, or the organization rejects user-bound OAuth tokens | `npm run sentry-login` and approve **Inspect Issues & Events** and **Seer**. If it persists, see "Known limitations" in the README |
| `sentry-login` says Sentry "granted more than this quickstart asked for" | The token reports a scope outside `SCOPES` in `src/sentry-login.ts` | Nothing was stored, and the old credential is untouched. Read which scope the message names before widening `SCOPES` |
| `mcp_egress_blocked_error` | `allow_mcp_servers: true` is missing from `environment.yaml` | Restore it and re-run `./agents/setup.sh` |
| Session never calls a Sentry tool, or parks waiting for a confirmation | The tools were disabled or set to `always_ask` in the Console after an agent update | Set the five tools back to enabled and always allow in the Console |
| Hosted Sentry MCP rejects a pasted API token | It accepts user tokens only as `Authorization: Sentry-Bearer`, and a `static_bearer` vault credential sends `Bearer` | Use `npm run sentry-login` (OAuth). Don't switch the credential type |
| Webhook returns 401 | `SENTRY_CLIENT_SECRET` is from a different integration, or a proxy re-serialized the body | Copy the Client Secret again. The signature covers the exact bytes Sentry sent |
| Webhook returns `{"ignored": true}` | Not `issue` / `created`, or `SENTRY_PROJECT` does not match the issue's project slug | Expected for other events. Check the slug |
| "already has a session" or "has ended" | This process is already driving a session with this `sentry_short_id`, or that session is terminated | Wait for it, or archive it (Console, or `ant beta:sessions archive --session-id ... < /dev/null`) to run the issue again |
| Log says "(picked back up)" | A session for the issue existed with no driver, because the host restarted or lost its stream. `drive()` replayed the event log and carried on | Nothing. This is the recovery path |
| Log says "fixes are already running" | `AUTOFIX_MAX_ACTIVE` sessions are in flight, and the new issue was skipped. Sentry does not redeliver | `npm run fix -- <SHORT-ID>` once there is room, or raise the limit |
| `open_pull_request` error names a commit that "would close or resolve an issue" | A commit message has fix, close, or resolve followed by an issue reference, or by a hyphenated word Sentry would read as a short ID (`Fix off-by-one`). The agent prompt asks for other verbs, so this is a slip or an injection | The agent recreates the commits on a new branch. If it keeps happening, read the Sentry event for injected text |
| Pull request closed with a comment from the autofix host | The end-of-session recheck failed closed. Either commits landed after the pull request opened and no longer pass inspection (only possible if revoking push access failed: look for "could not revoke push access" in the log), or GitHub could not be read three times in a row | The comment says which. For the first, read those commits and the Sentry event. For the second, check the commits and reopen the pull request |
| Run ends `failed`, note `stopped: budget_reached` | The session hit `AUTOFIX_MAX_USD` | Raise it for new sessions, or raise the paused session's budget in the Console to resume it |
| `open_pull_request` error "No commits between" | The push failed or went to another branch | Read the session in the Console. A rejected push to the base branch is the protection working |
| Pull request merged, issue still open in Sentry | Sentry resolves on the next release that contains the commit, not on merge | Create a release with commits associated, or resolve it by hand |
| `npm install` 404s in `demo-app/` behind a corporate mirror | The mirror lacks `@sentry/node` 10's newer dependencies | `npm install @sentry/node@9`. The two calls the demo uses are the same in 9 and 10 |
