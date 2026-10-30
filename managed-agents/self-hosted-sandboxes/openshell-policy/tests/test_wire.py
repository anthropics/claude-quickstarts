"""The gRPC translation, the prover envelope, the Managed Agents helpers and the command line."""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

import pytest
import yaml
from conftest import ENV, SESSION, run_cli_env

from agentpolicy import cli, managed_agents, convert
from agentpolicy.prover import CliProver, parse_envelope

pb = pytest.importorskip("agentpolicy._proto").sandbox_pb2


def test_rule_to_dict_round_trips_rest_rule():
    rule = pb.NetworkPolicyRule(name="r")
    ep = rule.endpoints.add(host="example.com", port=443, protocol="rest",
                            enforcement=pb.NETWORK_ENFORCEMENT_MODE_ENFORCE)
    ep.rules.add().allow.CopyFrom(pb.L7Allow(method="GET", path="/repos/**"))
    ep.deny_rules.add(method="*", path="/admin/**")
    rule.binaries.add(path="/usr/bin/curl")
    assert convert.rule_to_dict(rule) == {
        "name": "r",
        "endpoints": [{
            "host": "example.com", "port": 443, "protocol": "rest", "enforcement": "enforce",
            "rules": [{"allow": {"method": "GET", "path": "/repos/**"}}],
            "deny_rules": [{"method": "*", "path": "/admin/**"}],
        }],
        "binaries": [{"path": "/usr/bin/curl"}],
    }


def test_port_and_ports_become_one_form():
    # The gateway fills both; the prover needs one.
    ep = pb.NetworkEndpoint(host="h", port=443, ports=[443])
    out = convert.endpoint_to_dict(ep)
    assert out["port"] == 443 and "ports" not in out
    out = convert.endpoint_to_dict(pb.NetworkEndpoint(host="h", ports=[8443, 443, 443]))
    assert out["ports"] == [443, 8443] and "port" not in out
    with pytest.raises(convert.Unsupported):
        convert.endpoint_to_dict(pb.NetworkEndpoint(host="h", port=80, ports=[443]))


def test_access_preset_and_query_matchers():
    ep = pb.NetworkEndpoint(host="h", port=443, protocol="rest", access=pb.NETWORK_ACCESS_PRESET_READ_ONLY)
    assert convert.endpoint_to_dict(ep)["access"] == "read-only"
    ep = pb.NetworkEndpoint(host="h", port=443, protocol="rest")
    allow = ep.rules.add().allow
    allow.method, allow.path = "GET", "/d"
    allow.query["os"].any.extend(["linux-*"])
    assert convert.endpoint_to_dict(ep)["rules"][0]["allow"]["query"] == {"os": {"any": ["linux-*"]}}


def test_fields_outside_the_model_are_refused():
    ep = pb.NetworkEndpoint(host="h", port=443, protocol="mcp")
    ep.mcp.versions.append("2025-11-25")
    with pytest.raises(convert.Unsupported):
        convert.endpoint_to_dict(ep)
    ep = pb.NetworkEndpoint(host="h", port=443, protocol="graphql", graphql_max_body_bytes=10)
    with pytest.raises(convert.Unsupported):
        convert.endpoint_to_dict(ep)


def test_policy_to_dict():
    p = pb.SandboxPolicy(version=1)
    p.filesystem.read_only.append("/usr")
    p.filesystem.read_write.append("/workspace")
    p.landlock.compatibility = "hard_requirement"
    p.network_policies["r"].name = "r"
    out = convert.policy_to_dict(p)
    assert out["filesystem_policy"]["read_write"] == ["/workspace"]
    assert out["landlock"] == {"compatibility": "hard_requirement"}
    assert out["network_policies"]["r"]["name"] == "r"


def test_parse_envelope_requires_agreeing_exit_code():
    env = {"result": "within_boundary", "exit_code": 0}
    assert parse_envelope(json.dumps(env), 0).ok
    assert parse_envelope(json.dumps(env), 1).result == "error"
    assert parse_envelope("not json", 2, "boom").reason == "boom"
    ce = {"domain": "network", "host": "a.com", "port": 443, "binary": "/usr/bin/curl", "method": "POST", "path": "/"}
    p = parse_envelope(json.dumps({"result": "exceeds_boundary", "counterexample": ce}), 1)
    assert "/usr/bin/curl reaching a.com:443 with POST /" in p.summary()


def test_missing_prover_binary_is_an_error_not_a_pass():
    assert CliProver("/nonexistent/openshell-prover").check({}, {}).result == "error"
    assert parse_envelope('{"result": "invalid_input", "reason": "x"}', 2).result == "invalid_input"


def secret_for(token: str) -> str:
    bundle = json.dumps({"sessions_token": token, "other": "x"}).encode()
    return base64.urlsafe_b64encode(bundle).decode().rstrip("=")


def test_worker_token_extraction():
    assert managed_agents.worker_token(secret_for("tok-123")) == "tok-123"
    with pytest.raises(ValueError):
        managed_agents.worker_token(base64.urlsafe_b64encode(b'{"x":1}').decode())


class _Resp:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


def test_session_identity_reads_the_agent_not_the_metadata(monkeypatch):
    seen = {}

    def fake_get(url, headers, timeout):
        seen["url"], seen["auth"] = url, headers["authorization"]
        # A profile named in metadata is ignored: profiles belong to environments.
        return _Resp({"metadata": {"policy_profile": "wide-open"},
                      "agent": {"id": "agent_011Cabc", "version": 4, "metadata": {"policy_profile": "wide-open"}}})

    monkeypatch.setattr(managed_agents.httpx, "get", fake_get)
    assert managed_agents.session_identity("http://h:8400/", SESSION, "tok") == {
        "agent_id": "agent_011Cabc", "agent_version": "4", "outside_routes": []}
    assert seen["url"] == f"http://h:8400/v1/sessions/{SESSION}" and seen["auth"] == "Bearer tok"


def test_session_identity_survives_one_bad_answer_but_not_three(monkeypatch):
    answers = [managed_agents.httpx.ConnectError("down"), _Resp({"agent": {"id": "agent_011Cabc", "version": 4}})]

    def fake_get(url, headers, timeout):
        a = answers.pop(0) if answers else managed_agents.httpx.ConnectError("down")
        if isinstance(a, Exception):
            raise a
        return a

    monkeypatch.setattr(managed_agents.httpx, "get", fake_get)
    monkeypatch.setattr(managed_agents.time, "sleep", lambda s: None)
    assert managed_agents.session_identity("http://h:8400", SESSION, "tok")["agent_id"] == "agent_011Cabc"
    with pytest.raises(managed_agents.httpx.HTTPError):
        managed_agents.session_identity("http://h:8400", SESSION, "tok")


def toolset(**web):
    return {"type": "agent_toolset_20260401", "default_config": {"enabled": True},
            "configs": [{"name": n, "enabled": on} for n, on in web.items()]}


@pytest.mark.parametrize("agent, routes", [
    ({"tools": [toolset(web_fetch=False, web_search=False)], "mcp_servers": []}, []),
    ({"tools": [toolset(web_fetch=False)]}, ["web_search"]),  # on unless turned off
    ({"tools": [toolset(web_fetch=True, web_search=False)]}, ["web_fetch"]),
    ({"tools": [{"type": "agent_toolset_20260401", "default_config": {"enabled": False}, "configs": []}]}, []),
    ({"tools": [{"type": "custom", "name": "mine"}]}, []),
    ({"mcp_servers": [{"type": "url", "name": "jira", "url": "https://mcp.example"}],
      "tools": [{"type": "mcp_toolset", "mcp_server_name": "jira"}]}, ["MCP server 'jira'", "tool of type 'mcp_toolset'"]),
    ({"multiagent": {"agents": []}}, ["other agents it coordinates, whose tools are not checked"]),
])
def test_routes_around_the_sandbox_are_read_from_the_resolved_agent(agent, routes):
    assert managed_agents.outside_routes(agent) == routes


@pytest.mark.parametrize("agent", [{}, {"id": ""}, {"id": "agent_x y"}, {"id": "agent_ok", "version": "1 2"}])
def test_session_identity_refuses_a_missing_or_malformed_agent(monkeypatch, agent):
    monkeypatch.setattr(managed_agents.httpx, "get", lambda url, headers, timeout: _Resp({"agent": agent}))
    with pytest.raises(ValueError):
        managed_agents.session_identity("http://h:8400", SESSION, "tok")


def run_cli(repo: Path, prover_bin: str, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
    return run_cli_env(repo, prover_bin, {}, *args, stdin=stdin)


def test_cli_prepare_writes_proved_policy(repo, fake_prover_bin):
    out = repo / "policy.out.yaml"
    r = run_cli(repo, fake_prover_bin, "prepare", "--profile", "hello", "--session", SESSION,
                "--environment", ENV, "--out", str(out))
    assert r.returncode == 0, r.stderr
    policy = yaml.safe_load(out.read_text())
    assert f"/v1/sessions/{SESSION}" in json.dumps(policy)


def test_cli_prepare_refuses_grants_outside_ceiling(repo, fake_prover_bin):
    grants = repo / "policy" / "profiles" / "hello" / "policy.yaml"
    grants.write_text("network_policies:\n  gh:\n    endpoints: [{host: api.github.com, port: 443, protocol: rest,"
                      " enforcement: enforce, access: full}]\n    binaries: [{path: /usr/bin/curl}]\n")
    out = repo / "policy.out.yaml"
    r = run_cli(repo, fake_prover_bin, "prepare", "--profile", "hello", "--session", SESSION,
                "--environment", ENV, "--out", str(out))
    assert r.returncode == 1 and "refusing to create the sandbox" in r.stderr and not out.exists()


def test_cli_prepare_refuses_unsigned_ceiling(repo, fake_prover_bin):
    (repo / "policy" / "profiles" / "hello" / "ceiling.yaml.sig").unlink()
    r = run_cli(repo, fake_prover_bin, "prepare", "--profile", "hello", "--session", SESSION,
                "--environment", ENV, "--out", str(repo / "x.yaml"))
    assert r.returncode == 2 and "not signed" in r.stderr


def test_cli_ingest_tags_records(repo, fake_prover_bin):
    line = json.dumps({"class_uid": 4001, "action": "Allowed", "time": 1, "metadata": {"uid": "u"}})
    r = run_cli(repo, fake_prover_bin, "ingest-ocsf", "--profile", "hello", "--session", SESSION,
                stdin=f"junk\nOCSF-JSON {line}\n")
    assert r.returncode == 0, r.stderr
    files = list((repo / "state" / "ocsf" / "hello").glob("*.jsonl"))
    assert len(files) == 1
    rec = json.loads(files[0].read_text())
    assert rec["unmapped"] == {"managed_agents_session_id": SESSION, "policy_profile": "hello"}


def test_cli_check_and_status(repo, fake_prover_bin):
    r = run_cli(repo, fake_prover_bin, "check")
    assert r.returncode == 0 and "hello: within the ceiling" in r.stdout
    r = run_cli(repo, fake_prover_bin, "ceiling", "verify", "--profile", "hello")
    assert r.returncode == 0 and "owner@example.com" in r.stdout
    r = run_cli(repo, fake_prover_bin, "status")
    assert r.returncode == 0 and "hello: 0 starting grant(s)" in r.stdout


def test_the_cli_s_prover_also_checks_that_rules_are_enforced(repo, fake_prover_bin):
    """allowed_ips passes openshell-prover 0.1.2; only the Enforced wrapper stands between it and a sandbox."""
    grants = repo / "policy" / "profiles" / "hello" / "policy.yaml"
    grants.write_text("network_policies:\n  ex:\n    endpoints: [{host: example.com, port: 443, protocol: rest, enforcement: enforce,"
                      " access: read-only, allowed_ips: [10.0.0.0/8]}]\n    binaries: [{path: /usr/bin/curl}]\n")
    r = run_cli(repo, fake_prover_bin, "prepare", "--profile", "hello", "--session", SESSION,
                "--environment", ENV, "--out", str(repo / "out.yaml"))
    assert r.returncode == 1 and "allowed_ips" in r.stderr and not (repo / "out.yaml").exists()


def test_the_policy_owner_can_check_with_protect_signers_on(repo, fake_prover_bin):
    (repo / "agentpolicy.yaml").write_text((repo / "agentpolicy.yaml").read_text() + "protect_signers: true\n")
    assert run_cli(repo, fake_prover_bin, "check").returncode == 0
    r = run_cli(repo, fake_prover_bin, "prepare", "--profile", "hello", "--session", SESSION,
                "--environment", ENV, "--out", str(repo / "out.yaml"))
    assert r.returncode != 0 and "protect_signers" in r.stderr
