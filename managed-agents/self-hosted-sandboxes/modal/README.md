# Modal: one Sandbox per session, started by a webhook

Run managed-agent sessions in [Modal](https://modal.com) Sandboxes. Two files:

- `modal_sandbox_webhook.py` is a Modal app. It receives Anthropic's
  `session.status_run_started` webhook, verifies it with
  `client.beta.webhooks.unwrap()`, drains the self-hosted environment's work
  queue with `client.beta.environments.work.poller(drain=True, auto_stop=False)`,
  and starts a Modal Sandbox per claimed session. A per-session `modal.Volume`
  is mounted at `/workspace`, so the agent's working tree and downloaded skills
  survive across sandbox restarts for the same session.
- `sandbox_runner.py` runs inside that Sandbox:
  `client.beta.environments.work.worker(...).handle_item()`. It builds the
  per-session tool context, downloads the agent's skills into
  `/workspace/skills/<name>/`, runs a `SessionToolRunner` (heartbeat, reconcile,
  event stream, `bash`/`read`/`write`/`edit`/`glob`/`grep` dispatch, result
  posting), and force-stops the work item on exit. [`../daytona/`](../daytona/)
  uses an identical copy.

The webhook is only a wake-up signal. Each delivery drains everything that is
queued, so one delivery recovers any that were missed.

## Where the key lives

The environment key stays in the webhook function. The agent in the Sandbox
runs arbitrary bash, so whatever the Sandbox holds, the agent can read. It
therefore gets the work item's per-session `secret` and nothing else: the
sessions token inside it is scoped to that one session, so a leaked one cannot
claim another session's work.

Two consequences:

- **Skills are not downloaded.** The skills API only accepts the environment
  key. The runner logs `failed to download skill` and carries on.
- **A work item with no secret is refused.** Some environments do not issue
  per-session secrets. The webhook force-stops such an item and logs
  `REFUSED`. To run it anyway with the environment key inside the Sandbox, add
  `ALLOW_ENVIRONMENT_KEY_IN_SANDBOX=true` to the Modal secret. Do that only
  when every session in the environment trusts every other. It also restores
  skill downloads.

## How to use it

Needs Python 3.12, `pip install modal` and `modal setup`, the
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
cd modal
modal secret create self-hosted-sandboxes-secrets \
    ANTHROPIC_WEBHOOK_SECRET=placeholder \
    ANTHROPIC_ENVIRONMENT_ID='env_...' \
    ANTHROPIC_ENVIRONMENT_KEY='sk-ant-oat...'
modal deploy modal_sandbox_webhook.py    # prints a *.modal.run URL
```

Register that URL in the Console (Manage -> Webhooks) for the event
`session.status_run_started`, in the same workspace as the environment. Copy
the `whsec_...` secret it issues, then re-create the Modal secret with it:

```sh
modal secret create self-hosted-sandboxes-secrets \
    ANTHROPIC_WEBHOOK_SECRET='whsec_...' \
    ANTHROPIC_ENVIRONMENT_ID='env_...' \
    ANTHROPIC_ENVIRONMENT_KEY='sk-ant-oat...' \
    --force
```

No redeploy is needed: secrets are read when a container starts.

Test, from this directory. The IDs come out of the lockfile by the file that
declares each resource:

```sh
lock=../webhook-demo/claude-lock.json
agent=$(jq -r '.resources["./agents/webhook-demo.md"].id' "$lock")
environment=$(jq -r '.resources["./environments/webhook-demo.yaml"].id' "$lock")
ant beta:sessions create --agent "$agent" --environment-id "$environment" \
  --initial-event '{type: user.message, content: [{type: text, text: "Which tools do you have? Try each one."}]}'
modal app logs self-hosted-sandboxes
# [webhook] event=session.status_run_started session_id=...
# [webhook] work=... session=... sandbox=sb-... (created)
```

The Sandbox's own output (the `[runner]` lines, starting with
`credential=per-session token`) shows in the Modal dashboard under
Apps -> self-hosted-sandboxes -> Sandboxes.

Editing either Python file needs a redeploy. Editing only the secret does not.
For a clean slate while iterating, `modal app stop self-hosted-sandboxes`
before you redeploy.

## Using the worker as a library

`client.beta.environments.work.worker(...)` composes the whole loop: poll, set
up the workdir and download the session agent's skills, run the tools while
heartbeating the work-item lease, force-stop on exit, loop. `.run()` is the
long-lived form, for your own poller process:

```python
import asyncio, os
from anthropic import AsyncAnthropic

environment_key = os.environ["ANTHROPIC_ENVIRONMENT_KEY"]

async def main() -> None:
    async with AsyncAnthropic(auth_token=environment_key) as client:
        await client.beta.environments.work.worker(
            environment_id=os.environ["ANTHROPIC_ENVIRONMENT_ID"],
            environment_key=environment_key,
            workdir="/workspace",
        ).run()

asyncio.run(main())
```

`.handle_item()` is the per-item form `sandbox_runner.py` uses. It reads the
`ANTHROPIC_*` env vars and services the one work item something else already
claimed.

`worker(...)` accepts the same tool type as `client.beta.messages.tool_runner`,
so you can filter or extend the defaults. `tools` is a factory called once per
claimed session with that session's tool context:

```python
from anthropic.lib.tools import beta_async_tool
from anthropic.lib.tools.agent_toolset import AgentToolContext, beta_agent_toolset_20260401

@beta_async_tool
async def fetch_url(url: str) -> str: ...

def tools(env: AgentToolContext):
    # drop grep, add a custom tool
    return [t for t in beta_agent_toolset_20260401(env) if t.name != "grep"] + [fetch_url]

client.beta.environments.work.worker(..., tools=tools)
```

## How it works

| | |
|---|---|
| `modal_sandbox_webhook.py` | POST only, 1 MiB body cap, signature check, then the SDK poller drains the queue. Skips any work item whose environment or ID shape is wrong. A live Sandbox for the session is reused. |
| `sandbox_runner.py` | Decodes the sessions token from `ANTHROPIC_WORK_SECRET`, builds the client with it, and calls `handle_item()`. |

Both images pin `anthropic>=0.124.0,<1.0.0`. 0.124.0 is the first release whose
`handle_item()` accepts the per-session work secret.

Idle policy is the SDK default: the runner exits 60s after
`session.status_idle` with `stop_reason: end_turn`, and any other event resets
the clock. The Sandbox has a one-hour hard timeout.

Deliveries are deduplicated on the event ID in the container's memory, with
"handled" and "in flight" tracked separately. That is best effort: Modal may
serve a retry from another container. Nothing depends on it, because claiming
a work item is atomic on the server and a session's Sandbox is get-or-create.

Anyone who can create a session in your workspace with this `environment_id`
gets a Sandbox on your Modal bill. The environment is the unit of trust.
