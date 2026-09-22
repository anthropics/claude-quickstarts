# Road trip planner: stream sessions, scope vault credentials, override models, and review plans agent-to-agent

A Next.js chat built directly on a [Claude Managed Agent](https://platform.claude.com/docs/en/managed-agents/overview) [session](https://platform.claude.com/docs/en/managed-agents/sessions). There is no chat framework and no database: the session's event log is the message list, the live tokens are its SSE tail, and the only server code in the streaming path is a thin proxy that keeps the API key out of the browser. The agent plans road trips around any US national park. You'll see four API features on one screen:

1. **Stream the turn live.** `event_deltas[]=...` on [`GET /v1/sessions/{id}/events/stream`](https://platform.claude.com/docs/en/managed-agents/events-and-streaming) interleaves previews with the buffered event log. `agent.message` previews carry the reply token by token, and `agent.thinking` previews fire the moment extended thinking starts. Tool calls, results, retries, and usage ride the same stream, so the UI renders the whole turn as it happens. Without previews the same chat is seconds of blank, then a paragraph.
2. **Inject [vault credentials](https://platform.claude.com/docs/en/managed-agents/vaults) at a specific request location.** The agent authenticates to two vendor APIs with keys it never holds. The National Park Service wants its key in a request header and Windy wants it inside the JSON body. The `injection_location` field on each credential controls where the placeholder may be swapped for the real value at egress.
3. **Override agent settings per session.** Every session is created with the `agent_with_overrides` selector. The model picker adds a `model` override to it, rerunning the same stored agent on a different model. One agent, no per-user copies, no new versions.
4. **Hand the draft to a second agent.** The planner is a `multiagent` coordinator with one roster entry: a reviewer agent running Opus. When it drafts an itinerary it spawns the reviewer as a session thread, messages it the draft, and waits for the critique. The whole exchange is ordinary session events (`session.thread_created`, `agent.thread_message_sent`, `agent.thread_message_received`) on the same stream the chat already renders, so you watch the two agents talk to each other.

```
browser ──▶ POST /api/chat ──▶ sessions.events.send(user.message)
   ▲
   │ one EventSource              GET /v1/sessions/{id}/events/stream
   └── GET /api/stream ◀──────────   ?event_deltas[]=agent.message
       (a thin SSE proxy)            &event_deltas[]=agent.thinking

   src/lib/use-managed-agent-session.ts: accumulate previews (SDK helper),
   append buffered events, fold the log into turns, render

sandbox ── curl -H "X-Api-Key: $NATIONAL_PARK_SERVICE_API_KEY" ──▶ egress ──▶ developer.nps.gov
           the env var is an opaque placeholder                    └─ swaps in the real key when the
                                                                      host and the location are allowed

planner ── agent.thread_message_sent (the draft) ──▶ reviewer thread (Opus, same session)
        ◀── agent.thread_message_received (the critique) ──┘
```

The session is the backend: the agent remembers the conversation, the transcript is `GET /v1/sessions/{id}/events`, and the browser holds one httpOnly cookie with the session id.

The new API calls, and where to read them:

- `event_deltas` on the session event stream: [`src/app/api/stream/route.ts`](./src/app/api/stream/route.ts), the SSE proxy
- the SDK's `accumulateManagedAgentsEvent` folding previews in the browser: [`src/lib/use-managed-agent-session.ts`](./src/lib/use-managed-agent-session.ts)
- the event log folded into renderable turns: [`src/lib/transcript.ts`](./src/lib/transcript.ts)
- `injection_location` provisioned on each credential: the two credential blocks in [`agents/setup.sh`](./agents/setup.sh)
- `injection_location` flipped on a live credential: one `ant` CLI call, step 2 below
- `agent_with_overrides` on session create: [`src/app/api/session/route.ts`](./src/app/api/session/route.ts)
- the `multiagent` coordinator roster on the planner agent: [`agents/roadtrip-planner.md`](./agents/roadtrip-planner.md)
- thread events folded into the rail and the chat: [`src/lib/transcript.ts`](./src/lib/transcript.ts)

## Quickstart

Needs Node 20 or later, the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart) 1.34 or later (`brew install anthropics/tap/ant`), `jq`, and Anthropic auth for an organization with Managed Agents access: `ant auth login` once, or an API key from [platform.claude.com](https://platform.claude.com/). It also needs two free vendor keys:

- A National Park Service API key, emailed instantly: <https://www.nps.gov/subjects/developer/get-started.htm>
- A Windy Point Forecast API key, free tier: <https://api.windy.com/point-forecast/docs>

```bash
cd managed-agents/roadtrip-planner
npm install
claude "walk me through setting this up"   # reads skill.md and drives the rest
```

Or by hand:

```bash
ant auth login            # or put ANTHROPIC_API_KEY in .env
cp .env.example .env      # fill in NATIONAL_PARK_SERVICE_API_KEY and WINDY_API_KEY
./agents/setup.sh         # `ant apply`: environment + vault + 2 agents; then the 2 credentials
npm run dev               # http://localhost:3000
```

`setup.sh` runs [`ant apply`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/apply) on four files: the planner in [`agents/roadtrip-planner.md`](./agents/roadtrip-planner.md) and the reviewer in [`agents/plan-reviewer.md`](./agents/plan-reviewer.md) (frontmatter is the configuration, prose is the system prompt), the environment in [`environments/roadtrip-planner.yaml`](./environments/roadtrip-planner.yaml), and the vault in [`vaults/roadtrip-planner.yaml`](./vaults/roadtrip-planner.yaml). The planner's roster names the reviewer's file, so `ant apply` creates the reviewer first and pins the planner to its version. It records every ID in `claude-lock.json`, which the app reads. The one thing it never touches is a secret, so `setup.sh` then puts the two vendor keys into the vault as credentials. To change either agent (model, prompt, tools), edit its file and re-run `./agents/setup.sh`: apply publishes a new version that new trips pick up. `./agents/teardown.sh` archives everything and removes `claude-lock.json`. This repository ignores that file, since every reader creates their own resources. In a project of your own, commit it.

Setup provisions each credential with the injection location its vendor documents, hardcoded in [`agents/setup.sh`](./agents/setup.sh):

| secret | host | injected in |
|---|---|---|
| `NATIONAL_PARK_SERVICE_API_KEY` | `developer.nps.gov` | header (`X-Api-Key`) |
| `WINDY_API_KEY` | `api.windy.com` | body (`"key": ...`) |

Same credential type, same vault, opposite `injection_location`. The model never sees either value.

## Before you deploy

This demo has no user accounts. The cookie ties one browser to one session and nothing more, so run it on localhost. Three things are in place, and all three need to stay if you fork it:

- **Every route checks that the session belongs to this app.** The cookie value comes from the browser and becomes an API path parameter, and the server's Anthropic credentials can see every session in the workspace. `ownedSession()` in [`src/lib/client.ts`](./src/lib/client.ts) only accepts an ID that resolves, was created on this quickstart's planner agent, and is still live. Stream, chat, and interrupt answer 403 to anything else, and `/api/session` starts a new trip instead of returning someone else's events. Keep that function in the path of anything that takes a session ID from a client.
- **Every `/api/*` request has to come from this app's own page.** A web page open in the same browser can POST to `localhost:3000` with no preflight, and a DNS rebinding page can make itself same-origin with it. Either one could create sessions on your Anthropic credentials. [`src/proxy.ts`](./src/proxy.ts) refuses a request whose `Host` is not loopback or listed in `ALLOWED_HOSTS`, whose `Origin` does not match `Host`, or that the browser marks `Sec-Fetch-Site: cross-site`. Set `ALLOWED_HOSTS` to the public hostname if you serve the app from one.
- **The `model` override is checked against the picker's list** ([`src/lib/models.ts`](./src/lib/models.ts)) before it reaches `sessions.create`, so a caller cannot run your agent on a model you did not offer.

Put real authentication in front of all four routes before exposing the app beyond your machine.

## Four things to do with it

Each one is a runnable step. Together they are the quickstart.

### 1. Ask for a trip

"Plan a 5 day road trip split between Zion and Bryce Canyon for the first week of October." The agent resolves the parks first (`/parks?q=...`), then plans from what the APIs return. The status line flips to "thinking..." the moment the model starts reasoning: that is the `agent.thinking` preview, where the buffered event only lands when thinking ends. The reply renders as the model writes it. The right rail shows each `curl` the agent runs in its sandbox (it budgets itself to five per question), each against an allowed host, each authenticated with a key it cannot read. Any park works: swap in Acadia, Yellowstone, Joshua Tree.

### 2. Flip one field and watch a vendor reject the placeholder

Update the live credential with the `ant` CLI. It uses the same credentials `./agents/setup.sh` did. The vault's ID is in `claude-lock.json`, and the vault lists its credentials:

```bash
vault=$(jq -r '.resources["./vaults/roadtrip-planner.yaml"].id' claude-lock.json)
nps=$(ant beta:vaults:credentials list --vault-id "$vault" --format jsonl | jq -r 'select(.auth.secret_name == "NATIONAL_PARK_SERVICE_API_KEY").id')
ant beta:vaults:credentials update \
  --vault-id "$vault" \
  --credential-id "$nps" \
  --auth '{type: environment_variable, injection_location: {header: false, body: true}}'
```

The National Park Service only accepts its key in a header, and header injection is now off for that credential. Nothing substitutes the placeholder, the next NPS call carries it literally, and NPS rejects it. Ask "is anything closed at the park right now" and watch the 4xx land in the tool rail: the agent shows the status and body, retries the documented header location once, then says plainly that NPS is rejecting its key while it keeps planning with the weather API. Heal it by setting the credential back to the location its vendor documents:

```bash
ant beta:vaults:credentials update \
  --vault-id "$vault" \
  --credential-id "$nps" \
  --auth '{type: environment_variable, injection_location: {header: true, body: false}}'
```

One field, no secret rotation, no redeploy, visible consequence. The same flip works the other way on the Windy credential (`secret_name == "WINDY_API_KEY"`, with the two booleans inverted), because Windy only documents body auth.

### 3. Run the same agent on a different model

Pick another model in the header. A new trip starts with a `model` override on the selector every session already uses:

```ts
client.beta.sessions.create({
  agent: { type: "agent_with_overrides", id: agentId, model: "claude-opus-5" },
  // ...
});
```

The override replaces the stored agent's model for this session only. The header shows the model from the session's resolved `agent` snapshot (`session.agent.model`), so what you read is what the API resolved, not what the client asked for. The stored agent never changes: no copy, no new version, and "New trip" returns to its configured model. `system`, `tools`, `mcp_servers`, and `skills` are overridable the same way.

### 4. Watch the planner get its plan reviewed

Ask for a full multi-day itinerary (step 1's Zion and Bryce prompt works). After the draft is written, the status line flips to "waiting on Plan reviewer...": the planner spawned its roster agent as a session thread and messaged it the draft. The reviewer is a second stored agent. The planner's roster names its file, and `ant apply` turns that path into the reviewer's ID and version, creating the reviewer first:

```markdown
# agents/plan-reviewer.md
---
name: Plan reviewer
model: claude-opus-5
tools:
  - type: agent_toolset_20260401
    default_config:
      enabled: false
---
You review road trip itineraries drafted by another agent. ...

# agents/roadtrip-planner.md
---
name: Road trip planner
model: claude-sonnet-5
multiagent:
  type: coordinator
  agents:
    - ./plan-reviewer.md    # ant apply sends {type: agent, id, version}
---
```

Nobody asks for the review. The roster grants the capability, and the planner's own system prompt decides when to use it: a new day-by-day itinerary gets reviewed, a quick factual answer does not. The send is not a tool call and not an app request. The only trace is the thread events themselves.

Two models in one session: the planner drafts on Sonnet, the gut-check runs on Opus. The reviewer's toolset is deny-by-default, which is both a security boundary (a poisoned draft has no tool to reach) and what keeps the review fast: it judges the draft text alone. Its reply still routes back, because agent-to-agent messaging is platform machinery, not a tool.

The exchange renders in two places, fed by the same events. In the chat, two chips: "to Plan reviewer" (the draft going out) and "from Plan reviewer" (the critique coming back). In the rail: `session.thread_created`, then both `agent.thread_message_*` events with their full text, then the thread's status events as it goes idle. The planner's final reply ends with a "Reviewer flagged" line when the critique raised something it could not verify from the APIs.

The review costs one extra agent and zero plumbing: no queue, no webhook, no second session. The thread lives inside the session, its lifecycle events cross-post to the stream the page already holds open, and the agent-to-agent messages are persisted events, so the exchange survives a reload like everything else.

## The client

A Managed Agents session already is a resumable chat backend, so the client is three pieces, all in [`src/lib/use-managed-agent-session.ts`](./src/lib/use-managed-agent-session.ts) and [`src/lib/transcript.ts`](./src/lib/transcript.ts):

- **One EventSource** on `/api/stream`, a thin proxy of the session's SSE tail. The browser owns reconnect, and every connect re-fetches the event log first: the stream is a tail, not a replay, and previews are never persisted. That habit is the whole resume story: reload mid-answer and the page renders what streaming rendered.
- **The SDK's `accumulateManagedAgentsEvent`**, run in the browser, folds `event_start` / `event_delta` previews into one growing `agent.message` snapshot. Previews are speculative: the buffered event with the same id retires the snapshot, and because the ids match, the rendered part does not jump. A delta for a preview the client never saw open (it attached mid-generation) is dropped, and the buffered event delivers the whole thing. An errored model request never produces its buffered event, so its terminal `span.model_request_end` drops the snapshot instead.
- **One fold** from the event array to renderable turns. The same fold runs over hydrated history and the live array, so a reload renders what streaming rendered, turn stats included.

Everything else on the stream is a status signal: thinking starts drive the activity line, `span.model_request_*` drive the working state and token stats, `agent.thread_message_sent` flips the activity line to "waiting on Plan reviewer..." until the reply lands, and `session.error` distinguishes a retry in progress from a dead turn. Stop is a real API verb: the button POSTs `user.interrupt`, the agent winds down, and the `session.status_idle` that follows flips the UI back to ready.

<details>
<summary><strong>Caveats</strong></summary>

- `injection_location` has two flags: `header` and `body`. There is no query-string option, so a key in `?api_key=...` is never substituted. APIs that only accept query-param auth can't use environment variable credentials, and if the agent falls back to NPS's `?api_key=` form the request carries the placeholder.
- Two allowlists must agree. The [environment](https://platform.claude.com/docs/en/managed-agents/environments)'s `networking.allowed_hosts` controls what the sandbox can reach at all, and the credential's `networking.allowed_hosts` controls where its secret may be substituted. A host missing from the first never connects, and a host missing from the second gets the placeholder. Both list exact hosts. A wildcard on the credential would let the real key be substituted on a host you did not mean.
- Streaming previews cover `agent.message` (text deltas) and `agent.thinking` (start only) on the session's primary thread. Tool calls and subagent threads arrive as buffered events, so the reviewer's critique lands whole, not token by token.
- The roster is flat: 1 to 20 entries, and a roster agent cannot have a roster of its own (depth limit 1). The model picker overrides the planner only. The reviewer thread always runs the reviewer agent's stored model.
- Vaults and the model both attach at `sessions.create`. You can update a credential in a vault a running session already holds, but a different vault or a different model means a new session, which is why the picker starts a new trip.
- `./agents/setup.sh` creates the two credentials once. Re-running it applies edits to the vault, environment, and both agents from their files, but leaves live credentials alone so a flip from step 2 survives. To rotate a vendor key, update the credential's `secret_value` with `ant beta:vaults:credentials update`, or run `./agents/teardown.sh` and set up again.

</details>

## Files

| | |
|---|---|
| `agents/roadtrip-planner.md`, `agents/plan-reviewer.md` | The planner (with its roster) and the reviewer, as files for `ant apply` |
| `environments/roadtrip-planner.yaml`, `vaults/roadtrip-planner.yaml` | The sandbox and the vault container, as files for `ant apply` |
| `agents/setup.sh` | `ant apply` for the four resources, then the two credentials. Creates on the first run, updates in place after |
| `agents/teardown.sh` | Archive sessions and everything in `claude-lock.json`, then remove it |
| `src/lib/resources.ts` | Reads the planner, environment, and vault IDs from `claude-lock.json` |
| `src/lib/client.ts` | The shared SDK client, the session cookie name, and `ownedSession()` |
| `src/lib/models.ts` | The models the picker offers and `/api/session` accepts |
| `src/lib/use-managed-agent-session.ts` | The client runtime: one EventSource, the SDK accumulator, send/stop |
| `src/lib/transcript.ts` | The event log folded into renderable turns |
| `src/proxy.ts` | The gate on every `/api/*` route: loopback or `ALLOWED_HOSTS`, and same-origin only |
| `src/app/api/session/route.ts` | Create or resume the session behind the cookie, return the event log |
| `src/app/api/stream/route.ts` | SSE proxy of the session tail (the API key stays server-side) |
| `src/app/api/chat/route.ts` | Send one `user.message` |
| `src/app/api/interrupt/route.ts` | Send `user.interrupt` (the stop button) |
| `src/app/page.tsx` | The chat, the model picker, the tool rail |
| `skill.md` | Setup walkthrough and debugging table |

Requires `@anthropic-ai/sdk` ≥ 0.109.0.
