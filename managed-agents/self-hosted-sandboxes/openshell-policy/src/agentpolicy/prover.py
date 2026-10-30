"""The boundary check, run by OpenShell's own prover.

agentpolicy never decides containment itself. Every "is this inside the
ceiling" and "is this new policy no wider than the old one" question goes to
``openshell-prover check``, and only its ``within_boundary`` result counts as
a pass.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from . import policyfile

WITHIN = "within_boundary"
UNENFORCED = "unenforced_rule"


@dataclass
class Proof:
    """One prover result.

    ``result`` is the prover's own word: within_boundary, exceeds_boundary,
    error, invalid_input, unsupported, or inconclusive. Only within_boundary
    passes, and only exceeds_boundary says the candidate is too wide: the rest
    are no answer.
    """

    result: str
    counterexample: dict[str, Any] | None = None
    reason: str | None = None
    reason_code: str | None = None
    coverage: list[str] = field(default_factory=list)
    raw: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return self.result == WITHIN

    def summary(self) -> str:
        """One line a person or an agent can act on."""
        if self.ok:
            return "within the ceiling"
        if self.result == "exceeds_boundary" and self.counterexample:
            return "exceeds the ceiling, for example " + describe_counterexample(self.counterexample)
        detail = self.reason or self.reason_code or "no detail"
        return f"prover result {self.result}: {detail}"


def describe_counterexample(ce: dict[str, Any]) -> str:
    domain = ce.get("domain")
    if domain == "network":
        target = f"{ce.get('host')}:{ce.get('port')}"
        request = " ".join(p for p in (ce.get("method"), ce.get("path")) if p)
        who = ce.get("binary") or ce.get("ancestor_binary") or "any binary"
        return f"{who} reaching {target}" + (f" with {request}" if request else "")
    if domain == "filesystem":
        return f"{ce.get('access')} access to {ce.get('path')}"
    if domain == "process":
        return f"process {ce.get('field')} {ce.get('candidate')} (ceiling allows {ce.get('boundary')})"
    if domain == "landlock":
        return f"landlock {ce.get('candidate')} (ceiling requires {ce.get('boundary')})"
    return json.dumps(ce, sort_keys=True)


class Prover(Protocol):
    def check(self, candidate: dict[str, Any], boundary: dict[str, Any]) -> Proof: ...


class Enforced:
    """A prover whose pass also needs OpenShell to enforce each rule as written.

    Two things, both about rules the boundary does not hold itself (a rule it
    does hold, a person signed). Neither can turn a failure into a pass.

    Their deny rules are dropped before the proof. A deny rule subtracts from
    what the prover counts, so a candidate could use one to hide access that
    the enforcer then allows: 0.1.2 proves a deny rule with no path as "deny
    everything" and enforces it as nothing. Proving the rule without its
    denies asks about everything it could allow, however they are enforced.

    Then a pass becomes ``unsupported`` if one is a rule
    ``policyfile.unenforced`` names. openshell-prover 0.1.2 already answers
    ``unsupported`` for audit mode and ``tls: skip``, and passes
    ``allowed_ips`` (tests/test_real_prover.py). Checking here keeps that from
    resting on how one prover release models those fields.

    A boundary with a deny rule that cannot be relied on proves nothing.
    """

    def __init__(self, inner: Prover) -> None:
        self.inner = inner

    def check(self, candidate: dict[str, Any], boundary: dict[str, Any]) -> Proof:
        for name, rule in policyfile.network_rules(boundary).items():
            why = policyfile.bad_deny(rule)
            if why:
                return Proof(result="unsupported", reason=f"boundary rule {name!r}: {why}", reason_code=UNENFORCED)
        signed = [policyfile.rule_body(r) for r in policyfile.network_rules(boundary).values()]
        rules = policyfile.network_rules(candidate)
        ours = {n: r for n, r in rules.items() if policyfile.rule_body(r) not in signed}
        widest = {**candidate, "network_policies": {
            n: policyfile.without_denies(r) if n in ours else r for n, r in rules.items()}}
        proof = self.inner.check(widest, boundary)
        if not proof.ok:
            return proof
        for name, rule in ours.items():
            why = policyfile.unenforced(rule)
            if why:
                return Proof(result="unsupported", reason=f"rule {name!r}: {why}", reason_code=UNENFORCED,
                             coverage=proof.coverage, raw=proof.raw)
        return proof


class CliProver:
    """Runs the openshell-prover binary that OpenShell's installer ships."""

    def __init__(self, binary: str = "openshell-prover", timeout: str = "10s") -> None:
        self.binary = binary
        self.timeout = timeout

    def check(self, candidate: dict[str, Any], boundary: dict[str, Any]) -> Proof:
        with tempfile.TemporaryDirectory(prefix="agentpolicy-proof-") as tmp:
            cand = Path(tmp) / "candidate.yaml"
            bound = Path(tmp) / "boundary.yaml"
            cand.write_text(policyfile.dump(candidate))
            bound.write_text(policyfile.dump(boundary))
            cmd = [
                self.binary, "check", str(cand),
                "--boundary", str(bound),
                "--output", "json",
                "--timeout", self.timeout,
            ]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            except FileNotFoundError:
                return Proof(result="error", reason=f"{self.binary} not found on PATH")
            except subprocess.TimeoutExpired:
                return Proof(result="inconclusive", reason="prover did not answer in 120 s")
        return parse_envelope(proc.stdout, proc.returncode, proc.stderr)


def parse_envelope(stdout: str, returncode: int, stderr: str = "") -> Proof:
    try:
        env = json.loads(stdout)
    except json.JSONDecodeError:
        return Proof(result="error", reason=(stderr or stdout or f"exit {returncode}").strip()[:500])
    result = env.get("result") or "error"
    # The exit code and the result must agree; a disagreement is a failure.
    expected = {WITHIN: 0, "exceeds_boundary": 1, "error": 2, "invalid_input": 2}.get(result, 3)
    if returncode != expected:
        return Proof(result="error", reason=f"prover said {result} but exited {returncode}", raw=env)
    return Proof(
        result=result,
        counterexample=env.get("counterexample"),
        reason=env.get("reason"),
        reason_code=env.get("reason_code"),
        coverage=list((env.get("coverage") or {}).get("domains") or []),
        raw=env,
    )
