# Road trip planner (Claude Managed Agents + Next.js)

A Next.js chat built directly on a Managed Agent session: no chat framework,
the event log is the app state. Teaches session event streaming
(`event_deltas`), vault credential `injection_location`, per-session
`agent_with_overrides`, and `multiagent` coordinator rosters. The planner
calls the National Park Service and Windy APIs with keys it never holds,
then hands its draft to a second agent for a quick critique. That second
agent is an Opus reviewer running as a session thread.

## When the user asks to set this up, run it, or debug it

1. **Invoke `/claude-api` first.** It loads the Managed Agents API reference
   (agents, environments, sessions, events, vaults, credentials, webhooks).
   Use it as the source of truth for any SDK call you write or edit here.
   Don't guess field names.
2. **Read [`./skill.md`](./skill.md)** and walk the user through it in order.
   It has the key signups, the provisioning step, a pointer to the four
   README steps, and the debugging table.
3. The files worth reading before changing anything are
   `src/lib/use-managed-agent-session.ts` (the client runtime: one EventSource, the
   SDK accumulator, the re-sync-on-connect habit), `agents/setup.sh` (where
   each credential's `injection_location` is set), and
   `agents/roadtrip-planner.md` (the planner prompt and the `multiagent`
   roster, which names `agents/plan-reviewer.md` by path). `src/lib/transcript.ts` is the one fold both first
   paint and live streaming render through. `src/lib/client.ts` holds
   `ownedSession()`, the check every route runs on the session cookie.

Provisioning is `./agents/setup.sh` (ant 1.34 or later, `jq`): it runs
`ant apply --yes agents environments vaults`, which creates the environment,
vault, reviewer, and planner from those directories and records their IDs in
`claude-lock.json` (read by `src/lib/resources.ts`), then adds the two vendor
keys to the vault as credentials, skipping any the vault already holds. On
re-runs apply publishes file edits onto the same resources. If it prints
`refusing to apply`, a resource was changed or archived in the Console: show
the user the reason before reaching for `--force`. A new resource is one more
file in `agents/`, `environments/`, `vaults/`, or `memory_stores/` (add that
directory to the apply line), one more getter in `src/lib/resources.ts`, and
one more `archive` line in `agents/teardown.sh`.

## Invariants to preserve when editing

- The stream is a tail, not a replay, and previews are never persisted: every
  EventSource (re)connect re-fetches the event log (via `/api/session`)
  before trusting the tail. Do not "optimize" that fetch away. It is the
  entire resume story.
- Previews are speculative. The accumulator's snapshot retires when the
  buffered `agent.message` with the same id lands in the log, an orphan
  `event_delta` (attached mid-generation) is dropped, and an errored
  `span.model_request_end` discards the open snapshot.
- One fold (`transcript.ts`) renders both history and live state. If a new
  event type should render, it goes in the fold, not in a second mapping.
- Every route that takes the session cookie goes through `ownedSession()`
  before any other API call, and refuses when it returns null. The cookie is
  browser input and the server's credentials can see every session in the
  workspace. A new route that touches a session uses it too.
- `src/proxy.ts` gates every `/api/*` route: `Host` must be loopback or in
  `ALLOWED_HOSTS`, and `Origin` must match `Host`. The routes spend the
  server's credentials with no login, so a new route goes under `/api/` to
  stay behind it.
- The `model` override is checked against `src/lib/models.ts` on the server.
  The picker and the check share that one list.
- `web_search` and `web_fetch` stay disabled on the agent. With them on, the
  model answers from the open web and the vault demo proves nothing.
- The reviewer stays tool-free: its toolset is deny-by-default
  (`default_config: {enabled: false}`), and the prompt says the same. The
  review must come from the draft alone. A poisoned draft must have no tool
  to reach, and the rail must not fill with a second agent's curls.
- The handoff is prompt-triggered. The planner's "Review step" prompt
  section decides when to message the reviewer. The user never asks and the
  app sends nothing. Weaken that section and step 4 silently disappears.
- The environment's `allowed_hosts` and each credential's `allowed_hosts`
  both list the vendor host, as exact hosts with no wildcards. Drop either
  and the calls fail differently.
- The header's model picker shows `session.agent.model` from the API
  response, never client state. An override must be visible as the resolved
  snapshot or the demo proves nothing.
- Secrets reach the vault through the heredocs in `agents/setup.sh` and
  nowhere else. Never write a vendor key into a YAML or agent file (`ant
  apply` sends those whole) or pass one as a CLI flag.
- No database. If a change needs one, it does not belong in this quickstart.
