"""Shrink: remove starting grants that sessions stopped using.

The evidence is the OCSF audit trail. A starting grant whose rule no allowed
record names within the window is removed.

Two proofs guard every write:

* the new starting policy grants nothing the old one did not (so a shrink can
  never widen access, whatever the evidence said);
* the new starting policy still stays inside the ceiling.

Missing evidence is not evidence of disuse. Shrink refuses to run when the
logs do not reach back to the start of the window, when no session left
records in it (a quiet fortnight is not disuse), when any session the
dispatcher started in the window left no OCSF records, or when the audit
collector recorded a gap in the window: in each case some use is unknown.

The destinations it removes it also lists in the profile's revoked.txt, so
that the next promote does not bring them back from the ledger.
"""

from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass, field
from typing import Any

from . import ocsf, policyfile, profilecheck
from .config import Settings
from .policyfile import PolicyError
from .prover import Proof, Prover
from .store import Store

DAY_MS = 86_400_000


@dataclass
class ShrinkPlan:
    profile: str
    window_days: int
    removed: list[tuple[str, str]] = field(default_factory=list)
    revoke: list[str] = field(default_factory=list)
    kept: list[tuple[str, int]] = field(default_factory=list)
    old_grants: dict[str, Any] = field(default_factory=dict)
    new_grants: dict[str, Any] = field(default_factory=dict)
    no_wider: Proof | None = None
    within_ceiling: Proof | None = None
    refused: str = ""
    sessions: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.removed)

    @property
    def ok(self) -> bool:
        return (
            not self.refused
            and self.changed
            and self.no_wider is not None
            and self.no_wider.ok
            and self.within_ceiling is not None
            and self.within_ceiling.ok
        )


def plan(
    settings: Settings,
    store: Store,
    prover: Prover,
    profile: str,
    window_days: int | None = None,
    min_hits: int | None = None,
    now_ms: int | None = None,
    allow_short_evidence: bool = False,
    allow_missing_evidence: bool = False,
) -> ShrinkPlan:
    window_days = settings.shrink.window_days if window_days is None else window_days
    min_hits = settings.shrink.min_hits if min_hits is None else min_hits
    if window_days <= 0:
        raise policyfile.PolicyError(f"the window must be at least one day, got {window_days}")
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    since_ms = now_ms - window_days * DAY_MS

    old = store.grants_template(profile)
    rules = policyfile.network_rules(old)
    result = ShrinkPlan(profile=profile, window_days=window_days, old_grants=old)
    if not rules:
        result.refused = "the profile has no starting grants to shrink"
        return result

    records = list(ocsf.read(ocsf.files(settings.ocsf_dir / profile)))
    if not records:
        result.refused = "no OCSF records for this profile; without evidence nothing can be shown unused"
        return result
    oldest = min(int(r.get("time") or now_ms) for r in records)
    if oldest > since_ms and not allow_short_evidence:
        covered = (now_ms - oldest) / DAY_MS
        result.refused = (
            f"the records cover {covered:.1f} of the {window_days} days in the window; "
            "wait for more evidence or pass a shorter window"
        )
        return result

    result.sessions = len({ocsf.session_of(r) for r in records if int(r.get("time") or 0) >= since_ms})
    missing = _sessions_without_evidence(store, profile, records, since_ms)
    if missing and not allow_missing_evidence:
        result.refused = (
            f"{len(missing)} session(s) dispatched in the window left no OCSF records "
            f"(for example {missing[0]}); their use is unknown"
        )
        return result

    gaps = _audit_gaps(store, profile, since_ms)
    if gaps and not allow_missing_evidence:
        result.refused = (
            f"the audit collector recorded {len(gaps)} gap(s) in the window "
            f"(for example {gaps[0]}); use it could not see may have happened"
        )
        return result

    if not result.sessions and not allow_missing_evidence:
        result.refused = "no session left records in the window; a rule nobody had the chance to use is not unused"
        return result

    use = ocsf.usage(records, since_ms)
    new_rules: dict[str, Any] = {}
    for name, rule in rules.items():
        u = use.get(name)
        hits = u.hits if u else 0
        if hits < min_hits:
            result.removed.append((name, f"{hits} allowed use(s) in {window_days} days"))
            continue
        new_rules[name] = rule
        result.kept.append((name, hits))

    result.new_grants = {"network_policies": new_rules}
    gone = {d for name, _ in result.removed for d in policyfile.destinations(rules[name])}
    still = {d for rule in new_rules.values() for d in policyfile.destinations(rule)}
    result.revoke = sorted(gone - still - store.revoked(profile))
    if result.changed:
        result.no_wider = profilecheck.no_wider(settings, store, prover, result.new_grants, old)
        result.within_ceiling = profilecheck.within_ceiling(settings, store, prover, profile, result.new_grants)
    return result


def _audit_gaps(store: Store, profile: str, since_ms: int) -> list[str]:
    out: list[str] = []
    for e in store.ledger("audit_gap", profile=profile):
        if int(dt.datetime.fromisoformat(e["ts"]).timestamp() * 1000) >= since_ms:
            out.append(f"{e.get('session_id', '?')}: {e.get('reason', '')}")
    return out


def _sessions_without_evidence(store: Store, profile: str, records: list[dict[str, Any]], since_ms: int) -> list[str]:
    with_records = {ocsf.session_of(r) for r in records}
    missing: list[str] = []
    for e in store.ledger("dispatch", profile=profile):
        if e.get("proof") != "within_boundary":
            continue  # no sandbox was created
        t = int(dt.datetime.fromisoformat(e["ts"]).timestamp() * 1000)
        sid = e.get("session_id", "")
        if t >= since_ms and sid not in with_records and sid not in missing:
            missing.append(sid)
    return missing


def apply(store: Store, p: ShrinkPlan) -> None:
    if not p.ok:
        raise PolicyError("refusing to write a shrink that did not prove narrower and inside the ceiling")
    store.write_revoked(p.profile, p.revoke)  # first, so that no crash leaves a removed rule within promote's reach
    store.write_grants(p.profile, p.new_grants)
    store.record(
        "shrink",
        profile=p.profile,
        window_days=p.window_days,
        removed=[n for n, _ in p.removed],
        revoked=p.revoke,
        proof_no_wider=p.no_wider.result if p.no_wider else None,
        proof_within_ceiling=p.within_ceiling.result if p.within_ceiling else None,
        policy_digest=policyfile.digest(p.new_grants),
    )
