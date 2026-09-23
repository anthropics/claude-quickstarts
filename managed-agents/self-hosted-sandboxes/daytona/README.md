# Daytona: one sandbox per session, started by a webhook

Run managed-agent sessions in [Daytona](https://www.daytona.io/) sandboxes.
`daytona_webhook.py` is a FastAPI app. It receives Anthropic's
`session.status_run_started` webhook, verifies it with
`client.beta.webhooks.unwrap()`, drains the self-hosted environment's work
queue with `client.beta.environments.work.poller(drain=True, auto_stop=False)`,
and for each claimed session creates a Daytona sandbox, uploads
`sandbox_runner.py`, and starts it. Daytona sandboxes are full Linux
containers, so the default toolset (`bash`, `read`, `write`, `edit`, `glob`,
`grep`) works as it is.

`sandbox_runner.py` is an identical copy of the one in [`../modal/`](../modal/),
whose README explains what it does and how to customize its tools.

The webhook is only a wake-up signal. Each delivery drains everything that is
queued, so one delivery recovers any that were missed.

## Where the key lives

The environment key stays on the host that runs `daytona_webhook.py`. The
agent in the sandbox runs arbitrary bash, so whatever the sandbox holds, the
agent can read. It therefore gets the work item's per-session `secret` and
nothing else: the sessions token inside it is scoped to that one session, so a
leaked one cannot claim another session's work.

Two consequences:

- **Skills are not downloaded.** The skills API only accepts the environment
  key. The runner logs `failed to download skill` and carries on.
- **A work item with no secret is refused.** Some environments do not issue
  per-session secrets. The webhook force-stops such an item and logs
  `REFUSED`. To run it anyway with the environment key inside the sandbox,
  export `ALLOW_ENVIRONMENT_KEY_IN_SANDBOX=true` on the host. Do that only when
  every session in the environment trusts every other. It also restores skill
  downloads.

## How to use it

Needs Python 3.11+, a Daytona API key, the
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

Run the orchestrator:

```sh
cd daytona
# standardwebhooks backs client.beta.webhooks.unwrap(). Only this host needs it.
pip install fastapi uvicorn daytona-sdk standardwebhooks 'anthropic>=0.124.0,<1.0.0'

export DAYTONA_API_KEY=... DAYTONA_API_URL=...
export ANTHROPIC_ENVIRONMENT_ID=env_... ANTHROPIC_ENVIRONMENT_KEY=sk-ant-oat...
export ANTHROPIC_WEBHOOK_SECRET=placeholder    # until you register the webhook

uvicorn daytona_webhook:app --host 0.0.0.0 --port 8080
```

Put it anywhere that can serve HTTPS and reach the Daytona API: Fly, Render, a
VM behind a tunnel. Register its URL in the Console (Manage -> Webhooks) for
the event `session.status_run_started`, in the same workspace as the
environment. Export the `whsec_...` secret it issues as
`ANTHROPIC_WEBHOOK_SECRET` and restart.

Test, from this directory. The IDs come out of the lockfile by the file that
declares each resource:

```sh
lock=../webhook-demo/claude-lock.json
agent=$(jq -r '.resources["./agents/webhook-demo.md"].id' "$lock")
environment=$(jq -r '.resources["./environments/webhook-demo.yaml"].id' "$lock")
ant beta:sessions create --agent "$agent" --environment-id "$environment" \
  --initial-event '{type: user.message, content: [{type: text, text: "Which tools do you have? Try each one."}]}'
# uvicorn's output: [webhook] work=... session=... sandbox=... (created)
```

The runner's own log is `/tmp/runner.log` inside the Daytona sandbox.

## How it works

| | |
|---|---|
| `daytona_webhook.py` | One route, `POST /`. 1 MiB body cap, signature check, then the SDK poller drains the queue. Skips any work item whose environment or ID shape is wrong. A started sandbox labelled with the session ID is reused. |
| `sandbox_runner.py` | Decodes the sessions token from `ANTHROPIC_WORK_SECRET`, builds the client with it, and calls `handle_item()`. |

`_spawn()` runs `pip install` inside each fresh sandbox, which adds 10 to 15
seconds before the runner starts. For production, bake the SDK into a custom
Daytona image and drop that line. The two commands it runs in the sandbox are
constants: nothing from a webhook or a work item is interpolated into a shell
command.

Deliveries are deduplicated on the event ID in this process's memory, with
"handled" and "in flight" tracked separately, so a retry that arrives
mid-drain gets a 503 and the retry of a delivery that raised is processed from
scratch. Run several workers and a retry may land on another one. Nothing
depends on it, because claiming a work item is atomic on the server and a
session's sandbox is get-or-create.

Anyone who can create a session in your workspace with this `environment_id`
gets a sandbox on your Daytona bill. The environment is the unit of trust.
