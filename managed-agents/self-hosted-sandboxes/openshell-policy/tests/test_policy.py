from __future__ import annotations

import shutil

import pytest
from conftest import ENV, SESSION, curl_rule

from agentpolicy import policyfile, signing
from agentpolicy.policyfile import Bindings, PolicyError
from agentpolicy.store import CeilingError


def b() -> Bindings:
    return Bindings(SESSION, ENV, "host.openshell.internal", 8400)


def test_base_renders_with_session_routes(store):
    base = store.base(b())
    rule = base["network_policies"]["claude_managed_agents"]
    ep = rule["endpoints"][0]
    assert ep["host"] == "host.openshell.internal" and ep["port"] == 8400
    paths = [r["allow"]["path"] for r in ep["rules"]]
    assert f"/v1/sessions/{SESSION}" in paths
    assert f"/v1/environments/{ENV}/work/*/heartbeat" in paths
    assert not policyfile.has_placeholders(base)


def test_unknown_placeholder_is_refused():
    with pytest.raises(PolicyError, match="unknown placeholder"):
        policyfile.render_text("host: {{NOPE}}", b())


def test_bindings_refuse_malformed_ids():
    with pytest.raises(PolicyError):
        Bindings("sesn_../../etc", ENV, "h", 1)
    with pytest.raises(PolicyError):
        Bindings(SESSION, ENV, "host; rm -rf /", 1)
    with pytest.raises(PolicyError):
        Bindings("sesn_a_b", ENV, "h", 1)


def test_compose_adds_grants_and_refuses_collisions(store):
    base = store.base(b())
    out = policyfile.compose(base, {"network_policies": {"example": curl_rule()}})
    assert set(out["network_policies"]) == {"claude_managed_agents", "example"}
    with pytest.raises(PolicyError, match="collides"):
        policyfile.compose(base, {"network_policies": {"claude_managed_agents": curl_rule()}})
    with pytest.raises(PolicyError, match="only add network_policies"):
        policyfile.compose(base, {"filesystem_policy": {"read_write": ["/"]}})


def test_generalize_replaces_session_ids():
    rule = {"endpoints": [{"rules": [{"allow": {"method": "GET", "path": f"/v1/sessions/{SESSION}/x"}}]}]}
    out = policyfile.generalize(rule, b())
    assert out["endpoints"][0]["rules"][0]["allow"]["path"] == "/v1/sessions/{{SESSION_ID}}/x"


def test_ceiling_signature_round_trip(store):
    assert store.verify_ceiling("hello") == "owner@example.com"
    ceiling = store.ceiling("hello", b())
    assert set(ceiling["network_policies"]) == {"claude_managed_agents", "example_com"}


def test_edited_ceiling_is_refused(store, settings):
    path = settings.profile_dir("hello") / "ceiling.yaml"
    path.write_text(path.read_text().replace("read-only", "full"))
    with pytest.raises(CeilingError, match="changed since"):
        store.ceiling("hello", b())


def test_edited_base_invalidates_every_ceiling(store, settings):
    settings.base_path.write_text(settings.base_path.read_text() + "\n# harmless?\n")
    with pytest.raises(CeilingError):
        store.verify_ceiling("hello")


def test_untrusted_signer_is_refused(store, settings):
    settings.signers_file.write_text("signers: []\n")
    with pytest.raises(CeilingError, match="not a trusted signer"):
        store.verify_ceiling("hello")


def test_starting_policy_proves_inside_ceiling(store, prover):
    assert prover.check(store.starting_policy("hello", b()), store.ceiling("hello", b())).ok


def test_write_grants_round_trips_placeholders(store):
    rule = curl_rule()
    rule["endpoints"][0]["path"] = "/v1/sessions/{{SESSION_ID}}"
    store.write_grants("hello", {"network_policies": {"x": rule}})
    rendered = store.grants("hello", b())
    assert rendered["network_policies"]["x"]["endpoints"][0]["path"] == f"/v1/sessions/{SESSION}"


def test_base_is_the_quickstarts_policy(repo):
    """policy/base.yaml, filled in for api.anthropic.com, grants exactly what ../openshell/policy.yaml does.

    Only the network rule's name may differ. A route the quickstart adds or
    drops must be made here too, and the ceilings signed again.
    """
    import yaml
    from conftest import ROOT

    hosted = Bindings(SESSION, ENV, "api.anthropic.com", 443)
    ours = yaml.safe_load(policyfile.render_text((ROOT / "policy" / "base.yaml").read_text(), hosted))
    quickstart_text = (ROOT.parent / "openshell" / "policy.yaml").read_text()
    theirs = yaml.safe_load(quickstart_text.replace("SESSION_ID", SESSION).replace("ENVIRONMENT_ID", ENV))
    strip = lambda rules: [{k: v for k, v in r.items() if k != "name"} for r in rules.values()]  # noqa: E731
    assert strip(ours.pop("network_policies")) == strip(theirs.pop("network_policies"))
    assert ours == theirs


def test_another_key_under_a_trusted_name_is_refused(store, tmp_path):
    signing.generate(tmp_path / "mine.key")
    store.sign_ceiling("hello", tmp_path / "mine.key", "owner@example.com")
    with pytest.raises(CeilingError):
        store.verify_ceiling("hello")


def test_one_profile_s_signature_does_not_fit_another(store, settings):
    other = settings.profile_dir("hello").with_name("other")
    shutil.copytree(settings.profile_dir("hello"), other)  # the same ceiling, byte for byte, and its signature
    with pytest.raises(CeilingError):
        store.verify_ceiling("other")


def test_revoked_txt_as_a_person_would_edit_it(store, settings):
    path = settings.profile_dir("hello") / "revoked.txt"
    path.write_text("# why\n  A.example:443  # after the incident\n\nb.example:80")  # no newline at the end
    store.write_revoked("hello", ["c.example:443"])
    assert store.revoked("hello") == {"a.example:443", "b.example:80", "c.example:443"}
    path.write_text("a.example\n")
    with pytest.raises(PolicyError, match="not a host:port"):
        store.revoked("hello")
