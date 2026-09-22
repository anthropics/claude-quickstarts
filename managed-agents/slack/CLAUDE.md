# Slack × Claude Managed Agents bridge

Stateless webhook bridge: Slack `app_mention` → Managed Agents session (with routing metadata) → `session.status_idled` webhook → `chat.postMessage` in-thread.

## When the user asks to set this up, get it working, or debug it

1. **Invoke `/claude-api` first.** That skill loads the full Managed Agents API reference (agents, sessions, environments, events, webhooks, outcomes, multiagent, vaults, memory stores). Use it as the source of truth for any SDK call you write or edit. Don't guess field names.
2. **Read `./skill.md`** and walk the user through it step by step. It has the ordered checklist, every gotcha (scope vs event-subscription, `xoxb` vs `xapp`, workspace-scoped webhooks, retrieve-then-filter), and the debugging table.
3. **After the base bridge works, offer extensions.** Ask the user which (if any) they want, then edit `agents/slack-assistant/agent.yaml` and re-run `./agents/setup.sh`, which pushes the edit as a new agent version, and/or edit `src/agent.ts` for the session side. A new resource is a new YAML file in `agents/slack-assistant/` plus one more create/update block in `setup.sh`, copied from the two already there.
   - **GitHub repo**: mount a repo into the session container (`resources: [{type: "github_repository", ...}]` on `sessions.create`)
   - **MCP tools**: e.g. Slack or GitHub MCP so the agent can act, not only reply (`mcp_servers` + `mcp_toolset` in `agent.yaml`, `agents/slack-assistant/vault.yaml` plus an `ant beta:vaults create` block in `setup.sh` that appends `CLAUDE_VAULT_ID`, then `vault_ids` on the session)
   - **Outcomes**: rubric-graded iterate loop (`user.define_outcome` event instead of `user.message`)
   - **Multiagent**: coordinator + subagent roster (`multiagent: {type: coordinator, agents: [...]}` in `agent.yaml`)
   - **Memory store**: cross-session persistence (add `agents/slack-assistant/memory-store.yaml` and an `ant beta:memory-stores create` block in `setup.sh`, then `resources: [{type: "memory_store", ...}]` on `sessions.create`)
   - **Custom tools**: host-side execution via `agent.custom_tool_use` / `user.custom_tool_result`

   Pull exact shapes from the `/claude-api` skill's `shared/managed-agents-*.md` docs.

Run the server with `bun run dev`. Agent provisioning is `./agents/setup.sh`: it creates the agent and environment from `agents/slack-assistant/*.yaml` with the `ant` CLI, writes their IDs to `.env`, and on re-runs pushes YAML edits onto the same resources.
