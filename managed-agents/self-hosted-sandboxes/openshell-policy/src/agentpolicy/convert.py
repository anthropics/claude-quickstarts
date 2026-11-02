"""Translation from OpenShell's protobuf policy messages to policy YAML dicts.

The gateway hands proposals and effective policies over gRPC; the prover reads
YAML. This module turns one into the other for the fields this reference
understands. A message that sets a field outside that set raises
``Unsupported`` instead of being translated partially: a rule the prover
would see with a field missing could prove narrower than it is.
"""

from __future__ import annotations

from typing import Any

TLS = {0: None, 1: "skip"}
ENFORCEMENT = {0: None, 1: "enforce", 2: "audit"}
ACCESS = {0: None, 1: "read-only", 2: "read-write", 3: "full"}


class Unsupported(ValueError):
    """A policy message uses a field this translation does not handle."""


def _matcher(m: Any) -> Any:
    if m.glob and m.any:
        raise Unsupported("query matcher sets both glob and any")
    return {"any": list(m.any)} if m.any else m.glob


def _l7(match: Any, where: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in ("method", "path"):
        value = getattr(match, name)
        if value:
            out[name] = value
    if match.query:
        out["query"] = {k: _matcher(v) for k, v in match.query.items()}
    for name in ("command", "operation_type", "operation_name"):
        if getattr(match, name):
            raise Unsupported(f"{where} uses {name}, which only non-REST protocols set")
    if list(match.fields) or match.params:
        raise Unsupported(f"{where} uses fields or params, which only non-REST protocols set")
    return out


def endpoint_to_dict(ep: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if ep.host:
        out["host"] = ep.host
    # The gateway fills both port and ports (port 443, ports [443]); the
    # prover reads a rule carrying both as having no unambiguous port. Emit
    # one form. A port missing from ports is a disagreement, not translated.
    ports = list(ep.ports)
    if ports and ep.port and ep.port not in ports:
        raise Unsupported(f"endpoint {ep.host} names port {ep.port} outside its ports {ports}")
    distinct = sorted(set(ports)) or ([ep.port] if ep.port else [])
    if len(distinct) == 1:
        out["port"] = distinct[0]
    elif distinct:
        out["ports"] = distinct
    if ep.path:
        out["path"] = ep.path
    if ep.protocol:
        out["protocol"] = ep.protocol
    for key, table, value in (
        ("tls", TLS, ep.tls),
        ("enforcement", ENFORCEMENT, ep.enforcement),
        ("access", ACCESS, ep.access),
    ):
        if value not in table:
            raise Unsupported(f"unknown {key} value {value}")
        if table[value]:
            out[key] = table[value]
    if list(ep.rules):
        out["rules"] = [{"allow": _l7(r.allow, "allow rule")} for r in ep.rules]
    if list(ep.deny_rules):
        out["deny_rules"] = [_l7(r, "deny rule") for r in ep.deny_rules]
    if list(ep.allowed_ips):
        out["allowed_ips"] = list(ep.allowed_ips)
    if ep.allow_encoded_slash:
        out["allow_encoded_slash"] = True
    for flag in ("request_body_credential_rewrite", "websocket_credential_rewrite", "allow_uninspected_credentials"):
        if getattr(ep, flag):
            out[flag] = True
    for name in ("credential_signing", "signing_service", "signing_region"):
        if getattr(ep, name):
            out[name] = getattr(ep, name)
    if ep.HasField("credential_binding") and ep.credential_binding.provider:
        out["credential_binding"] = {"provider": ep.credential_binding.provider}
    if (
        ep.persisted_queries
        or ep.graphql_persisted_queries
        or ep.graphql_max_body_bytes
        or ep.json_rpc_max_body_bytes
        or ep.HasField("mcp")
    ):
        raise Unsupported("endpoint uses GraphQL, MCP or JSON-RPC options; review it by hand")
    # advisor_proposed and provider_credentialed are set by the gateway, not
    # by the policy author, and are not part of the YAML schema.
    return out


def _refuse_unknown_fields(msg: Any, what: str) -> None:
    """A gateway newer than the vendored proto may send fields this client cannot name."""
    known = type(msg)()
    known.CopyFrom(msg)
    known.DiscardUnknownFields()  # nested messages included
    if known.ByteSize() != msg.ByteSize():
        raise Unsupported(f"{what} carries fields this client's OpenShell proto does not define; update third_party/openshell")


def rule_to_dict(rule: Any) -> dict[str, Any]:
    _refuse_unknown_fields(rule, f"rule {rule.name!r}")
    out: dict[str, Any] = {}
    if rule.name:
        out["name"] = rule.name
    out["endpoints"] = [endpoint_to_dict(ep) for ep in rule.endpoints]
    out["binaries"] = [{"path": b.path} for b in rule.binaries]
    return out


def policy_to_dict(policy: Any) -> dict[str, Any]:
    _refuse_unknown_fields(policy, "policy")
    out: dict[str, Any] = {"version": policy.version or 1}
    if policy.HasField("filesystem"):
        fs = policy.filesystem
        out["filesystem_policy"] = {
            "include_workdir": fs.include_workdir,
            "read_only": list(fs.read_only),
            "read_write": list(fs.read_write),
        }
    if policy.HasField("landlock") and policy.landlock.compatibility:
        out["landlock"] = {"compatibility": policy.landlock.compatibility}
    if policy.HasField("process"):
        proc = {k: getattr(policy.process, k) for k in ("run_as_user", "run_as_group") if getattr(policy.process, k)}
        if proc:
            out["process"] = proc
    out["network_policies"] = {name: rule_to_dict(r) for name, r in policy.network_policies.items()}
    if policy.network_middlewares:
        raise Unsupported("policy attaches network middlewares; review it by hand")
    return out
