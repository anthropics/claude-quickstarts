"""The whole grow -> promote -> shrink loop against fakes."""

from __future__ import annotations

import json
import time

import pytest

from conftest import ENV, SESSION, FakeGateway, curl_rule, proposal

from agentpolicy import grow, ocsf, policyfile, promote, shrink

DAY = 86_400_000
OTHER = "sesn_011Cother0000000000zz"


def write_ocsf(settings, profile: str, records: list[dict], name: str = "s.jsonl", session: str = SESSION) -> None:
    d = settings.ocsf_dir / profile
    d.mkdir(parents=True, exist_ok=True)
    with open(d / name, "w") as fh:
        for i, r in enumerate(records):
            r.setdefault("metadata", {"uid": f"{name}-{i}"})
            r = ocsf.tag(r, session, profile)
            fh.write(json.dumps(r) + "\n")


def http_allowed(rule: str, method: str, path: str, t: int) -> dict:
    return {"class_uid": 4002, "action": "Allowed", "action_id": 1, "time": t,
            "firewall_rule": {"name": rule, "type": "l7"},
            "http_request": {"http_method": method, "url": {"hostname": "example.com", "path": path, "port": 443}},
            "actor": {"process": {"name": "/usr/bin/curl"}}}


def grow_once(settings, store, prover, rule):
    gw = FakeGateway()
    sb = gw.add_sandbox()
    gw.pending[sb.name] = [proposal(store, settings, rule)]
    logs: list[str] = []
    grow.run_once(settings, store, gw, prover, log=logs.append)
    return gw, logs


def test_grow_approves_inside_and_records_grant(settings, store, prover):
    gw, logs = grow_once(settings, store, prover, curl_rule())
    assert len(gw.approved) == 1 and not gw.rejected
    grants = list(store.ledger("grant", profile="hello"))
    assert grants and grants[0]["rule_name"] == "allow_example_com_443"


def test_grow_rejects_outside_with_guidance(settings, store, prover):
    gw, logs = grow_once(settings, store, prover, curl_rule("api.github.com"))
    assert not gw.approved
    assert gw.rejected[0][2].startswith("outside_ceiling: ")
    assert not list(store.ledger("grant"))


def test_grow_decides_each_token_once(settings, store, prover):
    gw = FakeGateway()
    sb = gw.add_sandbox()
    p = proposal(store, settings, curl_rule(), findings="prover: 1 new finding")
    gw.pending[sb.name] = [p]
    grow.run_once(settings, store, gw, prover, log=lambda _: None)
    grow.run_once(settings, store, gw, prover, log=lambda _: None)
    assert len(list(store.ledger("decision"))) == 1  # escalated once, not re-decided
    p.review_token = "t2"  # the gateway re-evaluated it
    grow.run_once(settings, store, gw, prover, log=lambda _: None)
    assert len(list(store.ledger("decision"))) == 2


def test_grow_skips_sandboxes_without_a_trusted_ceiling(settings, store, prover):
    (settings.profile_dir("hello") / "ceiling.yaml.sig").unlink()
    gw, logs = grow_once(settings, store, prover, curl_rule())
    assert not gw.approved and not gw.rejected
    assert any("not signed" in line for line in logs)


def test_promote_requires_use_then_writes_proved_grant(settings, store, prover):
    grow_once(settings, store, prover, curl_rule())
    plan = promote.plan(settings, store, prover, "hello")
    assert not plan.add and "used 0 time" in plan.skipped[0][1]

    write_ocsf(settings, "hello", [http_allowed("allow_example_com_443", "GET", "/", int(time.time() * 1000))])
    plan = promote.plan(settings, store, prover, "hello")
    assert list(plan.add) == ["allow_example_com_443"] and plan.ok
    promote.apply(store, plan)
    assert "allow_example_com_443" in policyfile.network_rules(store.grants_template("hello"))
    # Promoting again changes nothing.
    assert not promote.plan(settings, store, prover, "hello").add


def test_promote_refuses_what_the_ceiling_does_not_allow(settings, store, prover):
    # A grant recorded outside the reviewer (say, approved by hand at the
    # gateway) that the ceiling does not cover never becomes a starting grant.
    store.record("grant", profile="hello", session_id=SESSION, environment_id=ENV,
                 rule_name="allow_api_github_com_443", rule=curl_rule("api.github.com"))
    plan = promote.plan(settings, store, prover, "hello", require_use=False)
    assert not plan.add and not plan.ok and "exceeds" in plan.skipped[0][1]
    try:
        promote.apply(store, plan)
        raise AssertionError("apply should refuse")
    except policyfile.PolicyError:
        pass


def seed_grant(store, rule=None):
    rule = rule or curl_rule()
    store.write_grants("hello", {"network_policies": {rule["name"]: rule}})
    return rule["name"]


def test_shrink_refuses_without_evidence(settings, store, prover):
    seed_grant(store)
    p = shrink.plan(settings, store, prover, "hello")
    assert p.refused and "no OCSF records" in p.refused


def test_shrink_refuses_when_logs_do_not_cover_the_window(settings, store, prover):
    name = seed_grant(store)
    now = int(time.time() * 1000)
    write_ocsf(settings, "hello", [http_allowed("other", "GET", "/", now - 2 * DAY)])
    p = shrink.plan(settings, store, prover, "hello", window_days=14, now_ms=now)
    assert p.refused and "cover 2.0 of the 14 days" in p.refused


def test_shrink_removes_unused_grant_with_both_proofs(settings, store, prover):
    name = seed_grant(store)
    now = int(time.time() * 1000)
    write_ocsf(settings, "hello", [
        http_allowed(name, "GET", "/", now - 20 * DAY),  # used, but before the window
        http_allowed("claude_managed_agents", "POST", f"/v1/sessions/{SESSION}/events", now - 1 * DAY),
    ])
    p = shrink.plan(settings, store, prover, "hello", window_days=14, now_ms=now)
    assert [n for n, _ in p.removed] == [name]
    assert p.ok and p.no_wider.ok and p.within_ceiling.ok
    shrink.apply(store, p)
    assert not policyfile.network_rules(store.grants_template("hello"))


def test_shrink_keeps_a_used_grant(settings, store, prover):
    name = seed_grant(store)
    now = int(time.time() * 1000)
    write_ocsf(settings, "hello", [
        http_allowed(name, "GET", "/", now - 20 * DAY),
        http_allowed(name, "GET", "/index.html", now - DAY),
        http_allowed(name, "GET", "/index.html", now - DAY + 1),
    ])
    p = shrink.plan(settings, store, prover, "hello", window_days=14, now_ms=now)
    assert not p.changed and p.kept == [(name, 2)]


def test_ocsf_reader_handles_markers_and_duplicates(tmp_path):
    line = json.dumps(http_allowed("r", "GET", "/", 5) | {"metadata": {"uid": "u1"}})
    f1 = tmp_path / "a.jsonl"
    f1.write_text(f"2026-10-08T00:00:00Z INFO OCSF-JSON {line}\nnot json\n{line}\n")
    records = list(ocsf.read([f1, f1]))
    assert len(records) == 1
    use = ocsf.usage(records)
    assert use["r"].requests == 1


def test_ocsf_usage_ignores_denials_and_unnamed(tmp_path):
    records = [
        {"class_uid": 4001, "action": "Denied", "time": 1, "firewall_rule": {"name": "r"}},
        {"class_uid": 4001, "action": "Allowed", "time": 1, "firewall_rule": {"name": "-"}},
        {"class_uid": 4001, "action": "Allowed", "time": 1, "firewall_rule": {"name": "r"}},
    ]
    use = ocsf.usage(records)
    assert set(use) == {"r"} and use["r"].connections == 1


def test_grow_rejects_template_text(settings, store, prover):
    planted = curl_rule()
    planted["endpoints"][0]["path"] = "/{{NOPE}}"
    gw, _ = grow_once(settings, store, prover, planted)
    assert not gw.approved and gw.rejected[0][2].startswith("malformed_rule: ")


def test_grow_rejects_a_bad_rule_name(settings, store, prover):
    bad_name = {**curl_rule(), "name": "_bad name"}
    gw, _ = grow_once(settings, store, prover, bad_name)
    assert not gw.approved and gw.rejected[0][2].startswith("malformed_rule: ")


def test_promote_skips_a_bad_grant_and_promotes_the_rest(settings, store, prover):
    now = int(time.time() * 1000)
    good, bad = curl_rule(), curl_rule()
    bad["endpoints"][0]["path"] = "/{{NOPE}}"
    store.record("grant", profile="hello", session_id=SESSION, environment_id=ENV, rule_name="bad_rule", rule=bad)
    store.record("grant", profile="hello", session_id=SESSION, environment_id=ENV, rule_name=good["name"], rule=good)
    write_ocsf(settings, "hello", [http_allowed("bad_rule", "GET", "/", now), http_allowed(good["name"], "GET", "/", now)])
    plan = promote.plan(settings, store, prover, "hello")
    assert list(plan.add) == [good["name"]]
    assert any(n == "bad_rule" and "cannot be promoted" in why for n, why in plan.skipped)


def test_a_rule_openshell_would_not_enforce_is_never_promoted_and_blocks_nothing_else(settings, store, prover):
    """A person approved it at the gateway, for one session. It stays there."""
    from agentpolicy.prover import Enforced

    good, bad = curl_rule(), {**curl_rule(allowed_ips=["10.0.0.0/8"]), "name": "internal"}
    for rule in (good, bad):
        store.record("grant", profile="hello", session_id=SESSION, environment_id=ENV, rule_name=rule["name"], rule=rule)
    p = promote.plan(settings, store, Enforced(prover), "hello", require_use=False)
    assert p.ok and list(p.add) == [good["name"]]
    assert [n for n, why in p.skipped if "allowed_ips" in why] == ["internal"]


def used_grant(settings, store, prover, session=SESSION, name="s.jsonl"):
    """A session is approved the demo rule and uses it."""
    rule = curl_rule()
    store.record("grant", profile="hello", session_id=session, environment_id=ENV, rule_name=rule["name"], rule=rule)
    write_ocsf(settings, "hello", [http_allowed(rule["name"], "GET", "/", int(time.time() * 1000))], name=name, session=session)
    return rule


def test_what_shrink_removed_stays_out_until_a_person_deletes_the_line(settings, store, prover):
    rule = used_grant(settings, store, prover)
    promote.apply(store, promote.plan(settings, store, prover, "hello"))
    later = int(time.time() * 1000) + 30 * DAY
    write_ocsf(settings, "hello", [http_allowed("claude_managed_agents", "GET", "/", later - DAY)], name="other.jsonl", session=OTHER)
    p = shrink.plan(settings, store, prover, "hello", window_days=14, now_ms=later)
    assert [n for n, _ in p.removed] == [rule["name"]] and p.revoke == ["example.com:443"]
    shrink.apply(store, p)

    # Neither the old grant nor a new one, under any name or spelling, comes back.
    spelled = {**curl_rule(access=None, rules=[{"allow": {"method": "GET", "path": "/**"}}]), "name": "other_name"}
    store.record("grant", profile="hello", session_id=OTHER, environment_id=ENV, rule_name="other_name", rule=spelled)
    again = promote.plan(settings, store, prover, "hello", require_use=False)
    assert not again.add and all("example.com:443 is in revoked.txt" in why for _, why in again.skipped)

    path = settings.profile_dir("hello") / "revoked.txt"
    path.write_text(path.read_text().replace("example.com:443\n", ""))
    assert rule["name"] in promote.plan(settings, store, prover, "hello").add


def test_a_destination_another_grant_still_serves_is_not_revoked(settings, store, prover):
    used, unused = curl_rule(), {**curl_rule(access=None, rules=[{"allow": {"method": "GET", "path": "/x"}}]), "name": "unused"}
    store.write_grants("hello", {"network_policies": {used["name"]: used, "unused": unused}})
    now = int(time.time() * 1000)
    write_ocsf(settings, "hello", [http_allowed(used["name"], "GET", "/", now - 20 * DAY), http_allowed(used["name"], "GET", "/", now)])
    p = shrink.plan(settings, store, prover, "hello", window_days=14, now_ms=now)
    assert [n for n, _ in p.removed] == ["unused"] and p.revoke == []


@pytest.mark.parametrize("scope, target", [("session", SESSION), ("profile", "hello"), ("all", "")])
def test_a_stopped_session_s_grants_are_not_promoted_until_a_person_resumes_it(settings, store, prover, scope, target):
    rule = used_grant(settings, store, prover)
    store.record("stop", scope=scope, target=target, reason="breaker", by="breaker")
    p = promote.plan(settings, store, prover, "hello")
    assert not p.add and "is stopped" in p.skipped[0][1]
    store.record("resume", scope=scope, target=target, by="operator")
    assert list(promote.plan(settings, store, prover, "hello").add) == [rule["name"]]


def test_a_window_nobody_ran_in_removes_nothing(settings, store, prover):
    used_grant(settings, store, prover)
    promote.apply(store, promote.plan(settings, store, prover, "hello"))
    p = shrink.plan(settings, store, prover, "hello", window_days=14, now_ms=int(time.time() * 1000) + 30 * DAY)
    assert "no session left records" in p.refused and not p.removed


def test_a_grant_that_no_longer_proves_is_skipped_and_blocks_nothing_else(settings, store, prover):
    good = used_grant(settings, store, prover)
    bad = curl_rule("api.github.com")  # approved by hand at the gateway, say
    store.record("grant", profile="hello", session_id=SESSION, environment_id=ENV, rule_name=bad["name"], rule=bad)
    p = promote.plan(settings, store, prover, "hello", require_use=False)
    assert p.ok and list(p.add) == [good["name"]] and "exceeds" in dict(p.skipped)[bad["name"]]


def test_shrink_refuses_a_window_of_no_days(settings, store, prover):
    with pytest.raises(policyfile.PolicyError, match="at least one day"):
        shrink.plan(settings, store, prover, "hello", window_days=0)
