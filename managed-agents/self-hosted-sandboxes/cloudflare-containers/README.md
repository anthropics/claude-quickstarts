# Cloudflare Containers: one container per session, started by a webhook

Run managed-agent sessions in [Cloudflare Containers](https://developers.cloudflare.com/containers/).
A Worker (`src/index.ts`) receives Anthropic's `session.status_run_started`
webhook, verifies it with `client.beta.webhooks.unwrap()`, and drains the
self-hosted environment's work queue. For each claimed session it starts a
per-session container (`src/container.ts`, a Durable Object keyed by session
ID) whose entrypoint is `ant beta:worker run`. The CLI serves the session's
tools (`bash`, `read`, `write`, `edit`, `glob`, `grep`), heartbeats the
work-item lease, and exits 60s after the session idles.

The webhook is only a wake-up signal. Each delivery drains everything that is
queued, so one delivery recovers any that were missed.

## One key, shared trust

`ant beta:worker run` has no per-session credential, so the Worker passes the
**environment key** into every container. The agent runs arbitrary bash, so it
can read that key, and the key can claim any session's work in the
environment. Here the containers protect Cloudflare's hosts, not sessions from
each other. Use this variant only when every session in the environment trusts
every other. It fails closed: the Worker force-stops and refuses every work item
until you set `ALLOW_ENVIRONMENT_KEY_IN_SANDBOX = "true"` in `wrangler.toml`, the
same switch the sibling providers use for their fallback. Once it is on, the
Worker logs a warning each time it starts a container.

[`../cloudflare-worker/`](../cloudflare-worker/) keeps the key out of anything
the agent can read, and [`../modal/`](../modal/), [`../daytona/`](../daytona/),
[`../vercel/`](../vercel/), and [`../docker-memory/`](../docker-memory/) give
each sandbox a per-session token instead.

## How to use it

Needs Node 20+, a Cloudflare account with Containers enabled, the
[`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart)
1.30 or later (the first release with `ant apply`), `jq`, and
`ant auth login` once (or `ANTHROPIC_API_KEY` exported in your shell).

One-time setup, from `managed-agents/self-hosted-sandboxes/webhook-demo/`:

```sh
ant apply .          # creates the self-hosted environment + demo agent, records their IDs in claude-lock.json
jq -r '.resources["./environments/webhook-demo.yaml"].id' claude-lock.json    # the env_... ID the next step needs
# Mint a key for that environment in the Console (Environments -> it -> Keys)
```

[`ant apply`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/apply)
reads the agent from `agents/webhook-demo.md` and the environment from
`environments/webhook-demo.yaml`, shows the plan, and creates both once you
approve. The five webhook-started providers share that one directory, so run
it once whichever of them you deploy.

Deploy:

```sh
cd cloudflare-containers
npm install
# put the env_... ID from the setup step into wrangler.toml as ANTHROPIC_ENVIRONMENT_ID
npx wrangler secret put ANTHROPIC_ENVIRONMENT_KEY
npx wrangler secret put ANTHROPIC_WEBHOOK_SECRET    # any placeholder for now
npx wrangler deploy                                 # prints https://self-hosted-sandbox-containers.<you>.workers.dev
```

Register that URL in the Console (Manage -> Webhooks) for the event
`session.status_run_started`, in the same workspace as the environment. Copy
the `whsec_...` secret it issues and set it for real:

```sh
npx wrangler secret put ANTHROPIC_WEBHOOK_SECRET
```

Test, from this directory. The IDs come out of the lockfile by the file that
declares each resource:

```sh
lock=../webhook-demo/claude-lock.json
agent=$(jq -r '.resources["./agents/webhook-demo.md"].id' "$lock")
environment=$(jq -r '.resources["./environments/webhook-demo.yaml"].id' "$lock")
ant beta:sessions create --agent "$agent" --environment-id "$environment" \
  --initial-event '{type: user.message, content: [{type: text, text: "Which tools do you have? Try each one."}]}'
npx wrangler tail    # [webhook] polled work=... then the container's own JSON log
```

## How it works

| | |
|---|---|
| `src/index.ts` | The Worker. POST only, 1 MiB body cap, signature check, then poll → ack until the queue is empty (25 items at most). Skips any work item whose environment or ID shape is wrong. |
| `src/container.ts` | `SandboxContainer`, the Durable Object that owns one container. It streams the session's status to renew Cloudflare's `sleepAfter`, so Cloudflare does not reclaim the VM under a live `ant beta:worker run`. |
| `container/Dockerfile` | `debian:12-slim` + `ant` (pinned by `ARG ANT_VERSION`) + `rg`/`git`/`curl`/`jq`, running as a non-root `sandbox` user. `ENTRYPOINT ant beta:worker run`. |
| `wrangler.toml` | Bindings, the container image, `max_instances`, and the two non-secret vars. `ssh = { enabled = true }` lets you `wrangler containers ssh` into a runner while debugging. Turn it off for anything real. |

The CLI owns the idle policy: `--max-idle 60s` after `session.status_idle` with
`stop_reason: end_turn`, and any other event resets the clock. The Durable
Object owns the Cloudflare container's lifetime.

Deliveries are deduplicated on the event ID in the isolate's memory, with
"handled" and "in flight" tracked separately. That is best effort: Cloudflare
may serve a retry from another isolate. Nothing depends on it, because claiming
a work item is atomic on the server and a session's container is get-or-create.

Anyone who can create a session in your workspace with this `environment_id`
gets a container on your Cloudflare bill. The environment is the unit of trust.
