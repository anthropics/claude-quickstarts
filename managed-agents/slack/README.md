# Slack × Claude Managed Agents

`@mention` a Claude [Managed Agent](https://platform.claude.com/docs/en/managed-agents/overview) in Slack and get the reply in-thread. The bridge is stateless: the session's `metadata` (`slack_channel`, `slack_thread_ts`) is the only routing state, so there is no database and no mapping table.

```
Slack @mention ──▶ /slack/events ──▶ sessions.create (+ metadata) ──▶ 204
                                                  │
                                Claude runs to idle on Anthropic infra
                                                  │
/managed-agents/webhook ◀── session.status_idled ◀┘
      │
      └──▶ sessions.retrieve → read metadata → chat.postMessage
```

## Quickstart

Needs [Bun](https://bun.sh/), the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart) 1.30 or later (`brew install anthropics/tap/ant`), a public HTTPS tunnel such as ngrok, and Anthropic auth: `ant auth login` once, or an API key from [platform.claude.com](https://platform.claude.com/).

```bash
cd managed-agents/slack
bun install
claude "walk me through setting this up"   # reads skill.md and drives the rest
```

Claude walks through the Slack app, the agent and webhook, the env vars, and `bun run dev` in the order that works. The order matters: Slack verifies the Request URL the moment you save it, so the server has to be up first.

Or by hand:

```bash
ant auth login                  # or export ANTHROPIC_API_KEY
ant apply agents environments   # creates the agent + environment, records their IDs in claude-lock.json
cp .env.example .env            # then follow the local dev checklist in skill.md for the Slack and webhook halves
bun run dev
```

[`ant apply`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/apply) reads the agent from [`agents/slack-assistant.md`](agents/slack-assistant.md), whose frontmatter is the configuration and whose prose is the system prompt, and the environment from [`environments/slack-assistant.yaml`](environments/slack-assistant.yaml). It shows the plan and creates both once you approve, and the bridge reads their IDs from the `claude-lock.json` it writes. To change the agent (model, prompt, tools), edit its file and run a bare `ant apply`, which reconciles every file the lockfile tracks and publishes a new version of the same agent. This repository ignores `claude-lock.json`, since every reader creates their own resources. In a project of your own, commit it.

## Files

| | |
|---|---|
| `agents/slack-assistant.md`, `environments/slack-assistant.yaml` | The agent and its environment, as files for `ant apply` |
| `src/resources.ts` | Reads the agent and environment IDs from `claude-lock.json` (or `CLAUDE_*_ID` overrides) |
| `src/main.ts` | Bun server, routes |
| `src/slack-events.ts` | Verify Slack sig, `url_verification`, fire-and-forget kickoff |
| `src/agent.ts` | `sessions.create` + `user.message` with routing metadata |
| `src/managed-agents-webhook.ts` | `beta.webhooks.unwrap` → filter by metadata → `chat.postMessage` |
| `skill.md` | Mental model, gotchas, setup checklist, debugging |

Requires `@anthropic-ai/sdk` ≥ 0.109.0.
