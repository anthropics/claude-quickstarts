# Slack × Claude Managed Agents bridge

Stateless webhook bridge: Slack `app_mention` → Managed Agents session (with routing metadata) → `session.status_idled` webhook → `chat.postMessage` in-thread.

## When the user asks to set this up, get it working, or debug it

1. **Invoke `/claude-api` first.** That skill loads the full Managed Agents API reference (agents, sessions, environments, events, webhooks, outcomes, multiagent, vaults, memory stores). Use it as the source of truth for any SDK call you write or edit. Don't guess field names.
2. **Read `./skill.md`** and walk the user through it step by step. It has the ordered checklist, every gotcha (scope vs event-subscription, `xoxb` vs `xapp`, workspace-scoped webhooks, retrieve-then-filter), and the debugging table.
3. **After the base bridge works, offer extensions.** Ask the user which (if any) they want, then edit `agents/slack-assistant.md` and run a bare `ant apply --yes`, which publishes the edit as a new agent version, and/or edit `src/agent.ts` for the session side. A new resource is one more file (`memory_stores/<name>.yaml`, `vaults/<name>.yaml`, another `agents/<name>.md`) that `ant apply --yes agents environments memory_stores vaults` (name whichever directories exist) creates and records in `claude-lock.json`; read its ID in `src/resources.ts` the way the agent's is read.
   - **GitHub repo**: mount a repo into the session container (`resources: [{type: "github_repository", ...}]` on `sessions.create`)
   - **MCP tools**: e.g. Slack or GitHub MCP so the agent can act, not only reply (`mcp_servers` + `mcp_toolset` in `agents/slack-assistant.md`, a `vaults/<name>.yaml` for the credential, which `ant apply` manages from ant 1.34, then `vault_ids` on the session)
   - **Outcomes**: rubric-graded iterate loop (`user.define_outcome` event instead of `user.message`)
   - **Multiagent**: coordinator + subagent roster (`multiagent: {type: coordinator, agents: [./<other>.md]}` in `agents/slack-assistant.md`; `ant apply` resolves the path and pins the version)
   - **Memory store**: cross-session persistence (add `memory_stores/<name>.yaml`, apply it, then `resources: [{type: "memory_store", ...}]` on `sessions.create` with the store's ID from `claude-lock.json`)
   - **Custom tools**: host-side execution via `agent.custom_tool_use` / `user.custom_tool_result`

   Pull exact shapes from the `/claude-api` skill's `shared/managed-agents-*.md` docs.

Run the server with `bun run dev`. Agent provisioning is `ant apply --yes agents environments` from this directory (ant 1.30 or later; name the directories rather than `.`, and pass `--yes` because you have no terminal for its confirmation prompt, or `--dry-run` to show the plan first): it creates the agent and environment from `agents/slack-assistant.md` and `environments/slack-assistant.yaml`, records their IDs in `claude-lock.json`, which `src/resources.ts` reads, and on re-runs pushes file edits onto the same resources. It needs `ant auth login` or an exported `ANTHROPIC_API_KEY`; it does not read `.env`. If it prints `refusing to apply`, a resource was changed or archived in the Console: show the user the reason before reaching for `--force`.
