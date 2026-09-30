# Self-hosted sandbox demos

This file is the runbook for the four poller demos, `docker/`,
`docker-memory/`, `archil/`, and `openshell/`. The five webhook-started
providers (`cloudflare-containers/`, `cloudflare-worker/`, `daytona/`, `modal/`,
`vercel/`) share one agent and one environment, declared in `webhook-demo/`
and created with `ant apply --yes .` from that directory. Never run
`ant apply` from this directory: it walks into the poller demos and creates
their resources too, and the `claude-lock.json` it leaves here is then found
first by every directory below. Each provider's README is its own runbook:
setup, deploy, register the `session.status_run_started` webhook in the
Console, test. Their environment key and webhook secret go in the provider's
own secret store, never in a file here.

The Docker demos share one shape: a self-hosted environment is a work queue, the
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
`python seed.py` data load. `openshell/` has the same host side too, but its
`on-work.sh` runs `ant beta:worker run` in an NVIDIA OpenShell sandbox
confined by `policy.yaml` and pipes it the per-session token over stdin. The
sandbox belongs to the session: `on-work.sh` stops it when the worker exits
and restarts it for the session's next message. `README.md` here and in each
directory has the design. This file is the runbook.

## When the user asks to set one up, get it working, or debug it

For `openshell/`, read `openshell/setup-skill.md` first and walk the user
through it step by step. It has that demo's steps in order, the output to expect
from each, and where to find OpenShell's policy reference. The debugging tables
below still apply.

1. **Invoke `/claude-api` first** for the Managed Agents reference (agents,
   environments, sessions, memory stores). Don't guess field names.
2. **Check the host**: `docker version` works for this user, `ant --version`
   is 1.30 or later (the first release with `ant apply`), `jq` is on PATH,
   and `ant auth status` shows a login, or the user exports
   `ANTHROPIC_API_KEY` (the CLI does not read `.env` on its own). Nothing
   else: the Python SDK only runs inside the `docker-memory/` image.
   `openshell/` needs more: Docker 28 or later, `openshell --version` prints
   0.1.x (0.0.x has a different CLI), and `openshell sandbox list` succeeds.
   Don't use `openshell status` as the gateway check: it exits 0 with no
   gateway configured. The `ant` 1.32 that `--work-secret-file` needs is the
   copy in the image, which the Dockerfile pins. If `openshell` is missing,
   its README has the pinned install command. Ask before you run it: it
   installs a system package and starts the gateway as a user service.
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
   In `openshell/` it exits before the build if no gateway answers.
6. **Create a session from a second terminal** with the
   `ant beta:sessions create ... --initial-event ...` command from that
   demo's README (`docker-memory/` adds `--resource "{type: memory_store, ...}"`).
   The IDs come from `claude-lock.json` with the `jq` lines in that README,
   and `archil/` wraps the same thing in `./fanout.sh`. In `openshell/` keep
   the `session=$(...)` form: step 9 needs the ID.
7. **Watch it run** in the `start.sh` terminal: `[on-work] session=sesn_...
   (starting)`, then the container's own log (tool calls, and in the memory
   demo `downloaded N memories ... -> /mnt/memory/...`), then
   `session idle after end_turn ...; stopping` 60s after the agent finishes,
   and the container exits. One poller serves one session at a time (the CLI
   stops a work item when `on-work.sh` returns, so the script stays attached
   to the container). For concurrent sessions run more `start.sh` processes.
   In `openshell/` the first line is `[on-work] session=sesn_... work=sesn_...
   sandbox=shs-... (creating)`, or `(restarting)` for a later message to the
   same session, and the last is `[on-work] session=sesn_... worker exited
   rc=0, stopping shs-...`.
8. **Memory demo, prove persistence**: after the first container exits,
   create a second session asking what it remembers and confirm the recall
   in `ant beta:sessions:events list --session-id ...`. Server side:
   `ant beta:memory-stores:memories list --memory-store-id "$store" --view full`
   (`$store` as read from `claude-lock.json` in that README).
9. **OpenShell demo, check the policy held**: read the agent's report with
   the `ant beta:sessions:events list` command from its README. The writes to
   `/workspace` and `/tmp` succeed. `/etc/hi.txt` gets `Permission denied`,
   `example.com` gets `curl: (7) Failed to connect`, and `/v1/models` gets a
   403 with `"error":"policy_denied"`. Those three failures are the demo
   working, not bugs to fix. OpenShell's record of the two network denials:
   `openshell logs "$sandbox" --source sandbox -n 500 | grep -E 'ALLOWED|DENIED' | grep -v SSH:`
   (`$sandbox` as looked up in that README).

## Debugging

| Symptom | Cause and fix |
|---|---|
| Session sits in `running`, container log shows `tool 'repl' not owned by this runner` and nothing else happens | The agent isn't pinned to `tools: [{type: agent_toolset_20260401}]`. The file in `agents/` pins it. A hand-made agent may not. (A pinned agent can still log the odd `repl` line and carry on: that's fine.) |
| `on-work.sh` logs `carried no per-session secret` and exits 1 (memory demo, `openshell/`) | The environment issued no per-session token, so the sandbox would have no credential. Memory needs that token. Use `docker/` on that environment. |
| `sessions create --resource` returns 400 `resources are not supported with self-hosted environments` | The org doesn't have memory on self-hosted environments enabled yet. Nothing to fix locally. |
| Container log shows `failed to download skill` (memory demo) | Expected: the skills API takes the environment key, which this variant never puts in a container. See the README. |
| `start.sh` says `set ANTHROPIC_ENVIRONMENT_KEY` | Step 4 wasn't done: the key is neither in `.env` (uncommented) nor exported in that shell. |
| `start.sh` says `no environment ID` although `ant apply` ran and now reports `Everything is up to date` | `ant apply` was first run from another directory (the repo root, say), so `claude-lock.json` lives there and later runs walk up and adopt it. The scripts only read the lockfile beside them: move that `claude-lock.json` into the demo directory (its keys must read `./agents/...`, so if they carry a longer path, archive those resources with `ant apply --prune` from where it was created and apply again from the demo directory). |
| A user set up `docker/` or `docker-memory/` earlier with `agents/setup.sh` and has `CLAUDE_*_ID` lines in `.env` | `start.sh` still honors `CLAUDE_ENVIRONMENT_ID`, so their environment and key keep working. `ant apply` can't adopt those resources: either keep using them (read the agent and store IDs from `.env` for `sessions create`), or archive them in the Console and `ant apply .` fresh, then mint a key for the new environment. |
| Poller gets 401 | The environment key doesn't belong to the environment in `claude-lock.json`, or `ANTHROPIC_BASE_URL` in `.env` points at a different API host than the one `ant apply` used (the lockfile's `origin.base_url`). |
| `ant apply` prints `tracks resources on workspace X, but the credentials in use target Y` | `claude-lock.json` was written with different credentials (another `ant` profile or org). Re-run with that profile (`--profile`), or delete the lockfile to create fresh resources in the current workspace. |
| Container can't reach a service on the host (rootless Docker) | `SANDBOX_DOCKER_RUN_ARGS="--add-host=host.docker.internal:host-gateway" ./start.sh` and address the host as `host.docker.internal`. |
| Disk fills with `shs-ws-*` / `shs-mem-ws-*` volumes | Per-session `/workspace` volumes are never removed automatically. `docker volume rm` the dead sessions' ones. |

The rest are `openshell/` only. The gateway's log is
`journalctl --user -u openshell-gateway` on Linux. Its config file is
`~/.config/openshell/gateway.toml`, which opens with `[openshell]` and
`version = 2`. Restarting the gateway stops every running sandbox, so do it
when no session is live.

| Symptom | Cause and fix |
|---|---|
| `start.sh` says `no OpenShell gateway answered` | `openshell sandbox list` failed. Run `openshell status` to see why. `No gateway configured.` means the CLI has none registered: `openshell gateway add https://127.0.0.1:17670 --local --name openshell`. If one is registered and doesn't answer, restart it with `systemctl --user restart openshell-gateway` (`brew services restart openshell` on macOS) and read its log. |
| Gateway log shows `Using compute driver driver=kubernetes`, then `sandboxes.agents.x-k8s.io is forbidden` | The host is itself a Kubernetes pod (a cloud dev environment, a CI runner). With no driver set the gateway tries Kubernetes, then Podman, then Docker, and it takes `KUBERNETES_SERVICE_HOST` in its environment to mean Kubernetes. Pin the driver: `compute_driver = "docker"` under `[openshell.gateway]` in `gateway.toml`, or `OPENSHELL_COMPUTE_DRIVER=docker` in the gateway's environment. Restart the gateway. |
| `on-work.sh` exits 1 about 15s after `(creating)` with `ControlSupervisorStartFailed: Docker supervisor exited before becoming ready` and `failed to connect to OpenShell server` | Rootless Docker. Each sandbox's supervisor container uses host networking and dials the gateway on `127.0.0.1`, which under rootless Docker is RootlessKit's loopback, not the host's. `openshell doctor check` passes anyway. What worked on the one rootless host tested: `grpc_endpoint = "https://10.0.2.2:17670"` under `[openshell.drivers.docker]` in `gateway.toml`, and `10.0.2.2` added to the server certificate with `openshell-gateway generate-certs --output-dir ~/.local/state/openshell/tls --server-san host.openshell.internal --server-san 10.0.2.2`, which logs `server TLS certificate refreshed for current SAN set`. Restart the gateway. It stays bound to `127.0.0.1`. The fix may not carry over: `10.0.2.2` reaches the host only when slirp4netns runs without `--disable-host-loopback`, and Docker's stock `dockerd-rootless.sh` normally passes that flag. That case is untested. |
| `sandbox create` fails with `IdentityResolutionFailed: descriptor error: workload identity must not contain UID or GID zero` | The image declares `USER root`, and OpenShell refuses to run a workload as root. Keep the Dockerfile's `USER sandbox`, or use another non-root user that owns `/workspace` (OpenShell never chowns it). |
| `sandbox create` fails with `name exceeds maximum length (N > 19)` | A sandbox name is at most 19 characters of `[a-z0-9-]`. `on-work.sh` spends them on `shs-` plus the last 15 characters of the session ID, and keeps the whole ID in the `session` label. A longer prefix has to take fewer characters of the ID. |
| Every bash call returns `bash: start bash pty: open /dev/ptmx: permission denied` while read, write, and grep still work | `/dev/ptmx` and `/dev/pts` are gone from `read_write` in `policy.yaml`. The worker runs bash on a pseudo-terminal and needs both. Put them back, then test with a new session: file rules are fixed once a sandbox has started. |
| Worker log shows `failed to download skill`, or `openshell logs` shows `DENIED` on `/v1/skills/...` or `/v1/memory_stores/...` | Expected: `policy.yaml` allows only the six routes a session with no skills and no memory store uses, and the demo does not cover either one. The worker carries on without the skill. Bake skill files into the image, and use `docker-memory/` for memory. |
| Every call the worker makes gets a 403 with `"error":"policy_denied"`, starting with the heartbeat | The sandbox was created from `policy.yaml` as it is on disk, with `SESSION_ID` and `ENVIRONMENT_ID` still in the paths. `on-work.sh` fills the two IDs in with `sed` before `sandbox create`. Do the same for a sandbox you create by hand. |
| `on-work.sh` logs `is in Error and cannot be stopped: deleting it, /workspace included`, or `is in Error, deleting it` on the next work item | The sandbox's main process (`sleep infinity`) died, most likely killed by the agent, which runs as the same user, or `sandbox create` failed after the gateway accepted it (an image it cannot pull). OpenShell can neither start nor stop a sandbox in `Error`, so the script deletes it. After a killed main process, the session's next message gets a new sandbox with an empty `/workspace`. After a failed create, the session is stuck (next row): fix the image and create a new session. |
| `ant beta:sessions:events send` returns 400 `waiting on responses to events [...]` for a `user.message` | `on-work.sh` exited non-zero on that session's work item, so nothing answered the agent's tool call and nothing retries it. Fix what `on-work.sh` logged, then create a new session. |
| `openshell policy update ... --wait` prints `Timeout waiting for policy version N to load` and exits 124 | The sandbox is stopped, which it is from about 60s after the agent's last turn. The change is saved anyway and loads at the next start. Leave `--wait` off unless a worker is up. |
| `curl` run through `openshell sandbox exec` gets `curl: (7) Failed to connect` even on one of the six routes | The network rule names `/usr/local/bin/ant`, so it covers `ant` and the processes `ant` starts. The agent's shell is a child of the worker. A command you `exec` is not. Test the network policy through a session. |
| `openshell sandbox exec` hangs in a script and `--timeout` never fires | When stdin is not a terminal, `sandbox exec` reads it to the end before it sends the request, so an inherited pipe that stays open blocks it forever. Add `</dev/null`, as `on-work.sh` does on its `pgrep` call. The other `openshell` subcommands do not read stdin. |
| Worker log shows `stream disconnected; reconnecting` about 10s after a sandbox starts, or right after `openshell policy update`, and `openshell logs` shows `DENIED api.anthropic.com:443 [reason:L7 tunnel closed before inspection because policy changed ...]` | Expected. OpenShell closes a sandbox's open connections whenever it loads a policy, and it does that once about 10s after every start. The worker reconnects its event stream and picks up any tool call it missed. |
| Stopped `shs-*` sandboxes pile up in `openshell sandbox list` | By design: stopping keeps `/workspace` for the session's next message, and nothing removes a sandbox afterward. `openshell sandbox delete $(openshell sandbox list --selector app=shs-openshell --names)` deletes them all, running ones included, along with their decision logs. Run it when no session is live. |

All four `start.sh` scripts deliberately `unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN`:
the sandbox host runs on the environment key alone. Don't "fix" that.
