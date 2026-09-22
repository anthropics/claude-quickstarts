# Setup tips & tricks: Linear × Claude Managed Agents webhook bridge

Things that aren't obvious from the docs and tend to cost debugging time.

---

## Mental model

### A webhook is "call me when something happens"

It's an HTTP POST a service sends to a URL you gave it, with a small JSON body describing an event. You register the URL once, and the service calls it whenever the event fires. No polling, no held-open connections.

### The bridge is mandatory (today)

Linear's Agent Platform and Managed Agents don't share a wire format or credentials. Something has to translate "Linear @mention" → "`user.message`" on the way in, and "session idle" → "Linear comment" on the way out, while holding both sets of keys. That's the bridge.

### Two webhooks, one bridge

- **Linear → bridge** (`/linear-webhook`) fires on @mention or assignment. Payload carries `agentSession.id`, `organizationId`, and issue context.
- **Anthropic → bridge** (`/managed-agents/webhook`) fires on session idle. Payload carries **only** the session ID.

Neither carries a "callback URL." Neither carries the agent's output. Both are *signals* with IDs.

### The webhook is a doorbell, not a delivery

Anthropic's `session.status_idled` payload is deliberately thin: `{type, id}`. You always follow up with `sessions.retrieve(id)` (to get metadata) and `sessions.events.list(id)` (to get the output). Push the signal, pull the data. Retries stay cheap and data is never stale.

### `metadata` is the entire routing state

When the bridge creates the session it sets `metadata: {linear_session_id, linear_org_id}`. When the idle webhook arrives later with only a session ID, the bridge retrieves the session, reads those keys back, and knows exactly where to reply, with nothing stored in the bridge itself. This is what makes it stateless.

---

## Gotchas

### Anthropic webhooks are workspace-scoped

The endpoint you register in Console only receives events for sessions **in that same workspace**. If your Anthropic credentials belong to workspace A but you registered the endpoint in workspace B, you get **zero deliveries, silently**. Match the workspace picker on the Console's Webhooks page to the Workspace column on your API key, or to the workspace `ant auth login` signed you into.

### A workspace webhook fires for *every* session in the workspace

Not only yours. If the Anthropic workspace is shared with other agents, scripts, or teammates, every `session.status_idled` in that workspace hits your endpoint. Your handler **must** filter: `sessions.retrieve(id)` → check for your `metadata` keys → return 204 for anything that isn't yours. Also catch 404/403 on `sessions.retrieve`, and only those. Sessions created under other API keys in the same workspace aren't readable by yours, but a 429 or 5xx is a real failure that should be retried.

Corollaries: subscribe only to the event types you need (`session.status_idled`, `session.status_terminated`), not "All events". For production, consider a dedicated Anthropic workspace so there are no unrelated sessions to discard.

### Linear OAuth apps are workspace-admin-only

OAuth apps live at `linear.app/<your-workspace>/settings/api`. In the sidebar it's **Administration → API**, then the **OAuth Applications** section. If you're not an admin of your company workspace, spin up a free personal workspace for testing. It takes two minutes and you won't install an experimental agent into production.

When creating the app, the **Developer URL** field is required but cosmetic (it's a link shown on the consent screen). Any real `https://` URL is fine.

### `actor=app` is the load-bearing OAuth parameter

`scope=app:assignable,app:mentionable` + `actor=app` is what creates an **app user** in the Linear workspace that shows up in the @-picker. A personal `LINEAR_API_KEY` won't do this. The bridge must post back *as the app*, via the OAuth token.

### `BASE_URL` has to match the callback URL exactly

`src/oauth.ts` builds the redirect URI as `${BASE_URL}/oauth/callback` and sends it on both the authorize redirect and the token exchange. Linear rejects the exchange unless it matches the callback URL registered on the OAuth app character for character. A new ngrok URL means updating both `.env` and the Linear app.

### The first install owns the bridge

`/oauth/authorize` has no login in front of it. Anyone who can reach the server could install the agent into a Linear workspace they administer, and from then on every mention there would run a session on your Anthropic credentials. So the gate fails closed. With `LINEAR_ALLOWED_ORG_IDS` unset, the first workspace to install is the only one the bridge serves: a later install from a different workspace gets a 403 and its token is revoked, and webhook events from it are ignored. Install your own workspace right after you start the server, and check the log line names it.

Set `LINEAR_ALLOWED_ORG_IDS` to a comma-separated list of organization IDs to pin that choice or to serve more than one workspace. The server logs the organization ID on each install. To hand the bridge to a different workspace, delete `.linear-tokens.json` and install again.

The flow also uses a single-use `state` value that expires after 10 minutes, so a callback only succeeds if this server started it. Restarting the server forgets pending states. If you see "Unknown or expired state", start again at `/oauth/authorize`.

### The idle webhook only trusts routes it signed

`metadata` says where to reply, but it does not prove the session is the bridge's. Anyone with credentials for the same Anthropic workspace can start a session, on this same agent, with `linear_session_id` and `linear_org_id` of their choosing. A handler that trusted those keys would post their text into your Linear issue with your token. Checking `session.agent.id` and `session.environment_id` is a useful first filter and nothing more, because agent IDs are not secrets.

So at kickoff `src/agent.ts` stores `linear_route_sig`, an HMAC over the Claude session ID, the Linear session ID, and the organization ID, keyed by a secret derived from `LINEAR_CLIENT_SECRET`, which never leaves the bridge. `src/managed-agents-webhook.ts` recomputes it and compares in constant time before posting anything. The Claude session ID is part of the signed text on purpose: metadata is readable by the same people who can forge it, so a signature over the route alone could be copied onto another session. The signature is also single-use. A signed session is still a session that anyone with workspace credentials can send another message to, and its next idle would post their text into the issue. So once the bridge has delivered, or decided it never will, it deletes `linear_route_sig` from the metadata, and later idles are refused. A retryable failure leaves it in place so the retry can still verify. The bridge also remembers delivered sessions in memory and takes a per-session lock right after verifying, because the remote delete can fail and two idle events for one session carry different event ids. And the signed text includes an issued-at time: a route older than 24 hours is refused, so one whose delivery keeps failing does not stay live with no end. An agent run longer than that loses its reply. Raise `MAX_AGE_SECONDS` in `src/route-signature.ts` if yours do. If you fork this, keep the verify call between the metadata read and the first Linear call, and keep the delete after the delivery. Rotating `LINEAR_CLIENT_SECRET` invalidates the signatures of sessions still running, and their replies are dropped with a log line.

### Issue text is untrusted input

The prompt is the issue title, description, and comments, which anyone with access to the Linear workspace can write. `src/agent.ts` wraps each piece in a tag such as `<linear_issue_description>` and the system prompt tells the agent to treat tagged text as data. That lowers the odds that an injected instruction is followed. It does not remove them. The agent has the full toolset (`bash`, web fetch) with `always_allow`, in a sandbox with unrestricted egress, and nobody approves a step. Treat it like running a script a stranger wrote: keep secrets out of the sandbox, and if you mount a repo or add MCP tools, scope their credentials to what a hostile issue should be able to touch. `agents/linear-assistant/environment.yaml` is where to switch networking to `limited` with an allowlist.

### Linear's 10-second ack rule

The bridge must post *some* `agentActivity` (a `{type: "thought"}` is enough) within 10 seconds of receiving the `AgentSessionEvent`, or Linear marks the session failed. Do this *before* creating the Managed Agents session.

### `event.id` is your idempotency key

Anthropic retries failed deliveries with the **same** top-level `event.id`. Dedupe on it, but only mark an id handled once handling finished. If it threw, the retry has to be processed or the reply is lost. A duplicate that arrives while the first attempt is still running gets a 503, not a 204: acking it would mark the event delivered while the outcome is still unknown. Return 2xx once you've either handled it or decided to ignore it. Anything else triggers a retry, and ~20 consecutive failures auto-disables your endpoint. That is why a Linear error a retry can't fix (no token for the org, a revoked install or a refused token refresh, an agent session Linear has closed) is logged and acked instead of thrown.

### Stop interrupts the run, best effort

Linear sends Stop as a `prompted` event whose activity carries `signal: "stop"`. Treated as a prompt, it would start a second session. `src/agent.ts` remembers which Claude session is working on each Linear session, sends that session `user.interrupt`, posts "Stopped.", and the idle webhook then skips the interrupted run's half-finished text.

That map is the one piece of state the bridge keeps, and it lives in memory. After a restart the bridge has no record of runs started before it, so Stop says exactly that instead of claiming a stop that did not happen. Reply routing never depends on the map. It still reads `metadata`. For production, keep `linear_session_id → session.id` in Redis or a DB.

### No approval surface, so tools are `always_allow`

`agents/linear-assistant/agent.yaml` sets `permission_policy: {type: always_allow}` on the toolset. An `always_ask` tool idles the session to wait for a confirmation, the idle webhook fires, and the bridge posts whatever partial text exists. If you add an approval flow (Linear's `elicitation` activity plus `user.tool_confirmation`), switch the risky tools back to `always_ask`.

### Signature header names

The docs say `X-Webhook-Signature`. The wire uses `Webhook-Signature` / `Webhook-Id` / `Webhook-Timestamp` (Standard Webhooks spec). The SDK's `webhooks.unwrap()` handles this, so it only matters if you're verifying by hand.

---

## Local dev checklist

1. `ngrok http 3000` (or `cloudflared tunnel`) → note the public URL and set it as `BASE_URL` in `.env` (`cp .env.example .env` first). Everything below uses it.
2. `ant auth login` (or set `ANTHROPIC_API_KEY` in `.env`), then `./agents/setup.sh`. It appends `CLAUDE_AGENT_ID` and `CLAUDE_ENVIRONMENT_ID` to `.env`. **Don't overwrite them later** when you paste in the Linear secrets.
3. Linear OAuth app (**Administration → API → OAuth Applications → Create new**): Developer URL = any real `https://` URL (cosmetic). Callback `<url>/oauth/callback`. Webhook `<url>/linear-webhook`, events = Agent session events → copy client ID/secret + webhook secret into `.env`.
4. Claude Console → **Manage → Webhooks**: `<url>/managed-agents/webhook`, events = `session.status_idled` + `session.status_terminated` → copy `whsec_…` → `ANTHROPIC_WEBHOOK_SIGNING_KEY`. **Same workspace as your Anthropic credentials.**
5. `bun run dev`.
6. Visit `<url>/oauth/authorize` → approve → "Agent installed." The server logs `[oauth] installed in "<name>" (<org-id>)`. That workspace now owns the bridge. Put the ID in `LINEAR_ALLOWED_ORG_IDS` to pin it.
7. @mention it in an issue.

### Debugging a silent failure

- **"Thinking…" never appears** → Linear webhook isn't reaching you. Check the Linear app's webhook URL and that ngrok is up. If the log shows `ignored event from org …`, a different workspace installed first or that workspace isn't in `LINEAR_ALLOWED_ORG_IDS`.
- **"Thinking…" appears but no reply** → check `curl localhost:4040/api/requests/http` (ngrok's request log). If no POST to `/managed-agents/webhook`: workspace mismatch on the Anthropic side, or endpoint not saved. If POST arrives with 401: signing key mismatch. If the log shows `could not post to linear=…`: the message names the cause, usually a missing `.linear-tokens.json` entry (reinstall at `/oauth/authorize`).
- **`FATAL: … .linear-tokens.json is not valid`** at startup → the token file is corrupt. The bridge refuses to start on it, because reading it as empty would let any workspace install. Fix the JSON, or delete the file and reinstall at `/oauth/authorize`.
- **`FATAL: CLAUDE_AGENT_ID is required`** → `./agents/setup.sh` hasn't run yet. It appends the IDs to `.env` in this directory.
- **`./agents/setup.sh` fails with 409 on the environment** → environment names are unique per workspace and someone already created `quickstart-linear-assistant-env` there. Paste that environment's ID into `.env` as `CLAUDE_ENVIRONMENT_ID`, or change `name` in `agents/linear-assistant/environment.yaml`, then re-run.
- **`Linear refused to refresh the token for org …`** in the log → Linear answered `invalid_grant`: the workspace uninstalled the app. Reinstall at `/oauth/authorize`. An `invalid_client` in the log instead means `LINEAR_CLIENT_SECRET` is wrong.
- **"Linear rejected the install"** after approving → the server log has Linear's response. The usual cause is `BASE_URL` not matching the app's callback URL.
- **The bot answers with an old prompt or model** → Bun loads `.env.local` over `.env`. If you have one left from the cookbook version of this bridge, delete it.

---

## Production notes

- Replace ngrok with a real deploy (Cloudflare Workers, Fly, etc.). Nothing else changes.
- Replace the in-memory `seenEventIds` Set and the pending OAuth `state` map with Redis or a DB for multi-instance deploys.
- Replace the `.linear-tokens.json` file with a real secret store. The bridge writes it owner-only (`0600`) and replaces it atomically, which is enough for a laptop and not for a server.
- Narrow the Anthropic endpoint's event subscription to exactly what you handle.
