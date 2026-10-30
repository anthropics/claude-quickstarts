# OpenShell issues found building this project

What running this reference implementation against NVIDIA OpenShell turned up, for
OpenShell's maintainers to confirm and fix. Each entry says what was run, what happened,
what was expected, and what this repository does about it in the meantime; when one is
fixed upstream, the workaround it names can go.

All were seen on **OpenShell 0.1.2** (gateway, supervisor and sandbox images `:0.1.2`,
docker compute driver, gateway in a container with mTLS) unless marked otherwise, on
Docker Desktop 29.8 / Apple silicon, with the configuration in `stack/openshell/`.

| # | Issue | Impact here |
|---|---|---|
| 1 | [OCSF JSON is never written under the docker driver](#1-ocsf-json-is-never-written-under-the-docker-driver) | No structured audit trail; evidence parsed from text instead |
| 2 | [The log stream carries OCSF events as text only](#2-the-log-stream-carries-ocsf-events-as-text-only) | Evidence must be parsed from agent-influenced text |
| 3 | [The policy advisor guide never reaches the workload](#3-the-policy-advisor-guide-never-reaches-the-workload) | Agents cannot file proposals without it |
| 4 | [Draft policies carry both `port` and `ports`, which the prover rejects](#4-draft-policies-carry-both-port-and-ports-which-the-prover-rejects) | Every proposal was unprovable |
| 5 | [`config preflight` passes a docker-driver TLS config that cannot start](#5-config-preflight-passes-a-docker-driver-tls-config-that-cannot-start) | Gateway crash-loops after a clean preflight |
| 6 | [A crash-looping gateway leaves a container that blocks its next start](#6-a-crash-looping-gateway-leaves-a-container-that-blocks-its-next-start) | Manual cleanup needed |
| 7 | [Denied connections are refused, not answered with the documented 403](#7-denied-connections-are-refused-not-answered-with-the-documented-403) | Agents get no structured reason |
| 8 | [Docker Desktop needs the gateway on the VM's host network; undocumented](#8-docker-desktop-needs-the-gateway-on-the-vms-host-network-undocumented) | Setup trap on macOS |
| — | [Not an issue: binary rules extend to child processes](#not-an-issue-binary-rules-extend-to-child-processes) | — |
| — | [Not yet re-checked on 0.1.2: sandbox JWT expiry](#not-yet-re-checked-on-012-sandbox-jwt-expiry) | — |

## 1. OCSF JSON is never written under the docker driver

**Run:** set `ocsf_json_enabled=true` globally (`openshell settings set --global --key
ocsf_json_enabled --value true`), create a sandbox, make a network request from it.

**Happened:** the supervisor logs `OCSF JSONL logging toggled`, but no
`/var/log/openshell-ocsf.*.log` exists in either container. The supervisor container
runs as `65534:65534` with a read-only root filesystem, and its `/var/log` is empty and
root-owned; the workload container's `/var/log` has no OpenShell files. No error is
logged.

**Expected:** the JSONL file the OCSF JSON export docs describe ("written to
`/var/log/openshell-ocsf.YYYY-MM-DD.log` inside the sandbox"), on a writable path, or a
startup error saying export is unavailable.

**Here:** `agentpolicy collect-audit` takes evidence from the gateway's log stream instead
(ARCHITECTURE.md, Evidence).

## 2. The log stream carries OCSF events as text only

**Run:** `WatchSandbox` / `GetSandboxLogs` for a sandbox with network activity.

**Happened:** OCSF events arrive as `SandboxLogLine`s with `level: "OCSF"` and the
shorthand in `message`, e.g. `NET:OPEN [INFO] ALLOWED /usr/bin/curl(0) ->
example.com:443 [policy:r engine:opa]`. The `fields` map, documented as "structured
key-value fields from the tracing event", is empty on every line.

**Expected:** the event's structured data (ideally its full OCSF JSON) in `fields` or a
dedicated field. The shorthand interleaves text the sandboxed program chooses (binary
path, host, request path) with the supervisor's verdict, so any consumer that turns it
into evidence has to defend against injected text. This repository's parser does
(`src/agentpolicy/shorthand.py`), but structured fields would remove the need.

## 3. The policy advisor guide never reaches the workload

**Run:** create a sandbox from a non-root image (here, user 1000) and look for
`/etc/openshell/skills/policy_advisor.md` from inside it.

**Happened:** it does not exist in the workload container, nor in the supervisor
container. `install_static_skills()` writes under `/` of whichever process runs it;
under the docker driver the workload runs non-root with no capabilities and cannot
create `/etc/openshell`, and no error is logged. Agents told to read the guide found `policy.local` but would
not guess its API, so filed no proposals.

**Expected:** the guide (and `AGENTS.md`) present in the workload, e.g. staged into the
workload's filesystem the way the sandbox binary is.

**Here:** the sandbox image copies 0.1.2's guide in (`sandbox/openshell-skills/`).

## 4. Draft policies carry both `port` and `ports`, which the prover rejects

**Run:** `GetDraftPolicy` for a sandbox with a pending proposal, then
`openshell-prover check` of its `candidate_effective_policy` (converted to YAML) against
a boundary.

**Happened:** every endpoint in the gateway's policies, including the proposal's rule,
has both `port: 443` and `ports: [443]`. The prover answers `unsupported`:
`candidate policy rule '<name>' has no unambiguous host and port`. Every proposal was
therefore unprovable.

**Expected:** the gateway and prover to agree on one form: the gateway emitting a single
form, or the prover accepting `port` equal to the single element of `ports`.

**Here:** `src/agentpolicy/convert.py` emits one form, and refuses a rule whose two fields
disagree.

## 5. `config preflight` passes a docker-driver TLS config that cannot start

**Run:** a v2 gateway config with `compute_driver = "docker"`, TLS on
(`OPENSHELL_TLS_CERT`/`_KEY`/`_CLIENT_CA`) and `gateway_jwt`, but no `guest_tls_*`;
`openshell-gateway --config … config preflight`, then start the gateway.

**Happened:** preflight exits 0. Startup fails with `gateway TLS requires guest_tls_ca,
guest_tls_cert, and guest_tls_key in [openshell.gateway] when using the docker compute
driver`, and the container restarts in a loop. The docker deployment example
(`deploy/docker/gateway.toml`) does not mention these keys.

**Expected:** preflight to report the missing keys, and the docker example to show them
for a TLS gateway.

**Here:** `stack/openshell/gateway.toml` sets them.

## 6. A crash-looping gateway leaves a container that blocks its next start

**Run:** let the gateway fail at startup a few times (issue 5), fix the config, restart.

**Happened:** startup fails with `failed to create extractor container …: Conflict. The
container name "/openshell-supervisor-extract-1-0" is already in use`. A stopped
extractor container from an earlier attempt is left behind and must be removed by hand.

**Expected:** the extractor container removed on failure, or reused or replaced on the
next start.

## 7. Denied connections are refused, not answered with the documented 403

**Run:** from a sandbox, `curl https://example.com/` with no rule allowing it.

**Happened:** `curl: (7) Failed to connect to example.com port 443` immediately; the
supervisor logs `NET:OPEN [MED] DENIED … [reason:transparent_tcp_policy_denied]`. The
logging docs describe the HTTP CONNECT proxy answering a denial with an HTTP error and a
JSON body, which a client or agent can read for the reason.

**Expected:** either that structured answer, or docs saying that under the docker
driver's transparent mode a denial is a refused connection and the reason is available
only from `policy.local` (`/v1/denials`).

## 8. Docker Desktop needs the gateway on the VM's host network; undocumented

**Run:** the docker driver on Docker Desktop for macOS, with the gateway published on a
host port as in `deploy/docker/`.

**Happened:** each sandbox's supervisor container uses host networking and dials the
gateway at `127.0.0.1:<port>`, which on Docker Desktop is the Linux VM's loopback, not
the Mac's. A gateway that is reachable from the Mac is not reachable from the
supervisors unless it, too, runs on the VM's host network, which the Mac then cannot
reach.

**Expected:** the docker deployment docs to cover Docker Desktop: run the gateway with
`network_mode: host` and reach it from containers on the same network.

**Here:** the gateway runs with host networking (`stack/openshell/docker-compose.yml`),
and the CLI, prover and agentpolicy run in an ops container beside it (`scripts/ops`).

## Not an issue: binary rules extend to child processes

A process not in a rule's `binaries` can use the rule's endpoints if any ancestor is
listed. That held on **0.0.116** and holds on 0.1.2. An earlier version of this file
called it resolved in 0.1.2. That was a mistake in the test: `bash -c 'curl …'` execs a
lone command rather than forking, so the curl it ran had no bash ancestor.

Checked on 0.1.2 (Linux x86-64, Docker Engine 29.9, the supervisor logging
`require_binary_identity:true`) with a rule allowing only `/usr/bin/bash` to reach a host:

| Run | Decision |
|---|---|
| `bash -c 'exec 3<>/dev/tcp/HOST/443'` | `ALLOWED /usr/bin/bash` |
| `bash -c 'curl …; true'` (curl is a child of bash) | `ALLOWED /usr/bin/curl … [policy:bash_only]` |
| `bash -c 'sh -c "curl …; true"; true'` (a grandchild) | allowed |
| `curl …` | `DENIED /usr/bin/curl` |
| `sh -c 'curl …; true'` | `DENIED /usr/bin/curl` |
| `bash -c 'curl …'`, `bash -c 'exec curl …'` (bash replaced by curl) | `DENIED /usr/bin/curl` |

Containment proofs are unaffected, since both policies in a proof are read the same way.
What it changes is how to write a rule: listing a shell or an interpreter covers
everything it starts.

## Not yet re-checked on 0.1.2: sandbox JWT expiry

On **0.0.116**, with `gateway_jwt.ttl_secs` set, a sandbox older than the TTL lost its
supervisor-to-gateway channel (`ExpiredSignature`): no log or denial flushes, no policy
refresh, `sandbox exec` failing. Nothing renewed the token. This project leaves
`ttl_secs` unset; long-lived sandboxes are the shape that would hit it.
