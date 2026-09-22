# Setup tips & tricks: Slack × Claude Managed Agents webhook bridge

Things that aren't obvious from the docs and tend to cost debugging time.

---

## Mental model

### Two webhooks, one bridge

- **Slack → bridge** (`/slack/events`) fires on @mention. Payload carries `channel`, `ts`, `thread_ts`, `user`, `text`.
- **Anthropic → bridge** (`/managed-agents/webhook`) fires on session idle. Payload carries **only** the session ID.

Neither carries the agent's output. Both are *signals* with IDs.

### The webhook is a doorbell, not a delivery

Anthropic's `session.status_idled` payload is deliberately thin: `{type, id}`. You follow up with `sessions.retrieve(id)` (metadata) and `sessions.events.list(id)` (output). Push the signal, pull the data.

### `metadata` is the entire routing state

On kickoff, set `metadata: {slack_channel, slack_thread_ts, slack_team}`. When the idle webhook arrives later with only a session ID, retrieve the session, read those keys back, and `chat.postMessage` to exactly the right thread, with nothing stored in the bridge itself. This is what makes it stateless.

### Slack's 3-second ack window

Slack retries any event that doesn't get a 2xx within 3 seconds. The bridge **must** return before the session finishes. So: verify the signature, dedupe on `event_id`, fire `kickoffAgentSession()` without awaiting it, and return 204 immediately.

---

## Gotchas

### Use a developer sandbox, not your company workspace

Slack's [Developer Program sandboxes](https://api.slack.com/developer-program/sandboxes) give you a free Enterprise Grid org to test in: admin rights, fake users/channels, no risk of installing a half-built bot into production. This is **not** the "agent quickstart". It's **Developer Program → Sandboxes**:

1. Join the [Slack Developer Program](https://api.slack.com/developer-program) → activate via email → accept ToS.
2. From the program dashboard: **Provision Sandbox** → pick empty or pre-loaded with fake users/channels → click again.
3. Finish setup from the email invite. You become Primary Org Owner. Name the org and create at least one workspace inside it.
4. Create your app against that sandbox workspace and develop normally.

### OAuth scope ≠ event subscription

Adding `app_mentions:read` under **OAuth & Permissions → Bot Token Scopes** grants *permission* to see mentions. It does **not** cause Slack to deliver them. You must *also* go to **Event Subscriptions**, toggle it **On**, set the Request URL, and add `app_mention` under "Subscribe to bot events." Two separate pages. Miss the second one and you get zero deliveries with no error anywhere.

### `xoxb-` vs `xapp-`: two tokens, two pages, easy to grab the wrong one

| Token | Prefix | Page | Used for |
|---|---|---|---|
| Bot User OAuth Token | `xoxb-` | OAuth & Permissions (after install) | `chat.postMessage`. **This is the one you want** |
| App-Level Token | `xapp-` | Basic Information → App-Level Tokens | Socket Mode WebSocket only |

`chat.postMessage` with an `xapp-` token fails with `invalid_auth`. The `xoxb-` token only exists after you've added at least one bot scope **and** clicked Install/Reinstall to Workspace.

### Bridge must be running before you save the Request URL

Saving the Event Subscriptions URL triggers an immediate `url_verification` POST. If nothing is listening on the tunnel you get "Your URL didn't respond" and the URL won't save. Start `bun run dev` first, *then* paste the URL.

### Anthropic webhooks are workspace-scoped

The endpoint you register in Console only receives events for sessions **in that same workspace**. If your Anthropic credentials are from workspace A but you registered the endpoint in workspace B: zero deliveries, silently. Match the workspace picker on the Webhooks page to the Workspace column on your API key, or to the workspace `ant auth login` signed you into.

### A workspace webhook fires for *every* session in the workspace

Not only yours. If the Anthropic workspace is shared with other agents, scripts, or teammates, **every** `session.status_idled` in that workspace hits your endpoint. Your handler has to filter:

- **Retrieve-then-filter, always first.** `sessions.retrieve(id)` → check for your `slack_channel` metadata key → bail with 204 if absent. Do this *before* `events.list()` or any other work. Otherwise unrelated sessions throw 404 deeper in the handler.
- **Catch 404/403 on `sessions.retrieve`.** Sessions created under other API keys in the same workspace aren't readable by yours.
- **For production, use a dedicated Anthropic workspace.** Each unrelated session costs one `retrieve()` call to discard it. A workspace that only contains this agent's sessions avoids that.

### The idle webhook only trusts routes it signed

`metadata` says where to reply, but it does not prove the session is the bridge's. Anyone with credentials for the same Anthropic workspace can start a session, on this same agent, with `slack_channel` and `slack_thread_ts` of their choosing. A handler that trusted those keys would post their text into your Slack channel with your bot token. Checking `session.agent.id` and `session.environment_id` is a useful first filter and nothing more, because agent IDs are not secrets.

So at kickoff `src/agent.ts` stores `slack_route_sig`, an HMAC over the session ID, channel, and thread, keyed by a secret derived from `SLACK_SIGNING_SECRET`, which never leaves the bridge. `src/managed-agents-webhook.ts` recomputes it and compares in constant time before posting anything. The session ID is part of the signed text on purpose: metadata is readable by the same people who can forge it, so a signature over the route alone could be copied onto another session. The signature is also single-use. A signed session is still a session that anyone with workspace credentials can send another message to, and its next idle would post their text into the channel. So once the bridge has delivered, or decided it never will, it deletes `slack_route_sig` from the metadata, and later idles are refused. A retryable failure leaves it in place so the retry can still verify. The bridge also remembers delivered sessions in memory and takes a per-session lock right after verifying, because the remote delete can fail and two idle events for one session carry different event ids. And the signed text includes an issued-at time: a route older than 24 hours is refused, so one whose delivery keeps failing does not stay live with no end. An agent run longer than that loses its reply. Raise `MAX_AGE_SECONDS` in `src/route-signature.ts` if yours do. If you fork this, keep the verify call between the metadata read and the first Slack call, and keep the delete after the delivery. Rotating `SLACK_SIGNING_SECRET` invalidates the signatures of sessions still running, and their replies are dropped with a log line.

### Message text is untrusted input

The prompt is whatever a Slack user typed. The agent has the full toolset (`bash`, web fetch) with `always_allow`, in a sandbox with unrestricted egress, and nobody approves a step. `src/agent.ts` wraps the message in `<slack_message>` tags and the system prompt tells the agent that tagged text is data. That lowers the odds that an injected instruction is followed. It does not remove them. Keep secrets out of the sandbox, scope any repo or MCP credentials you add to what a hostile message should be able to touch, and consider switching `environments/slack-assistant.yaml` to `limited` networking with an allowlist.

### `unwrap()` needs a plain header map

`client.beta.webhooks.unwrap(body, {headers})` wants `Record<string, string>`, not a fetch `Headers` object. Pass `Object.fromEntries(req.headers)`.

### `event.id` is your idempotency key

Anthropic retries failed deliveries with the **same** top-level `event.id`. Slack retries with the same `event_id` inside the body. Dedupe on both, but only mark an Anthropic id handled once handling finished. If it threw, the retry has to be processed or the reply is lost. A duplicate that arrives while the first attempt is still running gets a 503, not a 204: acking it would mark the event delivered while the outcome is still unknown. Return 2xx once you've either handled or ignored the event. Anything else triggers a retry, and ~20 consecutive Anthropic failures auto-disables your endpoint.

### No approval surface, so tools are `always_allow`

`agents/slack-assistant.md` sets `permission_policy: {type: always_allow}` on the toolset. An `always_ask` tool idles the session with `stop_reason: requires_action`. The bridge reads the idle event's `stop_reason`, so it posts a warning that the agent is waiting on an approval nobody can give, not the half-finished preamble. `budget_reached` and `retries_exhausted` get a warning too. Only `end_turn` posts the reply. If you add an approval flow (a Slack button that sends `user.tool_confirmation`), switch the risky tools back to `always_ask`.

---

## Local dev checklist

1. `ngrok http 3000` → note the public URL. Optionally set it as `BASE_URL` in `.env` so the startup log prints the two full webhook URLs.
2. `ant auth login` (or export `ANTHROPIC_API_KEY`), then `ant apply agents environments`. It creates the agent and environment and writes their IDs to `claude-lock.json`, which the bridge reads at startup. Nothing to paste into `.env` for them; `cp .env.example .env` for the Slack secrets below.
3. Slack app → **OAuth & Permissions** → Bot Token Scopes: `app_mentions:read`, `chat:write` (+ `im:history` for DMs) → **Install to Workspace** → copy `xoxb-…` → `SLACK_BOT_TOKEN`.
4. Slack app → **Basic Information** → copy **Signing Secret** → `SLACK_SIGNING_SECRET`.
5. Claude Console → **Manage → Webhooks**: `<url>/managed-agents/webhook`, subscribe `session.status_idled` + `session.status_terminated` → copy `whsec_…` → `ANTHROPIC_WEBHOOK_SIGNING_KEY`. **Same workspace as your Anthropic credentials.**
6. `bun run dev`. The server must be up *before* step 7.
7. Slack app → **Event Subscriptions** → On → Request URL `<url>/slack/events` → Verified ✓ → add bot event `app_mention` (+ `message.im` for DMs, and turn on **App Home → Messages Tab**) → **Save Changes** → reinstall if prompted.
8. In Slack: `/invite @your-bot` to a channel, then `@your-bot hello`.

### Debugging a silent failure

- **Nothing in the bridge log at all** → Slack isn't reaching you. Check `curl localhost:4040/api/requests/http` (ngrok's request log). No `/slack/events` POSTs = Event Subscriptions not saved, or Socket Mode is on.
- **`[agent] kickoff` logged but no reply** → ngrok log shows `/managed-agents/webhook` POSTs? If none: Anthropic workspace mismatch or endpoint not saved. If 401: `ANTHROPIC_WEBHOOK_SIGNING_KEY` mismatch. If the log shows `chat.postMessage failed`: `invalid_auth` means `SLACK_BOT_TOKEN` is wrong (check for `xapp-`), `missing_scope` means no `chat:write`.
- **`FATAL: no agent or environment ID`** → `ant apply agents environments` hasn't run in this directory yet, so there is no `claude-lock.json` beside `package.json`, or it stopped partway and the lockfile lacks one of the two (run it again and read its error). If you ran it from another directory, the lockfile is there instead: run it again from here.
- **`ant apply` fails with 409 on the environment** → environment names are unique per workspace and someone already created `quickstart-slack-assistant-env` there (an earlier run of this quickstart's old `agents/setup.sh`, usually). The environment is created first, so the agent was not created either. `ant apply` can't adopt an existing resource: change `name` in `environments/slack-assistant.yaml` and run `ant apply agents environments` again. To reuse the existing environment instead, delete `environments/slack-assistant.yaml`, set its ID as `CLAUDE_ENVIRONMENT_ID` in `.env`, and run `ant apply agents`.
- **The bot answers with an old prompt or model** → check the `Using agent ... (from ...)` line the bridge prints at startup. `from CLAUDE_AGENT_ID` means there is no `claude-lock.json` entry and an ID from `.env` or `.env.local` is in use (Bun loads both, and an older setup of this bridge wrote IDs there): run `ant apply agents environments` here, or delete the stale lines.
- **`chat.postMessage failed ... not_in_channel`** → `/invite @your-bot` to the channel first.

---

## Production notes

- Replace ngrok with a real deploy. Nothing else changes.
- Replace the in-memory `seenEventIds` Sets with Redis/DB for multi-instance idempotency.
- For a distributed (multi-workspace) Slack app, swap the static `SLACK_BOT_TOKEN` for a per-team store keyed on `metadata.slack_team`, and add the Slack OAuth flow.
- Each @mention starts a fresh session (no memory across turns). For threaded conversations, cache `thread_ts → session_id` and send follow-ups via `sessions.events.send` instead of `sessions.create`.
