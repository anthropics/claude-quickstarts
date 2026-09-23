# Self-hosted sandboxes

Three demos of running managed-agent sessions on infrastructure you
control. All have the same shape: a self-hosted environment
(`config: {type: self_hosted}` in `environments/self-hosted.yaml`) is a work
queue rather than a sandbox template, a host process polls it with the
environment key, and each claimed session runs in its own short-lived
sandbox. The first two use plain Docker containers on the host, the third
uses Archil persistent sandboxes with a shared disk.

- [`docker/`](docker/) is the baseline, all `ant` CLI. The host runs
  `ant beta:worker poll` and each container runs `ant beta:worker run`.
  One credential, the environment key, everywhere, including inside the
  containers. An agent can read its container's environment, so in this
  variant the containers protect the host, not sessions from each other.
- [`docker-memory/`](docker-memory/) adds a memory store. The host side is
  the same CLI poller, and the container runs the Python SDK's
  `EnvironmentWorker`, which downloads the session's memory store to
  `/mnt/memory/...`, syncs edits back, and exits. The environment key never
  enters a container: each one authenticates with a per-session token
  instead, so a session cannot reach another session's work or memories.
- [`archil/`](archil/) runs each session in an [Archil](https://archil.com)
  persistent sandbox (a microVM created through the Archil Python SDK) with
  a 70 GB SEC EDGAR data set mounted as a shared disk. The host side is the
  same CLI poller with a Python `on-work.py`. Every sandbox reads the same
  disk and checks out its own `reports/<session>/` directory for writing,
  so many analyst sessions run in parallel against one copy of the data.

Five more variants are started by a webhook instead of a poller, each on a
different provider's compute. Anthropic sends `session.status_run_started`, a
handler you deploy verifies it, drains the environment's work queue, and
starts one sandbox per claimed session. They share one agent and one
self-hosted environment, which `ant apply .` creates from
[`webhook-demo/`](webhook-demo/). Those files sit in their own directory, not
in this one, for two reasons. `ant apply` walks the directory it is given, so
running it here would also create the three poller demos' resources. And it writes
`claude-lock.json` beside the first directory it is run from, then finds that
file again from any directory below it, so a lockfile here would capture the
poller demos' IDs where their `start.sh` does not look.
It is a different environment from the poller demos', because an environment
is one queue and a poller and a webhook handler on the same queue would
compete for its sessions. Each README is its own runbook: deploy, register
the webhook, test.

- [`cloudflare-containers/`](cloudflare-containers/): a Worker starts a
  [Cloudflare Container](https://developers.cloudflare.com/containers/) per
  session running `ant beta:worker run`. Like `docker/`, the environment key
  goes into the container, so use it only when sessions trust each other.
- [`cloudflare-worker/`](cloudflare-worker/): no container. A Durable Object
  runs the TypeScript `SessionToolRunner` over an in-memory filesystem with a
  stub `bash`. The reference for passing your own tools to the runner.
- [`daytona/`](daytona/): a FastAPI app starts a [Daytona](https://www.daytona.io/)
  sandbox per session running the Python SDK worker.
- [`modal/`](modal/): a [Modal](https://modal.com) app starts a Modal Sandbox
  per session with a per-session Volume at `/workspace`, running the same
  Python SDK worker.
- [`vercel/`](vercel/): a Vercel Function starts a
  [Vercel Sandbox](https://vercel.com/docs/vercel-sandbox) per session running
  the TypeScript SDK worker.

Memory stores mount at a fixed path on the sandbox filesystem, so two
sessions on one unvirtualized machine would read and overwrite each
other's memories. One container per session is the recommended way to run
more than one session per host once memory is attached. The
`docker-memory/` README covers the mechanics.

In all three, the resources are files: the agent under `agents/`, the
environment under `environments/`, and in `docker-memory/` the memory store
under `memory_stores/`.
[`ant apply .`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/apply)
creates them and records their IDs in `claude-lock.json`, which the scripts
read, and after you edit a file, running it again updates the same
resources. The one manual step is the environment key, which you mint in the
Console for the environment `ant apply` created.
