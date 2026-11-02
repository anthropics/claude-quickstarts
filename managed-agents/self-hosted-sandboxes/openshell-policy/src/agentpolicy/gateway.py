"""The OpenShell gateway, as the reviewer and the promoter need it.

``Gateway`` is the small surface the rest of the package depends on. The
gRPC implementation below talks to a real gateway with the client
certificate the ``openshell`` CLI registered; tests use a fake.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Protocol

from . import convert


@dataclass
class SandboxRef:
    name: str
    id: str
    labels: dict[str, str] = field(default_factory=dict)

    @property
    def session_id(self) -> str:
        return self.labels.get("session", "")

    @property
    def profile(self) -> str:
        return self.labels.get("profile", "")

    @property
    def environment_id(self) -> str:
        return self.labels.get("environment", "")

    @property
    def agent_id(self) -> str:
        return self.labels.get("agent", "")

    @property
    def agent_version(self) -> str:
        return self.labels.get("agent_version", "")


@dataclass
class Proposal:
    """One pending or decided entry in a sandbox's proposal inbox."""

    sandbox: str
    chunk_id: str
    status: str
    rule_name: str
    rule: dict[str, Any] | None
    rationale: str = ""
    security_notes: str = ""
    validation_result: str = ""
    review_token: str = ""
    application_error: str = ""
    binary: str = ""
    hit_count: int = 0
    candidate_policy: dict[str, Any] | None = None
    # Why ``rule`` or ``candidate_policy`` could not be translated, if so.
    unsupported: str = ""


class Gateway(Protocol):
    def list_sandboxes(self, app_label: str) -> list[SandboxRef]: ...
    def proposals(self, sandbox: str, status: str = "pending") -> list[Proposal]: ...
    def approve(self, sandbox: str, chunk_id: str, review_token: str) -> None: ...
    def reject(self, sandbox: str, chunk_id: str, reason: str) -> None: ...
    def lock_down(self, sandbox: str) -> None: ...
    def stop_sandbox(self, sandbox: str) -> None: ...


# ---------------------------------------------------------------------------
# gRPC implementation


def _openshell_config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "openshell"


def resolve_gateway(name: str = "", endpoint: str = "", mtls_dir: str = "") -> tuple[str, Path | None]:
    """Finds a gateway's endpoint and client certificate the way the CLI does.

    The CLI keeps each registered gateway under
    ``~/.config/openshell/gateways/<name>/`` (or ``/etc/openshell/gateways``),
    with ``metadata.json`` naming the endpoint and ``mtls/`` holding the
    client certificate. ``OPENSHELL_GATEWAY`` or else ``active_gateway`` names
    the default.
    """
    roots = [_openshell_config_dir(), Path(os.environ.get("OPENSHELL_SYSTEM_CONFIG_DIR", "/etc/openshell"))]
    name = name or os.environ.get("OPENSHELL_GATEWAY", "")
    if not name:
        for root in roots:
            active = root / "active_gateway"
            if active.exists():
                name = active.read_text().strip()
                break
    gw_dir = None
    if name:
        for root in roots:
            candidate = root / "gateways" / name
            if candidate.is_dir():
                gw_dir = candidate
                break
    if not endpoint:
        if gw_dir is None:
            raise RuntimeError("no OpenShell gateway is registered; run `openshell status` or set gateway.endpoint")
        meta = json.loads((gw_dir / "metadata.json").read_text())
        endpoint = meta["gateway_endpoint"]
    certs = Path(mtls_dir) if mtls_dir else (gw_dir / "mtls" if gw_dir else None)
    if certs is not None and not (certs / "tls.crt").exists():
        certs = None
    return endpoint, certs


class GrpcGateway:
    def __init__(self, endpoint: str, mtls_dir: Path | None, workspace: str = "default", server_name: str = "") -> None:
        import grpc

        from ._proto import openshell_pb2, openshell_pb2_grpc

        self.pb = openshell_pb2
        self.workspace = workspace
        target = endpoint.split("://", 1)[-1].rstrip("/")
        if endpoint.startswith("http://"):
            channel = grpc.insecure_channel(target)
        else:
            if mtls_dir is None:
                creds = grpc.ssl_channel_credentials()
            else:
                creds = grpc.ssl_channel_credentials(
                    root_certificates=(mtls_dir / "ca.crt").read_bytes(),
                    private_key=(mtls_dir / "tls.key").read_bytes(),
                    certificate_chain=(mtls_dir / "tls.crt").read_bytes(),
                )
            options = [("grpc.ssl_target_name_override", server_name)] if server_name else []
            channel = grpc.secure_channel(target, creds, options=options)
        self.stub = openshell_pb2_grpc.OpenShellStub(channel)

    def _scope(self, req: Any) -> Any:
        req.workspace_scope.workspace = self.workspace
        return req

    def list_sandboxes(self, app_label: str) -> list[SandboxRef]:
        out: list[SandboxRef] = []
        token = ""
        while True:
            req = self._scope(self.pb.ListSandboxesRequest(page_size=100, page_token=token, label_selector=f"app={app_label}"))
            resp = self.stub.ListSandboxes(req, timeout=30)
            for sb in resp.sandboxes:
                out.append(SandboxRef(name=sb.metadata.name, id=sb.metadata.id, labels=dict(sb.metadata.labels)))
            token = resp.next_page_token
            if not token:
                return out

    def proposals(self, sandbox: str, status: str = "pending") -> list[Proposal]:
        req = self._scope(self.pb.GetDraftPolicyRequest(sandbox=sandbox, status_filter=status))
        resp = self.stub.GetDraftPolicy(req, timeout=30)
        out = []
        for c in resp.chunks:
            p = Proposal(
                sandbox=sandbox,
                chunk_id=c.id,
                status=c.status,
                rule_name=c.rule_name,
                rule=None,
                rationale=c.rationale,
                security_notes=c.security_notes,
                validation_result=c.validation_result,
                review_token=c.review_token,
                application_error=c.application_error,
                binary=c.binary,
                hit_count=c.hit_count,
            )
            try:
                p.rule = convert.rule_to_dict(c.proposed_rule)
                if c.HasField("candidate_effective_policy"):
                    p.candidate_policy = convert.policy_to_dict(c.candidate_effective_policy)
            except convert.Unsupported as err:
                p.unsupported = str(err)
            out.append(p)
        return out

    def approve(self, sandbox: str, chunk_id: str, review_token: str) -> None:
        req = self._scope(self.pb.ApproveDraftChunkRequest(sandbox=sandbox, chunk_id=chunk_id, review_token=review_token))
        self.stub.ApproveDraftChunk(req, timeout=30)

    def reject(self, sandbox: str, chunk_id: str, reason: str) -> None:
        req = self._scope(self.pb.RejectDraftChunkRequest(sandbox=sandbox, chunk_id=chunk_id, reason=reason))
        self.stub.RejectDraftChunk(req, timeout=30)

    def lock_down(self, sandbox: str) -> None:
        """Replaces the sandbox's network rules with none: every new connection is denied.

        Network rules hot-reload, so this takes effect in a running sandbox at
        once. A sandbox-scoped update may change only the network rules; the
        filesystem, Landlock and process rules are sent back as they are.
        """
        status = self.stub.GetSandboxPolicyStatus(
            self._scope(self.pb.GetSandboxPolicyStatusRequest(sandbox=sandbox, version=0)), timeout=30)
        policy = type(status.revision.policy)()
        policy.CopyFrom(status.revision.policy)
        policy.ClearField("network_policies")
        req = self._scope(self.pb.UpdateConfigRequest(sandbox=sandbox, policy=policy))
        self.stub.UpdateConfig(req, timeout=30)

    def stop_sandbox(self, sandbox: str) -> None:
        """Stops the sandbox, or deletes it if it is in Error.

        An agent can kill its sandbox's main process, which puts the sandbox in
        Error. OpenShell 0.1.2 then answers a stop with success and leaves what
        the agent started running, so only a delete ends it. /workspace goes
        with it; the dispatcher would delete a sandbox in Error anyway.
        """
        sb = self.stub.GetSandbox(self._scope(self.pb.GetSandboxRequest(name=sandbox)), timeout=30).sandbox
        if sb.status.phase == self.pb.SANDBOX_PHASE_ERROR:
            self.stub.DeleteSandbox(self._scope(self.pb.DeleteSandboxRequest(name=sandbox, allow_missing=True)), timeout=60)
            return
        self.stub.StopSandbox(self._scope(self.pb.StopSandboxRequest(name=sandbox)), timeout=60)

    def policy_rules(self, sandbox: str) -> dict[str, list[str]]:
        """The sandbox's current network rules: name to binary paths."""
        req = self._scope(self.pb.GetSandboxPolicyStatusRequest(sandbox=sandbox, version=0))
        policy = self.stub.GetSandboxPolicyStatus(req, timeout=30).revision.policy
        return {name: [b.path for b in rule.binaries] for name, rule in policy.network_policies.items()}

    def watch_logs(self, sandbox: str, cursor: str = "", tail: int = 100000) -> Iterator[LogEvent]:
        """Follows the sandbox's supervisor log lines from the gateway.

        Resumes after ``cursor`` when one is given, else replays up to ``tail``
        buffered lines first. Raises CursorLost when the gateway can no longer
        resume from ``cursor`` (its buffer moved on, it restarted, or it is
        another gateway or version and never issued such a cursor).
        """
        import grpc

        req = self._scope(self.pb.WatchSandboxRequest(
            sandbox=sandbox, follow_logs=True, log_sources=["sandbox"],
            log_tail_lines=0 if cursor else tail, resume_after_cursor=cursor,
        ))
        try:
            for ev in self.stub.WatchSandbox(req):
                kind = ev.WhichOneof("payload")
                if kind == "log":
                    line = ev.log
                    t = line.event_time
                    yield LogEvent("log", ev.cursor, line.level, line.message,
                                   t.seconds * 1000 + t.nanos // 1_000_000, line.sandbox_id)
                elif kind == "warning":
                    yield LogEvent("gap", ev.cursor, "", ev.warning.message, 0, "")
        except grpc.RpcError as err:
            lost = (grpc.StatusCode.OUT_OF_RANGE, grpc.StatusCode.INVALID_ARGUMENT)
            if cursor and err.code() in lost:
                raise CursorLost(str(err.details())) from err
            raise


@dataclass
class LogEvent:
    """One event from a sandbox's log watch: a log line, or a reported gap."""

    kind: str  # "log" or "gap"
    cursor: str
    level: str
    message: str
    time_ms: int
    sandbox_id: str


class CursorLost(Exception):
    """The gateway cannot resume a log watch from the cursor it was given."""


def connect(settings: Any) -> GrpcGateway:
    g = settings.gateway
    endpoint, certs = resolve_gateway(g.name, g.endpoint, g.mtls_dir)
    return GrpcGateway(endpoint, certs, workspace=g.workspace, server_name=g.tls_server_name)
