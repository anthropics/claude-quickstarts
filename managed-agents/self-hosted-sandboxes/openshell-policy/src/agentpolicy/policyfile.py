"""Reading, rendering, and composing OpenShell policy files.

Policies here are plain dicts in the shape of OpenShell's YAML schema
(version, filesystem_policy, landlock, process, network_policies). Templates
carry ``{{NAME}}`` placeholders that are replaced as text before parsing, so a
template need not be valid YAML until it is rendered.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PLACEHOLDERS = ("SESSION_ID", "ENVIRONMENT_ID", "API_HOST", "API_PORT")
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Z_]+)\s*\}\}")

# A Managed Agents id: a short prefix, an underscore, then letters and digits.
ID_RE = re.compile(r"^(sesn|env|work)_[A-Za-z0-9]+$")
SESSION_RE = re.compile(r"^sesn_[A-Za-z0-9]+$")
ENVIRONMENT_RE = re.compile(r"^env_[A-Za-z0-9]+$")
AGENT_RE = re.compile(r"^agent_[A-Za-z0-9]+$")

# OpenShell reserves rule keys starting with _provider_ for provider rules.
RULE_NAME_RE = re.compile(r"^(?!_provider_)[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class PolicyError(ValueError):
    """A policy file or template is malformed or cannot be composed."""


@dataclass(frozen=True)
class Bindings:
    """The values one session's policy is rendered with."""

    session_id: str
    environment_id: str
    api_host: str
    api_port: int

    def __post_init__(self) -> None:
        for value in (self.session_id, self.environment_id):
            if not ID_RE.match(value):
                raise PolicyError(f"malformed Managed Agents id: {value!r}")
        if not re.fullmatch(r"[A-Za-z0-9.-]+", self.api_host):
            raise PolicyError(f"malformed API host: {self.api_host!r}")
        if not 0 < int(self.api_port) < 65536:
            raise PolicyError(f"malformed API port: {self.api_port!r}")

    @classmethod
    def sample(cls, api_host: str, api_port: int) -> "Bindings":
        """Bindings for proofs about a profile rather than one session.

        Every session's policy is the same template rendered with that
        session's ids, so a proof over these stand-in ids holds for all of
        them: the ids appear in the same places in candidate and boundary.
        """
        return cls(
            session_id="sesn_0profileproof0000000000",
            environment_id="env_0profileproof000000000",
            api_host=api_host,
            api_port=api_port,
        )

    def values(self) -> dict[str, str]:
        return {
            "SESSION_ID": self.session_id,
            "ENVIRONMENT_ID": self.environment_id,
            "API_HOST": self.api_host,
            "API_PORT": str(int(self.api_port)),
        }


def render_text(template: str, bindings: Bindings) -> str:
    """Replaces every placeholder; refuses an unknown one."""
    values = bindings.values()

    def sub(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            raise PolicyError(f"unknown placeholder {{{{{name}}}}}")
        return values[name]

    return _PLACEHOLDER_RE.sub(sub, template)


def parse(text: str, source: str = "<policy>") -> dict[str, Any]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as err:
        raise PolicyError(f"{source}: not valid YAML: {err}") from err
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise PolicyError(f"{source}: a policy must be a mapping")
    return data


def load_template(path: Path, bindings: Bindings) -> dict[str, Any]:
    """Reads a template file and renders it for one set of bindings."""
    return parse(render_text(path.read_text(), bindings), str(path))


def render(value: dict[str, Any], bindings: Bindings) -> dict[str, Any]:
    """Renders a policy dict whose strings may still carry placeholders."""
    return parse(render_text(dump(value), bindings))


def load(path: Path) -> dict[str, Any]:
    """Reads a policy file that carries no placeholders."""
    text = path.read_text()
    if _PLACEHOLDER_RE.search(text):
        raise PolicyError(f"{path}: has placeholders; render it with bindings")
    return parse(text, str(path))


def dump(policy: dict[str, Any]) -> str:
    return yaml.safe_dump(policy, sort_keys=False, default_flow_style=False)


def network_rules(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rules = policy.get("network_policies") or {}
    if not isinstance(rules, dict):
        raise PolicyError("network_policies must be a mapping of rule name to rule")
    return rules


def check_rule_name(name: str) -> None:
    if not RULE_NAME_RE.match(name):
        raise PolicyError(f"invalid rule name {name!r}")


def compose(base: dict[str, Any], grants: dict[str, Any]) -> dict[str, Any]:
    """Returns base with the grants' network rules added.

    Grants may only add network rules. A grant file that sets anything else,
    or a rule whose name the base already uses, is refused: the base is what
    every session must keep, and a profile cannot replace it.
    """
    extra = set(grants) - {"network_policies", "version"}
    if extra:
        raise PolicyError(f"grants may only add network_policies, found {sorted(extra)}")
    out = copy.deepcopy(base)
    out.setdefault("version", 1)
    merged = out.setdefault("network_policies", {}) or {}
    out["network_policies"] = merged
    for name, rule in network_rules(grants).items():
        check_rule_name(name)
        if name in merged:
            raise PolicyError(f"grant {name!r} collides with a base rule of the same name")
        rule = copy.deepcopy(rule)
        rule.setdefault("name", name)
        merged[name] = rule
    return out


def generalize(value: Any, bindings: Bindings) -> Any:
    """Replaces a session's own ids in a rule with their placeholders.

    A rule approved inside one session can mention that session (a route on
    the Managed Agents API, for instance). Before it becomes a starting grant for
    every later session, its ids must turn back into placeholders, or the
    grant would point every session at the first one.
    """
    swaps = {bindings.session_id: "{{SESSION_ID}}", bindings.environment_id: "{{ENVIRONMENT_ID}}"}
    if isinstance(value, str):
        for literal, placeholder in swaps.items():
            value = value.replace(literal, placeholder)
        return value
    if isinstance(value, list):
        return [generalize(v, bindings) for v in value]
    if isinstance(value, dict):
        return {k: generalize(v, bindings) for k, v in value.items()}
    return value


def has_placeholders(value: Any) -> bool:
    return bool(_PLACEHOLDER_RE.search(json.dumps(value)))


def canonical(value: Any) -> str:
    """A stable text form: equal for equal policies, whatever the key order."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def unenforced(rule: dict[str, Any]) -> str:
    """Why OpenShell would not enforce all of a rule's limits as written, or ""."""
    if not rule.get("binaries"):
        return "it lists no binaries, which the prover reads as no program and OpenShell's CLI as any program"
    for ep in rule.get("endpoints") or []:
        host = ep.get("host") or "an endpoint"
        if ep.get("protocol") and ep.get("enforcement") != "enforce":
            return (f"{host} names a protocol without enforcement enforce, "
                    "so OpenShell would log violations and forward them")
        if ep.get("tls") == "skip":
            return f"{host} sets tls skip, which turns off inspection of its requests"
        if ep.get("allowed_ips"):
            return f"{host} sets allowed_ips, which lets it resolve to addresses OpenShell otherwise blocks"
    return ""


def bad_deny(rule: dict[str, Any]) -> str:
    """Why one of a rule's deny rules cannot be relied on, or "".

    OpenShell 0.1.2's prover reads a REST deny rule with no path as "deny every
    path". Its enforcer matches a deny rule by path, so that one matches nothing.
    """
    for ep in rule.get("endpoints") or []:
        for deny in ep.get("deny_rules") or []:
            if not (deny.get("method") and deny.get("path")):
                return (f"{ep.get('host') or 'an endpoint'} has a deny rule without both a method and a path, "
                        "which OpenShell proves as a denial and does not enforce")
    return ""


def without_denies(rule: dict[str, Any]) -> dict[str, Any]:
    """The rule with its deny rules dropped: everything it could allow."""
    return {**rule, "endpoints": [{k: v for k, v in ep.items() if k != "deny_rules"}
                                  for ep in rule.get("endpoints") or []]}


def destinations(rule: dict[str, Any]) -> set[str]:
    """Every host:port a rule's endpoints name."""
    return {f"{str(ep.get('host', '')).lower()}:{port}"
            for ep in rule.get("endpoints") or [] for port in ep.get("ports") or [ep.get("port")]}


def rule_body(rule: dict[str, Any]) -> dict[str, Any]:
    """The part of a rule that decides what it allows: everything but its name."""
    return {k: v for k, v in rule.items() if k != "name"}
