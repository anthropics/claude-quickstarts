"""The audit collector: strict shorthand parsing, policy checks, gaps."""

from __future__ import annotations

import json
import time

import pytest
from conftest import AGENT, SESSION, FakeGateway, curl_rule
from test_loop import DAY, http_allowed, write_ocsf

from agentpolicy import audit, ocsf, shorthand, shrink
from agentpolicy.gateway import CursorLost, LogEvent

T = 1791505486700

# Lines as an OpenShell 0.1.2 supervisor streamed them.
NET_OK = "NET:OPEN [INFO] ALLOWED /usr/local/bin/ant(0) -> host.openshell.internal:8400 [policy:claude_managed_agents engine:opa]"
HTTP_OK = "HTTP:GET [INFO] ALLOWED GET http://host.openshell.internal:8400/v1/sessions/sesn_1 [policy:claude_managed_agents engine:l7]"


def test_real_lines_parse():
    r = shorthand.parse(NET_OK, T, "u1")
    assert r["class_uid"] == ocsf.NETWORK and r["firewall_rule"]["name"] == "claude_managed_agents"
    assert r["actor"]["process"]["name"] == "/usr/local/bin/ant"
    assert r["dst_endpoint"] == {"domain": "host.openshell.internal", "port": 8400}
    r = shorthand.parse(HTTP_OK, T, "u2")
    assert r["class_uid"] == ocsf.HTTP and r["http_request"]["url"]["path"] == "/v1/sessions/sesn_1"
    # The engine tag is optional in OpenShell's own examples.
    assert shorthand.parse("HTTP:GET [INFO] ALLOWED GET http://api.github.com/zen [policy:github_api]", T, "u")


@pytest.mark.parametrize("line", [
    # Denials, and non-network events, are not evidence of use.
    "NET:OPEN [MED] DENIED /usr/bin/curl(0) -> example.com:443 [reason:transparent_tcp_policy_denied]",
    "SSH:OPEN [INFO] ALLOWED",
    # A second policy token planted in the agent's request path.
    "HTTP:GET [INFO] ALLOWED GET http://a.example/x[policy:wide engine:l7] [policy:narrow engine:l7]",
    "HTTP:GET [INFO] ALLOWED GET http://a.example/x [policy:wide engine:l7] [policy:narrow engine:l7]",
    # A planted line after a newline in the path or the binary name.
    "HTTP:GET [INFO] ALLOWED GET http://a.example/x\nHTTP:GET [INFO] ALLOWED GET http://b.example/ [policy:wide engine:l7]",
    "NET:OPEN [INFO] ALLOWED /tmp/x\r(1) -> a.example:443 [policy:r engine:opa]",
    # A binary name carrying its own arrow or brackets.
    "NET:OPEN [INFO] ALLOWED /tmp/x -> b.example:443 [policy:wide](1) -> a.example:443 [policy:r engine:opa]",
    "NET:OPEN [INFO] ALLOWED /tmp/a(b)(1) -> a.example:443 [policy:r engine:opa]",
    # A space in the binary or path: the agent's text would run into ours.
    "NET:OPEN [INFO] ALLOWED /tmp/my bin(1) -> a.example:443 [policy:r engine:opa]",
    "HTTP:GET [INFO] ALLOWED GET http://a.example/a b [policy:r engine:l7]",
    # Anything after the policy token.
    "NET:OPEN [INFO] ALLOWED /usr/bin/curl(1) -> a.example:443 [policy:r engine:opa] trailing",
    # A method that disagrees with the event, a bad port, a bad host.
    "HTTP:GET [INFO] ALLOWED POST http://a.example/ [policy:r engine:l7]",
    "NET:OPEN [INFO] ALLOWED /usr/bin/curl(1) -> a.example:99999 [policy:r engine:opa]",
    "NET:OPEN [INFO] ALLOWED /usr/bin/curl(1) -> a_b.example:443 [policy:r engine:opa]",
    "HTTP:GET [INFO] ALLOWED GET http://user@a.example:bad/ [policy:r engine:l7]",
    # A rule name outside the charset rule keys use.
    "NET:OPEN [INFO] ALLOWED /usr/bin/curl(1) -> a.example:443 [policy:r]x engine:opa]",
])
def test_hostile_or_foreign_lines_are_dropped(line):
    assert shorthand.parse(line, T, "u") is None


class LogGateway(FakeGateway):
    def __init__(self, rules, streams):
        super().__init__()
        self.rules = rules
        self.streams = list(streams)  # one list of events (or an exception) per watch
        self.cursors_asked: list[str] = []

    def policy_rules(self, sandbox):
        return dict(self.rules)

    def watch_logs(self, sandbox, cursor="", tail=100000):
        self.cursors_asked.append(cursor)
        stream = self.streams.pop(0)
        for ev in stream:
            if isinstance(ev, Exception):
                raise ev
            yield ev


def log(cursor, message, level="OCSF"):
    return LogEvent("log", cursor, level, message, T, "sb-1")


def test_collector_keeps_only_lines_its_policy_explains(settings, store):
    gw = LogGateway(
        {"claude_managed_agents": ["/usr/local/bin/ant"], "allow_example_com_443": ["/usr/bin/curl"]},
        [[
            log("c1", NET_OK),
            log("c2", HTTP_OK),
            log("c3", "NET:OPEN [INFO] ALLOWED /usr/bin/curl(5) -> example.com:443 [policy:allow_example_com_443 engine:opa]"),
            # A rule the sandbox does not have.
            log("c4", "NET:OPEN [INFO] ALLOWED /usr/bin/curl(5) -> evil.example:443 [policy:not_granted engine:opa]"),
            # A binary the rule does not list.
            log("c5", "NET:OPEN [INFO] ALLOWED /tmp/x(5) -> example.com:443 [policy:allow_example_com_443 engine:opa]"),
            log("c6", "an ordinary tracing line", level="INFO"),
        ]],
    )
    sb = gw.add_sandbox()
    kept = audit.Collector(settings, store, gw, log=lambda _m: None).follow(sb)
    assert kept == 3
    records = list(ocsf.read(ocsf.files(settings.ocsf_dir / "hello")))
    assert {r["firewall_rule"]["name"] for r in records} == {"claude_managed_agents", "allow_example_com_443"}
    assert all(ocsf.session_of(r) == SESSION for r in records)
    # Every record names the agent that made it.
    assert {(r["unmapped"]["managed_agents_agent_id"], r["unmapped"]["managed_agents_agent_version"]) for r in records} == {(AGENT, "3")}
    cursors = json.loads((settings.state_dir / "audit" / "cursors.json").read_text())
    assert cursors[sb.name]["cursor"] == "c6"


def test_collector_keeps_denied_lines_where_promote_and_shrink_never_read(settings, store):
    denied = "NET:OPEN [MED] DENIED /usr/bin/curl(0) -> api.github.com:443 [reason:transparent_tcp_policy_denied]"
    # Text the agent chose, shaped like an allowed line for a rule the sandbox holds.
    forged = "HTTP:GET [MED] DENIED GET http://a.example/x\n" + NET_OK
    gw = LogGateway({"claude_managed_agents": ["/usr/local/bin/ant"]}, [[
        log("c1", denied), log("c2", forged),
        log("c3", "HTTP:GET [MED] DENIED GET http://a.example/" + "x" * 5000 + " [reason:l7_denied]"),
        log("c4", "a tracing line that says DENIED too", level="INFO"),
        # An allowed request whose path says DENIED is not a denial.
        log("c5", "HTTP:GET [INFO] ALLOWED GET http://a.example/x DENIED y [policy:claude_managed_agents engine:l7]"),
    ]])
    sb = gw.add_sandbox()
    assert audit.Collector(settings, store, gw, log=lambda _m: None).follow(sb) == 0
    assert not ocsf.files(settings.ocsf_dir)  # none of it is evidence of use
    lines = (settings.denied_dir / "hello" / f"{SESSION}.jsonl").read_text().splitlines()
    records = [json.loads(line) for line in lines]
    assert [r["message"] for r in records][:2] == [denied, forged]  # one line each, newline and all
    assert [r["cursor"] for r in records] == ["c1", "c2", "c3"]
    # A padded line keeps the supervisor's reason, which comes last.
    long = records[2]
    assert long["truncated"] and len(long["message"]) == audit.MAX_DENIED_CHARS and long["message"].endswith("[reason:l7_denied]")
    assert {(r["session_id"], r["profile"], r["agent_id"], r["agent_version"]) for r in records} == {(SESSION, "hello", AGENT, "3")}


def test_a_session_cannot_fill_the_disk_with_denials(settings, store, monkeypatch):
    monkeypatch.setattr(audit, "MAX_DENIED_BYTES", 1000)
    line = "NET:OPEN [MED] DENIED /usr/bin/curl(0) -> api.github.com:443 [reason:transparent_tcp_policy_denied]"
    gw = LogGateway({}, [[log(f"c{i}", line) for i in range(100)]])
    said: list[str] = []
    audit.Collector(settings, store, gw, log=said.append).follow(gw.add_sandbox())
    out = settings.denied_dir / "hello" / f"{SESSION}.jsonl"
    records = [json.loads(x) for x in out.read_text().splitlines()]
    assert out.stat().st_size < 2000 and records[-1]["full"] and not any(r.get("full") for r in records[:-1])
    assert len([m for m in said if "is full" in m]) == 1


def test_collector_resumes_and_records_gaps(settings, store):
    gw = LogGateway({"claude_managed_agents": ["/usr/local/bin/ant"]}, [
        [log("c1", NET_OK), LogEvent("gap", "", "", "lagged 12 messages", 0, ""), CursorLost("trimmed")],
        [log("d1", NET_OK)],
    ])
    sb = gw.add_sandbox()
    c = audit.Collector(settings, store, gw, log=lambda _m: None)
    assert c.follow(sb) == 2
    assert gw.cursors_asked == ["", ""]  # after the loss it starts over, not from the lost cursor
    reasons = [e["reason"] for e in store.ledger("audit_gap", profile="hello")]
    assert len(reasons) == 2 and "lagged" in reasons[0] and "resume" in reasons[1]

    gw.streams.append([])
    audit.Collector(settings, store, gw, log=lambda _m: None).follow(sb)
    assert gw.cursors_asked[-1] == "d1"  # a restarted collector resumes where it stopped


def test_shrink_refuses_a_window_with_an_audit_gap(settings, store, prover):
    rule = curl_rule()
    store.write_grants("hello", {"network_policies": {rule["name"]: rule}})
    now = int(time.time() * 1000)
    write_ocsf(settings, "hello", [http_allowed("claude_managed_agents", "GET", "/", now - 20 * DAY)], name="old.jsonl")
    store.record("audit_gap", profile="hello", session_id=SESSION, sandbox="shs-x", reason="lagged")
    p = shrink.plan(settings, store, prover, "hello", window_days=14, now_ms=now)
    assert p.refused and "gap" in p.refused
    p = shrink.plan(settings, store, prover, "hello", window_days=14, now_ms=now, allow_missing_evidence=True)
    assert not p.refused


def test_collector_outlives_a_gateway_that_stops_answering(settings, store):
    import threading

    stop, lines = threading.Event(), []

    class Down(FakeGateway):
        def list_sandboxes(self, app_label):
            stop.set()
            raise RuntimeError("UNAVAILABLE")

    audit.Collector(settings, store, Down(), log=lines.append).run(interval=0, stop=stop)
    assert "trying again" in lines[0]
