"""Stopping sessions: the operator's kill switch and the reviewer's circuit breaker.

A stop is a ledger entry naming what it covers: one session, every session of
an agent, of an environment or of a profile, or everything. While it stands:

* the dispatcher runs no worker for a session it covers (``agentpolicy
  stopped``, from ``on-work.sh``), so a stopped session gets no new sandbox
  when the work queue hands it out again;
* the reviewer decides nothing for a sandbox it covers.

Stopping also acts on what is already running, OpenShell side first, because
that side does not depend on the agent loop:

1. every covered sandbox's network rules are replaced with none, which
   hot-reloads, so no new connection leaves it;
2. the sandbox is stopped, which ends the worker and every tool it runs;
3. with your API key, each covered session is sent ``user.interrupt``,
   so the agent loop stops its turn too.

``agentpolicy resume`` with the same scope lifts a stop. Later entries win.
With your API key it also force-stops the work item of each covered session
left ``stopping`` after the dispatcher refused it; without that, the work
queue would never hand the session to a worker again.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .gateway import Gateway, SandboxRef
from .policyfile import AGENT_RE, SESSION_RE, PolicyError
from .store import Store, check_environment, check_profile

Log = Callable[[str], None]
Interrupt = Callable[[str], None]
Release = Callable[[str, str], str]  # (environment, session) -> what was done

SCOPES = ("session", "agent", "environment", "profile", "all")
ID_RE = {"session": SESSION_RE, "agent": AGENT_RE}


@dataclass(frozen=True)
class Scope:
    kind: str
    value: str = ""

    def __post_init__(self) -> None:
        if self.kind not in SCOPES:
            raise PolicyError(f"unknown stop scope {self.kind!r}")
        if (self.kind == "all") != (not self.value):
            raise PolicyError(f"stop scope {self.kind!r} {'takes no' if self.kind == 'all' else 'needs a'} value")
        if self.kind in ID_RE and not ID_RE[self.kind].match(self.value):
            raise PolicyError(f"invalid {self.kind} id {self.value!r}")
        if self.kind == "profile":
            check_profile(self.value)
        if self.kind == "environment":
            check_environment(self.value)

    def covers(self, session: str = "", agent: str = "", environment: str = "", profile: str = "") -> bool:
        if self.kind == "all":
            return True
        return bool(self.value) and self.value == {
            "session": session, "agent": agent, "environment": environment, "profile": profile,
        }[self.kind]

    def covers_sandbox(self, sb: SandboxRef) -> bool:
        return self.covers(sb.session_id, sb.agent_id, sb.environment_id, sb.profile)

    def __str__(self) -> str:
        return self.kind if self.kind == "all" else f"{self.kind} {self.value}"


def active_stops(store: Store) -> list[dict[str, Any]]:
    """The stops in force: for each scope, its latest stop not followed by a resume."""
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for e in store.ledger():
        if e.get("kind") in ("stop", "resume"):
            latest[(e.get("scope", ""), e.get("target", ""))] = e
    return [e for e in latest.values() if e["kind"] == "stop"]


def stopped(store: Store, session: str = "", agent: str = "", environment: str = "",
            profile: str = "", stops: Iterable[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """The stop that covers this session, if any."""
    for e in active_stops(store) if stops is None else stops:
        try:
            scope = Scope(e.get("scope", ""), e.get("target", ""))
        except PolicyError:
            continue
        if scope.covers(session, agent, environment, profile):
            return e
    return None


def covered_sessions(store: Store, scope: Scope) -> list[tuple[str, str]]:
    """(session, environment) of every session the ledger knows that the scope covers.

    Dispatches, halts and refusals all name the session's environment, which
    its work item is filed under.
    """
    seen: dict[str, str] = {}
    for e in store.ledger():
        if e.get("kind") not in ("dispatch", "halt", "refused"):
            continue
        session, environment = str(e.get("session_id") or ""), str(e.get("environment_id") or "")
        if not (ID_RE["session"].match(session) and environment):
            continue
        try:
            check_environment(environment)
        except PolicyError:
            continue
        if scope.covers(session, str(e.get("agent_id") or ""), environment, str(e.get("profile") or "")):
            seen[session] = environment
    return sorted(seen.items())


class Stopper:
    """Records stops and halts what they cover.

    ``gateway`` may be None (no gateway could be reached): the stop is still
    recorded and sessions still interrupted, and the missing halt is recorded.
    """

    def __init__(self, store: Store, gateway: Gateway | None, sandbox_label: str,
                 interrupt: Interrupt | None = None, log: Log = print, release: Release | None = None) -> None:
        self.store = store
        self.gateway = gateway
        self.label = sandbox_label
        self.interrupt = interrupt
        self.release = release
        self.log = log
        # The steps of the last stop() that failed. Each is also a halt entry with ok=false.
        self.failures: list[str] = []

    def stop(self, scope: Scope, reason: str, by: str) -> dict[str, Any]:
        """Records the stop, then halts every covered sandbox and session.

        The record comes first: from then on the dispatcher refuses the
        covered sessions, even if halting a running sandbox below fails. If
        the record itself cannot be written (a full disk, say), what is running
        is still halted, and the failure is reported: nothing then stops the
        dispatcher from serving the sessions again.
        """
        self.failures = []
        entry = self._record("stop", scope=scope.kind, target=scope.value, reason=reason, by=by)
        self.log(f"stopped {scope}: {reason}")
        sessions: set[str] = {scope.value} if scope.kind == "session" else set()
        try:
            if self.gateway is None:
                raise RuntimeError("no OpenShell gateway could be reached")
            sandboxes = self.gateway.list_sandboxes(self.label)
        except Exception as err:  # still interrupt what is known, and say what was not halted
            sandboxes = []
            self.failures.append("list_sandboxes")
            self.log(f"could not list sandboxes to halt: {err}")
            self._record("halt", step="list_sandboxes", ok=False, error=str(err)[:500],
                              scope=scope.kind, target=scope.value)
        for sb in sandboxes:
            if scope.covers_sandbox(sb):
                self.halt(sb, scope)
                sessions.add(sb.session_id)
        for session in sorted(s for s in sessions if s):
            self._interrupt(session, scope)
        return entry

    def resume(self, scope: Scope, by: str) -> dict[str, Any]:
        """Lifts the stop, then frees the work items its refusals left stuck.

        The record comes first, as for a stop: the dispatcher serves the
        sessions again from then on, whether or not freeing their items works.
        """
        entry = self.store.record("resume", scope=scope.kind, target=scope.value, by=by)
        self.log(f"resumed {scope}")
        pairs = covered_sessions(self.store, scope)
        if not pairs:
            return entry
        if self.release is None:
            self.log("not checking the Managed Agents API for stuck work items: no credential here (log in "
                     "with `ant auth login` or set ANTHROPIC_API_KEY, and run resume again). A session the dispatcher "
                     "refused is not dispatched again until its work item is force-stopped: POST "
                     "/v1/environments/<env>/work/<session>/stop {\"force\": true}. Sessions: "
                     + ", ".join(s for s, _ in pairs))
            return entry
        for session, environment in pairs:
            try:
                outcome, error = self.release(environment, session), ""
            except Exception as err:
                outcome, error = "", str(err)[:500]
                self.log(f"{session}: could not free its work item: {error}")
            if outcome == "force_stopped":
                self.log(f"{session}: freed its work item, which a refused worker left stopping")
            self.store.record("release", ok=not error, outcome=outcome or None, error=error or None,
                              scope=scope.kind, target=scope.value, session_id=session, environment_id=environment)
            if outcome == "force_stopped":
                self._settle(session, scope)
        return entry

    def _settle(self, session: str, scope: Scope) -> None:
        """Closes the tool call a refused session is still waiting on.

        Freeing the work item does not answer that call, and the session is
        not queued again by itself (observed: still parked after nine
        minutes). ``user.interrupt`` closes it with an error
        and idles the session, so its next message runs. No worker serves a
        refused session, so this cuts off no work.
        """
        if self.interrupt is None:
            self.log(f"{session}: may still wait on a tool call from while it was stopped; "
                     "send it user.interrupt, then a message")
            return
        try:
            self.interrupt(session)
            error = ""
            self.log(f"{session}: interrupted, so its next message runs")
        except Exception as err:
            error = str(err)[:500]
            self.log(f"{session}: user.interrupt failed: {error}")
        self.store.record("release", step="interrupt", ok=not error, error=error or None,
                          scope=scope.kind, target=scope.value, session_id=session)

    def _record(self, kind: str, **fields: Any) -> dict[str, Any]:
        """Records a stop or one of its steps. A ledger that cannot be written must not end the stop."""
        try:
            return self.store.record(kind, **fields)
        except OSError as err:
            self.failures.append("record")
            self.log(f"could not write {kind} to {self.store.s.ledger_path}: {err}")
            return {}

    def halt(self, sb: SandboxRef, scope: Scope) -> None:
        """Denies the sandbox every new connection, then stops it. Each step is recorded."""
        assert self.gateway is not None
        for step, act in (("lock_down", self.gateway.lock_down), ("stop_sandbox", self.gateway.stop_sandbox)):
            try:
                act(sb.name)
                error = ""
            except Exception as err:  # keep going: the next step, and the next sandbox
                error = str(err)[:500]
                self.failures.append(step)
                self.log(f"{sb.name}: {step} failed: {error}")
            self._record(
                "halt", step=step, ok=not error, error=error or None, scope=scope.kind, target=scope.value,
                sandbox=sb.name, session_id=sb.session_id, agent_id=sb.agent_id,
                environment_id=sb.environment_id, profile=sb.profile,
            )

    def _interrupt(self, session: str, scope: Scope) -> None:
        if self.interrupt is None:
            self.log(f"{session}: not interrupted at the Managed Agents API (no API key here); "
                     "the dispatcher refuses it")
            return
        try:
            self.interrupt(session)
            error = ""
        except Exception as err:
            error = str(err)[:500]
            self.failures.append("interrupt")
            self.log(f"{session}: user.interrupt failed: {error}")
        self._record("halt", step="interrupt", ok=not error, error=error or None,
                          scope=scope.kind, target=scope.value, session_id=session)


# The decision code for a draft OpenShell wrote itself (see review.gateway_draft).
GATEWAY_DRAFT = "gateway_draft"


def breaker_trips(store: Store, settings: Any, sb: SandboxRef, action: str, code: str) -> str:
    """Why a just-recorded decision should stop its session, or "" if it should not.

    A code in ``stop_on`` trips it whatever the action (a reviewer may escalate
    what it calls suspicious). Otherwise it counts the session's rejections
    since a resume last covered it, the one just recorded included. A draft of
    OpenShell's own (``gateway_draft``) is a denied connection, not a request,
    and does not count.
    """
    b = settings.breaker
    if code in b.stop_on:
        verb = {"reject": "rejected", "escalate": "escalated", "approve": "approved"}.get(action, action)
        return f"a proposal was {verb} as {code}"
    if action != "reject" or code == GATEWAY_DRAFT or b.max_rejections <= 0:
        return ""
    n = 0
    for e in store.ledger():
        if (e.get("kind") == "decision" and e.get("session_id") == sb.session_id and e.get("action") == "reject"
                and e.get("code") != GATEWAY_DRAFT):
            n += 1
        elif e.get("kind") == "resume":
            try:
                if Scope(e.get("scope", ""), e.get("target", "")).covers_sandbox(sb):
                    n = 0
            except PolicyError:
                pass
    if n >= b.max_rejections:
        return f"{n} proposals rejected (limit {b.max_rejections})"
    return ""
