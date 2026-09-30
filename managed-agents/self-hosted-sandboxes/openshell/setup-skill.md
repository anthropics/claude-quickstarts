---
name: openshell-sandbox
description: Set up NVIDIA OpenShell as the self-hosted sandbox for Claude Managed Agents, step by step. Covers the host check, installing OpenShell, creating the agent and environment, running a first session, confirming the policy held, and changing policy.yaml for your own agent. Use when someone asks to set up, run, adapt, or debug this quickstart, or asks where the OpenShell policy reference is.
---

# Setup walkthrough: NVIDIA OpenShell as a sandbox for Claude Managed Agents

Walk the user through these steps in order, from this directory. Each step
says what to run, what a healthy result looks like, and what to do when it is
not. Finish a step before you start the next. [`README.md`](./README.md) has
the design and [`../CLAUDE.md`](../CLAUDE.md) has the full debugging table.

## Ground rules

- **Never print the environment key or a session token.** Ask the user to
  paste the key into `.env` themselves.
- **Ask before you install anything.** The OpenShell installer adds a system
  package and starts a service.
- **Do not loosen the policy to make an error go away.** Three of the five
  commands in step 6 are supposed to fail. Keep `enforcement: enforce` and
  `compatibility: hard_requirement`: the defaults for both let violations
  through.
- **Shell variables do not outlive a shell.** Steps 6 to 8 share `$session`,
  `$environment`, and `$sandbox`. A person keeps one terminal open. If you are
  Claude Code, each command runs in a new shell, so start every command that
  uses them with the "set the variables again" lines in step 6, and run
  `./start.sh` in the background with its output in a file you can read.
- **Look fields up, do not guess them.** The
  [policy reference](#policy-reference) at the end lists where each one is
  documented.

## What you are building

```
your machine                                     Anthropic
┌────────────────────────────────────────┐      ┌──────────────────────┐
│ start.sh                               │      │ self-hosted          │
│  └─ ant beta:worker poll ──────────────┼─────▶│ environment          │
│       │  environment key               │      │ (a work queue)       │
│       └─ on-work.sh, once per work item│      │                      │
│            │  session token, on stdin  │      │ agent loop           │
│  ┌─────────▼──────────────────────┐    │      │                      │
│  │ OpenShell sandbox, one/session │    │      │                      │
│  │  ant beta:worker run ──────────┼────┼─────▶│ six routes: 4 on its │
│  │   └─ the agent's bash, files   │    │      │ session, 2 on work   │
│  └────────────────────────────────┘    │      │ items in its env     │
│    policy.yaml, enforced outside it    │      └──────────────────────┘
└────────────────────────────────────────┘
```

The agent loop runs on Anthropic's servers. Its tool calls run in a sandbox on
your machine, and OpenShell confines that sandbox to what `policy.yaml` allows.

## 1. Check the host

```sh
docker version --format '{{.Server.Version}}'   # 28 or later
jq --version                                    # 1.6 or later
ant --version                                   # 1.30 or later
ant auth status                                 # shows a login
uname -r                                        # Linux: 6.2 or later
```

- No login: `ant auth login`, or export `ANTHROPIC_API_KEY`. The CLI does not
  read `.env`.
- Linux also needs the Landlock kernel feature. Nothing here tests for it up
  front. `policy.yaml` sets `hard_requirement`, so on a kernel that cannot
  enforce Landlock the sandbox refuses to start in step 6. The fix is a kernel
  with Landlock on. Do not switch to `best_effort`: it starts the sandbox with
  no filesystem rules at all.
- macOS: Apple silicon, Docker Desktop with host networking on and Enhanced
  Container Isolation off.
- Anything else in doubt: OpenShell's
  [support matrix](https://docs.nvidia.com/openshell/latest/about/support-matrix).

## 2. Install OpenShell

Skip this if `openshell --version` already prints `0.1.x`. A `0.0.x` release
has a different CLI and will not work. Otherwise ask the user, then:

```sh
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/v0.1.2/install.sh | OPENSHELL_VERSION=v0.1.2 sh
```

Check the gateway, the local service that creates sandboxes:

```sh
openshell --version      # openshell 0.1.2
openshell sandbox list   # "No sandboxes found." and exit 0
```

Use `sandbox list` for this check. `openshell status` exits 0 even with no
gateway configured. If the list fails, `../CLAUDE.md` has rows for no gateway
registered and for a host that is itself a Kubernetes pod.

## 3. Create the agent and the environment

```sh
ant apply --dry-run .    # shows the plan
ant apply --yes .        # creates both, writes claude-lock.json
```

Healthy output lists `./environments/self-hosted.yaml` and
`./agents/openshell-demo.md` as `created`, or says `Everything is up to date`
on a later run. Run it from this directory, never
from the parent: `ant apply` walks the directory it is given. For the same
reason, never add a file named `skill.md` or `SKILL.md` here. `ant apply .`
would take the whole directory for one skill resource and stop finding the
agent and the environment.

## 4. Add the environment key

This is the one step you cannot do for the user. Ask them to:

1. Open the Console, then Environments, then
   `quickstart-self-hosted-sandbox-openshell-env`, then Keys, and mint a key.
2. Run `cp .env.example .env`.
3. Uncomment `ANTHROPIC_ENVIRONMENT_KEY=` in `.env` and paste the key there.

Confirm it without reading the file. This prints a count, not the key:

```sh
grep -c '^ANTHROPIC_ENVIRONMENT_KEY=.' .env    # 1
```

A `0` means the line is still commented out or empty, and step 5 would stop
with `set ANTHROPIC_ENVIRONMENT_KEY in .env and uncomment the line`.

## 5. Start the sandbox side

```sh
./start.sh
```

Leave it running. It checks the gateway, builds the `shs-openshell` image, and
starts the poller. Healthy output ends with `polling env=env_...`.

## 6. Run a first session

From this directory, in a second terminal:

```sh
agent=$(jq -r '.resources["./agents/openshell-demo.md"].id' claude-lock.json)
environment=$(jq -r '.resources["./environments/self-hosted.yaml"].id' claude-lock.json)
session=$(ant beta:sessions create \
  --agent "$agent" \
  --environment-id "$environment" \
  --initial-event '{type: user.message, content: [{type: text, text: "Run each of these and report the exact result: echo hi > /workspace/hi.txt, echo hi > /tmp/hi.txt, echo hi > /etc/hi.txt, curl -sS https://example.com, curl -sS https://api.anthropic.com/v1/models"}]}' \
  --transform id \
  --raw-output)
echo "$session"    # sesn_...
```

Note that ID. To set the variables again in a new shell:

```sh
session=sesn_...    # the ID you noted
environment=$(jq -r '.resources["./environments/self-hosted.yaml"].id' claude-lock.json)
sandbox=$(openshell sandbox list --selector "session=$session" --names)
```

The `start.sh` terminal prints `[on-work] session=sesn_... work=sesn_...
sandbox=shs-... (creating)`, then one `dispatched tool` line per tool call. One
`stream disconnected; reconnecting` warning about ten seconds in is expected.
The report is ready as soon as the tool calls stop. About a minute later the
worker prints `session idle after end_turn; stopping`, and `on-work.sh` prints
`worker exited rc=0, stopping shs-...` and stops the sandbox.

If `on-work.sh` exits non-zero instead, nothing retries that work item and the
session stays stuck. Fix what it logged, then create a new session. An exit
about 15 seconds after `(creating)` with `ControlSupervisorStartFailed` is
rootless Docker, and `../CLAUDE.md` has the row for it.

## 7. Confirm the policy held

Read the agent's report:

```sh
ant beta:sessions:events list \
  --session-id "$session" \
  --type agent.message \
  --transform 'content.#.text' \
  --format yaml
```

| Command | Expected result |
|---|---|
| write to `/workspace`, write to `/tmp` | succeeds |
| write to `/etc` | `Permission denied` |
| `curl https://example.com` | `curl: (7) Failed to connect` |
| `curl https://api.anthropic.com/v1/models` | a 403 body with `"error":"policy_denied"` |

Then read OpenShell's own record, which does not depend on what the agent says:

```sh
sandbox=$(openshell sandbox list --selector "session=$session" --names)
openshell logs "$sandbox" --source sandbox -n 500 | grep -E 'ALLOWED|DENIED' | grep -v SSH:
openshell rule get "$sandbox" --status pending
```

The log has one `ALLOWED` or `DENIED` line per connection and per request, with
the program, the destination, and the reason. Expect these `DENIED` lines and
no others:

| Line | Meaning |
|---|---|
| `NET:REFUSE ... DENIED example.com` and `NET:OPEN ... DENIED /usr/bin/curl(0) -> example.com:443` | One blocked `curl`, logged at the name lookup and at the connection |
| `HTTP:GET ... DENIED GET http://api.anthropic.com:443/v1/models` | The host is allowed and the route is not |
| `DENIED api.anthropic.com:443 [reason:L7 tunnel closed ... because policy changed ...]` | Not a refusal. OpenShell reloads its settings about ten seconds after each start and closes open connections, which is the worker's `reconnecting` warning |

`rule get` lists the rules OpenShell drafted from blocked connections, here one
for `example.com`. Read it as a summary of what was blocked. Nothing in it
applies until a person approves it. Do not approve a drafted rule to make the
demo pass, and leave the gateway's approval mode on manual.

Leave `--level warn` off `openshell logs`: it hides policy events. Filesystem
denials are not logged.

The setup is done when the report matches the first table and the log matches
the second.

## 8. Change the policy

To try a rule on one sandbox, add it, then send the session a message. By now
`on-work.sh` has stopped the sandbox, and the message restarts it:

```sh
openshell policy update "$sandbox" \
  --rule-name example \
  --binary /usr/bin/curl \
  --add-endpoint example.com:443:read-only:rest:enforce
ant beta:sessions:events send \
  --session-id "$session" \
  --event '{type: user.message, content: [{type: text, text: "I changed the policy to allow example.com. Run curl -sS -o /dev/null -w \"%{http_code}\" https://example.com and report the result."}]}'
```

The update prints `Policy version 2 submitted`, `start.sh` prints
`(restarting)`, and the agent reports `200`. Read the report with the command
from step 7.

To give the rule to every new session, add it under `network_policies` in
`policy.yaml`. This is the YAML OpenShell stores for the command above:

```yaml
  example:
    name: example
    endpoints:
      - host: example.com
        port: 443
        protocol: rest
        enforcement: enforce
        access: read-only
    binaries:
      - path: /usr/bin/curl
```

What reaches which sandbox:

| Change | Reaches |
|---|---|
| `openshell policy update`, network rules only | That one sandbox: within about ten seconds if it is running, at its next start if it is stopped. It survives stop and start |
| An edit to `policy.yaml`, any part | New sandboxes only, which means new sessions. `on-work.sh` reads the file when it creates a sandbox |

No command changes `filesystem_policy`, `landlock`, or `process` on a sandbox
that has started.

Check that a sandbox has not drifted from the file:

```sh
sed -e "s/SESSION_ID/$session/" -e "s/ENVIRONMENT_ID/$environment/" policy.yaml > boundary.yaml
openshell sandbox get "$sandbox" --policy-only > sandbox.yaml
openshell-prover check sandbox.yaml --boundary boundary.yaml
```

Straight after the update above it prints `result: exceeds_boundary`, names
`example.com:443` as the counterexample, and exits 1. That is the check working.
Now take the rule out, whether or not you ran the check, so the sandbox is not
left with a host the file does not allow:

```sh
openshell policy update "$sandbox" --remove-rule example
openshell sandbox get "$sandbox" --policy-only > sandbox.yaml
openshell-prover check sandbox.yaml --boundary boundary.yaml
```

It prints `result: within_boundary` and exits 0: the sandbox allows nothing the
file does not. Treat any other exit code as drift. The prover compares two
policies. It says nothing about what an agent did.

## 9. Make it yours

Work through these with the user for their own agent:

- **Tools the agent needs**: add packages to the `Dockerfile`. Keep
  `USER sandbox`, because OpenShell refuses to run a workload as root.
- **Hosts the agent needs**: one rule per host, as in step 8. Name the narrowest
  `binaries` and the narrowest `access` or `rules` that work. A rule matches a
  program or any of its parent processes, so a rule for `/usr/local/bin/ant`
  also covers the agent's shell.
- **Paths the agent needs**: add them to `read_only` or `read_write`. Keep
  `/dev/ptmx` and `/dev/pts` writable, or every bash call fails.
- **The `SESSION_ID` and `ENVIRONMENT_ID` placeholders**: leave them in.
  `on-work.sh` fills them in per session. OpenShell matches method and path, not
  credentials, so a wildcard there would open the same routes on any other
  session the sandbox held a credential for.
- **Tools that run on Anthropic's side**: `web_fetch`, `web_search`, and MCP
  servers never pass through the sandbox, so `policy.yaml` does not govern them.
  The agent file turns the two web tools off for that reason.
- **Skills and memory stores**: this demo covers neither. Bake skill files into
  the image, and see [`../docker-memory/`](../docker-memory/) for memory.
- **Limits**: none are set. `SANDBOX_CREATE_ARGS="--cpu 2 --memory 4Gi" ./start.sh`
  passes flags to `openshell sandbox create`. Rootless Docker without cgroup
  delegation accepts both and enforces neither.

| You changed | Then |
|---|---|
| `agents/openshell-demo.md` | `ant apply --yes .`, which publishes a new agent version |
| `policy.yaml` | Create a new session. `on-work.sh` reads the file each time it creates a sandbox |
| `Dockerfile` | Restart `./start.sh`, which rebuilds the image, then create a new session |

## 10. Clean up

Stop every `start.sh` with Ctrl-C. Stopped sandboxes keep `/workspace` for their
session's next message and are never removed automatically. When no session is
live, this deletes them all, with their logs:

```sh
openshell sandbox delete $(openshell sandbox list --selector app=shs-openshell --names)
rm -f boundary.yaml sandbox.yaml
```

With no sandboxes left, the first command stops with `required arguments were
not provided`, which is harmless.

Still in place, for the user to keep or remove: the agent and the environment
from step 3 (archive them in the Console), the session, and the `shs-openshell`
image (`docker rmi shs-openshell`). Ask them to revoke the environment key in
the Console when they are done with it.

## Policy reference

Read the page before you write a field. `latest` tracks the newest release, and
this quickstart is tested on 0.1.2, so use the tagged source when the two
disagree.

| Question | Where to look |
|---|---|
| Every field, its default, and its constraints, with a full example | [Policy Schema Reference](https://docs.nvidia.com/openshell/latest/how-it-works/policies/schema) |
| What a policy controls and where a sandbox's policy comes from | [Sandbox Policies](https://docs.nvidia.com/openshell/latest/how-it-works/policies/overview) |
| How network rules are evaluated, with examples for REST, package registries, WebSocket, GraphQL, MCP, and TCP | [Network Rules](https://docs.nvidia.com/openshell/latest/how-it-works/policies/network-rules) |
| The CLI for setting, inspecting, changing, and rolling back a policy, and global policies | [Manage Sandbox Policies](https://docs.nvidia.com/openshell/latest/how-it-works/policies/manage-policies) |
| What applies with no policy, and the paths OpenShell always adds | [Default Policy and Baseline Paths](https://docs.nvidia.com/openshell/latest/how-it-works/policies/default-policy) |
| Checking one policy against a boundary | [Policy Prover](https://docs.nvidia.com/openshell/latest/how-it-works/policies/prover) |
| Rules drafted from blocked requests, and who approves them | [Policy Advisor](https://docs.nvidia.com/openshell/latest/how-it-works/policies/advisor) |
| Each security control, its default, and the risk of changing it | [Security Best Practices](https://docs.nvidia.com/openshell/latest/security/best-practices) |
| A guided first policy | [Write Your First Sandbox Network Policy](https://docs.nvidia.com/openshell/latest/tutorials/first-network-policy) |
| The log format, ways to read the log, and export to a SIEM | [Sandbox Logging](https://docs.nvidia.com/openshell/latest/observability/logging), [Accessing Logs](https://docs.nvidia.com/openshell/latest/observability/accessing-logs), [OCSF JSON Export](https://docs.nvidia.com/openshell/latest/observability/ocsf-json-export) |
| The same pages as they were at 0.1.2 | [`docs/how-it-works/policies` at `v0.1.2`](https://github.com/NVIDIA/OpenShell/tree/v0.1.2/docs/how-it-works/policies) |

On the machine itself:

```sh
openshell policy --help                            # set, update, get, list, delete
openshell sandbox get "$sandbox" --policy-only     # the policy a sandbox has now
openshell policy list "$sandbox"                   # its revisions, and whether each one loaded
```

For the Claude Managed Agents side:
[self-hosted sandboxes](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes)
and their
[security model](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes-security).
