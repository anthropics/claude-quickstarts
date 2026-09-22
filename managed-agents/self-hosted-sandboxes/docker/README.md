# Docker demo: one container per session

Run managed-agent sessions on hardware you control. The host runs
`ant beta:worker poll` against a self-hosted environment, and for each
claimed session its `--on-work` script runs a short-lived Docker container
whose entrypoint is `ant beta:worker run`. That container downloads the
agent's skills, serves the session's tools (`bash`, `read`, `write`, `edit`,
`glob`, `grep`), heartbeats the work-item lease, and exits 60s after the
session idles. Nothing is exposed to the internet: the poller long-polls
the API.

## How to use it

Needs Docker, `jq`, the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart)
1.30 or later (`brew install anthropics/tap/ant`), and `ant auth login` once
(or `ANTHROPIC_API_KEY` exported in your shell).

```sh
cd managed-agents/self-hosted-sandboxes/docker
claude "help me set up and run this self-hosted sandbox demo"
```

Or by hand. One-time setup, from this directory:

```sh
ant apply .          # creates the self-hosted environment + agent, records their IDs in claude-lock.json
cp .env.example .env
# Mint a key for that environment in the Console (Environments -> it -> Keys)
# and set ANTHROPIC_ENVIRONMENT_KEY= in .env
```

[`ant apply`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/apply)
reads the agent from `agents/sandbox-demo.md`, whose frontmatter is the
configuration and whose prose is the system prompt, and the environment from
`environments/self-hosted.yaml`. It shows the plan and creates both once you
approve. To change the agent later, edit its file and run `ant apply` again:
it publishes a new version of the same agent, because `claude-lock.json`
remembers which resources these files became. This repository ignores that
file, since every reader creates their own resources. In a project of your
own, commit it.

Sandbox side, leave running:

```sh
./start.sh           # builds the image, then polls the environment for sessions
```

Control plane, from any other terminal or machine with the same
`claude-lock.json`. The IDs come out of the lockfile by the file that
declares each resource:

```sh
agent=$(jq -r '.resources["./agents/sandbox-demo.md"].id' claude-lock.json)
environment=$(jq -r '.resources["./environments/self-hosted.yaml"].id' claude-lock.json)
ant beta:sessions create --agent "$agent" --environment-id "$environment" \
  --initial-event '{type: user.message, content: [{type: text, text: "Which tools do you have? Try each one."}]}'
```

`start.sh` logs `[on-work] session=sesn_... (starting)` followed by the
container's own log (`downloaded skill ...`, `executing tool ...`) until it
prints `session idle after end_turn; stopping` and the container exits.
Send the session another message (`ant beta:sessions:events send`) and a
new container picks it up with the same `/workspace`, which lives on a
per-session volume (`shs-ws-<session_id>`). `docker volume rm` dead
sessions' volumes.

One poller serves one session at a time: the CLI stops a work item as soon
as its `--on-work` script returns, so `on-work.sh` stays attached to the
container until it exits. Run `./start.sh` in as many terminals or on as
many hosts as you want concurrent sessions. The environment is a queue and
spreads sessions across them.

## How it works

| | |
|---|---|
| `agents/sandbox-demo.md`, `environments/self-hosted.yaml` | The agent and the self-hosted environment, as files for `ant apply`. The agent pins `tools: [{type: agent_toolset_20260401}]`, the toolset `ant beta:worker run` serves. A server-default toolset includes tools the worker does not own and the session stalls on them. |
| `start.sh` | Builds the image, execs `ant beta:worker poll --on-work on-work.sh` with the environment ID from `claude-lock.json` and the environment key from `.env`. |
| `on-work.sh` | Once per claimed work item: runs an attached `--rm` per-session container and returns when it exits. `SANDBOX_DOCKER_RUN_ARGS` adds `docker run` flags (resource limits, networks). |
| `Dockerfile` | `debian:12-slim` + `ant` (pinned by `ARG ANT_VERSION`, fetched for the image's architecture) + `rg`/`git`/`curl`/`jq`, `ENTRYPOINT ant beta:worker run`. Add whatever else your agents need. |

One credential everywhere: the environment key. The poller claims work with
it and `on-work.sh` passes it into each container, where `ant beta:worker
run` uses it for the session's event stream, the lease heartbeat, and the
skills download. An agent can read its container's environment (it runs
arbitrary bash), so here the containers limit the blast radius for the
host, not between sessions. The [`docker-memory/`](../docker-memory/)
variant shows the per-session token split that isolates sessions from each
other, and what it costs.
