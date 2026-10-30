"""Settings, read from agentpolicy.yaml and then AGENTPOLICY_* environment variables.

Every path in the file is relative to the file's own directory, so the
repository works from any current directory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = "agentpolicy.yaml"

REVIEW_MODES = ("manual", "auto-within-ceiling", "claude")


@dataclass
class GatewaySettings:
    # Name of the OpenShell gateway registration to read the endpoint and
    # client certificate from. Empty means the active gateway.
    name: str = ""
    # Overrides the registered endpoint, for example https://127.0.0.1:17670.
    endpoint: str = ""
    # Overrides the directory holding ca.crt, tls.crt and tls.key.
    mtls_dir: str = ""
    # The server name the gateway certificate is checked against, when the
    # endpoint's host is not one of the certificate's names.
    tls_server_name: str = ""
    workspace: str = "default"


@dataclass
class ReviewSettings:
    mode: str = "auto-within-ceiling"
    # Gateway findings (OpenShell's own proposal risk check) normally send a
    # proposal to a person even when it is inside the ceiling. Set this to
    # let the Claude reviewer decide those too.
    reviewer_may_override_findings: bool = False


@dataclass
class ShrinkSettings:
    window_days: int = 14
    min_hits: int = 1


@dataclass
class ProfileSettings:
    # Whether agents on this profile may ask for more access at all. Off, every
    # proposal is rejected and the agent works within its starting policy:
    # the right setting for production. Growing access is for the sessions in
    # which a profile's ceiling and starting grants are worked out.
    proposals: bool = False
    # The agents that may run on this profile, by id. Empty admits any agent
    # whose session lands in an environment mapped to the profile.
    agents: list[str] = field(default_factory=list)
    # Admit a session whose agent has web tools, MCP servers or sub-agents.
    # Those run on Anthropic's side, where the ceiling does not apply.
    outside_routes: bool = False


@dataclass
class BreakerSettings:
    # Stop a session (``agentpolicy stop``) once this many of its proposals have
    # been rejected. 0 turns the count off.
    max_rejections: int = 3
    # Stop a session at the first rejection with one of these codes.
    stop_on: list[str] = field(default_factory=lambda: ["suspicious"])


@dataclass
class Settings:
    root: Path
    policy_dir: Path
    state_dir: Path
    # The Managed Agents API as a sandbox reaches it. The base policy's worker
    # routes name this host and port, and the worker in each sandbox is
    # pointed at this URL, so the two cannot disagree.
    api_scheme: str = "https"
    api_host: str = "api.anthropic.com"
    api_port: int = 443
    prover: str = "openshell-prover"
    prover_timeout: str = "10s"
    require_signed_ceiling: bool = True
    signers_file: Path | None = None
    # Refuse a signers file this process could write. Turn on in production,
    # where the policy owner, not the service account, owns that file.
    protect_signers: bool = False
    sandbox_label: str = "openshell-policy"
    gateway: GatewaySettings = field(default_factory=GatewaySettings)
    review: ReviewSettings = field(default_factory=ReviewSettings)
    shrink: ShrinkSettings = field(default_factory=ShrinkSettings)
    breaker: BreakerSettings = field(default_factory=BreakerSettings)
    # Per-profile settings. A profile not listed gets the defaults.
    profiles: dict[str, ProfileSettings] = field(default_factory=dict)
    # Which profile each Managed Agents environment's sessions run under. The operator
    # sets this on the sandbox host; nothing a session or agent carries can
    # change it. Entries here win over the environments file.
    environments: dict[str, str] = field(default_factory=dict)
    # The operator's environment-to-profile map, written by
    # ``agentpolicy environment set``. Default: <state_dir>/environments.yaml.
    environments_file: Path | None = None
    # Where agents/, environments/ and claude-lock.json are (`ant apply`).
    project_dir: Path | None = None

    def profile_settings(self, profile: str) -> ProfileSettings:
        return self.profiles.get(profile) or ProfileSettings()

    @property
    def environments_path(self) -> Path:
        return self.environments_file or self.state_dir / "environments.yaml"

    @property
    def sandbox_base_url(self) -> str:
        return f"{self.api_scheme}://{self.api_host}:{self.api_port}"

    @property
    def base_path(self) -> Path:
        return self.policy_dir / "base.yaml"

    def profile_dir(self, profile: str) -> Path:
        return self.policy_dir / "profiles" / profile

    @property
    def ledger_path(self) -> Path:
        return self.state_dir / "ledger.jsonl"

    @property
    def ocsf_dir(self) -> Path:
        return self.state_dir / "ocsf"

    @property
    def denied_dir(self) -> Path:
        """Outside ocsf_dir, so promote and shrink never read it."""
        return self.state_dir / "denied"


class ConfigMissing(ValueError):
    """No config file where one was asked for."""


def _merge_dataclass(obj: Any, values: dict[str, Any] | None) -> None:
    for key, value in (values or {}).items():
        if not hasattr(obj, key):
            raise ValueError(f"unknown setting {type(obj).__name__}.{key}")
        setattr(obj, key, value)


def load(path: str | os.PathLike[str] | None = None) -> Settings:
    path = Path(path or os.environ.get("AGENTPOLICY_CONFIG") or DEFAULT_CONFIG).resolve()
    if not path.is_file():
        # Defaults would point every command, the kill switch included, at a
        # state directory no dispatcher reads.
        raise ConfigMissing(f"no config at {path}; run from the directory that holds {DEFAULT_CONFIG}, "
                            "or pass --config or set AGENTPOLICY_CONFIG")
    data: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
    root = path.parent

    def rel(value: str | None, default: str) -> Path:
        return (root / (value or default)).resolve()

    s = Settings(
        root=root,
        policy_dir=rel(data.pop("policy_dir", None), "policy"),
        state_dir=rel(data.pop("state_dir", None), "state"),
    )
    s.signers_file = rel(data.pop("signers_file", None), "policy/signers.yaml")
    _merge_dataclass(s.gateway, data.pop("gateway", None))
    _merge_dataclass(s.review, data.pop("review", None))
    _merge_dataclass(s.shrink, data.pop("shrink", None))
    _merge_dataclass(s.breaker, data.pop("breaker", None))
    for name, values in (data.pop("profiles", None) or {}).items():
        ps = ProfileSettings()
        _merge_dataclass(ps, values)
        s.profiles[str(name)] = ps
    s.environments = {str(k): str(v) for k, v in (data.pop("environments", None) or {}).items()}
    s.project_dir = rel(data.pop("project_dir", None), ".")
    environments_file = data.pop("environments_file", None)
    if environments_file:
        s.environments_file = rel(environments_file, "")
    _merge_dataclass(s, data)

    env = os.environ
    if "AGENTPOLICY_API_SCHEME" in env:
        s.api_scheme = env["AGENTPOLICY_API_SCHEME"]
    if "AGENTPOLICY_API_HOST" in env:
        s.api_host = env["AGENTPOLICY_API_HOST"]
    if "AGENTPOLICY_API_PORT" in env:
        s.api_port = int(env["AGENTPOLICY_API_PORT"])
    if "AGENTPOLICY_PROVER" in env:
        s.prover = env["AGENTPOLICY_PROVER"]
    if "AGENTPOLICY_STATE_DIR" in env:
        s.state_dir = Path(env["AGENTPOLICY_STATE_DIR"]).resolve()
    if "AGENTPOLICY_REVIEW_MODE" in env:
        s.review.mode = env["AGENTPOLICY_REVIEW_MODE"]
    if "AGENTPOLICY_GATEWAY_ENDPOINT" in env:
        s.gateway.endpoint = env["AGENTPOLICY_GATEWAY_ENDPOINT"]

    if s.review.mode not in REVIEW_MODES:
        raise ValueError(f"review.mode must be one of {REVIEW_MODES}, got {s.review.mode!r}")
    s.api_port = int(s.api_port)
    return s
