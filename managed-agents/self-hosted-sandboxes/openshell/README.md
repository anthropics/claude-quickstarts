# NVIDIA OpenShell: one policy-governed sandbox per session

Run Claude Managed Agents sessions on hardware you control, with each
session's tools confined by a policy you write. Managed Agents sets its own
security boundary: the agent loop runs on Anthropic's servers, apart from the
sandbox where the agent's tool calls execute. In a self-hosted environment you
run that sandbox, and this demo adds another layer of control to it with
[NVIDIA OpenShell](https://docs.nvidia.com/openshell/latest/about/overview), an
open source (Apache 2.0) runtime for agents. OpenShell denies file and network
access that `policy.yaml` does not allow, enforces the policy outside the
agent's process, and logs its network decisions. The policy covers the sandbox
and nothing beyond it: `web_fetch`, `web_search`, and MCP servers run on
Anthropic's side and never pass through it.

The host runs `ant beta:worker poll` against a self-hosted environment, which
is a work queue that your own machines claim sessions from. For each claimed
session its `--on-work` script runs the worker, `ant beta:worker run`, inside
that session's OpenShell sandbox. Here a sandbox can reach six routes on
`api.anthropic.com` and no other host: four on its own session and two on work
items in its own environment. It can write files only under `/workspace` and
`/tmp`. The environment key never enters a sandbox: each worker gets its own
session's token, piped to it over stdin.

## How to use it

Needs Docker 28 or later, `jq` 1.6 or later, the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart)
1.30 or later (`brew install anthropics/tap/ant`), `ant auth login` once (or
`ANTHROPIC_API_KEY` exported in your shell), and OpenShell. OpenShell runs on
Linux 6.2 or later with the
[Landlock](https://docs.kernel.org/security/landlock.html) kernel feature
enabled, and on Apple silicon Macs through Docker Desktop with host networking
on and Enhanced Container Isolation off. Its
[support matrix](https://docs.nvidia.com/openshell/latest/about/support-matrix)
has the versions. Install 0.1.2, the release this demo was tested with (0.0.x
releases have a different CLI):

```sh
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/v0.1.2/install.sh | OPENSHELL_VERSION=v0.1.2 sh
openshell status     # expect "Status: Connected"
```

The installer adds a system package (with `sudo` on Linux, Homebrew on macOS)
and starts the gateway, the local service that creates sandboxes and keeps
their policies and logs. Then let Claude Code run the rest:

```sh
cd managed-agents/self-hosted-sandboxes/openshell
claude "help me set up and run this self-hosted sandbox demo"
```

Claude reads [`setup-skill.md`](./setup-skill.md) and walks you through it: ten
steps, from the host check to a policy for your own agent, each with the output
to expect, and a table of where OpenShell documents every policy field.

Or by hand. One-time setup, from this directory:

```sh
ant apply .          # creates the self-hosted environment + agent, records their IDs in claude-lock.json
cp .env.example .env
# Mint a key for that environment in the Console (Environments -> it -> Keys),
# then uncomment ANTHROPIC_ENVIRONMENT_KEY= in .env and set it
```

[`ant apply`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/apply)
reads the agent from `agents/openshell-demo.md`, whose frontmatter is the
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

Control plane, from this directory in any other terminal, or on any machine
with the same `claude-lock.json`. The IDs come out of the lockfile by the file
that declares each resource. The prompt asks for two things the policy allows
and three it denies:

```sh
agent=$(jq -r '.resources["./agents/openshell-demo.md"].id' claude-lock.json)
environment=$(jq -r '.resources["./environments/self-hosted.yaml"].id' claude-lock.json)
session=$(ant beta:sessions create \
  --agent "$agent" \
  --environment-id "$environment" \
  --initial-event '{type: user.message, content: [{type: text, text: "Run each of these and report the exact result: echo hi > /workspace/hi.txt, echo hi > /tmp/hi.txt, echo hi > /etc/hi.txt, curl -sS https://example.com, curl -sS https://api.anthropic.com/v1/models"}]}' \
  --transform id \
  --raw-output)
```

`start.sh` logs `[on-work] session=sesn_... work=sesn_... sandbox=shs-...
(creating)` followed by the worker's own log (`executing tool ...`,
`dispatched tool ...`). About ten seconds after a sandbox starts, expect one
`level=WARN msg="stream disconnected; reconnecting"`: OpenShell reloads its
settings once at that point and closes the sandbox's open connections, and the
worker reconnects without losing a tool call. About a minute after the agent
finishes, the worker prints `session idle after end_turn; stopping`, and then
`[on-work] ... worker exited rc=0, stopping shs-...`. The agent's report is
ready as soon as the tool calls stop:

```sh
ant beta:sessions:events list \
  --session-id "$session" \
  --type agent.message \
  --transform 'content.#.text' \
  --format yaml
```

The two writes under `/workspace` and `/tmp` succeed. The other three fail in
three different ways:

| Command | What the agent sees | Why |
|---|---|---|
| `echo hi > /etc/hi.txt` | `Permission denied` | `/etc` is under `read_only`. |
| `curl -sS https://example.com` | `curl: (7) Failed to connect to example.com port 443` | No rule names the host, so `connect()` fails at once. |
| `curl -sS https://api.anthropic.com/v1/models` | `{"binary":"/usr/bin/curl","detail":"GET /v1/models not permitted by policy","error":"policy_denied",...}` | The host is allowed. The route is not one of the six, so OpenShell answers with its own HTTP 403. |

One poller serves one session at a time. A work item is the queue entry a
session gets each time it has something to run, and the CLI stops it as soon
as the `--on-work` script returns, so `on-work.sh` waits for the worker to
exit. Run `./start.sh` in as many terminals as you want concurrent sessions.
The environment is a queue and spreads sessions across them. More hosts work
too, but a sandbox lives on one host's gateway, so a follow-up message that
another host claims starts with an empty `/workspace`.

## The policy

`policy.yaml` has three parts:

- **`filesystem_policy`** lists the paths a process in the sandbox can open. A
  path that is not listed cannot be read either: `ls /` fails. File rules are
  fixed once a sandbox has started, so a change needs a new sandbox.
- **`landlock`** is the Linux kernel feature that enforces those paths. With
  `hard_requirement`, a sandbox does not start if the kernel cannot enforce
  them. The default, `best_effort`, starts it without them.
- **`network_policies`** has one rule: `/usr/local/bin/ant` and the processes
  it starts can send six method and path pairs to `api.anthropic.com:443`.
  `enforcement: enforce` blocks any other request to that host. The default,
  `audit`, logs a violation and lets it through.

The six routes are what `ant beta:worker run` calls for an agent with no
skills and no memory store, and `policy.yaml` says what each one is for. The
file has `SESSION_ID` and `ENVIRONMENT_ID` where those IDs go, and `on-work.sh`
fills them in before it creates the sandbox. OpenShell matches a request's
method and path and not its credentials. With a wildcard there, code in the
sandbox could use the same routes to move data to any other session it had a
credential for, including one in someone else's organization. The work ID in
the last two routes stays a wildcard, so the same reasoning applies to the
heartbeat and stop of other work items in this environment.

To read a method and path, OpenShell decrypts the sandbox's HTTPS requests to
that host and re-encrypts them on the way to Anthropic, so it sees the session
token. `ant`, `curl`, and `git` trust its certificate through `SSL_CERT_FILE`
and equivalents that OpenShell sets in the sandbox.

### What the policy does and does not cover

The agent runs arbitrary bash in the sandbox, so it can read whatever the
sandbox holds.

- **The agent's shell can reach the same six routes.** The `binaries` list
  matches the program that opens a connection or any of its parent processes,
  and the worker starts the agent's shell. Listing `/usr/local/bin/ant` does
  not separate the worker from the agent. The route list is what limits the
  agent, which is why `/v1/models` gets a 403 in the demo.
- **Treat the session token as readable by the agent.** It is in the worker's
  memory and the agent's shell runs as the same user. With it the agent can
  send its own session any event the token allows, not only tool results, and
  can stop its own work item.
- **Tools that run on Anthropic's side do not pass through the sandbox.** The
  agent file turns `web_fetch` and `web_search` off so that the sandbox is the
  agent's only route to the network. An MCP server you add is another route.
- **`/workspace` and `/tmp` are writable and executable.** The agent can write
  a program there and run it, under the same policy.
- **The gateway can overrule this file.** A global policy replaces every
  sandbox's policy, and automatic approval adds rules OpenShell drafts from
  blocked connections. Both are off by default.

### Read the network log

`on-work.sh` names each sandbox after the last 15 characters of its session ID
and labels it with the whole ID:

```sh
sandbox=$(openshell sandbox list --selector "session=$session" --names)
openshell logs "$sandbox" --source sandbox -n 500 | grep -E 'ALLOWED|DENIED' | grep -v SSH:
```

One line of each kind, with the timestamp prefix removed:

```
NET:OPEN [INFO] ALLOWED /usr/local/bin/ant(0) -> api.anthropic.com:443 [policy:claude_managed_agents engine:opa]
HTTP:POST [INFO] ALLOWED POST http://api.anthropic.com:443/v1/environments/env_.../work/sesn_.../heartbeat [policy:claude_managed_agents engine:l7]
NET:REFUSE [MED] DENIED example.com [reason:policy_dns_ineligible]
NET:OPEN [MED] DENIED /usr/bin/curl(0) -> example.com:443 [reason:transparent_tcp_policy_denied]
NET:OPEN [INFO] ALLOWED /usr/bin/curl(0) -> api.anthropic.com:443 [policy:claude_managed_agents engine:opa]
HTTP:GET [MED] DENIED GET http://api.anthropic.com:443/v1/models [policy:claude_managed_agents engine:l7] [reason:L7_REQUEST deny GET api.anthropic.com:443/v1/models reason=GET /v1/models not permitted by policy]
```

`NET:OPEN` is the decision on a connection: which program, host, and port.
`HTTP:` is the decision on one request inside an allowed connection. OpenShell
prints `http://` for a request it has decrypted, and the connection to
Anthropic is still TLS. The `DENIED api.anthropic.com:443 [reason:L7 tunnel
closed ... because policy changed ...]` lines ten seconds after each start are
the settings reload, not a refused request.

The log is a buffer in the gateway's memory, 2,000 lines per sandbox. It goes
when the gateway restarts or the sandbox is deleted, and a stop drops the last
half second. OpenShell's
[logging docs](https://docs.nvidia.com/openshell/latest/observability/accessing-logs)
cover durable export. Filesystem denials are not logged.

### Allow one more host

Network rules can change after a sandbox is created, whether it is running or
stopped. `on-work.sh` stopped this one when the worker exited, so add the rule,
then send the session a message, which restarts the sandbox:

```sh
openshell policy update "$sandbox" \
  --rule-name example \
  --binary /usr/bin/curl \
  --add-endpoint example.com:443:read-only:rest:enforce
ant beta:sessions:events send \
  --session-id "$session" \
  --event '{type: user.message, content: [{type: text, text: "I changed the policy to allow example.com. Run curl -sS -o /dev/null -w \"%{http_code}\" https://example.com and report the result."}]}'
```

The agent reports `200`. `read-only` allows `GET`, `HEAD`, and `OPTIONS`, so a
`POST` to the same host still gets a 403. A running sandbox loads a change
within about ten seconds (`--wait` blocks until it has, and times out on a
stopped one). The change belongs to that one sandbox and survives its stop and
start. To give it to every new session, add the rule to `policy.yaml`.

### Check a sandbox against `policy.yaml`

`openshell-prover`, installed with OpenShell, checks that one policy allows
nothing a second policy (the boundary) does not. With this session's copy of
`policy.yaml` as the boundary, it shows whether a sandbox has drifted from the
file in this repository:

```sh
sed -e "s/SESSION_ID/$session/" -e "s/ENVIRONMENT_ID/$environment/" policy.yaml > boundary.yaml
openshell sandbox get "$sandbox" --policy-only > sandbox.yaml
openshell-prover check sandbox.yaml --boundary boundary.yaml
```

```
result: exceeds_boundary
coverage: domains=filesystem,network_l4,network_rest,process,landlock
counterexample: network binary=- ancestor_binary=- binary_identity_required=false host=example.com:443 destination_ip=8.8.8.8 trusted_gateway=false protocol=rest method=GET path=/
```

It exits 1 and names a request the sandbox's policy allows and the file does
not. Take the rule out (`openshell policy update "$sandbox" --remove-rule
example`), run the last two commands again, and it prints `result:
within_boundary` and exits 0. It exits 3 when it cannot decide, so treat
anything but 0 as drift. The prover compares two policies. It says nothing
about what an agent did.

## How it works

| | |
|---|---|
| `agents/openshell-demo.md`, `environments/self-hosted.yaml` | The agent and the self-hosted environment, as files for `ant apply`. The agent pins `tools: [{type: agent_toolset_20260401}]`, the toolset `ant beta:worker run` serves, and turns off `web_fetch` and `web_search`. |
| `policy.yaml` | What a sandbox may open and reach, with placeholders for the session and environment IDs. |
| `setup-skill.md` | The setup walkthrough Claude Code follows, and the index to OpenShell's policy reference. To load it as a skill in any session, copy it to `~/.claude/skills/openshell-sandbox/SKILL.md`. It still runs from this directory. It is not named `skill.md` because `ant apply .` takes a directory holding that file for a skill resource. |
| `start.sh` | Host. Checks the gateway answers, builds the image, execs `ant beta:worker poll --on-work on-work.sh` with the environment ID from `claude-lock.json` and the environment key from `.env`. |
| `on-work.sh` | Host, once per claimed work item. Takes the session token out of the item's `secret` on stdin, creates or restarts the session's sandbox, pipes the token to `ant beta:worker run` inside it, and stops the sandbox when the worker exits. Refuses items that carry no token. `SANDBOX_CREATE_ARGS` adds `openshell sandbox create` flags. The demo sets no CPU, memory, or disk limit: `--cpu` and `--memory` add the first two, and rootless Docker without cgroup delegation accepts both and enforces neither. |
| `Dockerfile` | `debian:12-slim` + `ant` (pinned by `ARG ANT_VERSION` and checked against a pinned SHA-256) + `rg`/`git`/`curl`/`jq`, a non-root user, and `/workspace`. No entrypoint, because OpenShell ignores it. Add whatever else your agents need. |

Three credentials, three blast radii. Your org credential (`ant auth login`
or `ANTHROPIC_API_KEY`) runs `ant apply` and creates sessions. The sandbox host
does not need it, and `start.sh` drops it from the poller's environment. The
environment key stays on the host, in `.env`, the poller, and the first lines
of `on-work.sh`. It can claim any session queued to this environment and act as
that session's worker. Each sandbox holds only a token
[issued for its one session](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes-security).

The token arrives inside the work item's `secret`, which bundles it with other
tokens the worker does not use. `on-work.sh` keeps the one, drops the rest,
and `ant beta:worker run` reads the result from `--work-secret-file
/dev/stdin`. That flag needs `ant` 1.32 or later in the image, and the
`Dockerfile` pins 1.35.0. The token is never in a file, on a command line, in
the sandbox definition the gateway stores, or in the worker's environment.

An agent with skills runs without them here: the policy has no route for the
skills API, so the worker logs the failed download and carries on. A route
alone may not fix that, because [`docker-memory/`](../docker-memory/) found
that API refuses the session token. Bake the skill files into the image
instead. That demo is also the one to read for memory stores.

The sandbox belongs to the session, not to the work item. `on-work.sh` stops it
when the worker exits, which kills every process inside and keeps `/workspace`
and `/tmp`. Send the session another message and a new work item restarts the
same sandbox with a new token. Creating or restarting one took under a second
in testing.

The agent runs as the same user as the process that holds the sandbox open, and
killing that process puts the sandbox in `Error`. `on-work.sh` then deletes the
sandbox, `/workspace` included. Stopped sandboxes are never removed
automatically. This deletes them all, running ones included, with their logs:

```sh
openshell sandbox delete $(openshell sandbox list --selector app=shs-openshell --names)
```

If `on-work.sh` exits non-zero (no gateway, an image the gateway cannot find, a
policy OpenShell rejects), the poller stops that work item and nothing retries
it. The session is left waiting on its tool call and rejects a new
`user.message` with a 400. Fix the cause and create a new session.

This demo uses OpenShell's Docker driver, which runs sandboxes as containers on
the gateway's own host, and it has only been run there. The
[Kubernetes](https://docs.nvidia.com/openshell/latest/kubernetes/setup) and
[MicroVM](https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/runtimes)
drivers need changes to it: both use `/sandbox` as the working directory, not
the image's `WORKDIR`, and a cluster pulls the image from a registry.
