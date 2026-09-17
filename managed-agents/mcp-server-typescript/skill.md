# Setup tips & tricks: Claude Managed Agents as an MCP server

Things that aren't obvious from the docs and tend to cost debugging time.

---

## Mental model

### Claude Desktop is the frontend, Managed Agents is the backend

The Claude you're typing to in Desktop is a **relay**. It calls `send_message` with your words, calls `wait_for_idle` to block until the managed agent finishes, then shows you the reply. The work itself (tool use, code execution, repo edits) happens in the Managed Agents session, not in Desktop.

### Eight 1:1 tools, one shim

`list_agents`, `get_agent`, `create_session`, `send_message`, `interrupt`, `get_session`, `list_events`, `archive_session` are straight endpoint wrappers. `wait_for_idle` is the only editorial: MCP is request/response and a Managed Agents turn completes over SSE, so something has to stream-to-idle inside a tool call.

### `session_id` is the only state, and Claude holds it

`create_session` returns it, and Claude passes it to every later call. The MCP server itself is stateless.

### Two transports, one tool set

`src/tools.ts` registers the nine tools. `src/server.ts` wraps it in stdio (Claude Desktop or Claude Code spawns it as a subprocess). `src/server-http.ts` wraps it in Streamable HTTP (claude.ai reaches it over the network). Pick one.

### No agents are created here

This server drives the agents already in your workspace. Create and update them with the `ant` CLI, the Console, or another quickstart's `./agents/setup.sh`. The one resource it needs is an environment, because `sessions.create` takes an `environment_id`. `environment.yaml` defines it.

---

## Setup: Claude Desktop or Claude Code (stdio, local)

1. **Auth and environment** (one time):
   ```bash
   ant auth login            # or: cp .env.example .env and set ANTHROPIC_API_KEY
   printf 'CLAUDE_ENVIRONMENT_ID=%s\n' \
     "$(ant beta:environments create --transform id --raw-output < environment.yaml)" >> .env
   ```
2. **Agents**: if the workspace has none, run `./agents/setup.sh` in `../slack` or `../chat-sdk`. Optionally list the IDs you want reachable in `ALLOWED_AGENT_IDS` in `.env`.
3. **Register with Claude Code**:
   ```bash
   claude mcp add managed-agents -- bun --env-file="$PWD/.env" run "$PWD/src/server.ts"
   ```
   **Or with Claude Desktop**: add this to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) and restart Desktop. Desktop does not read your shell's environment or `.env`, so the values go in the `env` block:
   ```json
   {
     "mcpServers": {
       "managed-agents": {
         "command": "/absolute/path/to/bun",
         "args": ["run", "/absolute/path/to/managed-agents/mcp-server-typescript/src/server.ts"],
         "env": {
           "ANTHROPIC_API_KEY": "<your key>",
           "CLAUDE_ENVIRONMENT_ID": "<from step 1>"
         }
       }
     }
   }
   ```
4. **Test**: in a new chat, ask *"list my managed agents, start a session with the first one, and relay this message to it: hello."*

---

## Setup: claude.ai (Streamable HTTP, remote)

Same tools, but the server runs at a public URL and claude.ai connects to it as a custom connector. Read "What the token can reach" below before step 3.

1. **Token**: generate it and keep it. The server refuses to start without one of at least 32 characters.
   ```bash
   echo "MANAGED_AGENTS_MCP_TOKEN=$(openssl rand -hex 32)" >> .env
   ```
2. **Run locally first**:
   ```bash
   bun run http   # http://127.0.0.1:3000/mcp
   ```
   To test through a tunnel (ngrok, cloudflared), add the tunnel's hostname to `ALLOWED_HOSTS`. The server answers 421 to any `Host` header it wasn't told about.
3. **Deploy**: the `Dockerfile` targets Fly, Railway, Render, and Cloud Run. Set `ANTHROPIC_API_KEY`, `CLAUDE_ENVIRONMENT_ID`, `MANAGED_AGENTS_MCP_TOKEN`, `ALLOWED_HOSTS`, and `ALLOWED_AGENT_IDS` as secrets on the platform. The image sets `HOST=0.0.0.0`, and the server will not start on a non-loopback host until `ALLOWED_HOSTS` names the public hostname. Terminate TLS in front of it. Cloudflare Workers also works: `WebStandardStreamableHTTPServerTransport` is fetch-native, so swap `process.env` for `env` and `Bun.serve` for `export default { fetch }`.
4. **claude.ai → Settings → Connectors → Add custom connector**:

   | Field | Value |
   |---|---|
   | Name | `Managed Agents` |
   | URL | `https://<your-deploy>/mcp` |
   | Authentication | Bearer token → your `MANAGED_AGENTS_MCP_TOKEN` |

   > **Team and Enterprise orgs:** adding a connector by URL is typically **org-admin only**. Individual users see a curated directory, not a URL field. An admin adds the URL and token once in org settings, and it then appears in every member's connector list to enable. That is the shape you want for rolling out to non-technical users anyway.

5. **Test**: new chat → enable the connector → same prompt as above.

---

## Relay mode (recommended Project instructions)

Without guidance, the frontend Claude will try to answer the user itself instead of relaying. Put this in a Project's custom instructions:

> You are a frontend for a backend Managed Agent reached through the `managed-agents` MCP tools. On the first user turn: `list_agents` (if needed) → `create_session` → `send_message(user text verbatim)` → `wait_for_idle` → return the `reply` verbatim. On later turns: `send_message` → `wait_for_idle`. Do not answer from your own knowledge, and do not paraphrase the backend's reply. If `wait_for_idle` returns `status: "timeout"`, tell the user it's still running and offer to keep waiting. If it returns any status other than `"idle"` or `"timeout"`, tell the user the turn stopped early and give the status.

---

## Gotchas

### What the token can reach

The caller of these tools is a model, and whoever holds the bearer token is whoever can talk to that model. The server's Anthropic credentials can see **every agent and every session in the workspace**. With no allowlist, so can the caller: `list_agents` enumerates them, `get_agent` returns their full system prompts and tool configs, `create_session` runs any of them on your bill, and any `session_id` the caller learns or guesses can be read, messaged, interrupted, or archived.

`ALLOWED_AGENT_IDS` narrows all of that to the agents you name:

- `list_agents` fetches exactly those agents and nothing else.
- `get_agent` and `create_session` refuse any other `agent_id`.
- Every tool that takes a `session_id` retrieves the session first and refuses unless its agent is on the list. That check runs before the send, interrupt, archive, or stream.
- A refusal says "not available through this server" whether or not the ID exists.

The check lives in one place, `src/scope.ts`, and `src/tools.ts` runs it from the scope each tool declares at registration. A tool whose scope doesn't match its schema throws when the server starts.

Two more layers, both independent of the allowlist: every ID is matched against `agent_…` / `sesn_…` / `sevt_…` before it reaches the API, so a model-supplied string never becomes a URL path segment unchecked. And for production, give the server an API key from a **dedicated workspace** that holds only the agents it should serve. Then the workspace boundary does the scoping and the allowlist is the second line.

### stdio = your machine, HTTP = the network

Browser claude.ai can't spawn a local process, so stdio only works with Claude Desktop and Claude Code. The HTTP path gets you claude.ai, but now the URL is public and the **bearer token is the gate** in front of everything above. The server compares it in constant time, never logs it, and answers a wrong one with a bare 401. Don't deploy without TLS, and rotate the token like any API key.

### The Host and Origin checks

`src/server-http.ts` answers 421 unless the `Host` header is one it was told about: the loopback names by default, or `ALLOWED_HOSTS`. It answers 403 to any request that carries an `Origin` header not in `ALLOWED_ORIGINS`. Server-to-server MCP clients send no `Origin`, so this only stops browsers. Together they close DNS rebinding against a server running on your laptop, where a web page you visit resolves its own hostname to `127.0.0.1` and talks to your local port.

### Replies are untrusted text

`wait_for_idle` and `list_events` hand the backend agent's words to the frontend model. That agent may have read web pages or repo files, so treat its output as data. The tools return it inside a JSON text block, the tool descriptions are fixed strings, and `list_events` clips each field at 4,000 characters and returns a page of at most 500 events. The relay instructions above tell the frontend to pass the reply through, not to act on it.

### `idle` means finished, and nothing else does

`wait_for_idle` returns `status: "idle"` only when the agent ended its turn. `requires_action` means it is parked on a tool approval or a custom tool result that this server has no way to supply. `retries_exhausted` and `budget_reached` mean it gave up or hit its cap. `terminated` means the session is gone. In each of those, `reply` may hold a half-finished preamble. `timeout` means it is still running.

### Long turns vs tool timeout

`wait_for_idle` blocks, and the deadline is real: a timer drops the stream at `timeout_sec` even if the session emits nothing. If the agent runs for minutes (big repo clone, many tool calls), the MCP client may time out the tool call first. Mitigations: pass a smaller `timeout_sec` and loop (`status: "timeout"` comes with `last_event_id`, so call again), or have Claude poll `get_session` + `list_events(after_id=...)`.

Over HTTP there is a second clock. Nothing is written to the response while the agent works, and Bun closes a connection that has been silent for `idleTimeout` seconds (10 by default). Proxies and load balancers do the same. `src/server-http.ts` sets the transport's SSE keep-alive comment to every 5 seconds and Bun's `idleTimeout` to 30, so a quiet wait survives. If a proxy in front of your deploy still cuts long calls, its own idle timeout is shorter than 5 seconds or it buffers SSE.

### Billing

Usage bills to the Anthropic credentials in the server config, not to the chat user's account. That's the point (non-technical users, no keys), but size the workspace limits accordingly. An agent-level session budget is the other lever.

### Deliberately not exposed

| Endpoint | Why not |
|---|---|
| `agents.archive` | Permanent, no undo. One bad tool call bricks a prod agent |
| `agents.create` / `update` | Authoring belongs in the `ant` CLI or the Console, not a chat turn |
| `sessions.list` | Would enumerate every session in the workspace. Add it only with the allowlist filter `listAgents` uses |
| `sessions.delete`, `environments.*` | Destructive infra ops |
| `vaults.*`, `credentials.*` | Secrets |
| `sessions.resources.add` | Needs tokens or file IDs the chat user won't have |

Adding one is a function in `src/managed-agents.ts` plus a registration in `src/tools.ts` with its scope.

---

## Debugging

| Symptom | Check |
|---|---|
| Desktop shows no `managed-agents` tools | Config path wrong, or `bun` not on PATH for the Desktop process (use an absolute path to `bun`). Check Desktop's MCP logs. |
| `CLAUDE_ENVIRONMENT_ID is required` | Env block missing from the Desktop config. stdio servers don't read your shell's env. With Claude Code, check the `--env-file` path. |
| `ALLOWED_AGENT_IDS has an entry that is not an agent ID` | A typo or a stray space-separated value. The list is comma-separated `agent_…` IDs, and the server stops on a bad one so a typo can't pass for a working allowlist. |
| A tool answers "not available through this server" | The agent, or the session's agent, is not in `ALLOWED_AGENT_IDS`. The message is the same if the ID doesn't exist. |
| `wait_for_idle` returns empty `reply` | The agent went idle without emitting text (for example only tool calls), or `status` is not `"idle"`. `list_events` shows the full log. |
| Every turn starts a new session | Claude isn't threading `session_id`. Tighten the Project instructions. |
| `FATAL: MANAGED_AGENTS_MCP_TOKEN must be set` | Not in `.env`, or shorter than 32 characters. `bun run http` loads `.env` from this directory. |
| `FATAL: HOST=… is not loopback, so ALLOWED_HOSTS is required` | You set `HOST=0.0.0.0` (the Docker image does). Name the public hostname in `ALLOWED_HOSTS`. |
| HTTP 421 | The `Host` header isn't in `ALLOWED_HOSTS`. Add the tunnel or deploy hostname, with the port if the client sends one. |
| HTTP 403 | The request carried an `Origin` header that isn't in `ALLOWED_ORIGINS`. A browser is calling, not an MCP client. |
| HTTP 401, or the connector shows "couldn't connect" | URL wrong, server not reachable, or token mismatch. |
