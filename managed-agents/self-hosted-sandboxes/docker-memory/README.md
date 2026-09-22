# Docker demo with memory: one container per session

Run managed-agent sessions on your own hardware with a memory store that
persists across them. The host polls a self-hosted environment with the
`ant` CLI and starts one Docker container per claimed session. The container
downloads the session's memory store to `/mnt/memory/<store-slug>`, serves
the agent's tools, syncs memory edits back while the session runs, and
exits. The server keeps the memories, so containers are disposable.

It is the [`docker/`](../docker/) demo plus two things: the container runs
the Python SDK's `EnvironmentWorker` (which does the memory download and
sync), and the environment key never enters a container.

## How to use it

Needs Docker, `jq`, the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart)
1.30 or later (`brew install anthropics/tap/ant`), and `ant auth login` once
(or `ANTHROPIC_API_KEY` exported in your shell). No Python on the host: the
SDK lives in the image.

```sh
cd managed-agents/self-hosted-sandboxes/docker-memory
claude "help me set up and run this self-hosted sandbox memory demo"
```

Or by hand. One-time setup, from this directory:

```sh
ant apply .         # creates the memory store, self-hosted environment, and agent; records their IDs in claude-lock.json
cp .env.example .env
# Mint a key for that environment in the Console (Environments -> it -> Keys)
# and set ANTHROPIC_ENVIRONMENT_KEY= in .env
```

[`ant apply`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/apply)
reads one file per resource: the agent from `agents/memory-demo.md`, whose
frontmatter is the configuration and whose prose is the system prompt, the
environment from `environments/self-hosted.yaml`, and the store from
`memory_stores/user-preferences.yaml`. It shows the plan and creates all
three once you approve. To change the agent later, edit its file and run
`ant apply` again: it publishes a new version of the same agent, because
`claude-lock.json` remembers which resources these files became. This
repository ignores that file, since every reader creates their own
resources. In a project of your own, commit it.

Sandbox side, leave running:

```sh
./start.sh          # builds the image, then polls the environment for sessions
```

Control plane, from any other terminal or machine with the same
`claude-lock.json`. Read the three IDs out of the lockfile by the file that
declares each resource, then create a session on the environment with the
store attached and a first message:

```sh
agent=$(jq -r '.resources["./agents/memory-demo.md"].id' claude-lock.json)
environment=$(jq -r '.resources["./environments/self-hosted.yaml"].id' claude-lock.json)
store=$(jq -r '.resources["./memory_stores/user-preferences.yaml"].id' claude-lock.json)
ant beta:sessions create --agent "$agent" --environment-id "$environment" \
  --resource "{type: memory_store, memory_store_id: $store, access: read_write}" \
  --initial-event "{type: user.message, content: [{type: text, text: 'Remember that I indent with tabs, 3 wide.'}]}"
```

`start.sh` logs `[on-work] session=sesn_... (starting)` followed by the
container's own log: `downloaded N memories ... -> /mnt/memory/user-preferences`,
the tool calls, and `session idle after end_turn for 60s; stopping` before
the container exits. Then prove the memory outlived it: run the same command
with `text: 'What do you know about my preferences?'`. A fresh container
downloads the store and the agent answers from it. What the server holds:

```sh
ant beta:memory-stores:memories list --memory-store-id "$store" --view full
```

`access: read_only` attaches the store for sessions that may read but never
write (the file tools refuse writes under that mount). A different
`memory_store_id` is a blank slate the first store's sessions never see:
one store per end user is the pattern.

One poller serves one session at a time: the CLI stops a work item as soon
as its `--on-work` script returns, so `on-work.sh` stays attached to the
container until it exits. Run `./start.sh` in as many terminals or on as
many hosts as you want concurrent sessions. The environment is a queue and
spreads sessions across them.

## How it works

| | |
|---|---|
| `agents/memory-demo.md`, `environments/self-hosted.yaml`, `memory_stores/user-preferences.yaml` | The agent, self-hosted environment, and memory store, as files for `ant apply`. The agent pins `tools: [{type: agent_toolset_20260401}]`, the toolset `worker.py` serves. A server-default toolset includes tools the worker does not own and the session stalls (`tool 'repl' not owned by this runner`). |
| `start.sh` | Host. Builds the image, execs `ant beta:worker poll --on-work on-work.sh` with the environment ID from `claude-lock.json` and the environment key from `.env`. |
| `on-work.sh` | Host, once per claimed work item. Reads the item's per-session `secret` off stdin and runs an attached `--rm` container with only that secret, returning when it exits. Refuses items that carry no secret. `SANDBOX_DOCKER_RUN_ARGS` adds `docker run` flags. |
| `Dockerfile`, `worker.py` | Container. `python:3.12-slim` + the `anthropic` SDK (0.125.0 or later, the first with memory sync for self-hosted sandboxes) + `rg`/`git`/`curl`/`jq`. `worker.py` pulls the sessions token out of the secret and calls `EnvironmentWorker.handle_item()`: memory download and sync, tool dispatch, lease heartbeat, force-stop on exit. |

Three credentials, three blast radii. Your org credential (`ant auth login`
or `ANTHROPIC_API_KEY`) runs `ant apply` and creates sessions, and never
reaches the sandbox host. The environment key lives only in the `start.sh`
poller and can only claim work. Each container holds only its session's
token, so an agent that reads its own environment (it runs arbitrary bash)
cannot claim other sessions' work or read their memories. The memory
endpoints reject the environment key outright. The trade-off: the skills
API takes the environment key and not the token, so an agent with skills
runs without them here (the worker logs the failed download and carries
on). If you need skills, pass the key in as `docker/` does and accept its
weaker isolation, or bake the skill files into the image.

One container per session is what keeps memories apart. A store mounts at
a fixed path derived from its name (`/mnt/memory/user-preferences`), and
the agent addresses that exact path, so two sessions on one filesystem
would read and overwrite each other's directory. A fresh container gives
each session its own mount, clean even after a crash. Only `/workspace`
persists, on a per-session volume (`shs-mem-ws-<session_id>`) that is never
removed automatically: `docker volume rm` dead sessions' volumes.

## How sync behaves

The SDK downloads the store before the session's tools run, reconciles the
directory with the server every 30s (checked after each tool call, tunable
via `memory_sync_interval` on `EnvironmentWorker`) plus once at a clean end,
gives a session that dies mid-run a bounded push-only flush, and removes the
directory on teardown. Reconcile is per file: local-only changes upload,
remote-only changes download, a same-file conflict takes the server version
with a warning. Uploads carry a `content_sha256` precondition, so two
sessions sharing a store merge cleanly when they write different files and
a lost race on the same file drops the loser's push instead of corrupting
it. A local delete propagates only after the file has stayed gone for 30s
and a re-check, so a wiped directory re-downloads instead of emptying the
store. The `.anthropic-memory-store` marker in each mount is how the SDK
decides to trust the folder. It never syncs, and agents can ignore it.
