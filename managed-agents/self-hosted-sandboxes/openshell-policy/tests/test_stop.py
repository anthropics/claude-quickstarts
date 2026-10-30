"""Proposals off by default, the circuit breaker, the kill switch, agent identity and the environment map."""

from __future__ import annotations

import pytest
from conftest import AGENT, ENV, SESSION, FakeGateway, curl_rule, proposal, run_cli_env

from agentpolicy import config, grow
from agentpolicy.policyfile import PolicyError
from agentpolicy.stop import Scope, Stopper, active_stops, stopped

OTHER_SESSION = "sesn_011CotherSESSION98765"
NEW_ENV = "env_01NEWenv000000000"


def quiet(_: str) -> None:
    pass


def pend(gw, store, settings, sb, rules, session=SESSION):
    gw.pending[sb.name] = [proposal(store, settings, r, chunk_id=f"c{i}", token=f"t{i}", session=session)
                           for i, r in enumerate(rules)]


# ---- proposals --------------------------------------------------------------------


def test_a_profile_not_opted_in_gets_every_proposal_rejected_unreviewed(settings, store, prover):
    settings.profiles.clear()
    gw = FakeGateway()
    sb = gw.add_sandbox()
    pend(gw, store, settings, sb, [curl_rule()])
    grow.run_once(settings, store, gw, prover, log=quiet)
    assert not gw.approved and gw.rejected[0][2].startswith("proposals_disabled: ")
    assert not prover.calls  # nothing to prove: the answer is no either way
    assert not list(store.ledger("grant"))


def test_decisions_and_grants_name_the_agent(settings, store, prover):
    gw = FakeGateway()
    sb = gw.add_sandbox()
    pend(gw, store, settings, sb, [curl_rule()])
    grow.run_once(settings, store, gw, prover, log=quiet)
    for kind in ("decision", "grant"):
        (e,) = store.ledger(kind)
        assert e["agent_id"] == AGENT and e["agent_version"] == "3"


# ---- the circuit breaker ----------------------------------------------------------


def test_breaker_stops_a_session_after_max_rejections(settings, store, prover):
    gw = FakeGateway()
    sb = gw.add_sandbox()
    hosts = ["api.github.com", "evil.example", "pastebin.com", "one-more.example"]
    pend(gw, store, settings, sb, [curl_rule(h) for h in hosts])
    grow.run_once(settings, store, gw, prover, log=quiet)
    # The third rejection trips the breaker; the fourth proposal is never decided.
    assert len(gw.rejected) == 3
    assert gw.locked_down == [sb.name] and gw.stopped == [sb.name]
    (stop,) = active_stops(store)
    assert stop["by"] == "breaker" and stop["scope"] == "session" and stop["target"] == SESSION
    assert "3 proposals rejected" in stop["reason"]
    # Later passes decide nothing for it, even an approvable proposal.
    pend(gw, store, settings, sb, [curl_rule()])
    grow.run_once(settings, store, gw, prover, log=quiet)
    assert not gw.approved


def test_breaker_stops_at_once_on_a_listed_code(settings, store, prover):
    settings.breaker.stop_on = ["outside_ceiling"]
    gw = FakeGateway()
    sb = gw.add_sandbox()
    pend(gw, store, settings, sb, [curl_rule("api.github.com"), curl_rule()])
    grow.run_once(settings, store, gw, prover, log=quiet)
    assert len(gw.rejected) == 1 and not gw.approved and gw.stopped == [sb.name]
    assert "rejected as outside_ceiling" in active_stops(store)[0]["reason"]


def test_breaker_counts_per_session(settings, store, prover):
    gw = FakeGateway()
    a = gw.add_sandbox()
    b = gw.add_sandbox(session=OTHER_SESSION)
    pend(gw, store, settings, a, [curl_rule("api.github.com"), curl_rule("evil.example")])
    pend(gw, store, settings, b, [curl_rule("pastebin.com")], session=OTHER_SESSION)
    grow.run_once(settings, store, gw, prover, log=quiet)
    assert len(gw.rejected) == 3 and not gw.stopped and not active_stops(store)


def test_breaker_count_starts_over_after_a_resume(settings, store, prover):
    gw = FakeGateway()
    sb = gw.add_sandbox()
    pend(gw, store, settings, sb, [curl_rule(h) for h in ("a.example", "b.example", "c.example")])
    grow.run_once(settings, store, gw, prover, log=quiet)
    assert active_stops(store)
    Stopper(store, gw, "openshell-policy", log=quiet).resume(Scope("session", SESSION), "op")
    gw.pending[sb.name] = [proposal(store, settings, curl_rule("d.example"), chunk_id="c9", token="t9")]
    gw.stopped.clear()
    grow.run_once(settings, store, gw, prover, log=quiet)
    assert len(gw.rejected) == 4 and not gw.stopped and not active_stops(store)


def test_breaker_trips_on_a_listed_code_even_when_escalated(settings, store, prover):
    settings.breaker.stop_on = ["risk_findings"]
    gw = FakeGateway()
    sb = gw.add_sandbox()
    gw.pending[sb.name] = [proposal(store, settings, curl_rule(), findings="prover: 1 new finding")]
    grow.run_once(settings, store, gw, prover, log=quiet)
    assert not gw.rejected and gw.stopped == [sb.name]
    assert "escalated as risk_findings" in active_stops(store)[0]["reason"]


def test_a_breaker_failure_does_not_redecide_or_continue(settings, store, prover):
    class Broken(FakeGateway):
        def list_sandboxes(self, app_label):
            if self.calls:
                raise RuntimeError("gateway timed out")
            self.calls += 1
            return super().list_sandboxes(app_label)

    settings.breaker.stop_on = ["outside_ceiling"]
    gw = Broken()
    gw.calls = 0
    sb = gw.add_sandbox()
    pend(gw, store, settings, sb, [curl_rule("api.github.com"), curl_rule()])
    grow.run_once(settings, store, gw, prover, log=quiet)
    # The stop is recorded although the halt could not list sandboxes, and the
    # next proposal is not approved.
    assert active_stops(store) and not gw.approved
    assert [e["action"] for e in store.ledger("decision")] == ["reject"]
    assert any(e["step"] == "list_sandboxes" and not e["ok"] for e in store.ledger("halt"))


def test_grow_decides_nothing_for_a_sandbox_whose_environment_was_remapped(settings, store, prover):
    gw = FakeGateway()
    sb = gw.add_sandbox(env=NEW_ENV)
    pend(gw, store, settings, sb, [curl_rule()])
    logs: list[str] = []
    grow.run_once(settings, store, gw, prover, log=logs.append)
    assert not gw.approved and not gw.rejected and any("not mapped" in line for line in logs)


def test_a_stop_landing_mid_pass_is_honoured(settings, store, prover):
    class StopsMidPass(FakeGateway):
        def proposals(self, sandbox, status="pending"):
            if status == "pending":
                store.record("stop", scope="session", target=SESSION, reason="mid-pass", by="op")
            return super().proposals(sandbox, status)

    gw = StopsMidPass()
    sb = gw.add_sandbox()
    pend(gw, store, settings, sb, [curl_rule()])
    grow.run_once(settings, store, gw, prover, log=quiet)
    assert not gw.approved


def test_breaker_off(settings, store, prover):
    settings.breaker.max_rejections = 0
    settings.breaker.stop_on = []
    gw = FakeGateway()
    sb = gw.add_sandbox()
    pend(gw, store, settings, sb, [curl_rule(f"h{i}.example") for i in range(5)])
    grow.run_once(settings, store, gw, prover, log=quiet)
    assert len(gw.rejected) == 5 and not gw.stopped


# ---- the kill switch --------------------------------------------------------------


def test_stop_by_agent_halts_only_its_sandboxes_and_interrupts_their_sessions(store):
    gw = FakeGateway()
    mine = gw.add_sandbox()
    other = gw.add_sandbox(session=OTHER_SESSION, agent="agent_011Csomeoneelse")
    interrupted: list[str] = []
    Stopper(store, gw, "openshell-policy", interrupted.append, log=quiet).stop(Scope("agent", AGENT), "incident 42", "op")
    assert gw.locked_down == [mine.name] and gw.stopped == [mine.name] and interrupted == [SESSION]
    assert other.name not in gw.stopped
    assert stopped(store, SESSION, AGENT, ENV, "hello")["reason"] == "incident 42"
    assert stopped(store, OTHER_SESSION, "agent_011Csomeoneelse", ENV, "hello") is None
    halts = [(e["step"], e["ok"]) for e in store.ledger("halt")]
    assert halts == [("lock_down", True), ("stop_sandbox", True), ("interrupt", True)]


def test_stop_keeps_going_when_a_step_fails(store):
    gw = FakeGateway()
    sb = gw.add_sandbox()
    gw.fail.add("lock_down")

    def refuse(_session: str) -> None:
        raise RuntimeError("server unreachable")

    s = Stopper(store, gw, "openshell-policy", refuse, log=quiet)
    s.stop(Scope("all"), "drill", "op")
    assert gw.stopped == [sb.name]
    assert s.failures == ["lock_down", "interrupt"]  # what `agentpolicy stop` turns into a non-zero exit
    halts = {e["step"]: e for e in store.ledger("halt")}
    assert not halts["lock_down"]["ok"] and halts["stop_sandbox"]["ok"] and not halts["interrupt"]["ok"]
    # The stop stands even though parts of the halt failed: the dispatcher refuses the session.
    assert stopped(store, SESSION, AGENT, ENV, "hello") is not None


def test_a_stop_is_recorded_and_interrupts_with_no_gateway(store):
    interrupted: list[str] = []
    Stopper(store, None, "openshell-policy", interrupted.append, log=quiet).stop(Scope("session", SESSION), "x", "op")
    assert interrupted == [SESSION] and stopped(store, SESSION, AGENT, ENV, "hello") is not None


def test_a_torn_or_foreign_ledger_line_does_not_hide_a_stop(store, settings):
    store.record("stop", scope="session", target=SESSION, reason="x", by="op")
    with open(settings.ledger_path, "a") as fh:
        fh.write("[1, 2]\n\"text\"\n{\"kind\": \"stop\"\n")
    assert stopped(store, SESSION, AGENT, ENV, "hello") is not None


def test_a_session_stop_interrupts_even_with_no_sandbox_running(store):
    interrupted: list[str] = []
    Stopper(store, FakeGateway(), "openshell-policy", interrupted.append, log=quiet).stop(
        Scope("session", SESSION), "user asked", "op")
    assert interrupted == [SESSION]


def test_resume_lifts_only_the_same_scope(store):
    s = Stopper(store, FakeGateway(), "openshell-policy", log=quiet)
    s.stop(Scope("profile", "hello"), "a", "op")
    s.stop(Scope("session", SESSION), "b", "op")
    s.resume(Scope("profile", "hello"), "op")
    assert stopped(store, SESSION, AGENT, ENV, "hello")["reason"] == "b"
    assert stopped(store, OTHER_SESSION, AGENT, ENV, "hello") is None
    s.resume(Scope("session", SESSION), "op")
    assert stopped(store, SESSION, AGENT, ENV, "hello") is None


def test_resuming_one_session_leaves_another_s_stop_in_force(store):
    s = Stopper(store, FakeGateway(), "openshell-policy", log=quiet)
    s.stop(Scope("session", SESSION), "a", "op")
    s.stop(Scope("session", OTHER_SESSION), "b", "op")
    s.resume(Scope("session", OTHER_SESSION), "op")
    assert stopped(store, SESSION, AGENT, ENV, "hello")["reason"] == "a"
    assert stopped(store, OTHER_SESSION, AGENT, ENV, "hello") is None


def test_the_stop_is_on_record_before_anything_is_halted(store):
    class Checks(FakeGateway):
        def lock_down(self, sandbox):
            assert active_stops(store)
            super().lock_down(sandbox)

    gw = Checks()
    gw.add_sandbox()
    Stopper(store, gw, "openshell-policy", log=quiet).stop(Scope("all"), "drill", "op")
    assert gw.locked_down


def refuse(store, session=SESSION, agent=AGENT, environment=ENV, profile="hello"):
    store.record("refused", scope="session", target=session, session_id=session, agent_id=agent,
                 environment_id=environment, profile=profile)


def test_resume_frees_the_work_items_of_the_sessions_it_covers(store):
    s = Stopper(store, FakeGateway(), "openshell-policy", log=quiet)
    s.stop(Scope("agent", AGENT), "a", "op")
    refuse(store)
    refuse(store, OTHER_SESSION, agent="agent_011CsomeoneELSE01")
    released: list[tuple[str, str]] = []
    s.release = lambda env, session: released.append((env, session)) or "force_stopped"
    interrupted: list[str] = []
    s.interrupt = interrupted.append
    s.resume(Scope("agent", AGENT), "op")
    assert released == [(ENV, SESSION)]
    # The tool call it was refused on is closed, so its next message runs.
    assert interrupted == [SESSION]
    freed, settled = store.ledger("release")
    assert freed["ok"] and freed["outcome"] == "force_stopped" and freed["session_id"] == SESSION
    assert settled["step"] == "interrupt" and settled["ok"]


def test_resume_is_recorded_when_freeing_fails_or_cannot_be_tried(store):
    s = Stopper(store, FakeGateway(), "openshell-policy", log=quiet)
    s.stop(Scope("session", SESSION), "a", "op")
    refuse(store)
    said: list[str] = []
    Stopper(store, None, "openshell-policy", log=said.append).resume(Scope("session", SESSION), "op")
    assert stopped(store, SESSION, AGENT, ENV, "hello") is None
    assert SESSION in said[-1] and "force" in said[-1] and not list(store.ledger("release"))

    def boom(env: str, session: str) -> str:
        raise RuntimeError("server down")

    s.stop(Scope("session", SESSION), "b", "op")
    Stopper(store, None, "openshell-policy", log=quiet, release=boom).resume(Scope("session", SESSION), "op")
    assert stopped(store, SESSION, AGENT, ENV, "hello") is None
    (e,) = store.ledger("release")
    assert not e["ok"] and e["error"] == "server down"


def test_release_work_force_stops_only_a_stopping_item():
    from types import SimpleNamespace

    from agentpolicy import managed_agents

    class Work:
        def __init__(self, state: str) -> None:
            self.state, self.stops = state, []

        def retrieve(self, work_id, *, environment_id):
            return SimpleNamespace(state=self.state)

        def stop(self, work_id, *, environment_id, force):
            self.stops.append((environment_id, work_id, force))

    for state, outcome, stops in (("stopping", "force_stopped", [(ENV, SESSION, True)]),
                                  ("stopped", "stopped", []), ("active", "active", [])):
        w = Work(state)
        c = SimpleNamespace(beta=SimpleNamespace(environments=SimpleNamespace(work=w)))
        assert managed_agents.release_work(c, ENV, SESSION) == outcome and w.stops == stops


@pytest.mark.parametrize("kind,value", [("session", "not-a-session"), ("agent", "agent_a b"), ("profile", "Bad"),
                                        ("environment", "env_$x"), ("all", "x"), ("session", ""), ("galaxy", "x")])
def test_scope_refuses_malformed_targets(kind, value):
    with pytest.raises(PolicyError):
        Scope(kind, value)


# ---- the environment map and the command line --------------------------------------


def test_environment_map(repo, fake_prover_bin):
    r = run_cli_env(repo, fake_prover_bin, {}, "environment", "get", NEW_ENV)
    assert r.returncode == 2 and "not mapped" in r.stderr
    r = run_cli_env(repo, fake_prover_bin, {}, "environment", "set", NEW_ENV, "no-such-profile")
    assert r.returncode == 2
    r = run_cli_env(repo, fake_prover_bin, {}, "environment", "set", NEW_ENV, "hello")
    assert r.returncode == 0, r.stderr
    assert (repo / "state" / "environments.yaml").stat().st_mode & 0o777 == 0o644
    r = run_cli_env(repo, fake_prover_bin, {}, "environment", "get", NEW_ENV)
    assert r.returncode == 0 and r.stdout.strip() == "hello"
    listed = run_cli_env(repo, fake_prover_bin, {}, "environment", "list").stdout.splitlines()
    assert listed == sorted([f"{ENV}\thello", f"{NEW_ENV}\thello"])


def test_environment_set_refuses_a_tampered_map(repo, store):
    path = repo / "state" / "environments.yaml"
    path.write_text(path.read_text() + "  env_01PLANTED: hello\n")
    path.chmod(0o664)
    with pytest.raises(PolicyError, match="writable by its group"):
        store.set_environment(NEW_ENV, "hello")


def test_settings_entries_win_over_the_file(repo, store):
    store.set_environment(ENV, "hello")
    cfg = repo / "agentpolicy.yaml"
    cfg.write_text(cfg.read_text() + f"environments:\n  {ENV}: other\n")
    s = config.load(cfg)
    assert s.environments[ENV] == "other"
    assert type(store)(s).environments()[ENV] == "other"
    with pytest.raises(PolicyError, match="settings file, which wins"):
        type(store)(s).set_environment(ENV, "hello")


def test_stopped_command_exit_codes(repo, store, fake_prover_bin):
    args = ["stopped", "--session", SESSION, "--agent", AGENT, "--environment", ENV, "--profile", "hello"]
    assert run_cli_env(repo, fake_prover_bin, {}, *args).returncode == 0
    store.record("stop", scope="environment", target=ENV, reason="maintenance", by="op")
    r = run_cli_env(repo, fake_prover_bin, {}, *args)
    assert r.returncode == 3 and "maintenance" in r.stdout
    (e,) = store.ledger("refused")  # so resume can free the work item the refusal leaves stopping
    assert e["session_id"] == SESSION and e["environment_id"] == ENV and e["target"] == ENV


def test_stop_and_resume_work_with_no_gateway(repo, store, fake_prover_bin):
    env = {"AGENTPOLICY_GATEWAY_ENDPOINT": "", "XDG_CONFIG_HOME": str(repo / "nowhere"),
           "OPENSHELL_SYSTEM_CONFIG_DIR": str(repo / "nowhere")}
    r = run_cli_env(repo, fake_prover_bin, env, "stop", "--session", SESSION, "--reason", "gateway is down")
    # Recorded, but nothing was halted: the exit code says so.
    assert r.returncode == 1, r.stderr
    assert "without halting sandboxes" in r.stderr and "may still be running" in r.stderr
    assert stopped(store, SESSION, AGENT, ENV, "hello") is not None
    assert run_cli_env(repo, fake_prover_bin, env, "resume", "--session", SESSION).returncode == 0
    assert stopped(store, SESSION, AGENT, ENV, "hello") is None


def test_defaults_are_safe():
    s = config.Settings(root=None, policy_dir=None, state_dir=None)  # type: ignore[arg-type]
    assert not s.profile_settings("anything").proposals
    assert s.breaker.max_rejections == 3 and s.breaker.stop_on == ["suspicious"]


def draft(host: str, port: int = 443) -> dict:
    """What OpenShell files by itself for a denied connection."""
    return {"name": f"allow_{host.replace('.', '_')}_{port}", "endpoints": [{"host": host, "port": port}],
            "binaries": [{"path": "/usr/bin/curl"}]}


def test_openshells_own_drafts_are_rejected_without_counting_as_requests(settings, store, prover):
    gw = FakeGateway()
    sb = gw.add_sandbox()
    pend(gw, store, settings, sb, [draft(h) for h in ("pypi.org", "files.pythonhosted.org", "github.com", "example.com")])
    grow.run_once(settings, store, gw, prover, log=quiet)
    # example.com is inside the ceiling, but nobody asked for it.
    assert len(gw.rejected) == 4 and all(r[2].startswith("gateway_draft: ") for r in gw.rejected)
    assert not gw.approved and not active_stops(store) and not prover.calls


def test_drafts_are_told_apart_with_proposals_off_and_whatever_the_case(settings, store, prover):
    settings.profiles.clear()
    gw = FakeGateway()
    sb = gw.add_sandbox()
    pend(gw, store, settings, sb, [draft(h) for h in ("a.example", "B.Example", "c.example", "d.example")])
    grow.run_once(settings, store, gw, prover, log=quiet)
    assert [r[2].split(":")[0] for r in gw.rejected] == ["gateway_draft"] * 4 and not active_stops(store)


def test_one_sandboxs_backlog_is_spread_over_passes(settings, store, prover):
    gw = FakeGateway()
    sb = gw.add_sandbox()
    pend(gw, store, settings, sb, [draft(f"h{i}.example") for i in range(grow.MAX_PER_PASS + 2)])
    assert len(grow.run_once(settings, store, gw, prover, log=quiet)) == grow.MAX_PER_PASS
    assert len(grow.run_once(settings, store, gw, prover, log=quiet)) == 2


def test_a_stop_halts_what_is_running_even_when_it_cannot_be_recorded(store, monkeypatch):
    gw = FakeGateway()
    sb = gw.add_sandbox()

    def full(*a, **kw):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(store, "record", full)
    interrupted: list[str] = []
    s = Stopper(store, gw, "openshell-policy", interrupted.append, log=quiet)
    assert s.stop(Scope("all"), "drill", "op") == {}
    assert gw.locked_down == [sb.name] and gw.stopped == [sb.name] and interrupted == [SESSION]
    assert set(s.failures) == {"record"}


def test_a_missing_config_is_an_error_not_a_set_of_defaults(tmp_path, repo, fake_prover_bin):
    with pytest.raises(config.ConfigMissing):
        config.load(tmp_path / "nope.yaml")
    (repo / "agentpolicy.yaml").rename(repo / "moved.yaml")
    r = run_cli_env(repo, fake_prover_bin, {}, "stop", "--all", "--reason", "x")
    assert r.returncode == 2 and "no config at" in r.stderr
    assert not (repo / "state" / "ledger.jsonl").exists()


def test_stop_says_which_ledger_it_wrote(repo, fake_prover_bin):
    r = run_cli_env(repo, fake_prover_bin, {"AGENTPOLICY_GATEWAY_ENDPOINT": "http://127.0.0.1:1"}, "stop", "--all", "--reason", "x")
    assert str(repo / "state" / "ledger.jsonl") in r.stdout


def test_check_fails_when_there_is_nothing_to_check(repo, fake_prover_bin):
    import shutil

    shutil.rmtree(repo / "policy" / "profiles")
    r = run_cli_env(repo, fake_prover_bin, {}, "check")
    assert r.returncode == 2 and "nothing was checked" in r.stderr
