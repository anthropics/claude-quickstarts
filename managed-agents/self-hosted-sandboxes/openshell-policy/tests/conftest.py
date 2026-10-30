from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import fakeprover  # noqa: E402
from agentpolicy import config, signing  # noqa: E402
from agentpolicy.gateway import Proposal, SandboxRef  # noqa: E402
from agentpolicy.prover import parse_envelope  # noqa: E402
from agentpolicy.store import Store  # noqa: E402

SESSION = "sesn_011CabcDEF0123456789xyz"
ENV = "env_01ABCdef0123456789"
AGENT = "agent_011CagentXYZ0123"


class FakeProver:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def check(self, candidate: dict[str, Any], boundary: dict[str, Any]):
        self.calls.append((candidate, boundary))
        env = fakeprover.check(candidate, boundary)
        import json

        return parse_envelope(json.dumps(env), env["exit_code"])


class FakeGateway:
    def __init__(self) -> None:
        self.sandboxes: list[SandboxRef] = []
        self.pending: dict[str, list[Proposal]] = {}
        self.approved: list[tuple[str, str, str]] = []
        self.rejected: list[tuple[str, str, str]] = []
        self.approved_elsewhere: dict[str, list[Proposal]] = {}
        self.locked_down: list[str] = []
        self.stopped: list[str] = []
        self.fail: set[str] = set()

    def add_sandbox(self, profile: str = "hello", session: str = SESSION, env: str = ENV,
                    agent: str = AGENT) -> SandboxRef:
        sb = SandboxRef(name=f"shs-{session[-15:].lower()}", id="sb-1",
                        labels={"app": "openshell-policy", "profile": profile, "session": session, "environment": env,
                                "agent": agent, "agent_version": "3"})
        self.sandboxes.append(sb)
        self.pending.setdefault(sb.name, [])
        return sb

    def list_sandboxes(self, app_label: str):
        return [s for s in self.sandboxes if s.labels.get("app") == app_label]

    def proposals(self, sandbox: str, status: str = "pending"):
        if status == "approved":
            return list(self.approved_elsewhere.get(sandbox, []))
        return list(self.pending.get(sandbox, []))

    def approve(self, sandbox: str, chunk_id: str, review_token: str) -> None:
        self.approved.append((sandbox, chunk_id, review_token))
        self.pending[sandbox] = [p for p in self.pending[sandbox] if p.chunk_id != chunk_id]

    def reject(self, sandbox: str, chunk_id: str, reason: str) -> None:
        self.rejected.append((sandbox, chunk_id, reason))
        self.pending[sandbox] = [p for p in self.pending[sandbox] if p.chunk_id != chunk_id]

    def lock_down(self, sandbox: str) -> None:
        if "lock_down" in self.fail:
            raise RuntimeError("gateway said no")
        self.locked_down.append(sandbox)

    def stop_sandbox(self, sandbox: str) -> None:
        self.stopped.append(sandbox)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A copy of the repository's policy tree with a fresh signing key and signed ceilings."""
    shutil.copytree(ROOT / "policy", tmp_path / "policy", ignore=shutil.ignore_patterns("*.sig", "signers.yaml"))
    (tmp_path / "agentpolicy.yaml").write_text(
        "api_scheme: http\napi_host: host.openshell.internal\napi_port: 8400\nprofiles:\n  hello:\n    proposals: true\n")
    key_path = tmp_path / "owner.key"
    key = signing.generate(key_path)
    (tmp_path / "policy" / "signers.yaml").write_text(
        f"signers:\n  - identity: owner@example.com\n    public_key: {signing.public_key_text(key)}\n"
    )
    s = config.load(tmp_path / "agentpolicy.yaml")
    store = Store(s)
    for profile in store.profiles():
        store.sign_ceiling(profile, key_path, "owner@example.com")
    store.set_environment(ENV, "hello")
    return tmp_path


@pytest.fixture
def settings(repo: Path):
    return config.load(repo / "agentpolicy.yaml")


@pytest.fixture
def store(settings):
    return Store(settings)


@pytest.fixture
def prover():
    return FakeProver()


@pytest.fixture
def fake_prover_bin(tmp_path: Path) -> str:
    script = tmp_path / "openshell-prover"
    script.write_text(f"#!{sys.executable}\nimport sys\nsys.path.insert(0, {str(Path(__file__).parent)!r})\n"
                      "import fakeprover\nsys.exit(fakeprover.main(sys.argv))\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return str(script)


def curl_rule(host: str = "example.com", **ep: Any) -> dict[str, Any]:
    endpoint = {"host": host, "port": 443, "protocol": "rest", "enforcement": "enforce", "access": "read-only"}
    endpoint.update(ep)
    endpoint = {k: v for k, v in endpoint.items() if v is not None}
    return {"name": f"allow_{host.replace('.', '_')}_443", "endpoints": [endpoint], "binaries": [{"path": "/usr/bin/curl"}]}


def proposal(store: Store, settings, rule: dict[str, Any], chunk_id: str = "c1", token: str = "t1",
             findings: str = "prover: no new findings", session: str = SESSION, env: str = ENV,
             profile: str = "hello", **kw: Any) -> Proposal:
    from agentpolicy.policyfile import Bindings

    b = Bindings(session, env, settings.api_host, settings.api_port)
    candidate = store.starting_policy(profile, b)
    candidate["network_policies"][rule["name"]] = rule
    return Proposal(sandbox=f"shs-{session[-15:].lower()}", chunk_id=chunk_id, status="pending",
                    rule_name=rule["name"], rule=rule, validation_result=findings, review_token=token,
                    binary="/usr/bin/curl", hit_count=1, candidate_policy=candidate, **kw)


def run_cli_env(repo: Path, prover_bin: str, extra: dict[str, str], *args: str, stdin: str = ""):
    """Runs the agentpolicy command in a clean environment against a test repository."""
    import subprocess

    env = {"PYTHONPATH": str(ROOT / "src"), "AGENTPOLICY_PROVER": prover_bin, "PATH": "/usr/bin:/bin",
           "HOME": str(repo), **extra}  # never the developer's own `ant auth login`
    if "LD_LIBRARY_PATH" in os.environ:
        env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    return subprocess.run([sys.executable, "-m", "agentpolicy.cli", "--config", str(repo / "agentpolicy.yaml"), *args],
                          input=stdin, capture_output=True, text=True, env=env, cwd=repo)


os.environ.pop("AGENTPOLICY_CONFIG", None)
