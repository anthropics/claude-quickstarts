"""The shipped base and demo ceiling against the real openshell-prover.

Every other test uses a stand-in (fakeprover.py), which says nothing about how
OpenShell's prover answers. These run when ``openshell-prover`` is on PATH, as
it is in CI, and pin what the design relies on: the shipped policy proves, and
no way of loosening the demo rule comes back ``within_boundary``. Re-run them
before moving to another OpenShell release.
"""

from __future__ import annotations

import shutil

import pytest
from conftest import curl_rule

from agentpolicy import policyfile, profilecheck
from agentpolicy.policyfile import Bindings
from agentpolicy.prover import CliProver, Enforced

pytestmark = pytest.mark.skipif(not shutil.which("openshell-prover"), reason="openshell-prover not installed")


def check(store, settings, rule):
    b = Bindings.sample(settings.api_host, settings.api_port)
    candidate = policyfile.compose(store.base(b), {"network_policies": {rule["name"]: rule}})
    return CliProver().check(candidate, store.ceiling("hello", b))


def test_the_shipped_starting_policy_proves_inside_the_demo_ceiling(store, settings):
    # The boundary holds base.yaml's REST allow-list, a shape some prover builds call unsupported.
    proof = profilecheck.within_ceiling(settings, store, CliProver(), "hello", store.grants_template("hello"))
    assert proof.ok, proof.summary()
    assert {"network_l4", "network_rest"} <= set(proof.coverage)


@pytest.mark.parametrize("rule", [
    curl_rule(),
    curl_rule(access=None, rules=[{"allow": {"method": "GET", "path": "/"}}]),
], ids=["the ceiling's own rule", "narrower: one method and path"])
def test_inside_the_ceiling(store, settings, rule):
    proof = check(store, settings, rule)
    assert proof.ok, proof.summary()


def other_binary(path: str):
    return {**curl_rule(), "binaries": [{"path": path}]}


@pytest.mark.parametrize("rule, result", [
    (curl_rule("api.github.com"), "exceeds_boundary"),
    (curl_rule(access="read-write"), "exceeds_boundary"),
    (curl_rule(protocol=None, enforcement=None, access=None), "exceeds_boundary"),
    (other_binary("/usr/bin/bash"), "exceeds_boundary"),
    (other_binary("/usr/bin/*"), "exceeds_boundary"),
    (curl_rule(enforcement="audit"), "unsupported"),
    (curl_rule(enforcement=None), "unsupported"),
    (curl_rule(tls="skip"), "unsupported"),
    (curl_rule(allow_encoded_slash=True), "unsupported"),
], ids=["other host", "writes", "no L7 inspection", "a shell", "globbed binary", "audit mode",
        "enforcement left out", "tls skip", "encoded slashes"])
def test_every_way_of_loosening_the_demo_rule_fails(store, settings, rule, result):
    assert check(store, settings, rule).result == result


def test_allowed_ips_proves_inside_which_is_why_review_checks_it(store, settings):
    # prover.Enforced leaves it for a person. If this starts failing, the prover has caught up.
    assert check(store, settings, curl_rule(allowed_ips=["10.0.0.0/8"])).ok


def test_a_rule_with_no_binaries_proves_inside_which_is_why_review_checks_it(store, settings):
    # A live 0.1.2 sandbox agrees with the prover (no program matches). OpenShell's CLI calls it "any binary".
    assert check(store, settings, {**curl_rule(), "binaries": []}).ok


NO_PATH = [{"method": "*"}]
HIDDEN = [
    curl_rule("evil.example.net", access="full", deny_rules=NO_PATH),
    curl_rule(access="full", deny_rules=NO_PATH),
    curl_rule(access=None, rules=[{"allow": {"method": "POST", "path": "/**"}}], deny_rules=[{"method": "POST"}]),
    curl_rule("evil.example.net", access="full", deny_rules=[{"method": "*", "path": "/**"}]),
]
HIDDEN_IDS = ["a host the ceiling never names", "writes to the ceiling's host", "one method", "a deny that is enforced"]


@pytest.mark.parametrize("rule", HIDDEN[:3], ids=HIDDEN_IDS[:3])
def test_the_prover_alone_passes_access_hidden_behind_a_deny_rule_with_no_path(store, settings, rule):
    # It reads the deny as "every path". The enforcer matches deny rules by path, so this one matches
    # nothing: on a live 0.1.2 sandbox a POST to the unnamed host went out. If this starts failing, the
    # prover has caught up, and Enforced still costs nothing.
    assert check(store, settings, rule).ok


@pytest.mark.parametrize("rule", HIDDEN, ids=HIDDEN_IDS)
def test_a_candidate_cannot_hide_access_behind_its_own_deny_rules(store, settings, rule):
    b = Bindings.sample(settings.api_host, settings.api_port)
    candidate = policyfile.compose(store.base(b), {"network_policies": {rule["name"]: rule}})
    assert Enforced(CliProver()).check(candidate, store.ceiling("hello", b)).result == "exceeds_boundary"


def test_a_deny_rule_on_access_the_ceiling_allows_anyway_still_proves(store, settings):
    rule = curl_rule(deny_rules=[{"method": "GET", "path": "/private/**"}])
    b = Bindings.sample(settings.api_host, settings.api_port)
    candidate = policyfile.compose(store.base(b), {"network_policies": {rule["name"]: rule}})
    assert Enforced(CliProver()).check(candidate, store.ceiling("hello", b)).ok
