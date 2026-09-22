# MCP server (TypeScript) × Claude Managed Agents

MCP server that exposes Managed Agents session primitives as tools. Two entrypoints sharing one tool set: `src/server.ts` (stdio → Claude Desktop and Claude Code) and `src/server-http.ts` (Streamable HTTP → claude.ai custom connector).

## When the user asks to set this up, extend it, or debug it

1. **Invoke `/claude-api` first.** That skill loads the full Managed Agents API reference (agents, sessions, events, environments). Use it as the source of truth for any SDK call. Don't guess field names.
2. **Read `./skill.md`** and walk the user through it. First ask which client they're targeting (Claude Desktop or Claude Code → stdio path, claude.ai → HTTP + deploy + connector), then follow that path's checklist. Both end with the same `send_message → wait_for_idle` loop and relay-mode Project instructions. For the HTTP path, do not skip "What the token can reach": get `ALLOWED_AGENT_IDS` set before anything is deployed.
3. **Adding a tool?** Write the SDK call in `src/managed-agents.ts`, then register it in `src/tools.ts` with a zod schema and a scope (`"agent"`, `"session"`, or `"listing"`). The scope is what runs the `ALLOWED_AGENT_IDS` check, and registration throws if it doesn't match the schema. A `"listing"` tool takes no ID, so it has to filter its own results the way `listAgents` does. See the table in `skill.md` for what is deliberately **not** exposed (destructive ops, secrets).

This quickstart creates no agents, so there is no `agents/` directory. It needs one environment, created once from `environment.yaml` (the command is in that file and in `README.md`).

Commands: `bun run stdio` (Desktop, Code), `bun run http` (claude.ai), `bun run typecheck`.
