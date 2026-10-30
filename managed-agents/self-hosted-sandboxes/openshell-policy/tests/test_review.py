from __future__ import annotations

import pytest
from conftest import ENV, SESSION, curl_rule, proposal

from agentpolicy.policyfile import Bindings
from agentpolicy.prover import Enforced, Proof
from agentpolicy.review import APPROVE, ESCALATE, REJECT, Context, Decision, decide


def ctx(store, settings) -> Context:
    b = Bindings(SESSION, ENV, settings.api_host, settings.api_port)
    return Context(profile="hello", session_id=SESSION, ceiling=store.ceiling("hello", b))


def test_inside_ceiling_is_approved(store, settings, prover):
    p = proposal(store, settings, curl_rule())
    d = decide(p, ctx(store, settings), prover, "auto-within-ceiling")
    assert d.action == APPROVE and d.code == "within_ceiling"


def test_narrower_than_ceiling_is_approved(store, settings, prover):
    rule = curl_rule(access=None, rules=[{"allow": {"method": "GET", "path": "/"}}])
    d = decide(proposal(store, settings, rule), ctx(store, settings), prover, "auto-within-ceiling")
    assert d.action == APPROVE


def test_outside_ceiling_is_rejected_with_counterexample(store, settings, prover):
    d = decide(proposal(store, settings, curl_rule("api.github.com")), ctx(store, settings), prover, "auto-within-ceiling")
    assert d.action == REJECT and d.code == "outside_ceiling"
    assert "api.github.com:443" in d.reason
    assert d.rejection_text().startswith("outside_ceiling: ")


def test_wider_method_is_rejected(store, settings, prover):
    d = decide(proposal(store, settings, curl_rule(access="read-write")), ctx(store, settings), prover, "auto-within-ceiling")
    assert d.action == REJECT and "POST" in d.reason


def test_other_binary_is_rejected(store, settings, prover):
    rule = curl_rule()
    rule["binaries"] = [{"path": "/usr/bin/python3"}]
    d = decide(proposal(store, settings, rule), ctx(store, settings), prover, "auto-within-ceiling")
    assert d.action == REJECT


def test_l4_rule_is_rejected_under_l7_ceiling(store, settings, prover):
    rule = curl_rule(protocol=None, enforcement=None, access=None)
    d = decide(proposal(store, settings, rule), ctx(store, settings), prover, "auto-within-ceiling")
    assert d.action == REJECT


def test_audit_mode_is_unproven_and_escalated(store, settings, prover):
    d = decide(proposal(store, settings, curl_rule(enforcement="audit")), ctx(store, settings), prover, "auto-within-ceiling")
    assert d.action == ESCALATE and d.code == "unproven"


class Yes:
    """A prover that would pass anything: the check on a rule's shape must not depend on it."""

    def check(self, candidate, boundary):
        return Proof(result="within_boundary")


UNENFORCED_SHAPES = [
    {"enforcement": "audit"},
    {"enforcement": None},  # OpenShell's default is audit
    {"protocol": "websocket", "enforcement": None},
    {"tls": "skip"},
    {"allowed_ips": ["10.0.0.0/8"]},
]


@pytest.mark.parametrize("ep", UNENFORCED_SHAPES)
def test_a_rule_whose_limits_would_not_be_enforced_is_left_for_a_person(store, settings, ep):
    d = decide(proposal(store, settings, curl_rule(**ep)), ctx(store, settings), Enforced(Yes()), "auto-within-ceiling")
    assert d.action == ESCALATE and d.code == "unenforced_rule" and "example.com" in d.reason
    assert d.proof is not None and not d.proof.ok


def test_a_rule_that_lists_no_binaries_is_left_for_a_person(store, settings):
    rule = {**curl_rule(), "binaries": []}
    d = decide(proposal(store, settings, rule), ctx(store, settings), Enforced(Yes()), "auto-within-ceiling")
    assert d.action == ESCALATE and d.code == "unenforced_rule" and "no binaries" in d.reason


def test_outside_the_ceiling_is_still_rejected_whatever_the_rule_s_shape(store, settings, prover):
    # Or an agent could dodge the rejection, and the breaker that counts it.
    rule = curl_rule("api.github.com", allowed_ips=["140.82.0.0/16"])
    d = decide(proposal(store, settings, rule), ctx(store, settings), Enforced(prover), "auto-within-ceiling")
    assert d.action == REJECT and d.code == "outside_ceiling"


def test_a_shape_the_ceiling_itself_holds_passes():
    rule = curl_rule(allowed_ips=["10.0.0.0/8"])
    policy = {"network_policies": {"r": rule}}
    assert Enforced(Yes()).check(policy, {"network_policies": {"signed": {**rule, "name": "signed"}}}).ok
    assert not Enforced(Yes()).check(policy, {"network_policies": {"signed": curl_rule()}}).ok


def test_gateway_findings_escalate_even_inside_ceiling(store, settings, prover):
    p = proposal(store, settings, curl_rule(), findings="prover: 1 new finding\n  capability_expansion: ...")
    d = decide(p, ctx(store, settings), prover, "auto-within-ceiling")
    assert d.action == ESCALATE and d.code == "risk_findings"


def test_manual_mode_only_recommends(store, settings, prover):
    d = decide(proposal(store, settings, curl_rule()), ctx(store, settings), prover, "manual")
    assert d.action == ESCALATE and d.code == "recommend_approve"


def test_unsupported_and_inapplicable_escalate(store, settings, prover):
    p = proposal(store, settings, curl_rule(), unsupported="endpoint uses MCP options")
    assert decide(p, ctx(store, settings), prover, "auto-within-ceiling").action == ESCALATE
    p = proposal(store, settings, curl_rule(), application_error="merge failed")
    assert decide(p, ctx(store, settings), prover, "auto-within-ceiling").code == "not_applicable"


class StubReviewer:
    name = "stub"

    def __init__(self, action: str) -> None:
        self.action = action
        self.calls = 0

    def review(self, proposal, ctx, proof):
        self.calls += 1
        return Decision(self.action, "stub says so", "too_broad", reviewer=self.name)


def test_reviewer_runs_only_after_the_ceiling_proof(store, settings, prover):
    r = StubReviewer(APPROVE)
    d = decide(proposal(store, settings, curl_rule("api.github.com")), ctx(store, settings), prover, "claude", reviewer=r)
    assert d.action == REJECT and r.calls == 0


def test_reviewer_can_reject_inside_ceiling(store, settings, prover):
    r = StubReviewer(REJECT)
    d = decide(proposal(store, settings, curl_rule()), ctx(store, settings), prover, "claude", reviewer=r)
    assert d.action == REJECT and d.reviewer == "stub" and r.calls == 1


def test_reviewer_sees_findings_only_when_allowed(store, settings, prover):
    p = proposal(store, settings, curl_rule(), findings="prover: 1 new finding")
    r = StubReviewer(APPROVE)
    assert decide(p, ctx(store, settings), prover, "claude", reviewer=r).action == ESCALATE
    assert decide(p, ctx(store, settings), prover, "claude", reviewer=r, reviewer_may_override_findings=True).action == APPROVE


class Seen(Yes):
    def check(self, candidate, boundary):
        self.candidate = candidate
        return super().check(candidate, boundary)


def test_a_candidate_s_own_deny_rules_are_dropped_before_the_proof():
    # What they subtract in the proof, the enforcer may not subtract (tests/test_real_prover.py).
    inner = Seen()
    mine = curl_rule("a.example", access="full", deny_rules=[{"method": "*"}])
    signed = curl_rule(access="full", deny_rules=[{"method": "POST", "path": "/admin/**"}])
    Enforced(inner).check({"network_policies": {"mine": mine, "theirs": signed}}, {"network_policies": {"s": signed}})
    assert "deny_rules" not in inner.candidate["network_policies"]["mine"]["endpoints"][0]
    assert inner.candidate["network_policies"]["theirs"] == signed  # a person signed that one, denies and all


@pytest.mark.parametrize("deny", [{"method": "*"}, {"path": "/**"}, {"method": "POST", "path": ""}])
def test_a_boundary_with_a_deny_rule_that_is_not_enforced_proves_nothing(deny):
    rule = curl_rule(access="full", deny_rules=[deny])
    policy = {"network_policies": {"r": rule}}
    proof = Enforced(Yes()).check(policy, policy)
    assert not proof.ok and "deny rule" in proof.reason


def test_a_revoked_destination_is_left_for_a_person(store, settings, prover):
    store.write_revoked("hello", ["example.com:443"])
    b = Bindings(SESSION, ENV, settings.api_host, settings.api_port)
    c = Context(profile="hello", session_id=SESSION, ceiling=store.ceiling("hello", b), revoked=store.revoked("hello"))
    # The same access under another name, and spelled another way.
    spelled = curl_rule(access=None, rules=[{"allow": {"method": "GET", "path": "/**"}}])
    for again in ({**curl_rule(), "name": "another_name"}, {**spelled, "name": "third_name"}):
        d = decide(proposal(store, settings, again), c, prover, "auto-within-ceiling")
        assert d.action == ESCALATE and d.code == "revoked", again


@pytest.mark.parametrize("result", ["exceeds_boundary", "unsupported", "inconclusive", "invalid_input", "error", "", "yes"])
def test_nothing_but_within_boundary_is_ever_approved(store, settings, result):
    class Says:
        def check(self, candidate, boundary):
            return Proof(result=result)

    d = decide(proposal(store, settings, curl_rule()), ctx(store, settings), Says(), "auto-within-ceiling")
    assert d.action != APPROVE
