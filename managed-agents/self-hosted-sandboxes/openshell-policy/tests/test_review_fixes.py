"""Behaviors added after review: retries, isolation, evidence and trust-root checks."""

from __future__ import annotations

import os
import time

import pytest
from conftest import ENV, SESSION, FakeGateway, curl_rule, proposal
from test_loop import DAY, http_allowed, write_ocsf

from agentpolicy import config, grow, promote, shrink
from agentpolicy.policyfile import Bindings
from agentpolicy.store import CeilingError, Store

OTHER = "sesn_011Cother0000000000zz"


def grower(settings, store, gw, prover):
    return grow.Grower(settings, store, gw, prover, log=lambda _: None)


def test_proposal_without_gateway_verdict_waits_then_is_decided(settings, store, prover):
    gw = FakeGateway()
    sb = gw.add_sandbox()
    p = proposal(store, settings, curl_rule(), findings="")
    gw.pending[sb.name] = [p]
    g = grower(settings, store, gw, prover)
    g.run_once()
    assert not gw.approved and not list(store.ledger("decision"))
    p.validation_result = "prover: no new findings"  # the gateway's check finished
    g.run_once()
    assert len(gw.approved) == 1


def test_proposal_that_never_gets_a_verdict_goes_to_a_person(settings, store, prover):
    gw = FakeGateway()
    sb = gw.add_sandbox()
    gw.pending[sb.name] = [proposal(store, settings, curl_rule(), findings="")]
    g = grower(settings, store, gw, prover)
    for _ in range(grow.MAX_ATTEMPTS):
        g.run_once()
    decisions = list(store.ledger("decision"))
    assert len(decisions) == 1 and decisions[0]["action"] == "escalate"


class FlakyGateway(FakeGateway):
    def __init__(self, failures: int) -> None:
        super().__init__()
        self.failures = failures

    def approve(self, sandbox, chunk_id, review_token):
        if self.failures:
            self.failures -= 1
            raise RuntimeError("sandbox is restarting")
        super().approve(sandbox, chunk_id, review_token)


class CountingProver:
    def __init__(self, inner) -> None:
        self.inner, self.calls = inner, 0

    def check(self, c, b):
        self.calls += 1
        return self.inner.check(c, b)


def test_gateway_refusal_retries_the_same_decision(settings, store, prover):
    gw = FlakyGateway(failures=2)
    sb = gw.add_sandbox()
    gw.pending[sb.name] = [proposal(store, settings, curl_rule())]
    counting = CountingProver(prover)
    g = grower(settings, store, gw, counting)
    for _ in range(3):
        g.run_once()
    assert len(gw.approved) == 1
    assert counting.calls == 1  # decided once, applied on the third try
    assert len(list(store.ledger("decision_failed"))) == 2


def test_persistent_gateway_refusal_escalates(settings, store, prover):
    gw = FlakyGateway(failures=99)
    sb = gw.add_sandbox()
    gw.pending[sb.name] = [proposal(store, settings, curl_rule())]
    g = grower(settings, store, gw, prover)
    for _ in range(grow.MAX_ATTEMPTS + 1):
        g.run_once()
    decisions = list(store.ledger("decision"))
    assert [d["code"] for d in decisions] == ["gateway_refused"] and not list(store.ledger("grant"))


class BrokenSandboxGateway(FakeGateway):
    def proposals(self, sandbox, status="pending"):
        if sandbox == "shs-broken":
            raise RuntimeError("sandbox not found")
        return super().proposals(sandbox, status)


def test_one_broken_sandbox_does_not_stall_the_rest(settings, store, prover):
    gw = BrokenSandboxGateway()
    broken = gw.add_sandbox(session=OTHER)
    broken.name = "shs-broken"
    sb = gw.add_sandbox()
    gw.pending[sb.name] = [proposal(store, settings, curl_rule())]
    grower(settings, store, gw, prover).run_once()
    assert len(gw.approved) == 1


def test_approvals_made_at_the_gateway_become_grants(settings, store, prover):
    gw = FakeGateway()
    sb = gw.add_sandbox()
    approved = proposal(store, settings, curl_rule(), chunk_id="by-hand")
    approved.status = "approved"
    gw.approved_elsewhere[sb.name] = [approved]
    g = grower(settings, store, gw, prover)
    g.run_once()
    g.run_once()
    grants = list(store.ledger("grant"))
    assert len(grants) == 1 and grants[0]["approved_by"] == "gateway" and grants[0]["chunk_id"] == "by-hand"


def test_promotion_counts_only_the_granting_sessions_use(settings, store, prover):
    store.record("grant", profile="hello", session_id=SESSION, environment_id=ENV,
                 rule_name="allow_example_com_443", rule=curl_rule())
    now = int(time.time() * 1000)
    # Another session used a rule of the same name; that is not this grant's use.
    write_ocsf(settings, "hello", [http_allowed("allow_example_com_443", "GET", "/", now)], session=OTHER)
    plan = promote.plan(settings, store, prover, "hello")
    assert not plan.add and "by its session" in plan.skipped[0][1]
    write_ocsf(settings, "hello", [http_allowed("allow_example_com_443", "GET", "/", now)], name="mine.jsonl")
    assert list(promote.plan(settings, store, prover, "hello").add) == ["allow_example_com_443"]


def test_shrink_refuses_when_a_dispatched_session_left_no_evidence(settings, store, prover):
    rule = curl_rule()
    store.write_grants("hello", {"network_policies": {rule["name"]: rule}})
    now = int(time.time() * 1000)
    write_ocsf(settings, "hello", [http_allowed("claude_managed_agents", "GET", "/", now - 20 * DAY)], name="old.jsonl", session=OTHER)
    store.record("dispatch", profile="hello", session_id=SESSION, environment_id=ENV, proof="within_boundary")
    p = shrink.plan(settings, store, prover, "hello", window_days=14, now_ms=now)
    assert p.refused and "left no OCSF records" in p.refused
    p = shrink.plan(settings, store, prover, "hello", window_days=14, now_ms=now, allow_missing_evidence=True)
    assert not p.refused and [n for n, _ in p.removed] == [rule["name"]]


def test_torn_ledger_line_is_skipped(settings, store):
    store.record("decision", sandbox="a", chunk_id="1")
    with open(settings.ledger_path, "a") as fh:
        fh.write('{"ts": "2026-10-08T00:00:00+00:00", "kind": "dec')  # writer killed mid-line
    store.record("decision", sandbox="b", chunk_id="2")
    assert [e["sandbox"] for e in store.ledger("decision")] == ["a", "b"]


def test_signature_covers_the_api_address(repo, monkeypatch):
    monkeypatch.setenv("AGENTPOLICY_API_HOST", "attacker.example")
    s = config.load(repo / "agentpolicy.yaml")
    with pytest.raises(CeilingError, match="API address"):
        Store(s).ceiling("hello", Bindings(SESSION, ENV, s.api_host, s.api_port))


def test_writable_signers_file_is_refused(settings, store):
    os.chmod(settings.signers_file, 0o666)
    with pytest.raises(CeilingError, match="writable by its group or by others"):
        store.verify_ceiling("hello")
    os.chmod(settings.signers_file, 0o644)
    settings.protect_signers = True
    with pytest.raises(CeilingError, match="owns or can write"):
        store.verify_ceiling("hello")
    # Read-only is not enough: its owner can change the mode back, or rename another file over it.
    os.chmod(settings.signers_file, 0o444)
    with pytest.raises(CeilingError):
        store.verify_ceiling("hello")


def test_protect_signers_looks_at_the_owner_and_every_directory_above(settings, store, monkeypatch):
    settings.protect_signers = True
    me = os.stat(settings.signers_file).st_uid
    monkeypatch.setattr(os, "access", lambda p, m: False)
    monkeypatch.setattr(os, "geteuid", lambda: me + 1)  # someone else owns the file and its directories
    assert store.verify_ceiling("hello") == "owner@example.com"
    monkeypatch.setattr(os, "access", lambda p, m: str(p) == str(settings.signers_file.parent))
    with pytest.raises(CeilingError, match=f"can write {settings.signers_file.parent},"):
        store.verify_ceiling("hello")
