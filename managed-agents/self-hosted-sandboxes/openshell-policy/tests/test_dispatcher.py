"""../openshell/on-work.sh with dispatcher/hook.sh, run for real against a stub openshell and a stub server."""

from __future__ import annotations

import base64
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from conftest import AGENT, ENV, ROOT, SESSION

QUICKSTART = ROOT.parent / "openshell"
WORK = "work_01ABCdef"
TOKEN = "test-session-token-xyz"
ENV_KEY = "test-ENVIRONMENT-KEY-must-not-leak"

OPENSHELL_STUB = r"""#!/usr/bin/env bash
# Records every call; keeps one sandbox's phase in a file.
state="$STUB_DIR/phase"
printf '%s\n' "$*" >> "$STUB_DIR/calls"
env | grep -c ENVIRONMENT_KEY >> "$STUB_DIR/envkey-seen" || true
case "$1 $2" in
  "sandbox get")
    [ -s "$state" ] || exit 1
    if printf '%s' "$*" | grep -q -- --policy-only; then cat "$STUB_DIR/policy.yaml"; exit 0; fi
    printf '{"phase":"%s"}\n' "$(cat "$state")" ;;
  "sandbox create")
    while [ $# -gt 0 ]; do [ "$1" = --policy ] && cp "$2" "$STUB_DIR/policy.yaml"; shift; done
    echo Ready > "$state"
    if [ -x "$STUB_DIR/on-create" ]; then "$STUB_DIR/on-create"; fi ;;
  "sandbox exec")
    if printf '%s' "$*" | grep -q 'ant beta:worker run'; then cat > "$STUB_DIR/stdin"; exit 0; fi
    if printf '%s' "$*" | grep -q 'openshell-ocsf'; then
      printf '%s\n' '{"class_uid":4001,"action":"Allowed","time":1,"firewall_rule":{"name":"claude_managed_agents"},"metadata":{"uid":"u1"}}'
      exit 0
    fi
    exit 1 ;;
  "sandbox stop") echo Stopped > "$state" ;;
  "sandbox start") echo Ready > "$state" ;;
  "sandbox delete") : > "$state" ;;
  *) exit 0 ;;
esac
"""


class SessionHandler(http.server.BaseHTTPRequestHandler):
    agent_id = AGENT
    extra: dict = {}

    def do_GET(self):  # noqa: N802
        ok = self.path == f"/v1/sessions/{SESSION}" and self.headers.get("authorization") == f"Bearer {TOKEN}"
        # The metadata names another profile; the dispatcher must not care.
        body = json.dumps({"id": SESSION, "metadata": {"policy_profile": "wide-open"},
                           "agent": {"id": self.agent_id, "version": 7, "metadata": {"policy_profile": "wide-open"}, **self.extra}})
        self.send_response(200 if ok else 401)
        self.end_headers()
        self.wfile.write(body.encode() if ok else b"{}")

    def log_message(self, *a):
        pass


@pytest.fixture
def api_server():
    srv = http.server.HTTPServer(("127.0.0.1", 0), SessionHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture
def harness(repo: Path, tmp_path: Path, fake_prover_bin: str):
    if not shutil.which("jq"):
        pytest.skip("jq not installed")
    stub = tmp_path / "stub"
    bindir = tmp_path / "bin"
    stub.mkdir()
    bindir.mkdir()
    (bindir / "openshell").write_text(OPENSHELL_STUB)
    (bindir / "agentpolicy").write_text(f"#!/usr/bin/env bash\nexec {sys.executable} -m agentpolicy.cli \"$@\"\n")
    for f in bindir.iterdir():
        f.chmod(0o755)
    shutil.copytree(ROOT / "dispatcher", repo / "dispatcher")
    map_environment(repo, "hello")
    return repo, stub, bindir, fake_prover_bin


def map_environment(repo: Path, profile: str) -> None:
    """The operator's environment-to-profile map, as `agentpolicy environment set` writes it."""
    path = repo / "state" / "environments.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"environments:\n  {ENV}: {profile}\n")
    path.chmod(0o644)


def work_item() -> str:
    secret = base64.urlsafe_b64encode(json.dumps({"sessions_token": TOKEN, "other": "x"}).encode()).decode()
    return json.dumps({"id": WORK, "secret": secret})


def setting(bindir: Path, env: dict, name: str) -> str:
    """What start.sh reads before it starts the poller."""
    return subprocess.run([str(bindir / "agentpolicy"), "setting", name], capture_output=True, text=True,
                          env=env, check=True).stdout.strip()


def run_on_work(repo, stub, bindir, prover, base_url):
    env = {
        "PATH": f"{bindir}:/usr/bin:/bin",
        "PYTHONPATH": str(ROOT / "src"),
        "STUB_DIR": str(stub),
        "AGENTPOLICY_PROVER": prover,
        "ANTHROPIC_SESSION_ID": SESSION,
        "ANTHROPIC_ENVIRONMENT_ID": ENV,
        "ANTHROPIC_WORK_ID": WORK,
        "ANTHROPIC_ENVIRONMENT_KEY": ENV_KEY,
        "ANTHROPIC_BASE_URL": base_url,
        "AGENTPOLICY_CONFIG": str(repo / "agentpolicy.yaml"),
        "ON_WORK_HOOK": str(repo / "dispatcher" / "hook.sh"),
        "ON_WORK_LOCK_DIR": str(stub),
    }
    if "LD_LIBRARY_PATH" in os.environ:
        env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    env["SANDBOX_APP_LABEL"] = setting(bindir, env, "sandbox_label")
    env["SANDBOX_BASE_URL"] = setting(bindir, env, "sandbox_base_url")
    return subprocess.run(["bash", str(QUICKSTART / "on-work.sh")], input=work_item(),
                          capture_output=True, text=True, env=env, cwd=repo, timeout=120)


def test_on_work_creates_a_proved_sandbox_and_hands_over_only_the_token(harness, api_server):
    repo, stub, bindir, prover = harness
    r = run_on_work(repo, stub, bindir, prover, api_server)
    assert r.returncode == 0, r.stderr
    calls = (stub / "calls").read_text()
    create = next(line for line in calls.splitlines() if line.startswith("sandbox create"))
    for label in ("app=openshell-policy", f"session={SESSION}", f"environment={ENV}", "profile=hello",
                  f"agent={AGENT}", "agent_version=7"):
        assert label in create
    # The sandbox was created from the proved starting policy for this session.
    policy = (stub / "policy.yaml").read_text()
    assert f"/v1/sessions/{SESSION}" in policy and "host.openshell.internal" in policy
    # The worker got this session's token on stdin, and nothing else did.
    sent = base64.urlsafe_b64decode((stub / "stdin").read_text() + "==")
    assert json.loads(sent) == {"sessions_token": TOKEN}
    assert TOKEN not in calls and ENV_KEY not in calls
    assert set((stub / "envkey-seen").read_text().split()) == {"0"}
    assert "ANTHROPIC_BASE_URL=http://host.openshell.internal:8400" in calls
    # The sandbox stopped. Evidence of use is the audit collector's job, so
    # nothing was read out of the sandbox first.
    assert calls.strip().splitlines()[-1].startswith("sandbox stop")
    assert "openshell-ocsf" not in calls
    ledger = [json.loads(x) for x in (repo / "state" / "ledger.jsonl").read_text().splitlines()]
    # The file was proved before the sandbox was made, and what the gateway made of it after.
    assert [e["kind"] for e in ledger[-2:]] == ["dispatch", "reverify"]
    for e in ledger[-2:]:
        assert e["proof"] == "within_boundary" and e["agent_id"] == AGENT and e["agent_version"] == "7"
    # The hook logs which agent, environment and profile the session runs under.
    assert f"[hook] session={SESSION} agent={AGENT}@7 env={ENV} profile=hello" in r.stderr


def test_on_work_refuses_a_session_that_turned_a_web_tool_back_on(harness, api_server, monkeypatch):
    repo, stub, bindir, prover = harness
    monkeypatch.setattr(SessionHandler, "extra", {"tools": [{"type": "agent_toolset_20260401", "configs": []}]})
    r = run_on_work(repo, stub, bindir, prover, api_server)
    assert r.returncode != 0 and "outside its sandbox: web_fetch, web_search" in r.stderr
    assert "sandbox create" not in calls_of(stub)


def test_on_work_refuses_an_agent_the_profile_does_not_list(harness, api_server):
    repo, stub, bindir, prover = harness
    cfg = repo / "agentpolicy.yaml"
    cfg.write_text(cfg.read_text().replace("    proposals: true", "    proposals: true\n    agents: [agent_01Other]"))
    r = run_on_work(repo, stub, bindir, prover, api_server)
    assert r.returncode != 0 and f"does not list agent {AGENT}" in r.stderr
    assert "sandbox create" not in calls_of(stub)


def test_on_work_refuses_without_a_trusted_ceiling(harness, api_server):
    repo, stub, bindir, prover = harness
    (repo / "policy" / "profiles" / "hello" / "ceiling.yaml.sig").unlink()
    r = run_on_work(repo, stub, bindir, prover, api_server)
    assert r.returncode != 0
    assert "sandbox create" not in (stub / "calls").read_text() if (stub / "calls").exists() else True
    assert "not signed" in r.stderr


def calls_of(stub: Path) -> str:
    return (stub / "calls").read_text() if (stub / "calls").exists() else ""


def test_on_work_refuses_unknown_profile(harness, api_server):
    repo, stub, bindir, prover = harness
    map_environment(repo, "no-such-profile")
    r = run_on_work(repo, stub, bindir, prover, api_server)
    assert r.returncode != 0
    assert "sandbox create" not in calls_of(stub)


def test_on_work_refuses_an_environment_the_operator_did_not_map(harness, api_server):
    repo, stub, bindir, prover = harness
    (repo / "state" / "environments.yaml").unlink()
    r = run_on_work(repo, stub, bindir, prover, api_server)
    assert r.returncode != 0 and "no profile for environment" in r.stderr
    assert "sandbox create" not in calls_of(stub)


def test_on_work_refuses_a_group_writable_environment_map(harness, api_server):
    repo, stub, bindir, prover = harness
    (repo / "state" / "environments.yaml").chmod(0o664)
    r = run_on_work(repo, stub, bindir, prover, api_server)
    assert r.returncode != 0 and "writable by its group" in r.stderr
    assert "sandbox create" not in calls_of(stub)


def test_on_work_refuses_a_session_with_no_agent(harness, api_server):
    repo, stub, bindir, prover = harness
    SessionHandler.agent_id = ""
    try:
        r = run_on_work(repo, stub, bindir, prover, api_server)
    finally:
        SessionHandler.agent_id = AGENT
    assert r.returncode != 0
    assert "sandbox create" not in calls_of(stub)


@pytest.mark.parametrize("scope", [["--session", SESSION], ["--agent", AGENT], ["--environment", ENV],
                                   ["--profile", "hello"], ["--all"]])
def test_on_work_runs_no_worker_for_a_stopped_session(harness, api_server, scope):
    repo, stub, bindir, prover = harness
    from agentpolicy import config
    from agentpolicy.stop import Scope
    from agentpolicy.store import Store

    store = Store(config.load(repo / "agentpolicy.yaml"))
    target = Scope(scope[0][2:], scope[1] if len(scope) > 1 else "")
    store.record("stop", scope=target.kind, target=target.value, reason="testing", by="op")
    r = run_on_work(repo, stub, bindir, prover, api_server)
    assert r.returncode != 0 and "testing; refusing" in r.stderr
    calls = calls_of(stub)
    assert "sandbox create" not in calls and "ant beta:worker run" not in calls
    # Lifted, the session runs again.
    store.record("resume", scope=target.kind, target=target.value, by="op")
    assert run_on_work(repo, stub, bindir, prover, api_server).returncode == 0


def test_stopped_sandbox_that_still_fits_is_restarted(harness, api_server):
    repo, stub, bindir, prover = harness
    assert run_on_work(repo, stub, bindir, prover, api_server).returncode == 0
    (stub / "calls").unlink()
    r = run_on_work(repo, stub, bindir, prover, api_server)
    assert r.returncode == 0, r.stderr
    calls = (stub / "calls").read_text()
    assert "sandbox start" in calls and "sandbox create" not in calls and "(restarting)" in r.stderr
    assert "ant beta:worker run" in calls


def test_stopped_sandbox_outside_a_narrowed_ceiling_is_replaced(harness, api_server):
    repo, stub, bindir, prover = harness
    assert run_on_work(repo, stub, bindir, prover, api_server).returncode == 0
    # The sandbox had picked up a grant that the ceiling no longer allows.
    policy = (stub / "policy.yaml").read_text()
    policy += ("  stale:\n    endpoints: [{host: api.github.com, port: 443, protocol: rest, enforcement: enforce,"
               " access: full}]\n    binaries: [{path: /usr/bin/curl}]\n")
    (stub / "policy.yaml").write_text(policy)
    (stub / "calls").unlink()
    r = run_on_work(repo, stub, bindir, prover, api_server)
    assert r.returncode == 0, r.stderr
    calls = (stub / "calls").read_text().splitlines()
    assert any(c.startswith("sandbox delete") for c in calls) and any(c.startswith("sandbox create") for c in calls)
    assert not any(c.startswith("sandbox start") for c in calls)
    assert "api.github.com" not in (stub / "policy.yaml").read_text()


def test_a_locked_down_sandbox_is_replaced_not_reused(harness, api_server):
    repo, stub, bindir, prover = harness
    assert run_on_work(repo, stub, bindir, prover, api_server).returncode == 0
    # A stop took every network rule away; the stop has since been lifted.
    policy = (stub / "policy.yaml").read_text()
    (stub / "policy.yaml").write_text(policy.split("network_policies:")[0] + "network_policies: {}\n")
    (stub / "calls").unlink()
    r = run_on_work(repo, stub, bindir, prover, api_server)
    assert r.returncode == 0, r.stderr
    assert "lacks the base rules ['claude_managed_agents']" in r.stderr
    calls = (stub / "calls").read_text().splitlines()
    assert any(c.startswith("sandbox delete") for c in calls) and any(c.startswith("sandbox create") for c in calls)
    assert "claude_managed_agents" in (stub / "policy.yaml").read_text()


def test_a_stop_recorded_while_the_sandbox_is_made_still_stops_the_worker(harness, api_server):
    repo, stub, bindir, prover = harness
    # The stop lands after the first check, while the sandbox is being created.
    stop = json.dumps({"kind": "stop", "scope": "all", "target": "", "reason": "late", "by": "op"})
    hook = stub / "on-create"
    hook.write_text(f"#!/usr/bin/env bash\necho '{stop}' >> {repo / 'state' / 'ledger.jsonl'}\n")
    hook.chmod(0o755)
    r = run_on_work(repo, stub, bindir, prover, api_server)
    assert r.returncode != 0 and "late; refusing" in r.stderr
    calls = (stub / "calls").read_text()
    assert "sandbox create" in calls and "ant beta:worker run" not in calls
    assert calls.strip().splitlines()[-1].startswith("sandbox stop")


def test_a_new_sandbox_whose_live_policy_is_wider_than_the_file_gets_no_worker(harness, api_server):
    repo, stub, bindir, prover = harness
    # The gateway adds a rule of its own at create, as a global policy or a provider would.
    hook = stub / "on-create"
    hook.write_text("#!/usr/bin/env bash\ncat >> \"$STUB_DIR/policy.yaml\" <<'Y'\n  extra:\n    name: extra\n"
                    "    endpoints: [{host: evil.example, port: 443}]\n    binaries: [{path: /usr/bin/curl}]\nY\n")
    hook.chmod(0o755)
    r = run_on_work(repo, stub, bindir, prover, api_server)
    assert r.returncode != 0 and "is not the one asked for; refusing" in r.stderr
    assert "ant beta:worker run" not in calls_of(stub)


@pytest.mark.parametrize("broken", ["/nonexistent/openshell-prover", "crash", "unsupported 3", "inconclusive 3", "invalid_input 2"])
def test_no_answer_about_a_sandbox_never_costs_the_session_its_sandbox(harness, api_server, broken, tmp_path):
    repo, stub, bindir, prover = harness
    assert run_on_work(repo, stub, bindir, prover, api_server).returncode == 0
    if broken == "crash":  # agentpolicy itself dies, on a policy that is not text
        (stub / "policy.yaml").write_bytes(b"\xff\xfe")
        broken = prover
    elif " " in broken:  # the prover runs, and gives no verdict
        result, code = broken.split()
        script = tmp_path / "no-verdict"
        script.write_text(f"#!/bin/sh\necho '{{\"result\": \"{result}\"}}'\nexit {code}\n")
        script.chmod(0o755)
        broken = str(script)
    (stub / "calls").unlink()
    r = run_on_work(repo, stub, bindir, broken, api_server)
    assert r.returncode != 0
    calls = (stub / "calls").read_text()
    assert "sandbox delete" not in calls and "sandbox create" not in calls and "ant beta:worker run" not in calls


def test_a_hook_that_writes_an_empty_policy_gets_no_sandbox(harness, api_server):
    repo, stub, bindir, prover = harness
    hook = repo / "dispatcher" / "hook.sh"
    hook.write_text('#!/usr/bin/env bash\n[ "$1" = admit ] && cat >/dev/null\nexit 0\n')
    r = run_on_work(repo, stub, bindir, prover, api_server)
    assert r.returncode != 0 and "wrote no policy" in r.stderr
    assert "sandbox create" not in (stub / "calls").read_text()


def test_restart_is_refused_once_the_ceiling_is_not_trusted(harness, api_server):
    repo, stub, bindir, prover = harness
    assert run_on_work(repo, stub, bindir, prover, api_server).returncode == 0
    (repo / "policy" / "profiles" / "hello" / "ceiling.yaml.sig").unlink()
    (stub / "calls").unlink()
    r = run_on_work(repo, stub, bindir, prover, api_server)
    assert r.returncode != 0
    calls = (stub / "calls").read_text()
    assert "ant beta:worker run" not in calls and "sandbox start" not in calls


def test_sandbox_label_comes_from_settings(harness, api_server):
    repo, stub, bindir, prover = harness
    cfg = repo / "agentpolicy.yaml"
    cfg.write_text(cfg.read_text() + "sandbox_label: team-a\n")
    assert run_on_work(repo, stub, bindir, prover, api_server).returncode == 0
    assert "--label app=team-a" in (stub / "calls").read_text()


def test_without_a_hook_on_work_is_the_quickstart_as_it_was(harness):
    """The quickstart's own path: its fixed policy.yaml, its labels, and no hook call."""
    repo, stub, bindir, prover = harness
    env = {"PATH": f"{bindir}:/usr/bin:/bin", "STUB_DIR": str(stub), "ANTHROPIC_SESSION_ID": SESSION,
           "ANTHROPIC_ENVIRONMENT_ID": ENV, "ANTHROPIC_WORK_ID": WORK, "ANTHROPIC_ENVIRONMENT_KEY": ENV_KEY}
    r = subprocess.run(["bash", str(QUICKSTART / "on-work.sh")], input=work_item(), capture_output=True,
                       text=True, env=env, cwd=repo, timeout=60)
    assert r.returncode == 0, r.stderr
    create = next(c for c in calls_of(stub).splitlines() if c.startswith("sandbox create"))
    assert "--label app=shs-openshell --label session=" in create and "profile=" not in create
    expected = (QUICKSTART / "policy.yaml").read_text()
    expected = expected.replace("SESSION_ID", SESSION).replace("ENVIRONMENT_ID", ENV)
    assert (stub / "policy.yaml").read_text() == expected
    assert "ANTHROPIC_BASE_URL=https://api.anthropic.com" in calls_of(stub) and "[hook]" not in r.stderr
    assert ENV_KEY not in calls_of(stub) and set((stub / "envkey-seen").read_text().split()) == {"0"}
