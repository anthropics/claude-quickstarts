"""Deciding one proposal.

The order is fixed, and each step can only make the answer stricter:

1. The rule must translate cleanly (``convert``); otherwise a person decides.
2. The sandbox's policy with the rule must prove to stay inside the profile's
   signed ceiling. If it does not, the proposal is rejected with the
   prover's counterexample as guidance. No reviewer can override this.
3. OpenShell's own proposal risk check (the gateway's ``validation_result``)
   must report no new findings; otherwise a person decides, unless the
   operator lets the Claude reviewer take those too.
4. Depending on ``review.mode``:
   - ``manual``: record a recommendation and leave the proposal pending;
   - ``auto-within-ceiling``: approve;
   - ``claude``: ask the reviewer agent, which may approve, reject with
     guidance, or send the proposal to a person.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from . import policyfile
from .gateway import Proposal
from .prover import UNENFORCED, Proof, Prover
from .stop import GATEWAY_DRAFT

APPROVE = "approve"
REJECT = "reject"
ESCALATE = "escalate"  # leave pending for a person
# Not decided yet; ask again on a later pass. Used for conditions expected to
# clear on their own: the gateway has not run its risk check yet, the prover
# failed to run or timed out, the reviewer agent did not answer. The grow
# loop gives up and escalates after a few deferrals.
DEFER = "defer"
CLEAN = "prover: no new findings"


@dataclass
class Decision:
    action: str
    reason: str
    # A short machine-readable tag, mirrored at the front of rejection reasons
    # so the agent in the sandbox can tell why without parsing prose.
    code: str
    proof: Proof | None = None
    reviewer: str = "rules"
    details: dict[str, Any] = field(default_factory=dict)

    def rejection_text(self) -> str:
        return f"{self.code}: {self.reason}"


@dataclass
class Context:
    """What the reviewer knows about the session a proposal came from."""

    profile: str
    session_id: str
    ceiling: dict[str, Any]
    agent_description: str = ""
    # The host:port destinations in the profile's revoked.txt.
    revoked: frozenset[str] = frozenset()


class Reviewer(Protocol):
    """A judgement step that runs only after every deterministic gate passed."""

    name: str

    def review(self, proposal: Proposal, ctx: Context, proof: Proof) -> Decision: ...


def candidate_policy(proposal: Proposal, current: dict[str, Any] | None) -> dict[str, Any] | None:
    """The sandbox's policy as it would be with the proposal applied.

    The gateway reports this itself; recomputing it is the fallback.
    """
    if proposal.candidate_policy is not None:
        return proposal.candidate_policy
    if current is None or proposal.rule is None:
        return None
    name = proposal.rule_name
    policy = dict(current)
    rules = dict(policyfile.network_rules(current))
    if name in rules:
        return None
    rules[name] = proposal.rule
    policy["network_policies"] = rules
    return policy


def gateway_draft(p: Proposal) -> bool:
    """Whether this has the shape of the draft OpenShell files for each denied connection.

    That is one host and port with no protocol, named ``allow_<host>_<port>``.
    OpenShell 0.1.2 does not mark who wrote a proposal, so the shape is all
    there is to go on, and an agent can copy it. Copying it earns a rejection
    with no proof run and nothing else.
    """
    endpoints = (p.rule or {}).get("endpoints") or []
    if len(endpoints) != 1 or not isinstance(endpoints[0], dict) or endpoints[0].get("protocol"):
        return False
    host, port = str(endpoints[0].get("host", "")), endpoints[0].get("port")
    return p.rule_name.lower() == f"allow_{re.sub(r'[^a-z0-9]', '_', host.lower())}_{port}"


def decide(
    proposal: Proposal,
    ctx: Context,
    prover: Prover,
    mode: str,
    reviewer: Reviewer | None = None,
    reviewer_may_override_findings: bool = False,
    current_policy: dict[str, Any] | None = None,
) -> Decision:
    if proposal.application_error:
        return Decision(ESCALATE, f"the gateway cannot apply it: {proposal.application_error}", "not_applicable")
    if proposal.unsupported or proposal.rule is None:
        return Decision(ESCALATE, proposal.unsupported or "the proposal carries no rule", "needs_person")
    # Template syntax in a proposed rule, or a name no policy file may carry,
    # would later stop promotion for the whole profile. An agent has no reason
    # to write either.
    if policyfile.has_placeholders(proposal.rule):
        return Decision(REJECT, "the rule contains {{...}} template text; propose literal hosts and paths", "malformed_rule")
    try:
        policyfile.check_rule_name(proposal.rule_name)
    except policyfile.PolicyError:
        return Decision(REJECT, "the rule name must start with a letter or digit and use only letters, digits, '_', '.' or '-'", "malformed_rule")

    if gateway_draft(proposal):
        return Decision(REJECT, "OpenShell drafted this from a denied connection; nobody asked for it. To ask, propose "
                                "a rule of your own with protocol rest and the narrowest method and path that work.",
                        GATEWAY_DRAFT)

    candidate = candidate_policy(proposal, current_policy)
    if candidate is None:
        return Decision(ESCALATE, "the policy with this rule applied is not available to prove", "needs_person")

    proof = prover.check(candidate, ctx.ceiling)
    if not proof.ok:
        if proof.result == "exceeds_boundary":
            return Decision(
                REJECT,
                f"{proof.summary()}. Ask only for access this profile's ceiling allows: "
                "the same binary, host and port, with protocol rest, enforcement enforce, "
                "and the narrowest method and path that work."
                + (" A proposal's deny_rules are left out of the proof, so allow only what you need instead."
                   if policyfile.without_denies(proposal.rule) != proposal.rule else ""),
                "outside_ceiling",
                proof,
            )
        if proof.result == "error" or proof.reason_code == "solver_timeout":
            return Decision(DEFER, proof.summary(), "proof_failed_to_run", proof)
        # unsupported or inconclusive: the proof did not pass, but the rule was
        # not shown to be too broad either. A person decides.
        return Decision(ESCALATE, proof.summary(), UNENFORCED if proof.reason_code == UNENFORCED else "unproven", proof)

    again = sorted(policyfile.destinations(proposal.rule) & ctx.revoked)
    if again:
        return Decision(ESCALATE, f"inside the ceiling, but {again[0]} was taken away from the profile (revoked.txt)",
                        "revoked", proof)

    findings = proposal.validation_result.strip()
    if not findings:
        # The gateway fills this in once its own risk check has run.
        return Decision(DEFER, "waiting for OpenShell's risk check", "awaiting_gateway_check", proof)
    clean = findings == CLEAN
    if not clean and not (mode == "claude" and reviewer_may_override_findings):
        return Decision(
            ESCALATE,
            f"inside the ceiling, but OpenShell's risk check reported: {findings}",
            "risk_findings",
            proof,
        )

    if mode == "manual":
        return Decision(ESCALATE, "inside the ceiling; review mode is manual", "recommend_approve", proof)
    if mode == "auto-within-ceiling":
        return Decision(APPROVE, "inside the ceiling and OpenShell's risk check is clean", "within_ceiling", proof)
    if mode == "claude":
        if reviewer is None:
            return Decision(ESCALATE, "review mode is claude but no reviewer is configured", "needs_person", proof)
        decision = reviewer.review(proposal, ctx, proof)
        decision.proof = proof
        # A reviewer may narrow the outcome but never widen it past the gates.
        if decision.action not in (APPROVE, REJECT, ESCALATE, DEFER):
            return Decision(ESCALATE, f"reviewer returned {decision.action!r}", "needs_person", proof)
        return decision
    raise ValueError(f"unknown review mode {mode!r}")
