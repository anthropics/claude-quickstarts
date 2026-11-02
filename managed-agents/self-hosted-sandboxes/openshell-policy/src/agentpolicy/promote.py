"""Promote: turn grants that sessions approved and used into starting grants.

An approved grant lives only in the sandbox of the session that asked for it,
and Managed Agents gives every session a sandbox of its own. Without promotion, every
new session would have to ask again. Promotion is deliberately conservative:

* a grant is promoted only if the session it was granted to used it (an
  allowed OCSF record from that session names its rule), unless the operator
  says otherwise;
* a grant from a session that a stop covers is left out: what such a session
  asked for is not evidence of need. A person who resumes it vouches for it;
* a grant that reaches a destination in the profile's revoked.txt stays out;
* the session's own ids in the rule become placeholders again;
* the whole new starting policy must prove to stay inside the ceiling, or
  nothing is written.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import ocsf, policyfile, profilecheck, stop
from .config import Settings
from .policyfile import Bindings, PolicyError
from .prover import Proof, Prover
from .store import Store


@dataclass
class PromotionPlan:
    profile: str
    add: dict[str, dict[str, Any]] = field(default_factory=dict)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    new_grants: dict[str, Any] = field(default_factory=dict)
    proof: Proof | None = None

    @property
    def ok(self) -> bool:
        return bool(self.add) and self.proof is not None and self.proof.ok


def plan(
    settings: Settings,
    store: Store,
    prover: Prover,
    profile: str,
    require_use: bool = True,
    min_hits: int = 1,
) -> PromotionPlan:
    current = dict(policyfile.network_rules(store.grants_template(profile)))
    bodies = {policyfile.digest(policyfile.rule_body(r)): n for n, r in current.items()}
    use = ocsf.usage(ocsf.read(ocsf.files(settings.ocsf_dir / profile)))
    result = PromotionPlan(profile=profile)
    revoked = store.revoked(profile)
    stops = stop.active_stops(store)

    for g in store.ledger("grant", profile=profile):
        name = g.get("rule_name") or ""
        rule = g.get("rule")
        if not name or not isinstance(rule, dict):
            result.skipped.append((name or "?", "ledger entry has no rule"))
            continue
        try:
            b = Bindings(g["session_id"], g["environment_id"], settings.api_host, settings.api_port)
        except (KeyError, PolicyError) as err:
            result.skipped.append((name, f"ledger entry is incomplete: {err}"))
            continue
        rule = policyfile.generalize(rule, b)
        body = policyfile.digest(policyfile.rule_body(rule))
        if body in bodies:
            result.skipped.append((name, f"already a starting grant as {bodies[body]!r}"))
            continue
        no = sorted(policyfile.destinations(rule) & revoked)
        if no:
            result.skipped.append((name, f"{no[0]} is in revoked.txt; delete the line to allow it again"))
            continue
        if stop.stopped(store, g["session_id"], str(g.get("agent_id") or ""), g["environment_id"], profile, stops):
            result.skipped.append((name, f"its session {g['session_id']} is stopped"))
            continue
        hits = use[name].hits_by_session.get(g["session_id"], 0) if name in use else 0
        if require_use and hits < min_hits:
            result.skipped.append((name, f"approved but used {hits} time(s) by its session; promotion needs {min_hits}"))
            continue
        final = name
        if final in current or final in result.add:
            final = f"{name}_{body[:8]}"
        # One bad ledger entry is skipped, never allowed to stop the profile:
        # the name must be valid and the rule must render for its session.
        try:
            policyfile.check_rule_name(final)
            policyfile.render({"network_policies": {final: rule}}, b)
        except PolicyError as err:
            result.skipped.append((name, f"cannot be promoted: {err}"))
            continue
        # A person may have approved such a rule at the gateway for one
        # session. Left in, it would fail the proof of every later plan.
        why = policyfile.unenforced(rule)
        if why:
            result.skipped.append((name, f"cannot be promoted: {why}"))
            continue
        # On its own first: a grant that no longer proves (the ceiling narrowed, or it was approved at the
        # gateway) is skipped, rather than failing the proof of every plan from now on.
        alone = profilecheck.within_ceiling(settings, store, prover, profile, {"network_policies": {**current, final: rule}})
        if alone.result == "error":
            raise PolicyError(alone.summary())
        if not alone.ok:
            result.skipped.append((name, f"cannot be promoted: {alone.summary()}"))
            continue
        # The ledger stores rules with sorted keys; restore the schema's order.
        rule = {"name": final, **{k: rule[k] for k in ("endpoints", "binaries") if k in rule},
                **{k: v for k, v in rule.items() if k not in ("name", "endpoints", "binaries")}}
        result.add[final] = rule
        bodies[body] = final

    result.new_grants = {"network_policies": {**current, **result.add}}
    if result.add:
        result.proof = profilecheck.within_ceiling(settings, store, prover, profile, result.new_grants)
    return result


def apply(store: Store, p: PromotionPlan) -> None:
    if not p.ok:
        raise PolicyError("refusing to write a promotion that did not prove inside the ceiling")
    store.write_grants(p.profile, p.new_grants)
    store.record(
        "promote",
        profile=p.profile,
        added=sorted(p.add),
        rules=p.add,
        proof=p.proof.result if p.proof else None,
        policy_digest=policyfile.digest(p.new_grants),
    )
