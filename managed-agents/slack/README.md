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

Needs [Bun](https://bun.sh/), the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart) 1.19 or later (`brew install anthropics/tap/ant`), a public HTTPS tunnel such as ngrok, and Anthropic auth: `ant auth login` once, or an API key from [platform.claude.com](https://platform.claude.com/).

```bash
cd managed-agents/slack
bun install
claude "walk me through setting this up"   # reads skill.md and drives the rest
```

Claude walks through the Slack app, the agent and webhook, the env vars, and `bun run dev` in the order that works. The order matters: Slack verifies the Request URL the moment you save it, so the server has to be up first.

Or by hand:

```bash
ant auth login            # or put ANTHROPIC_API_KEY in .env (cp .env.example .env)
./agents/setup.sh         # creates the agent + environment from agents/slack-assistant/*.yaml, writes their IDs to .env
bun run dev               # then follow the local dev checklist in skill.md for the Slack and webhook halves
```

To change the agent (model, prompt, tools), edit [`agents/slack-assistant/agent.yaml`](agents/slack-assistant/agent.yaml) and re-run `./agents/setup.sh`.

## Files

| | |
|---|---|
| `agents/slack-assistant/` | The agent and environment definitions `setup.sh` provisions |
| `src/main.ts` | Bun server, routes |
| `src/slack-events.ts` | Verify Slack sig, `url_verification`, fire-and-forget kickoff |
| `src/agent.ts` | `sessions.create` + `user.message` with routing metadata |
| `src/managed-agents-webhook.ts` | `beta.webhooks.unwrap` → filter by metadata → `chat.postMessage` |
| `skill.md` | Mental model, gotchas, setup checklist, debugging |

Requires `@anthropic-ai/sdk` ≥ 0.109.0.
