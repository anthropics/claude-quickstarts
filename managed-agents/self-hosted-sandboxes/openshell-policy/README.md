# NVIDIA OpenShell: a signed ceiling on each agent's network access, proved before anything runs

[`../openshell/`](../openshell/) runs each Claude Managed Agents session's
tools in an [NVIDIA OpenShell](https://docs.nvidia.com/openshell/latest/about/overview)
sandbox, and every session gets the same `policy.yaml`. That stops being
enough with a second kind of agent. Someone has to decide what each kind may
reach. Something has to hold every sandbox to that decision, including the
ones that were edited by hand at 2 a.m. And you need a way to find out what a
new agent needs that is not "open everything and read the logs".

This directory is a reference for those three things:

- **A ceiling.** One file per kind of agent says the most network access any
  of its sessions may ever hold. A person writes it and signs it. Nothing here
  accepts one that is unsigned or changed since. OpenShell calls this file a
  boundary policy.
- **A proof.** No sandbox gets a worker until its policy is proved to allow
  nothing the ceiling does not: the file before the sandbox is made, what the
  gateway made of it after, and what it has become each time it is reused.
  The same proof runs in CI on every policy change. The decision is made by
  OpenShell's own prover (`openshell-prover`), a solver that reasons over
  both policies, so it covers every request the policy could allow and not
  only the ones a test thought of.
- **A record.** Every proof, decision, stop and change of policy is a line in
  one ledger, and every connection OpenShell allowed or denied is kept beside
  it, each with the session and agent it concerns.

You use it in two phases:

| | **Discover** (staging) | **Run** (production) |
|---|---|---|
| The question | What does this agent need? | Is it held to what we agreed? |
| Proposals | On. A blocked agent proposes a rule, and it is approved only if the policy with that rule still proves inside the ceiling (**grow**). | Off. A blocked agent stays blocked and says so. |
| Starting policy | **Promote** and **shrink** turn what sessions used, and stopped using, into a diff of `policy.yaml`. A person reads it and merges it. | Frozen. It changes by a reviewed commit, proved in CI. |
| Services | Dispatcher, reviewer, audit collector | Dispatcher, audit collector. The reviewer only answers "no". |

The ceiling is the security boundary, in both phases. Growing, promoting and
shrinking keep an agent's standing access close to what it uses, which limits
what an accident can touch. They are no defence against an agent that has been
turned against you: it can ask for anything inside the ceiling and be given
it. So sign only a ceiling you would accept an agent holding all of, and read
[Threat model](ARCHITECTURE.md#threat-model) before you rely on this.

**Use this if** you run several kinds of agents on sandboxes you host, a
different person decides their limits than operates them, and you need to show
afterwards that the limits held. **Look elsewhere if** one static `policy.yaml`
covers your agents (`../openshell` is that), if you run sandboxes on more than
one host (see [Limits](#limits)), or if your agents' risk is in MCP servers or
web tools, which never pass through a sandbox.

```
   a person signs                                agentpolicy proves, with openshell-prover
   policy/profiles/<p>/ceiling.yaml  ─────▶  starting policy      ⊆ ceiling   before a sandbox is made, and in CI
                                             the sandbox's policy ⊆ ceiling   after it is made, and at every reuse
                                             policy + proposal    ⊆ ceiling   every approval     (Discover)
                                             promoted             ⊆ ceiling   every promotion    (Discover)
                                             shrunk ⊆ previous    ⊆ ceiling   every shrink       (Discover)
```

It plugs into `../openshell/on-work.sh` through that script's policy hook
(`ON_WORK_HOOK`, see its README), so the poller, the sandbox lifecycle and the
token handling are that quickstart's own. What you would own if you adopt it
is about 3,900 lines of Python (`src/agentpolicy/`), an 80-line hook, and the
policy files. [`ARCHITECTURE.md`](ARCHITECTURE.md) explains the design and the
trust boundaries. [`ISSUES.md`](ISSUES.md) lists the OpenShell issues found
building it.

## Run the demo

The demo is the Discover phase on one laptop. Run
[`../openshell/`](../openshell/) first: it installs OpenShell 0.1.2, checks
Docker, `jq` and the `ant` CLI, and shows one sandbox per session working.
This directory needs those plus Python 3.11 or later.

There are two ways to run the gateway. The steps below use the one
`../openshell` installs. The other runs it in Docker, for machines where
OpenShell's binaries cannot run: see the
[appendix](#appendix-running-the-gateway-in-docker). The whole demo has run
end to end only the second way ([Status](#status)).

**1. Install agentpolicy and run its tests.** They need no API access and no
OpenShell.

```sh
cd managed-agents/self-hosted-sandboxes/openshell-policy
make dev     # .venv with agentpolicy, and the OpenShell gRPC client generated
make test
source .venv/bin/activate    # puts `agentpolicy` on your PATH for the commands below
```

**2. Sign the demo profile's ceiling.** `policy/profiles/hello/ceiling.yaml`
lets curl read `example.com` and nothing else.

```sh
make keys    # a demo copy of policy/ in state/demo, a local key trusted there; signs every ceiling
make check   # verifies each signature and proves each profile's grants inside its ceiling
```

**3. Create the agents and the environment.** `make apply` runs `ant apply`
on `agents/` and `environments/` (the demo agent, the reviewer, and an
environment for each), then maps the worker environment to the `hello`
profile. Once it has run, mint a key for that environment in the Console
(Environments, the environment `ant apply` just created, Keys) and put it in
`.env`. A file is fine for the demo. In production, keep the key in a secrets
manager.

```sh
make apply
cp .env.example .env    # uncomment ANTHROPIC_ENVIRONMENT_KEY= and set it
```

**4. Configure the gateway, build the images, and check enforcement.**

```sh
make openshell-settings    # proposals on, gateway auto-approval off, OCSF JSON on
make image                 # ../openshell's image, and this one on top of it
make enforce-check         # one throwaway sandbox, four requests, four "ok" lines
```

`make enforce-check` is the one step that tests your host and not this code.
A proof compares two files. Whether the sandbox then holds the line depends on
where it runs: behind an egress proxy that intercepts TLS, for example,
OpenShell sees no requests, and method and path limits are not enforced. The
check sends a read, a write, a request to another host and a request from
another program, and looks for OpenShell's own decision on each.

**5. Start the services**, each in its own terminal and left running:

```sh
make dispatcher    # ../openshell's poller and on-work.sh, with dispatcher/hook.sh deciding each session's policy
make reviewer      # decides every proposal: proof first, then the review mode
make audit         # collects every sandbox's allowed decisions (the evidence promote and shrink use) and its denied ones
```

**6. Run the demo.** It creates two sessions with your own credentials (`ant
auth login`, or `ANTHROPIC_API_KEY`), as `../openshell` does.

```sh
make demo
```

1. The first session's agent is blocked on `example.com`, proposes a
   read-only rule for curl, and the reviewer approves it: inside the ceiling.
   It is then blocked on `api.github.com`, proposes a rule, and the reviewer
   rejects it with the prover's counterexample as the reason: outside the
   ceiling. The agent reports the refusal. The reviewer's terminal shows one
   line for each, ending `approved (within_ceiling)` and
   `rejected (outside_ceiling)`.
2. `agentpolicy promote` prints the example.com grant as a diff of the
   profile's `policy.yaml`, because the session used it. The script then
   applies it, standing in for the person who would read it.
3. The second session reads example.com with no proposal at all.
4. `agentpolicy shrink` shows which starting grants would be removed for
   disuse. With too little evidence for its window it refuses: missing
   evidence is not evidence of disuse.

`make status` and `state/ledger.jsonl` show every decision, grant, promotion,
shrink and stop. `state/denied/` holds the connections OpenShell refused, up
to 5 MB a session.

**To clean up**, stop the three services with Ctrl-C, then:

```sh
openshell sandbox list --selector app=openshell-policy --names | while read -r name; do openshell sandbox delete "$name"; done
rm -rf state/demo state/ocsf state/denied state/audit state/ledger.jsonl state/environments.yaml
```

The agents and environments `make apply` created stay in your workspace until
you archive them in the Console.

The sandbox is the control this demo shows. The demo agent leaves `bash` on
the toolset's default `always_allow` and its sessions have no budget. For your
own agents, set both as the
[security guide](https://platform.claude.com/docs/en/managed-agents/secure-deployment)
describes. Tool calls are not recorded here: they are in the session's own
event stream, which joins to these files by session id.

## Your own agents

The demo never changes the tracked `policy/` tree: `make keys` copies it to
`state/demo/`, and every `make` target uses that copy while it exists.
**Remove `state/demo/` before you start on your own profiles.** `make check`
and `make sign` say when they are reading the copy, and fail if `policy/` has
changed since it was made. `agentpolicy status` prints the policy directory
and ledger it used.

### Set up a profile

1. **Make a signing key**, on the policy owner's machine and not on the
   sandbox host: `agentpolicy ceiling keygen --key <file> --identity
   <you@corp>`. It prints the entry to add to `policy/signers.yaml`.
2. **Create the profile**: `policy/profiles/<name>/ceiling.yaml`, `task.md`
   with one paragraph on what the agent does (the Claude reviewer reads it),
   and an empty `policy.yaml` (`network_policies: {}`). See
   [Writing a ceiling](#writing-a-ceiling).
3. **Sign it, then check it**: `make sign PROFILE=<name> KEY=<file>
   SIGNER=<you@corp>`, then `make check`, after every edit.
4. **Give it an environment.** Each kind of agent runs in a self-hosted
   environment of its own, and the operator maps that environment to the
   profile on the sandbox host: `agentpolicy environment set <env_id>
   <name>`. An environment nobody mapped gets no worker. Whoever creates a
   session chooses its environment, and so its profile, so list the agents a
   profile admits (`profiles.<name>.agents` in `agentpolicy.yaml`). Nothing
   in a session's or an agent's metadata is read.
5. **Turn the agent's `web_fetch` and `web_search` off**, and give it no MCP
   servers. They run on Anthropic's side, outside any sandbox policy. The
   dispatcher reads the agent as this session resolved it, overrides included,
   and refuses the session if any is on. `profiles.<name>.outside_routes:
   true` accepts them, and with them a way out that the ceiling does not
   govern.
6. **Protect the trust root.** Have the policy owner own `policy/`,
   `agentpolicy.yaml` and the directories above them, run the services as an
   account of its own that can write only `state/`, and set
   `protect_signers: true`. They then refuse to run if that account could edit
   or replace `signers.yaml`. `promote` and `shrink` with `--apply`, `check` and
   `ceiling` are for a person who can write `policy/`.

### Discover

Do this in staging, on tasks you chose, with nothing in reach that you would
mind the agent touching.

1. Set `profiles.<name>.proposals: true` and start all three services.
2. Run the agent on real tasks. Each rule it asks for is decided at once; see
   [Review modes](#review-modes).
3. `agentpolicy promote --profile <name>` prints the grants that sessions were
   given and then used, as a diff of `policy.yaml`, proved inside the ceiling.
   **Read it.** It changes what every later session of this kind of agent
   starts with, on the word of the sessions that asked. `--apply` works the
   plan out again and writes it, so read `git diff` before you commit.
4. `agentpolicy shrink --profile <name>` prints the starting grants no session
   used in the window (14 days by default), the same way. It refuses when the
   evidence has holes. A rule used less often than the window, such as a
   monthly job's, looks unused: keep it by not applying that part.
5. Repeat until promote has nothing to add.

Neither command belongs on a schedule with `--apply`. Run them by hand or have
a job open a pull request with the diff.

### Freeze

Commit `policy.yaml`. Set `proposals: false` (the default) and restart the
reviewer, which reads `agentpolicy.yaml` only when it starts. Narrow the ceiling
to what Discover showed the agent needs, with room only for what you expect it
to need next, and sign it again. A ceiling much wider than the starting policy
buys nothing in Run, where nothing can grow into it.

### Run

- **CI** runs `agentpolicy check` on every change to `policy/`, with the real
  prover on `PATH`. `.github/workflows` in this repository installs it pinned
  by checksum.
- **The dispatcher** proves each sandbox before its worker starts, as above.
- **The audit collector** keeps running. Its records are your evidence of what
  the agent did reach.
- **The reviewer** is optional. Without it a proposal waits unanswered, since
  the gateway is set never to approve by itself. With it the agent is told no
  at once, and the circuit breaker works.
- **Shrink** is a report: run it without `--apply` and let a person decide.
- When the agent needs more, that is a change to `policy.yaml` in a pull
  request, or a return to Discover in staging.

A change to a ceiling or a starting policy reaches new sandboxes only. A
sandbox that already exists keeps its rules, and is checked against the
ceiling, not the new starting policy, at its session's next work item. After
you narrow either, stop the sessions that were already running.

## Writing a ceiling

Write it the way the prover can compare it: exact binaries, exact hosts,
`protocol: rest` with `enforcement: enforce`, and explicit methods and paths
wherever the host serves more than you need.

- **Every host you allow is a way out.** `access: read-only` means the methods
  GET, HEAD and OPTIONS on every path. It does not mean nothing leaves: a
  query string, a header or a GET body carries data to whoever runs the host.
- **A host is not a tenant.** Allowing `github.com` or an object store allows
  every account on it, including one the attacker owns, reached with
  credentials the attacker supplies in the prompt. Pin the paths to your
  organization (`/repos/<org>/**`), and allow write methods on a shared host
  only under such a path.
- **A rule covers the programs it lists and every program they start.** Never
  list a shell or an interpreter unless the task is that program. List only
  binaries under read-only paths, never `/workspace` or `/tmp`: a binary there
  is whatever the agent puts there.
- **A WebSocket upgrade ends inspection.** Once a server answers 101, OpenShell
  relays bytes both ways with no further checks. Do not allow a host that
  offers one unless you accept that.
- **Deny rules belong in the ceiling only.** Give each a method and a path;
  every proof against a ceiling that has one without both fails. In a proposal or a starting grant they are
  left out of the proof, so the rule has to fit the ceiling on its allows
  alone.

## What a proof says

A policy that proves inside its ceiling allows no binary, host, port, method
or path that the ceiling does not allow, for the rule shapes the prover
models. With OpenShell 0.1.2:

| Rule shape | The prover's answer | What agentpolicy does |
|---|---|---|
| `protocol: rest`, `enforcement: enforce`, an `access` preset or `rules` with method and path | Decides it | Follows it |
| No protocol, or `protocol: tcp` (host, port and binary only) | Decides it | Follows it. Inside a REST ceiling rule it exceeds. |
| `deny_rules` in a proposal or a grant | Subtracts them, including one with no path, which OpenShell does not enforce | Drops them before the proof |
| `enforcement: audit` or none, `tls: skip` | `unsupported` | Leaves it for a person |
| `allowed_ips` | Passes it | Leaves it for a person |
| A path with a wildcard in the middle (`/repos/*/x/**` against a wildcard ceiling) | May time out | Tries again, then leaves it for a person |
| Rules on query parameters; GraphQL, MCP, JSON-RPC options | `unsupported`, or not translated | Leaves it for a person |
| An exact host under a wildcard-host ceiling rule | `exceeds_boundary` | Rejects it. Use exact hosts in ceilings. |
| `credential_binding` | Not checked here | Not used. See [ARCHITECTURE.md](ARCHITECTURE.md#credential-injection). |

A proof says nothing about query strings, headers, bodies, or traffic after an
upgrade, and nothing about what the agent did with a request that was allowed.
It compares two files, so it is worth as much as the distance between their
authors: a ceiling written by the person who writes the policy, or equal to
it, proves nothing. `tests/test_real_prover.py` pins the prover's answers
above, and CI runs it.

## Review modes

Choose in `agentpolicy.yaml`. This matters only where proposals are on.

| `review.mode` | What happens to a proposal inside the ceiling |
|---|---|
| `manual` | Recorded as "recommend approve" and left for a person (`openshell rule approve`). |
| `auto-within-ceiling` | Approved, if OpenShell's own risk check also reports no findings. The demo's mode. |
| `claude` | Sent to the reviewer agent, which may approve, reject with guidance, or escalate. Experimental: see [Status](#status). |

In every mode a proposal outside the ceiling is rejected, one the prover cannot
decide is left for a person, and so is one that reaches a host and port in the
profile's `revoked.txt`. No mode lets anything past the ceiling.

OpenShell also files a draft of its own for every connection it denies: that
host and port, any method and path, named `allow_<host>_<port>`. Nobody asked
for those, so the reviewer rejects each without a proof (`gateway_draft`) and
does not count it against the session.

The ceiling binds agentpolicy, not the gateway. A rule a person approves at
the gateway (`openshell rule approve`) or writes there (`openshell policy
update`) is live at once, with no proof. An approved proposal is recorded as a
grant. A policy update is not recorded at all. Either is checked only at the
session's next work item: a sandbox outside the ceiling is replaced, and one
the prover cannot decide gets no worker until a person removes the rule or
deletes the sandbox. So approve only what the ledger shows proved inside
(`recommend_approve`), and reject the rest with a reason the agent can act on.

## Taking access back

Delete the rule from the profile's `policy.yaml`, and add its destination to
`revoked.txt` beside it, one `host:port` a line. Both files are in git, so this
is a commit like any other.

The ledger keeps every grant ever approved, so without that line the next
promote would offer the rule again. With it, promote skips every grant that
reaches the destination, however the rule is named or spelled, and a proposal
for it waits for a person instead of being approved. Shrink adds a line, in the
same diff, for each destination it removes. Delete a line to give one back.
The match is on the text, so a wildcard host does not match the hosts under it.
When two rules reach one destination and only one of them goes, nothing is
listed, and promote will offer that rule again.

Sandboxes that already hold the rule keep it until they are replaced, so stop
those sessions.

## Stopping

`agentpolicy stop` is the kill switch. It covers one session, every session
of an agent, of an environment or of a profile, or everything, on this
sandbox host:

```sh
agentpolicy stop --session sesn_... --reason "what happened"     # or --agent, --environment, --profile, --all
agentpolicy status                                              # lists the stops in force, and the ledger they are in
agentpolicy resume --session sesn_...                           # lifts the stop with that scope
```

A stop is recorded in the ledger first, and from then on the hook refuses
every session it covers and the reviewer decides nothing for them. Then each
running sandbox it covers has its network rules replaced with none and is
stopped, which ends the worker and every tool it runs, and each covered
session is sent `user.interrupt` so its turn ends. In testing the network
rules took about eight seconds to take effect. A sandbox whose agent has
killed its main process is deleted instead, because OpenShell 0.1.2 reports
stopping one as a success and leaves it running.

If a step fails the others still run, and the command says which failed and
exits non-zero. That includes the record: with a full disk the sandboxes are
still halted, and the command says in capitals that the dispatcher will go on
serving those sessions until the stop can be written.

**The stop is a line in one file.** `stop` prints the ledger it wrote to. A
dispatcher reading another ledger does not see the stop, so run the command
with the dispatcher's own config: with none it refuses to run. See
[Limits](#limits) for what that file must never have done to it.

The stop halts the sandboxes this host's gateway lists. Pollers on other
hosts, and the same agent's sessions on cloud environments, are untouched, and
nothing is held at the Managed Agents API. For that side (interrupt, archive,
rotate the environment key) see
[Set limits and a way to stop](https://platform.claude.com/docs/en/managed-agents/secure-deployment#set-limits-and-a-way-to-stop)
in the security guide.

`resume` lifts only the stop with the same scope: after `stop --all`,
`resume --session` leaves that session stopped. A sandbox a stop locked down
is replaced, not reused, when its session next runs. The new one starts from
the profile's current starting policy, so the rules that session was granted
and everything in its `/workspace` are gone. While a stop stands, promote
leaves the covered sessions' grants out.

While a stop stands, each covered session the API hands out is refused, and
its work item is left `stopping`, which nothing releases on its own. `resume`
force-stops those items and sends each such session `user.interrupt`, which
closes the tool call it was refused on, so its next message runs. `stop`,
`resume` and the reviewer use your own credentials for these calls (`ant
auth login` or `ANTHROPIC_API_KEY`); without any, they do the rest and say
what they could not do.

The reviewer stops sessions itself through the same path. `breaker` in
`agentpolicy.yaml` stops a session after `max_rejections` rejected proposals
(3 by default), counted since it was last resumed, or at the first decision with a code
in `stop_on` (`suspicious`, the Claude reviewer's code, by default). With
proposals off every proposal is a rejection, so an agent that keeps asking is
stopped at the third.

## Limits

- **One sandbox host.** The ledger, the stops, the evidence and the starting
  grants are files on one machine. A second host has its own, so a stop on one
  does not reach the other, and shrink on one would remove a rule used only on
  the other. Running a fleet needs those four in a shared store, which is not
  built here.
- **The ledger is state, not a log.** Stops, breaker counts, which proposals
  were decided and which sandboxes agentpolicy made are all read from
  `state/ledger.jsonl`. Never rotate, truncate or move it: a stop in the part
  that went is no longer in force, and every sandbox whose record went is
  replaced at its next work item, `/workspace` included. Back it up and ship
  copies of it. `agentpolicy status` prints which file is in use.
- **One account.** The dispatcher, the reviewer, the collector, `stop` and
  `resume` all write `state/`, so they run as the same account on the sandbox
  host.
- **Stopped sandboxes pile up.** Nothing deletes a finished session's sandbox,
  because its `/workspace` is the session's way to carry on. The collector
  holds one stream open per sandbox that exists, and the gateway allows 1,024
  on a connection. Delete old ones on a schedule, with the command under
  [Run the demo](#run-the-demo) and a filter of your own.
- **Restarting the gateway interrupts everything.** OpenShell's Docker driver
  stops every sandbox when the gateway shuts down, and each worker's
  connection runs through the gateway. It also loses the log buffer, which the collector
  records as a gap for every sandbox it was following, and shrink refuses any
  window with a gap in it. To upgrade: stop the poller, wait for workers to go
  idle, restart, then run `make test`, `make check` and `make enforce-check`
  before starting the poller again.
- **An agent can hold shrink up.** It can kill its sandbox's main process. The
  sandbox is replaced under the same name, the collector cannot resume the old
  stream, and that is a gap, so shrink refuses the profile for a window. Shrink
  fails toward keeping access. `--allow-missing-evidence` overrides it once you
  have read the `audit_gap` entries.
- **Shrink does not know how old a grant is.** It counts uses by rule name over
  the window, so a grant added yesterday, or one promote renamed because the
  name was taken, shows no use and is listed for removal. Read the diff.
- **A full disk.** `stop` still halts what is running, and says the stop is not
  recorded. Everything else that writes the ledger fails. Keep `state/` on a
  volume of its own and watch it: allowed requests are logged without a cap,
  and each connection to a host no rule names adds a `gateway_draft` line to
  the ledger without counting toward the breaker.
- **No alerts.** A proposal left for a person, a tripped breaker and a dead
  collector are each a line in a file or a terminal. Watch the ledger for
  `"action": "escalate"`, `"kind": "stop"` and `"kind": "audit_gap"`, and run
  the services under a supervisor that restarts them.

## How it works

| | |
|---|---|
| `start.sh` | Host. `make dispatcher` runs it: `../openshell`'s poller and `on-work.sh`, with `ON_WORK_HOOK=dispatcher/hook.sh`. |
| `dispatcher/hook.sh` | The hook: `admit` (the profile from the operator's map, the agent read with the session's token and checked against the profile, refused if stopped), `policy` (a starting policy proved inside the signed ceiling), `verify` (a new or existing sandbox's live policy proved), `start` (a last check for a stop). |
| `policy/base.yaml` | What every sandbox needs: `../openshell/policy.yaml`, with the API's host and port as placeholders. A test holds the two to the same grants. |
| `policy/profiles/<p>/` | One kind of agent: `ceiling.yaml` (person-owned, signed), `policy.yaml` (starting grants), `task.md`. |
| `policy/signers.yaml` | Public keys trusted to sign ceilings. |
| `agents/`, `environments/` | The demo agent, the reviewer, and their environments, as files for `ant apply`. |
| `agentpolicy.yaml` | Settings: review mode, breaker, what each profile admits, the API address sandboxes reach. |
| `src/agentpolicy/` | Prepare, grow, promote, shrink, stop; the environment map; the audit collector; the prover and gateway clients; the Claude reviewer. |
| `scripts/enforce-check.sh` | `make enforce-check`. |
| `sandbox/` | The image: `../openshell`'s, plus OpenShell's policy advisor guide (`openshell-skills/`, Apache-2.0), which tells the agent how to propose a rule. |
| `stack/` | Gateway settings, and the containerized gateway (`stack/openshell/`). |
| `ops/`, `scripts/ops` | The ops container, and running commands in it. |
| `examples/hello-world/` | The demo. |
| `third_party/openshell/proto/` | OpenShell's protocol files (Apache-2.0), from which the gRPC client is generated. |
| `tests/` | Tests, with a stand-in prover; they run `../openshell/on-work.sh` for real against a stub `openshell`. `test_real_prover.py` runs the shipped base and demo ceiling through the real `openshell-prover` when it is on `PATH`, as it is in CI. |

The three credentials of `../openshell` keep their places. Your own
credential creates agents and sessions. The dispatcher never holds it:
`start.sh` drops it. The reviewer service needs it only in `claude` mode or to
send interrupts, as do `stop` and `resume`. The environment key stays on the
sandbox host. Each sandbox's workload holds only its own session's token. Two
more come with this directory. The gateway's client certificate lets its
holder manage every sandbox and approve any rule. The dispatcher, the reviewer
and the collector use it, and with gateway TLS on, the Docker driver hands the
same certificate to each sandbox's supervisor container, which the agent's
container cannot read. The policy owner's signing key belongs on no machine
that runs agents.

## What this does not cover

- **MCP servers, web search and web fetch.** They run on Anthropic's side, so
  neither the ceiling nor your firewall limits them. A session that has any is
  refused at admission unless the profile accepts them. That check runs when a
  work item arrives, on the agent as the API reports it.
- **What an agent does with access it holds.** See
  [What a proof says](#what-a-proof-says).
- **Sub-agents.** They share the session's sandbox, token and policy, and a
  session that coordinates other agents is refused like one with web tools.
  Give different trust levels different sessions and profiles.
- **The session token.** The agent can read its own, and its shell can use the
  base policy's six routes. Four are pinned to its own session. The two work
  item routes are pinned only to the environment, so there it is the API's
  check of the token, not the policy, that keeps it from another session. One
  of the four posts events to its own session. The public docs do not say
  which event types a session token may post, so do not count a permission
  policy such as `always_ask` on a tool that runs in the sandbox as a control
  independent of the agent.
- **Credentials.** OpenShell's credential injection is not wired up here. Do
  not put secrets in a sandbox's environment or files.

[`ARCHITECTURE.md`](ARCHITECTURE.md#what-this-does-not-cover) has the rest. The
security guide's
[Choose where the agent runs](https://platform.claude.com/docs/en/managed-agents/secure-deployment#choose-where-the-agent-runs)
covers what a self-hosted sandbox does and does not contain.

## Status

A reference implementation: a complete, working shape, written to be read and
adapted. What has run, and where:

| | Apple-silicon Mac, Docker Desktop, containerized gateway | Linux x86-64, Docker Engine, same gateway, CLI on the host |
|---|---|---|
| The demo, against the Managed Agents API, in `auto-within-ceiling` mode | An earlier version of this code | Not run |
| The kill switch on live sessions (stop mid-tool, a refused message, resume, the session carrying on in a new sandbox) | An earlier version of this code | Not run |
| Real sandboxes driven with `openshell sandbox exec`: proposals approved, rejected and left for a person with the real prover, the collector, `verify-sandbox`, `stop` | | This code |
| `make enforce-check` | Not run | This code, over plain HTTP: that network intercepts TLS |
| Admission's check of web tools, MCP servers and listed agents | Not run | Tests only, against the SDK's types for the session's resolved agent |
| `claude` review mode | Not run | Tests only. Treat it as experimental. |

The Run phase uses the same dispatcher, prover and collector as the demo, with
`proposals: false`. No demo walks through it yet.

Tested with OpenShell 0.1.2 and its Docker driver only. Before moving to
another release, see "Restarting the gateway" under [Limits](#limits). What is
still open is in [`ARCHITECTURE.md`](ARCHITECTURE.md#open-points).

## Appendix: running the gateway in Docker

Where OpenShell's host binaries cannot run (macOS with endpoint protection, for
example), run them in Docker. This replaces "run `../openshell` first": you
need Docker, `jq`, Python and the `ant` CLI on the machine, and nothing of
OpenShell's.
The gateway runs as a container on Docker Desktop's host network (the Linux
VM's, where OpenShell's per-sandbox supervisors dial it), with mTLS required.
Nothing on the Mac itself can reach that network, so the OpenShell CLI, the
prover, `ant` and agentpolicy run in an ops container beside it:
`scripts/ops <command>` runs any command there, with this repository mounted
at its own path.

```sh
make dev                       # on the machine itself: .venv for `make apply`, and the gRPC client, which the container shares
make ops-image                 # hash-locked packages; PIP_CONF names a mirror, PUBLIC_INDEX=1 allows PyPI
make pki                       # the gateway's CA, server and client certificates, JWT key
make gateway-up                # the gateway on 127.0.0.1:18670 (VM loopback); registers it for the CLI
scripts/ops openshell status   # "Connected", "Authenticated (mTLS transport)"
```

Then put `scripts/ops` in front of each `make` target above, except `make
dev`, `make apply`, `make image`, `make pki` and `make gateway-up`, which run on
the machine itself.
Commands that call the API with your credentials need your `ant auth login`
profile in the container: `OPS_ANT_PROFILE=1` mounts it read-only. Never set
it for the dispatcher, which runs on the environment key alone.

```sh
scripts/ops make test
scripts/ops make keys && scripts/ops make check
make apply && make image
scripts/ops make openshell-settings
scripts/ops make enforce-check
scripts/ops make dispatcher                 # and, in their own terminals:
OPS_ANT_PROFILE=1 scripts/ops make reviewer
scripts/ops make audit
OPS_ANT_PROFILE=1 scripts/ops make demo
```

The ops container runs as root, which `protect_signers: true` refuses. It is
for a laptop, not for production.

On Linux the host shares the gateway's network, so the ops container is
optional: with the OpenShell CLI and prover installed on the host, run the
`make` targets as they are, with
`XDG_CONFIG_HOME=$PWD/state/openshell/config` so the CLI and agentpolicy find
the gateway `make gateway-up` registered.

This gateway uses its own ports, compose project and sandbox label, so it can
run beside another OpenShell gateway on the same Docker engine.

## License

MIT, as the rest of this repository; see [`LICENSE`](../../../LICENSE). It
includes NVIDIA OpenShell material that stays under the Apache License 2.0;
see [`NOTICE`](NOTICE).
