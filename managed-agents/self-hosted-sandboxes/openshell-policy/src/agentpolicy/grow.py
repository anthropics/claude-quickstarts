"""Grow: decide every pending proposal in every worker sandbox.

Runs host-side, beside the OpenShell gateway, never inside a sandbox. Each
pending proposal is decided at most once per review token: a proposal the
gateway re-evaluates (because the sandbox's policy changed) gets a new token
and is decided again.

A pass also records, as grants, rules that a person approved at the gateway
(``openshell rule approve``) rather than through this service, so that
promotion sees every approval whoever made it.

Two things end the asking:

* a profile whose settings leave ``proposals`` off has every proposal
  rejected without review: its agents work within their starting policy;
* the circuit breaker (``breaker`` in the settings) stops a session whose
  proposals keep being rejected, or that made one rejected as suspicious,
  through ``stop.Stopper``. Nothing is decided for a stopped session.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .config import Settings
from .gateway import Gateway, Proposal, SandboxRef
from .policyfile import Bindings, PolicyError
from .prover import Prover
from .review import APPROVE, DEFER, ESCALATE, REJECT, Context, Decision, Reviewer, decide, gateway_draft
from .stop import Scope, Stopper, active_stops, breaker_trips, stopped
from .store import Store

Log = Callable[[str], None]
Key = tuple[str, str, str]

# How many passes may defer one proposal, or fail to apply one decision at the
# gateway, before it is left for a person.
MAX_ATTEMPTS = 5
# Proposals looked at per sandbox per pass.
MAX_PER_PASS = 5


@dataclass
class Grower:
    settings: Settings
    store: Store
    gateway: Gateway
    prover: Prover
    reviewer: Reviewer | None = None
    log: Log = print
    # Halts sessions the breaker trips on. Without one, a Stopper with no
    # Managed Agents client is used: sandboxes are stopped, sessions are not interrupted.
    stopper: Stopper | None = None
    # Proposals deferred so far, by (sandbox, chunk, token).
    deferrals: dict[Key, int] = field(default_factory=dict)
    # Decisions the gateway refused to apply, kept so a retry does not decide
    # (and in claude mode, pay for a review) again.
    unapplied: dict[Key, tuple[Decision, int]] = field(default_factory=dict)

    def run_once(self) -> list[dict[str, Any]]:
        """Decides what is pending now. Returns the ledger entries it wrote."""
        seen = {(e.get("sandbox"), e.get("chunk_id"), e.get("review_token")) for e in self.store.ledger("decision")}
        granted = {(e.get("sandbox"), e.get("chunk_id")) for e in self.store.ledger("grant")}
        stops = active_stops(self.store)
        written: list[dict[str, Any]] = []
        for sb in self.gateway.list_sandboxes(self.settings.sandbox_label):
            if self._stopped(sb, stops):
                continue
            try:
                written += self._sandbox(sb, seen, granted)
            except Exception as err:  # one sandbox's trouble must not stall the rest
                self.log(f"{sb.name}: skipped this pass: {err}")
        return written

    def _sandbox(self, sb: SandboxRef, seen: set, granted: set) -> list[dict[str, Any]]:
        if not (sb.profile and sb.session_id and sb.environment_id):
            self.log(f"skip {sb.name}: missing profile, session or environment label")
            return []
        try:
            mapped = self.store.profile_for_environment(sb.environment_id)
            if mapped != sb.profile:
                # Remapped since the sandbox was made; the dispatcher replaces it.
                raise PolicyError(f"labelled profile {sb.profile} but its environment now maps to {mapped}")
            ctx = self._context(sb)
        except PolicyError as err:
            # No trusted ceiling means nothing can be proved inside it.
            self.log(f"skip {sb.name}: {err}")
            return []
        written = self._record_outside_approvals(sb, granted)
        tried = 0
        for p in self.gateway.proposals(sb.name, "pending"):
            key = (sb.name, p.chunk_id, p.review_token)
            if key in seen:
                continue
            # One sandbox's backlog waits for the next pass, so the others get their turn.
            tried += 1
            if tried > MAX_PER_PASS:
                break
            # A stop may have landed since the pass began, or with the last decision.
            if self._stopped(sb):
                break
            try:
                entry = self._one(sb, ctx, p, key)
            except Exception as err:  # the prover or reviewer failed for this one
                entry = self._defer(sb, p, key, Decision(DEFER, f"could not decide: {err}", "decide_failed"))
            if entry is not None:
                seen.add(key)
                written.append(entry)
        return written

    def _stopped(self, sb: SandboxRef, stops: list[dict[str, Any]] | None = None) -> bool:
        return stopped(self.store, sb.session_id, sb.agent_id, sb.environment_id, sb.profile, stops) is not None

    def _context(self, sb: SandboxRef) -> Context:
        s = self.settings
        bindings = Bindings(sb.session_id, sb.environment_id, s.api_host, s.api_port)
        ceiling = self.store.ceiling(sb.profile, bindings)
        task_file = s.profile_dir(sb.profile) / "task.md"
        description = task_file.read_text().strip() if task_file.exists() else ""
        return Context(profile=sb.profile, session_id=sb.session_id, ceiling=ceiling, agent_description=description,
                       revoked=self.store.revoked(sb.profile))

    def _one(self, sb: SandboxRef, ctx: Context, p: Proposal, key: Key) -> dict[str, Any] | None:
        if key in self.unapplied:
            d, _ = self.unapplied[key]
        elif not self.settings.profile_settings(sb.profile).proposals and not gateway_draft(p):
            d = Decision(REJECT, "agents on this profile cannot be granted more access; finish what you can "
                                 "with the access you have and report what you could not do", "proposals_disabled")
        else:
            d = decide(
                p, ctx, self.prover, self.settings.review.mode,
                reviewer=self.reviewer,
                reviewer_may_override_findings=self.settings.review.reviewer_may_override_findings,
            )
        if d.action == DEFER:
            return self._defer(sb, p, key, d)
        self.deferrals.pop(key, None)
        try:
            if d.action == APPROVE:
                self.gateway.approve(sb.name, p.chunk_id, p.review_token)
            elif d.action == REJECT:
                self.gateway.reject(sb.name, p.chunk_id, d.rejection_text())
        except Exception as err:  # the gateway refused; retry the same decision
            _, attempts = self.unapplied.get(key, (d, 0))
            attempts += 1
            self.store.record(
                "decision_failed", profile=sb.profile, session_id=sb.session_id, sandbox=sb.name,
                chunk_id=p.chunk_id, action=d.action, attempt=attempts, error=str(err)[:500],
            )
            if attempts < MAX_ATTEMPTS:
                self.unapplied[key] = (d, attempts)
                self.log(f"{sb.name}/{p.chunk_id}: {d.action} refused by the gateway (attempt {attempts}): {err}")
                return None
            self.unapplied.pop(key, None)
            d = Decision(ESCALATE, f"the gateway refused {d.action} {attempts} times: {err}", "gateway_refused", d.proof)
        self.unapplied.pop(key, None)
        return self._record(sb, p, d)

    def _defer(self, sb: SandboxRef, p: Proposal, key: Key, d: Decision) -> dict[str, Any] | None:
        n = self.deferrals.get(key, 0) + 1
        if n < MAX_ATTEMPTS:
            self.deferrals[key] = n
            if n == 1:
                self.log(f"{sb.name}/{p.rule_name}: not decided yet ({d.code}): {d.reason}")
            return None
        self.deferrals.pop(key, None)
        return self._record(sb, p, Decision(ESCALATE, f"still undecided after {n} passes: {d.reason}", d.code, d.proof))

    def _record(self, sb: SandboxRef, p: Proposal, d: Decision) -> dict[str, Any]:
        entry = self.store.record(
            "decision",
            profile=sb.profile,
            session_id=sb.session_id,
            agent_id=sb.agent_id,
            agent_version=sb.agent_version,
            environment_id=sb.environment_id,
            sandbox=sb.name,
            chunk_id=p.chunk_id,
            review_token=p.review_token,
            rule_name=p.rule_name,
            rule=p.rule,
            binary=p.binary,
            action=d.action,
            code=d.code,
            reason=d.reason,
            reviewer=d.reviewer,
            proof=d.proof.result if d.proof else None,
            counterexample=d.proof.counterexample if d.proof else None,
            gateway_findings=p.validation_result,
        )
        if d.action == APPROVE:
            self._grant(sb, p, approved_by="agentpolicy")
        verb = {APPROVE: "approved", REJECT: "rejected", ESCALATE: "left for a person"}[d.action]
        self.log(f"{sb.name}/{p.rule_name}: {verb} ({d.code}): {d.reason}")
        try:
            why = breaker_trips(self.store, self.settings, sb, d.action, d.code)
            if why:
                stopper = self.stopper or Stopper(self.store, self.gateway, self.settings.sandbox_label, log=self.log)
                stopper.stop(Scope("session", sb.session_id), f"circuit breaker: {why}", by="breaker")
        except Exception as err:  # the decision stands either way; never re-decide it
            self.log(f"{sb.name}: circuit breaker failed: {err}")
        return entry

    def _grant(self, sb: SandboxRef, p: Proposal, approved_by: str) -> dict[str, Any]:
        return self.store.record(
            "grant",
            profile=sb.profile,
            session_id=sb.session_id,
            agent_id=sb.agent_id,
            agent_version=sb.agent_version,
            environment_id=sb.environment_id,
            sandbox=sb.name,
            chunk_id=p.chunk_id,
            rule_name=p.rule_name,
            rule=p.rule,
            approved_by=approved_by,
        )

    def _record_outside_approvals(self, sb: SandboxRef, granted: set) -> list[dict[str, Any]]:
        out = []
        for p in self.gateway.proposals(sb.name, "approved"):
            if (sb.name, p.chunk_id) in granted or p.rule is None:
                continue
            out.append(self._grant(sb, p, approved_by="gateway"))
            granted.add((sb.name, p.chunk_id))
            self.log(f"{sb.name}/{p.rule_name}: recorded an approval made at the gateway")
        return out


def run_once(settings: Settings, store: Store, gateway: Gateway, prover: Prover,
             reviewer: Reviewer | None = None, log: Log = print, stopper: Stopper | None = None) -> list[dict[str, Any]]:
    """One pass with fresh retry state (see ``Grower`` for a long-running loop)."""
    return Grower(settings, store, gateway, prover, reviewer, log, stopper=stopper).run_once()


def watch(interval_s: float, grower: Grower) -> None:
    while True:
        try:
            grower.run_once()
        except Exception as err:  # keep watching; a gateway restart is routine
            grower.log(f"grow pass failed: {err}")
        time.sleep(interval_s)
