"""The gRPC gateway client and `agentpolicy grow`, against an in-process fake gateway."""

from __future__ import annotations

import json
import sys
from concurrent import futures

import pytest
from conftest import ENV, SESSION, run_cli_env

proto = pytest.importorskip("agentpolicy._proto")
grpc = pytest.importorskip("grpc")
pb, pb_grpc, spb = proto.openshell_pb2, proto.openshell_pb2_grpc, proto.sandbox_pb2

from agentpolicy.gateway import GrpcGateway  # noqa: E402
from agentpolicy.policyfile import Bindings  # noqa: E402
from agentpolicy.store import Store  # noqa: E402

SANDBOX = f"shs-{SESSION[-15:].lower()}"


def rest_endpoint(rule, host, access=spb.NETWORK_ACCESS_PRESET_READ_ONLY):
    rule.endpoints.add(host=host, port=443, protocol="rest",
                       enforcement=spb.NETWORK_ENFORCEMENT_MODE_ENFORCE, access=access)
    rule.binaries.add(path="/usr/bin/curl")
    return rule


def dict_to_policy_proto(policy: dict) -> object:
    """Builds a SandboxPolicy message from a policy dict (enough for these tests)."""
    p = spb.SandboxPolicy(version=1)
    fs = policy["filesystem_policy"]
    p.filesystem.include_workdir = fs.get("include_workdir", False)
    p.filesystem.read_only.extend(fs["read_only"])
    p.filesystem.read_write.extend(fs["read_write"])
    p.landlock.compatibility = policy["landlock"]["compatibility"]
    for name, rule in policy["network_policies"].items():
        r = p.network_policies[name]
        r.name = rule.get("name", name)
        for ep in rule["endpoints"]:
            e = r.endpoints.add(host=ep["host"], port=ep["port"], protocol=ep.get("protocol", ""))
            if ep.get("enforcement") == "enforce":
                e.enforcement = spb.NETWORK_ENFORCEMENT_MODE_ENFORCE
            if ep.get("access") == "read-only":
                e.access = spb.NETWORK_ACCESS_PRESET_READ_ONLY
            for allow in ep.get("rules") or []:
                e.rules.add().allow.CopyFrom(spb.L7Allow(method=allow["allow"]["method"], path=allow["allow"]["path"]))
        for b in rule["binaries"]:
            r.binaries.add(path=b["path"])
    return p


class FakeOpenShell(pb_grpc.OpenShellServicer):
    def __init__(self, starting_policy: dict) -> None:
        self.starting = starting_policy
        self.approved: list = []
        self.rejected: list = []
        self.workspaces: set = set()
        self.updates: list = []
        self.stopped: list = []
        self.deleted: list = []
        self.phase = pb.SANDBOX_PHASE_READY
        self.chunks = [self._chunk("c1", "allow_example_com_443", "example.com", "t1"),
                       self._chunk("c2", "allow_api_github_com_443", "api.github.com", "t2")]

    def _chunk(self, cid, name, host, token):
        rule = rest_endpoint(spb.NetworkPolicyRule(name=name), host)
        current = dict_to_policy_proto(self.starting)
        candidate = dict_to_policy_proto(self.starting)
        candidate.network_policies[name].CopyFrom(rule)
        return pb.PolicyChunk(id=cid, status="pending", rule_name=name, proposed_rule=rule, binary="/usr/bin/curl",
                              rationale="need it", validation_result="prover: no new findings", review_token=token,
                              current_effective_policy=current, candidate_effective_policy=candidate)

    def ListSandboxes(self, request, context):
        self.workspaces.add(request.workspace_scope.workspace)
        assert request.label_selector == "app=openshell-policy"
        sb = pb.Sandbox()
        sb.metadata.name = SANDBOX
        sb.metadata.id = "sb-1"
        sb.metadata.labels.update({"app": "openshell-policy", "profile": "hello", "session": SESSION, "environment": ENV})
        return pb.ListSandboxesResponse(sandboxes=[sb])

    def GetDraftPolicy(self, request, context):
        self.workspaces.add(request.workspace_scope.workspace)
        assert request.sandbox == SANDBOX and request.status_filter in ("pending", "approved")
        return pb.GetDraftPolicyResponse(chunks=[c for c in self.chunks if c.status == request.status_filter])

    def ApproveDraftChunk(self, request, context):
        self.approved.append((request.sandbox, request.chunk_id, request.review_token))
        for c in self.chunks:
            if c.id == request.chunk_id:
                c.status = "approved"
        return pb.ApproveDraftChunkResponse(policy_version=2)

    def GetSandboxPolicyStatus(self, request, context):
        policy = dict_to_policy_proto(self.starting)
        return pb.GetSandboxPolicyStatusResponse(revision=pb.SandboxPolicyRevision(version=1, policy=policy))

    def UpdateConfig(self, request, context):
        self.workspaces.add(request.workspace_scope.workspace)
        self.updates.append(request)
        return pb.UpdateConfigResponse(version=2)

    def GetSandbox(self, request, context):
        sb = pb.Sandbox()
        sb.metadata.name = request.name
        sb.status.phase = self.phase
        return pb.SandboxResponse(sandbox=sb)

    def DeleteSandbox(self, request, context):
        self.deleted.append(request.name)
        return pb.DeleteSandboxResponse()

    def StopSandbox(self, request, context):
        self.stopped.append(request.name)
        return pb.SandboxResponse()

    def RejectDraftChunk(self, request, context):
        self.rejected.append((request.sandbox, request.chunk_id, request.reason))
        for c in self.chunks:
            if c.id == request.chunk_id:
                c.status = "rejected"
        return pb.RejectDraftChunkResponse()


@pytest.fixture
def fake_gateway(store, settings):
    b = Bindings(SESSION, ENV, settings.api_host, settings.api_port)
    servicer = FakeOpenShell(store.starting_policy("hello", b))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    pb_grpc.add_OpenShellServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    yield servicer, f"http://127.0.0.1:{port}"
    server.stop(0)


def test_client_reads_and_translates_proposals(fake_gateway):
    servicer, endpoint = fake_gateway
    gw = GrpcGateway(endpoint, None, workspace="team-a")
    sbs = gw.list_sandboxes("openshell-policy")
    assert sbs[0].session_id == SESSION and sbs[0].profile == "hello"
    props = gw.proposals(SANDBOX)
    assert [p.rule_name for p in props] == ["allow_example_com_443", "allow_api_github_com_443"]
    assert props[0].rule["endpoints"][0]["access"] == "read-only"
    assert "allow_example_com_443" in props[0].candidate_policy["network_policies"]
    assert servicer.workspaces == {"team-a"}


def test_cli_grow_once_end_to_end(repo, fake_gateway, fake_prover_bin):
    servicer, endpoint = fake_gateway
    r = run_cli_env(repo, fake_prover_bin, {"AGENTPOLICY_GATEWAY_ENDPOINT": endpoint}, "grow", "--once")
    assert r.returncode == 0, r.stderr
    assert servicer.approved == [(SANDBOX, "c1", "t1")]
    assert servicer.rejected[0][1] == "c2" and servicer.rejected[0][2].startswith("outside_ceiling: ")
    ledger = [json.loads(line) for line in (repo / "state" / "ledger.jsonl").read_text().splitlines()]
    assert [e["kind"] for e in ledger] == ["decision", "grant", "decision"]
    # A second pass finds nothing new to decide.
    r = run_cli_env(repo, fake_prover_bin, {"AGENTPOLICY_GATEWAY_ENDPOINT": endpoint}, "grow", "--once")
    assert r.returncode == 0 and len(servicer.approved) == 1 and len(servicer.rejected) == 1


def test_lock_down_sends_the_same_static_rules_and_no_network_rules(fake_gateway):
    servicer, endpoint = fake_gateway
    gw = GrpcGateway(endpoint, None, workspace="team-a")
    gw.lock_down(SANDBOX)
    gw.stop_sandbox(SANDBOX)
    (req,) = servicer.updates
    assert req.sandbox == SANDBOX and req.workspace_scope.workspace == "team-a"
    assert len(req.policy.network_policies) == 0
    assert list(req.policy.filesystem.read_write) == list(servicer.starting["filesystem_policy"]["read_write"])
    assert req.policy.landlock.compatibility == servicer.starting["landlock"]["compatibility"]
    assert servicer.stopped == [SANDBOX]


def test_a_sandbox_in_error_is_deleted_because_a_stop_would_leave_it_running(fake_gateway):
    servicer, endpoint = fake_gateway
    servicer.phase = pb.SANDBOX_PHASE_ERROR
    GrpcGateway(endpoint, None).stop_sandbox(SANDBOX)
    assert servicer.deleted == [SANDBOX] and not servicer.stopped


def test_a_field_the_vendored_proto_does_not_define_is_refused():
    from agentpolicy import convert

    rule = rest_endpoint(spb.NetworkPolicyRule(name="r"), "example.com")
    assert convert.rule_to_dict(rule)["endpoints"][0]["host"] == "example.com"
    ep = type(rule.endpoints[0]).FromString(rule.endpoints[0].SerializeToString() + bytes([0x98, 0x06, 0x01]))  # field 99
    newer = spb.NetworkPolicyRule(name="r", endpoints=[ep])
    with pytest.raises(convert.Unsupported, match="does not define"):
        convert.rule_to_dict(newer)


def test_cli_stop_and_resume_end_to_end(repo, fake_gateway, fake_prover_bin):
    servicer, endpoint = fake_gateway
    env = {"AGENTPOLICY_GATEWAY_ENDPOINT": endpoint}
    r = run_cli_env(repo, fake_prover_bin, env, "stop", "--session", SESSION, "--reason", "incident 7", "--by", "oncall")
    assert r.returncode == 0, r.stderr
    assert servicer.stopped == [SANDBOX] and len(servicer.updates) == 1
    # No API key here: the session is not interrupted, and the output says so.
    assert "not interrupted at the Managed Agents API" in r.stdout
    # A stopped session is decided nothing.
    r = run_cli_env(repo, fake_prover_bin, env, "grow", "--once")
    assert r.returncode == 0 and not servicer.approved and not servicer.rejected
    r = run_cli_env(repo, fake_prover_bin, env, "status")
    assert "stop in force: session " + SESSION in r.stdout and "incident 7" in r.stdout
    assert run_cli_env(repo, fake_prover_bin, env, "resume", "--session", SESSION).returncode == 0
    r = run_cli_env(repo, fake_prover_bin, env, "grow", "--once")
    assert r.returncode == 0 and servicer.approved


def test_the_gateway_is_chosen_as_the_cli_chooses_it(tmp_path, monkeypatch):
    from agentpolicy.gateway import resolve_gateway

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("OPENSHELL_GATEWAY", raising=False)
    root = tmp_path / "openshell"
    for name in ("a", "b"):
        (root / "gateways" / name).mkdir(parents=True)
        (root / "gateways" / name / "metadata.json").write_text(f'{{"gateway_endpoint": "https://{name}"}}')
    (root / "active_gateway").write_text("a\n")
    assert resolve_gateway()[0] == "https://a"
    monkeypatch.setenv("OPENSHELL_GATEWAY", "b")
    assert resolve_gateway()[0] == "https://b"
