# Vercel: one Sandbox per session, started by a webhook

Run managed-agent sessions in [Vercel Sandboxes](https://vercel.com/docs/vercel-sandbox).
A Vercel Function (`api/webhook.ts`) receives Anthropic's
`session.status_run_started` webhook, verifies it with
`client.beta.webhooks.unwrap()`, drains the self-hosted environment's work
queue, and for each claimed session acks it, creates a Vercel Sandbox, uploads
`runner/runner.mjs`, and starts it detached. The runner is the TypeScript SDK's
`EnvironmentWorker.handleItem()` with the default toolset (`bash`, `read`,
`write`, `edit`, `glob`, `grep`) against the sandbox's real filesystem.

The webhook is only a wake-up signal. Each delivery drains everything that is
queued, so one delivery recovers any that were missed. A bad work item is
logged and skipped, so it cannot wedge the rest of the queue.

## Where the key lives

The environment key stays in the function. The agent in the Sandbox runs
arbitrary bash, so whatever the Sandbox holds, the agent can read. It therefore
gets the work item's per-session `secret` and nothing else: the sessions token
inside it is scoped to that one session, so a leaked one cannot claim another
session's work.

A work item with no secret is refused. Some environments do not issue
per-session secrets. The function force-stops such an item and logs `REFUSED`.
To run it anyway with the environment key inside the Sandbox, set
`ALLOW_ENVIRONMENT_KEY_IN_SANDBOX=true` with `vercel env add`. Do that only when
every session in the environment trusts every other.

## How to use it

Needs Node 20+, the [Vercel CLI](https://vercel.com/docs/cli) (`npm i -g vercel`),
the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart)
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
cd vercel
npm install
vercel link
vercel env add ANTHROPIC_ENVIRONMENT_ID     # the env_... ID from the setup step
vercel env add ANTHROPIC_ENVIRONMENT_KEY
vercel env add ANTHROPIC_WEBHOOK_SECRET     # any placeholder for now
vercel deploy --prod                        # prints https://<project>.vercel.app
```

Register `https://<project>.vercel.app/api/webhook` in the Console (Manage ->
Webhooks) for the event `session.status_run_started`, in the same workspace as
the environment. Copy the `whsec_...` secret it issues, then:

```sh
vercel env rm ANTHROPIC_WEBHOOK_SECRET production
vercel env add ANTHROPIC_WEBHOOK_SECRET production
vercel deploy --prod
```

Test, from this directory. The IDs come out of the lockfile by the file that
declares each resource:

```sh
lock=../webhook-demo/claude-lock.json
agent=$(jq -r '.resources["./agents/webhook-demo.md"].id' "$lock")
environment=$(jq -r '.resources["./environments/webhook-demo.yaml"].id' "$lock")
ant beta:sessions create --agent "$agent" --environment-id "$environment" \
  --initial-event '{type: user.message, content: [{type: text, text: "Which tools do you have? Try each one."}]}'
vercel logs <project>.vercel.app
# [webhook] event=session.status_run_started session_id=...
# [webhook] acked work=... session=... sandbox=sbx_... (created)
```

The Sandbox's own output (the `[runner]` lines, starting with
`credential=per-session token`) shows under the project's Observability ->
Sandboxes tab. The function also copies the runner's first 30 seconds of output
into its own log, so a crash on start is visible from `vercel logs` alone.

## Using the worker as a library

`client.beta.environments.work.worker(...)` composes the whole loop: poll, set
up the workdir and download the session agent's skills, run the tools while
heartbeating the work-item lease, force-stop on exit, loop. `.run()` is the
long-lived form, for your own poller process:

```ts
import Anthropic from "@anthropic-ai/sdk";

const environmentKey = process.env.ANTHROPIC_ENVIRONMENT_KEY!;
const client = new Anthropic({ authToken: environmentKey });
const ctrl = new AbortController();
process.once("SIGTERM", () => ctrl.abort());

await client.beta.environments.work
  .worker({
    environmentId: process.env.ANTHROPIC_ENVIRONMENT_ID!,
    environmentKey,
    workdir: "/workspace",
    signal: ctrl.signal,
  })
  .run();
```

`.handleItem()` is the per-item form `runner/runner.mjs` uses. It reads the
`ANTHROPIC_*` env vars and services the one work item something else already
claimed.

`worker(...)` accepts the same tool type as `client.beta.messages.toolRunner`,
so you can filter or extend the defaults. `tools` is a factory called once per
claimed session with that session's tool context:

```ts
import { betaZodTool } from "@anthropic-ai/sdk/helpers/beta/zod";
import { betaAgentToolset20260401 } from "@anthropic-ai/sdk/tools/agent-toolset/node";

client.beta.environments.work.worker({
  // ...
  tools: (ctx) => [...betaAgentToolset20260401(ctx).filter((t) => t.name !== "grep"), myZodTool],
});
```

## How it works

| | |
|---|---|
| `api/webhook.ts` | Only `POST` is exported. 1 MiB body cap, signature check, then poll → ack until the queue is empty (25 items at most). Skips any work item whose environment or ID shape is wrong. |
| `runner/runner.mjs` | Decodes the sessions token from `ANTHROPIC_WORK_SECRET`, builds the client with it, and calls `handleItem()`. |
| `vercel.json` | `maxDuration: 60` for the function, and `includeFiles` so the runner source ships with it. |

Both the function and the in-sandbox `npm install` use
`@anthropic-ai/sdk >=0.124.0 <1.0.0`. 0.124.0 is the first release whose
`handleItem()` accepts the per-session work secret.

- `Sandbox.create()`, `writeFiles()`, and `npm install` take 15 to 25 seconds
  before the function responds. The runner itself is detached. To cut about
  10 seconds from cold start, bundle `runner/runner.mjs` with esbuild and
  upload the bundle.
- **Sandbox reuse.** Vercel Sandbox has no tag or get-by-name API, so reuse
  needs external state. With a [Vercel KV](https://vercel.com/storage/kv) store
  attached (`KV_REST_API_URL` and `KV_REST_API_TOKEN` set), the function
  records `session_id → sandbox_id`, reuses a running sandbox on the next
  `run_started`, and calls `extendTimeout()` so an active session keeps its VM
  across turns. Without KV every delivery creates a fresh sandbox.
  `SessionToolRunner` dedups tool calls, so a duplicate runner is wasteful, not
  wrong.
- **Working directories.** The function creates `/mnt/session` and `/workspace`
  when the sandbox starts and uses `/workspace` as the workdir, like the other
  variants. They are plain directories, not persistent volumes: Vercel Sandbox
  has no volume API, so the working tree is gone when the sandbox stops.
- **Egress.** The sandbox's network policy allows the Anthropic API host and
  `registry.npmjs.org`. Add hosts your tools need in `Sandbox.create()`.

Deliveries are deduplicated on the event ID in the function instance's memory,
with "handled" and "in flight" tracked separately. That is best effort: Vercel
may serve a retry from another instance. Nothing depends on it, because
claiming a work item is atomic on the server.

Anyone who can create a session in your workspace with this `environment_id`
gets a Sandbox on your Vercel bill. The environment is the unit of trust.
