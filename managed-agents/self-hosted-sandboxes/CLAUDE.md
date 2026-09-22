# Self-hosted sandbox demos

Two demos with one shape: a self-hosted environment is a work queue, the
host runs `ant beta:worker poll --on-work on-work.sh` with the environment
key, and `on-work.sh` starts one short-lived Docker container per claimed
session. In `docker/` the container runs `ant beta:worker run` with the
environment key. In `docker-memory/` the container runs the Python SDK's
`EnvironmentWorker` (`worker.py`) with only a per-session token, and the
session's memory store is mounted at `/mnt/memory/<slug>` and synced back.
`archil/` has the same host side (`on-work.py` instead of `on-work.sh`)
but runs each session in an Archil persistent sandbox with a shared EDGAR
disk instead of a local container: see its README for the extra Archil
credentials, `pip install -r requirements.txt`, and the one-time
`python seed.py` data load. `README.md` here and in each directory has the
design. This file is the runbook.

## When the user asks to set one up, get it working, or debug it

1. **Invoke `/claude-api` first** for the Managed Agents reference (agents,
   environments, sessions, memory stores). Don't guess field names.
2. **Check the host**: `docker version` works for this user, `ant --version`
   is 1.30 or later (the first release with `ant apply`), `jq` is on PATH,
   and `ant auth status` shows a login, or the user exports
   `ANTHROPIC_API_KEY` (the CLI does not read `.env` on its own). Nothing
   else: the Python SDK only runs inside the `docker-memory/` image.
3. **`ant apply --yes .`** from the demo's directory creates the resources
   from `agents/*.md`, `environments/*.yaml`, and `memory_stores/*.yaml`,
   and records their IDs in `./claude-lock.json`. You have no terminal for
   its confirmation prompt, hence `--yes`. Run `ant apply --dry-run .` first
   if you want to show the user the plan. Re-running after a file edit
   updates the same resources in place as a new agent version. If it says
   `refusing to apply`, a resource was changed or archived in the Console:
   show the user the reason it printed before reaching for `--force`.
4. **The one step you can't do for the user**: the environment key. They
   mint it in the Console (Environments, the environment `ant apply` just
   created, Keys). Its `env_...` ID is in the apply output and in
   `claude-lock.json`. Then they `cp .env.example .env` and add
   `ANTHROPIC_ENVIRONMENT_KEY=...` to `.env` (the example line is commented
   out). Ask them to paste it there. Never echo it or log it.
5. **Start the sandbox side** with `./start.sh` and leave it running. It
   builds the image first. Healthy output ends with `polling env=env_...`.
6. **Create a session from a second terminal** with the
   `ant beta:sessions create ... --initial-event ...` command from that
   demo's README (`docker-memory/` adds `--resource "{type: memory_store, ...}"`).
   The IDs come from `claude-lock.json` with the `jq` lines in that README,
   and `archil/` wraps the same thing in `./fanout.sh`.
7. **Watch it run** in the `start.sh` terminal: `[on-work] session=sesn_...
   (starting)`, then the container's own log (tool calls, and in the memory
   demo `downloaded N memories ... -> /mnt/memory/...`), then
   `session idle after end_turn ...; stopping` 60s after the agent finishes,
   and the container exits. One poller serves one session at a time (the CLI
   stops a work item when `on-work.sh` returns, so the script stays attached
   to the container). For concurrent sessions run more `start.sh` processes.
8. **Memory demo, prove persistence**: after the first container exits,
   create a second session asking what it remembers and confirm the recall
   in `ant beta:sessions:events list --session-id ...`. Server side:
   `ant beta:memory-stores:memories list --memory-store-id "$store" --view full`
   (`$store` as read from `claude-lock.json` in that README).

## Debugging

| Symptom | Cause and fix |
|---|---|
| Session sits in `running`, container log shows `tool 'repl' not owned by this runner` and nothing else happens | The agent isn't pinned to `tools: [{type: agent_toolset_20260401}]`. The file in `agents/` pins it. A hand-made agent may not. (A pinned agent can still log the odd `repl` line and carry on: that's fine.) |
| `on-work.sh` logs `carried no per-session secret` and exits 1 (memory demo) | The environment issued no per-session token, so a container would have no credential. Memory needs that token. Use `docker/` on that environment. |
| `sessions create --resource` returns 400 `resources are not supported with self-hosted environments` | The org doesn't have memory on self-hosted environments enabled yet. Nothing to fix locally. |
| Container log shows `failed to download skill` (memory demo) | Expected: the skills API takes the environment key, which this variant never puts in a container. See the README. |
| `start.sh` says `set ANTHROPIC_ENVIRONMENT_KEY` | Step 4 wasn't done: the key is neither in `.env` (uncommented) nor exported in that shell. |
| `start.sh` says `no environment ID` although `ant apply` ran and now reports `Everything is up to date` | `ant apply` was first run from another directory (the repo root, say), so `claude-lock.json` lives there and later runs walk up and adopt it. The scripts only read the lockfile beside them: move that `claude-lock.json` into the demo directory (its keys must read `./agents/...`, so if they carry a longer path, archive those resources with `ant apply --prune` from where it was created and apply again from the demo directory). |
| A user set up `docker/` or `docker-memory/` earlier with `agents/setup.sh` and has `CLAUDE_*_ID` lines in `.env` | `start.sh` still honors `CLAUDE_ENVIRONMENT_ID`, so their environment and key keep working. `ant apply` can't adopt those resources: either keep using them (read the agent and store IDs from `.env` for `sessions create`), or archive them in the Console and `ant apply .` fresh, then mint a key for the new environment. |
| Poller gets 401 | The environment key doesn't belong to the environment in `claude-lock.json`, or `ANTHROPIC_BASE_URL` in `.env` points at a different API host than the one `ant apply` used (the lockfile's `origin.base_url`). |
| `ant apply` prints `tracks resources on workspace X, but the credentials in use target Y` | `claude-lock.json` was written with different credentials (another `ant` profile or org). Re-run with that profile (`--profile`), or delete the lockfile to create fresh resources in the current workspace. |
| Container can't reach a service on the host (rootless Docker) | `SANDBOX_DOCKER_RUN_ARGS="--add-host=host.docker.internal:host-gateway" ./start.sh` and address the host as `host.docker.internal`. |
| Disk fills with `shs-ws-*` / `shs-mem-ws-*` volumes | Per-session `/workspace` volumes are never removed automatically. `docker volume rm` the dead sessions' ones. |

All three `start.sh` scripts deliberately `unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN`:
the sandbox host runs on the environment key alone. Don't "fix" that.
