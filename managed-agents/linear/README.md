# Linear × Claude Managed Agents

`@mention` a Claude [Managed Agent](https://platform.claude.com/docs/en/managed-agents/overview) in a Linear issue, or assign the issue to it, and get the reply as a comment. The bridge is stateless: the session's `metadata` (`linear_session_id`, `linear_org_id`) is the only routing state, so there is no database and no mapping table.

```
Linear @mention ──▶ /linear-webhook ──▶ sessions.create (+ metadata) ──▶ 200
                                                   │
                                 Claude runs to idle on Anthropic infra
                                                   │
/managed-agents/webhook ◀── session.status_idled ◀─┘
      │
      └──▶ sessions.retrieve → read metadata → createAgentActivity
```

## Quickstart

Needs [Bun](https://bun.sh/), the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart) 1.19 or later (`brew install anthropics/tap/ant`), a public HTTPS tunnel such as ngrok, admin rights on a Linear workspace, and Anthropic auth: `ant auth login` once, or an API key from [platform.claude.com](https://platform.claude.com/).

```bash
cd managed-agents/linear
bun install
claude "walk me through setting this up"   # reads skill.md and drives the rest
```

Claude walks through the Linear OAuth app, the agent and webhook, the env vars, and `bun run dev` in the order that works.

Or by hand:

```bash
ant auth login            # or put ANTHROPIC_API_KEY in .env (cp .env.example .env)
./agents/setup.sh         # creates the agent + environment from agents/linear-assistant/*.yaml, writes their IDs to .env
bun run dev               # then follow the local dev checklist in skill.md for the Linear and webhook halves
```

To change the agent (model, prompt, tools), edit [`agents/linear-assistant/agent.yaml`](agents/linear-assistant/agent.yaml) and re-run `./agents/setup.sh`.

## Before you expose it

`/oauth/authorize` has no login in front of it, and every mention from an installed workspace runs a session on your Anthropic credentials. So the first Linear workspace to install owns the bridge, and installs from any other workspace are refused and revoked. To pin that choice, or to serve more than one workspace, set `LINEAR_ALLOWED_ORG_IDS` in `.env` (the server logs the organization ID on install). See `skill.md`, "Issue text is untrusted input", for what a mention can make the agent do.

## Files

| | |
|---|---|
| `agents/linear-assistant/` | The agent and environment definitions `setup.sh` provisions |
| `src/main.ts` | Bun server, routes |
| `src/oauth.ts` | Linear OAuth (`actor=app`, single-use `state`) + token store |
| `src/agent.ts` | `sessions.create` + `user.message` with routing metadata |
| `src/managed-agents-webhook.ts` | `beta.webhooks.unwrap` → filter by metadata → post reply |
| `skill.md` | Mental model, gotchas, setup checklist, debugging |

Requires `@anthropic-ai/sdk` ≥ 0.109.0.
