# Cloudflare Worker: the tool runner in a Durable Object, no container

Same webhook → drain the queue → per-session runner shape as
[`../cloudflare-containers/`](../cloudflare-containers/), but there is no
container. The runner is a Durable Object (`src/runner.ts`) running the
TypeScript SDK's `client.beta.sessions.events.toolRunner()` against an
in-isolate fake filesystem (`src/tools.ts`). `read`, `write`, `edit`, `glob`,
and `grep` work on a `Map<string, string>` held in the Durable Object. `bash`
returns a "not available" stub.

This is the library-usage reference for the lower-level `SessionToolRunner`:
you pass your own tools, and your code owns the work item's heartbeat and
force-stop. `EnvironmentWorker` composes all of that for you, but it pulls in
the Node-only `agent-toolset/node` module, which a Workers isolate cannot run.
For a real shell, use the Containers, Vercel, Modal, or Daytona variant.

## Where the key lives

The environment key stays in the Worker and the Durable Object, which is code
you wrote. The agent cannot read it: its bash is a stub and its filesystem is a
`Map`. No org API key is involved anywhere.

## How to use it

Needs Node 20+, a Cloudflare account, the
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
cd cloudflare-worker
npm install
# put the env_... ID from the setup step into wrangler.toml as ANTHROPIC_ENVIRONMENT_ID
npx wrangler secret put ANTHROPIC_ENVIRONMENT_KEY
npx wrangler secret put ANTHROPIC_WEBHOOK_SECRET    # any placeholder for now
npx wrangler deploy                                 # prints https://self-hosted-sandbox-worker.<you>.workers.dev
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
  --initial-event '{type: user.message, content: [{type: text, text: "Write hello.txt, read it back, then grep it."}]}'
npx wrangler tail    # [webhook] polled work=... then [runner] dispatched tool=write ...
```

## How it works

| | |
|---|---|
| `src/index.ts` | The Worker. POST only, 1 MiB body cap, signature check, then poll → ack until the queue is empty (25 items at most). Skips any work item whose environment or ID shape is wrong. |
| `src/runner.ts` | `SandboxRunner`, one Durable Object per session. Runs `toolRunner()` detached with `ctx.waitUntil`, heartbeats the lease in parallel, and force-stops the work item on exit. |
| `src/tools.ts` | Six `betaZodTool` definitions over the fake filesystem: the same shape `client.beta.messages.toolRunner` accepts. `glob` and `grep` compile a `RegExp` from text the model wrote, so pattern length and match count are capped. |

Idle policy is the SDK default: the runner exits 60s after
`session.status_idle` with `stop_reason: end_turn`, and any other event resets
the clock.

Deliveries are deduplicated on the event ID in the isolate's memory, with
"handled" and "in flight" tracked separately. That is best effort: Cloudflare
may serve a retry from another isolate. Nothing depends on it, because claiming
a work item is atomic on the server and a session's runner is get-or-create.

The filesystem lives in the Durable Object's memory. It is gone when the
object is evicted, so treat this variant as a reference for the runner API, not
as somewhere to keep work.
