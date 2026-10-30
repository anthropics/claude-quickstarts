"""The agentpolicy command."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from . import managed_agents, config, ocsf, policyfile, profilecheck, promote, shrink
from .policyfile import Bindings, PolicyError
from .prover import CliProver, Enforced
from .store import Store


def _settings(args: argparse.Namespace) -> config.Settings:
    return config.load(args.config)


def _prover(s: config.Settings) -> Enforced:
    return Enforced(CliProver(s.prover, s.prover_timeout))


def _read_secret(path: str | None) -> str:
    if path:
        return Path(path).read_text().strip()
    return sys.stdin.read().strip()


def _api_key_if_any(args: argparse.Namespace) -> str:
    if getattr(args, "api_key_file", None):
        return Path(args.api_key_file).read_text().strip()
    return ""


def _control_plane(args: argparse.Namespace) -> Any:
    """A client for operator calls (interrupt, freeing work items), or None.

    An API key from --api-key-file when given; otherwise the SDK's own
    credentials (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN or an `ant auth
    login` profile) when this process has any. Never on the sandbox host:
    start.sh clears these.
    """
    key = _api_key_if_any(args)
    if key:
        return managed_agents.client(args.base_url, key)
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") \
            or (Path.home() / ".config" / "anthropic").is_dir():
        return managed_agents.client(args.base_url)
    return None


def _interrupter(args: argparse.Namespace) -> Any:
    """``user.interrupt`` for a session, when this process has a control-plane credential; else None."""
    client = _control_plane(args)
    if client is None:
        return None
    return lambda session_id: managed_agents.interrupt(client, session_id)


# ---- sandbox preparation (dispatcher) ---------------------------------------


def cmd_prepare(args: argparse.Namespace) -> int:
    """Writes the starting policy for one session, after proving it inside the ceiling."""
    s = _settings(args)
    store = Store(s)
    b = Bindings(args.session, args.environment, s.api_host, s.api_port)
    starting = store.starting_policy(args.profile, b)
    ceiling = store.ceiling(args.profile, b)
    proof = _prover(s).check(starting, ceiling)
    store.record(
        "dispatch", profile=args.profile, session_id=args.session, environment_id=args.environment,
        agent_id=args.agent, agent_version=args.agent_version,
        proof=proof.result, policy_digest=policyfile.digest(starting),
    )
    if not proof.ok:
        print(f"refusing to create the sandbox: the starting policy is not proved inside the ceiling: {proof.summary()}",
              file=sys.stderr)
        return 1
    Path(args.out).write_text(policyfile.dump(starting))
    return 0


REPLACE_EXIT = 4


def cmd_verify_sandbox(args: argparse.Namespace) -> int:
    """Proves an existing sandbox's policy inside its profile's current ceiling.

    Exit 0: inside. Exit 4: outside, or not fit to reuse (replace the sandbox,
    /workspace included). Any other exit is no answer: the ceiling is not
    trusted, the prover gave no verdict, or this command failed. Run nothing,
    and keep the sandbox. Replacing deletes the session's work, so it has an
    exit code no failure shares.
    """
    s = _settings(args)
    store = Store(s)
    b = Bindings(args.session, args.environment, s.api_host, s.api_port)
    ceiling = store.ceiling(args.profile, b)
    current = policyfile.parse(Path(args.policy).read_text(), args.policy)
    why_not = _unfit_for_reuse(store, args, b, current)
    if why_not:
        store.record("reverify", profile=args.profile, session_id=args.session, environment_id=args.environment,
                     agent_id=args.agent, agent_version=args.agent_version, proof=None, refused=why_not)
        print(f"the sandbox cannot be reused: {why_not}", file=sys.stderr)
        return REPLACE_EXIT
    proof = _prover(s).check(current, ceiling)
    store.record("reverify", profile=args.profile, session_id=args.session, environment_id=args.environment,
                 agent_id=args.agent, agent_version=args.agent_version,
                 proof=proof.result, policy_digest=policyfile.digest(current))
    if not proof.ok:
        print(f"the sandbox's policy is not proved inside the current ceiling: {proof.summary()}", file=sys.stderr)
        return REPLACE_EXIT if proof.result == "exceeds_boundary" else 2
    return 0


def _unfit_for_reuse(store: Store, args: argparse.Namespace, b: Bindings, current: dict[str, Any]) -> str:
    """Why an existing sandbox must be replaced even if its policy fits, or "".

    * It must have been made for this profile and agent. Its labels, which
      the reviewer, the audit collector and stops go by, are fixed at
      creation, so a remapped environment needs a new sandbox.
    * It must still hold the base policy's rules. A stop takes every network
      rule away; a sandbox left like that cannot reach the Managed Agents API.
    """
    made = None
    for e in store.ledger("dispatch"):
        if e.get("session_id") == args.session:
            made = e
    if made is None:
        return "no record of this sandbox being made"
    if made.get("profile") != args.profile:
        return f"made for profile {made.get('profile')}, but its environment now maps to {args.profile}"
    if args.agent and made.get("agent_id") != args.agent:
        return f"made for agent {made.get('agent_id') or '(unrecorded)'}, not {args.agent}"
    missing = set(policyfile.network_rules(store.base(b))) - set(policyfile.network_rules(current))
    if missing:
        return f"it lacks the base rules {sorted(missing)} (stopped and locked down?)"
    return ""


def cmd_session_identity(args: argparse.Namespace) -> int:
    """Prints the session's agent id and version as JSON, read with its work secret.

    With --profile, exits 1 unless the profile admits that agent as this
    session runs it.
    """
    token = managed_agents.worker_token(_read_secret(args.secret_file))
    try:
        identity = managed_agents.session_identity(args.base_url, args.session, token)
    except (ValueError, httpx.HTTPError) as err:
        print(f"cannot read session {args.session}: {err}", file=sys.stderr)
        return 1
    if args.profile:
        ps = _settings(args).profile_settings(args.profile)
        if ps.agents and identity["agent_id"] not in ps.agents:
            print(f"profile {args.profile} does not list agent {identity['agent_id']}", file=sys.stderr)
            return 1
        if identity["outside_routes"] and not ps.outside_routes:
            print(f"this session's agent reaches the network outside its sandbox: {', '.join(identity['outside_routes'])}. "
                  f"Turn them off, or set profiles.{args.profile}.outside_routes to accept them", file=sys.stderr)
            return 1
    print(json.dumps(identity, sort_keys=True))
    return 0


def cmd_environment(args: argparse.Namespace) -> int:
    """Reads or sets which profile an environment's sessions run under (operator only)."""
    store = Store(_settings(args))
    if args.action == "list":
        for env_id, profile in sorted(store.environments().items()):
            print(f"{env_id}\t{profile}")
        return 0
    if not args.environment:
        raise SystemExit(f"environment {args.action} needs an environment id")
    if args.action == "get":
        print(store.profile_for_environment(args.environment))
        return 0
    if not args.profile:
        raise SystemExit("environment set needs a profile")
    store.set_environment(args.environment, args.profile)
    print(f"{args.environment} -> {args.profile} ({store.s.environments_path})")
    return 0


# ---- stopping ------------------------------------------------------------------


def _scope(args: argparse.Namespace) -> Any:
    from .stop import Scope

    if args.all:
        return Scope("all")
    for kind in ("session", "agent", "environment", "profile"):
        value = getattr(args, kind)
        if value:
            return Scope(kind, value)
    raise SystemExit("name what to cover: --session, --agent, --environment, --profile or --all")


STOPPED_EXIT = 3

# The Managed Agents API as operator tools reach it.
DEFAULT_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com"


def cmd_stopped(args: argparse.Namespace) -> int:
    """Exit 0 if no stop covers this session; exit 3, printing the reason, if one does.

    Any other exit (an error) must be read as "stopped": the dispatcher does.
    """
    from .stop import stopped

    store = Store(_settings(args))
    e = stopped(store, args.session, args.agent, args.environment, args.profile)
    if e is None:
        return 0
    # The refused session's work item is left stopping at the API; resume
    # finds it by this entry and frees it.
    store.record("refused", scope=e.get("scope"), target=e.get("target"), session_id=args.session,
                 agent_id=args.agent, environment_id=args.environment, profile=args.profile)
    covers = " ".join(x for x in (e.get("scope"), e.get("target")) if x)
    print(f"stopped ({covers}, {e.get('ts')}, by {e.get('by')}): {e.get('reason')}")
    return STOPPED_EXIT


def cmd_stop(args: argparse.Namespace) -> int:
    from . import gateway
    from .stop import Stopper

    s = _settings(args)
    scope = _scope(args)
    # Neither a missing gateway nor a missing key may keep the stop from being
    # recorded: the record is what makes the dispatcher refuse the sessions.
    gw = interrupt = None
    try:
        gw = gateway.connect(s)
    except Exception as err:
        print(f"agentpolicy: no OpenShell gateway ({err}); recording the stop without halting sandboxes", file=sys.stderr)
    if not args.no_interrupt:
        try:
            interrupt = _interrupter(args)
        except Exception as err:
            print(f"agentpolicy: cannot interrupt sessions ({err})", file=sys.stderr)
    stopper = Stopper(Store(s), gw, s.sandbox_label, interrupt)
    entry = stopper.stop(scope, args.reason, by=args.by)
    if entry:
        print(f"recorded in {s.ledger_path}; a dispatcher that reads another ledger does not see it")
    else:
        print(f"agentpolicy: THE STOP IS NOT RECORDED ({s.ledger_path} could not be written), so the dispatcher "
              "still serves these sessions. Stop the dispatcher, free the disk, and run the same stop again.",
              file=sys.stderr)
    interrupts = stopper.failures.count("interrupt")
    halts = sorted(set(stopper.failures) - {"interrupt", "record"})
    if halts:
        print(f"agentpolicy: a sandbox this stop covers may still be running (failed: {', '.join(halts)}). "
              "Run the same stop again once the gateway answers.", file=sys.stderr)
    if interrupts:
        print(f"agentpolicy: {interrupts} session(s) could not be sent user.interrupt; "
              "see the halt entries in the ledger.", file=sys.stderr)
    return 1 if stopper.failures else 0


def cmd_resume(args: argparse.Namespace) -> int:
    from .stop import Stopper

    s = _settings(args)
    scope = _scope(args)
    release = interrupt = None
    try:
        client = _control_plane(args)
        if client is not None:
            release = lambda environment, session: managed_agents.release_work(client, environment, session)  # noqa: E731
            interrupt = lambda session: managed_agents.interrupt(client, session)  # noqa: E731
    except Exception as err:  # the resume is still recorded
        print(f"agentpolicy: cannot reach the Managed Agents API to free work items ({err})", file=sys.stderr)
    Stopper(Store(s), None, s.sandbox_label, interrupt, release=release).resume(scope, by=args.by)
    print(f"recorded in {s.ledger_path}")
    return 0


SETTINGS_FOR_SCRIPTS = {
    "sandbox_base_url": lambda s: s.sandbox_base_url,
    "sandbox_label": lambda s: s.sandbox_label,
}


def cmd_setting(args: argparse.Namespace) -> int:
    print(SETTINGS_FOR_SCRIPTS[args.name](_settings(args)))
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    s = _settings(args)
    out_dir = s.ocsf_dir / args.profile
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{args.session}-{int(time.time())}.jsonl"
    n = 0
    with open(out, "w", encoding="utf-8") as fh:
        for line in sys.stdin:
            record = ocsf.parse_line(line)
            if record is None:
                continue
            record = ocsf.tag(record, args.session, args.profile, args.agent, args.agent_version)
            fh.write(json.dumps(record, sort_keys=True) + "\n")
            n += 1
    if n == 0:
        out.unlink()
    print(f"{n} OCSF record(s) from {args.session}", file=sys.stderr)
    return 0


# ---- audit -----------------------------------------------------------------


def cmd_collect_audit(args: argparse.Namespace) -> int:
    from . import audit, gateway

    s = _settings(args)
    collector = audit.Collector(s, Store(s), gateway.connect(s))
    print(f"collecting audit evidence for sandboxes labelled app={s.sandbox_label} into {s.ocsf_dir}, "
          f"and denied decisions into {s.denied_dir}")
    collector.run(interval=args.interval)
    return 0


# ---- grow ------------------------------------------------------------------


def cmd_grow(args: argparse.Namespace) -> int:
    from . import gateway, grow

    s = _settings(args)
    store = Store(s)
    gw = gateway.connect(s)
    reviewer = None
    if s.review.mode == "claude":
        from .claude_reviewer import ClaudeReviewer, ReviewerIds

        state = managed_agents.resource_ids(s.project_dir)
        reviewer = ClaudeReviewer(
            managed_agents.client(args.base_url, _api_key_if_any(args)),
            ReviewerIds(state["reviewer_agent_id"], state["reviewer_environment_id"]),
        )
    from .stop import Stopper

    stopper = Stopper(store, gw, s.sandbox_label, _interrupter(args))
    grower = grow.Grower(s, store, gw, _prover(s), reviewer, stopper=stopper)
    if args.once:
        grower.run_once()
    else:
        grow.watch(args.interval, grower)
    return 0


# ---- promote and shrink -----------------------------------------------------


def _print_diff(path: Path, new: str) -> None:
    """The change to a profile's file as a patch, for a person to read and merge."""
    old = path.read_text() if path.exists() else ""
    sys.stdout.writelines(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                               fromfile=f"a/{path.name}", tofile=f"b/{path.name}"))


def _print_proof(label: str, proof: Any) -> None:
    if proof is not None:
        print(f"  {label}: {proof.summary()}")


def cmd_promote(args: argparse.Namespace) -> int:
    s = _settings(args)
    store = Store(s)
    p = promote.plan(s, store, _prover(s), args.profile, require_use=not args.include_unused, min_hits=args.min_hits)
    print(f"promote {args.profile}:")
    for name in p.add:
        print(f"  + {name}")
    for name, why in p.skipped:
        print(f"  = {name}: {why}")
    _print_proof("ceiling proof", p.proof)
    if not p.add:
        print("  nothing to promote")
        return 0
    if not p.ok:
        return 1
    _print_diff(s.profile_dir(args.profile) / "policy.yaml", store.grants_text(args.profile, p.new_grants))
    if args.apply:
        promote.apply(store, p)
        print(f"  wrote {s.profile_dir(args.profile) / 'policy.yaml'}")
    else:
        print("  nothing written; read the diff, then run again with --apply")
    return 0


def cmd_shrink(args: argparse.Namespace) -> int:
    s = _settings(args)
    store = Store(s)
    p = shrink.plan(
        s, store, _prover(s), args.profile,
        window_days=args.window_days, min_hits=args.min_hits,
        allow_short_evidence=args.allow_short_evidence,
        allow_missing_evidence=args.allow_missing_evidence,
    )
    if p.refused:
        print(f"shrink {args.profile} over {p.window_days} days:\n  refused: {p.refused}")
        return 1
    print(f"shrink {args.profile} over {p.window_days} days, {p.sessions} session(s) with records:")
    for name, why in p.removed:
        print(f"  - {name}: {why}")
    for name, hits in p.kept:
        print(f"  = {name}: {hits} use(s)")
    _print_proof("no wider than before", p.no_wider)
    _print_proof("inside the ceiling", p.within_ceiling)
    if not p.changed:
        print("  nothing to shrink")
        return 0
    if not p.ok:
        return 1
    _print_diff(s.profile_dir(args.profile) / "policy.yaml", store.grants_text(args.profile, p.new_grants))
    _print_diff(s.profile_dir(args.profile) / "revoked.txt", store.revoked_text(args.profile, p.revoke))
    if args.apply:
        shrink.apply(store, p)
        print(f"  wrote {s.profile_dir(args.profile) / 'policy.yaml'}")
    else:
        print("  nothing written; read the diff, then run again with --apply")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Verifies every profile's ceiling signature and proves its grants inside it."""
    s = _settings(args)
    s.protect_signers = False  # that setting is about the service account; the policy owner and CI run this
    store = Store(s)
    profiles = [args.profile] if args.profile else store.profiles()
    if not profiles:
        raise PolicyError(f"no profiles under {s.policy_dir / 'profiles'}, so nothing was checked")
    failed = 0
    for profile in profiles:
        try:
            store.revoked(profile)
            proof = profilecheck.within_ceiling(s, store, _prover(s), profile, store.grants_template(profile))
            status = proof.summary()
            failed += 0 if proof.ok else 1
        except PolicyError as err:
            status = f"error: {err}"
            failed += 1
        print(f"{profile}: {status}")
    return 1 if failed else 0


def cmd_ceiling(args: argparse.Namespace) -> int:
    from . import signing

    # The policy owner makes keys on their own machine, where there is no config.
    if args.action == "keygen":
        if not args.key or not args.identity:
            raise SystemExit("keygen needs --key (where to write the private key) and --identity")
        key = signing.generate(Path(args.key))
        print(f"wrote {args.key}; add this entry to the signers file (policy/signers.yaml):")
        print(f"  - identity: {args.identity}\n    public_key: {signing.public_key_text(key)}")
        return 0
    if args.action == "pubkey":
        if not args.key or not args.identity:
            raise SystemExit("pubkey needs --key and --identity")
        key = signing.load_private_key(Path(args.key))
        print(f"  - identity: {args.identity}\n    public_key: {signing.public_key_text(key)}")
        return 0
    s = _settings(args)
    s.protect_signers = False  # as in check
    store = Store(s)
    if not args.profile:
        raise SystemExit(f"{args.action} needs --profile")
    if args.action == "sign":
        if not args.key or not args.identity:
            raise SystemExit("sign needs --key and --identity")
        path = store.sign_ceiling(args.profile, Path(args.key), args.identity)
        store.verify_ceiling(args.profile)
        print(f"signed {args.profile} as {args.identity}: {path}")
        return 0
    who = store.verify_ceiling(args.profile)
    print(f"{args.profile}: signed by {who}; base and ceiling unchanged since")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    s = _settings(args)
    store = Store(s)
    print(f"policy: {s.policy_dir}\nledger: {s.ledger_path}")
    for profile in [args.profile] if args.profile else store.profiles():
        grants = policyfile.network_rules(store.grants_template(profile))
        counts: dict[str, int] = {}
        for e in store.ledger(profile=profile):
            key = e["kind"] if e["kind"] != "decision" else f"decision:{e.get('action')}"
            counts[key] = counts.get(key, 0) + 1
        proposals = "on" if s.profile_settings(profile).proposals else "off"
        print(f"{profile}: {len(grants)} starting grant(s) {sorted(grants)}; proposals {proposals}")
        for key in sorted(counts):
            print(f"  {key}: {counts[key]}")
    from .stop import active_stops

    for e in active_stops(store):
        covers = " ".join(x for x in (e.get("scope"), e.get("target")) if x)
        print(f"stop in force: {covers} since {e.get('ts')} by {e.get('by')}: {e.get('reason')}")
    return 0


# ---- Managed Agents operator commands ---------------------------------------------------


def cmd_agents_run(args: argparse.Namespace) -> int:
    s = _settings(args)
    state = managed_agents.resource_ids(s.project_dir)
    env_id = args.environment or os.environ.get("ANTHROPIC_ENVIRONMENT_ID") or state.get("worker_environment_id")
    if not env_id:
        raise SystemExit("no worker environment: pass --environment, or run `make apply`")
    client = managed_agents.client(args.base_url, _api_key_if_any(args))
    session_id = managed_agents.run_session(client, args.agent or state["agent_id"], env_id, args.message)
    if args.session_id_file:
        Path(args.session_id_file).write_text(session_id + "\n")
    return 0


# ---- parser -------------------------------------------------------------------


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agentpolicy", description=__doc__)
    p.add_argument("--config", help="path to agentpolicy.yaml (default: $AGENTPOLICY_CONFIG or ./agentpolicy.yaml)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("prepare", help="write one session's starting policy, proved inside its ceiling")
    sp.add_argument("--profile", required=True)
    sp.add_argument("--session", required=True)
    sp.add_argument("--environment", required=True)
    sp.add_argument("--agent", default="")
    sp.add_argument("--agent-version", default="")
    sp.add_argument("--out", required=True)
    sp.set_defaults(fn=cmd_prepare)

    sp = sub.add_parser("session-identity", help="print a session's agent id and version, using its work secret")
    sp.add_argument("--base-url", required=True)
    sp.add_argument("--session", required=True)
    sp.add_argument("--secret-file", help="file holding the work secret (default: standard input)")
    sp.add_argument("--profile", default="", help="refuse an agent this profile does not admit")
    sp.set_defaults(fn=cmd_session_identity)

    sp = sub.add_parser("environment", help="which profile each Managed Agents environment runs under (operator-owned)")
    sp.add_argument("action", choices=["get", "set", "list"])
    sp.add_argument("environment", nargs="?")
    sp.add_argument("profile", nargs="?")
    sp.set_defaults(fn=cmd_environment)

    def scope_args(sp: argparse.ArgumentParser, exclusive: bool) -> None:
        g = sp.add_mutually_exclusive_group(required=exclusive) if exclusive else sp
        for kind in ("session", "agent", "environment", "profile"):
            g.add_argument(f"--{kind}", default="")
        if exclusive:
            g.add_argument("--all", action="store_true")

    sp = sub.add_parser("stopped", help="for the dispatcher: exit 0 if no stop covers this session, 3 if one does")
    scope_args(sp, exclusive=False)
    sp.set_defaults(fn=cmd_stopped)

    sp = sub.add_parser("stop", help="kill switch: deny, stop and interrupt sessions, and refuse them new sandboxes")
    scope_args(sp, exclusive=True)
    sp.add_argument("--reason", required=True)
    sp.add_argument("--by", default=os.environ.get("USER") or "operator")
    sp.add_argument("--no-interrupt", action="store_true", help="do not send user.interrupt to the Managed Agents API")
    sp.add_argument("--base-url", default=DEFAULT_BASE_URL)
    sp.add_argument("--api-key-file", help="an API key, for user.interrupt (default: the SDK's own credentials)")
    sp.set_defaults(fn=cmd_stop)

    sp = sub.add_parser("resume", help="lift a stop with the same scope, and free the work items it left stuck")
    scope_args(sp, exclusive=True)
    sp.add_argument("--by", default=os.environ.get("USER") or "operator")
    sp.add_argument("--base-url", default=DEFAULT_BASE_URL)
    sp.add_argument("--api-key-file", help="an API key, to free refused sessions' work items "
                    "(default: the SDK's own credentials)")
    sp.set_defaults(fn=cmd_resume)

    sp = sub.add_parser("setting", help="print one setting, for the dispatcher scripts")
    sp.add_argument("name", choices=sorted(SETTINGS_FOR_SCRIPTS))
    sp.set_defaults(fn=cmd_setting)

    sp = sub.add_parser("verify-sandbox", help="prove an existing sandbox's policy inside its current ceiling")
    sp.add_argument("--profile", required=True)
    sp.add_argument("--session", required=True)
    sp.add_argument("--environment", required=True)
    sp.add_argument("--agent", default="")
    sp.add_argument("--agent-version", default="")
    sp.add_argument("--policy", required=True, help="the sandbox's policy, from `openshell sandbox get --policy-only`")
    sp.set_defaults(fn=cmd_verify_sandbox)

    sp = sub.add_parser("ingest-ocsf", help="store a sandbox's OCSF records, read from standard input")
    sp.add_argument("--profile", required=True)
    sp.add_argument("--session", required=True)
    sp.add_argument("--agent", default="")
    sp.add_argument("--agent-version", default="")
    sp.set_defaults(fn=cmd_ingest)

    sp = sub.add_parser("collect-audit", help="follow every worker sandbox's decisions from the gateway as evidence of use")
    sp.add_argument("--interval", type=float, default=5.0, help="seconds between looks for new sandboxes")
    sp.set_defaults(fn=cmd_collect_audit)

    sp = sub.add_parser("grow", help="decide pending proposals in every worker sandbox")
    sp.add_argument("--once", action="store_true")
    sp.add_argument("--interval", type=float, default=3.0)
    sp.add_argument("--base-url", default=DEFAULT_BASE_URL)
    sp.add_argument("--api-key-file", help="an API key: the claude reviewer, and user.interrupt when the "
                    "breaker stops a session (default: the SDK's own credentials)")
    sp.set_defaults(fn=cmd_grow)

    sp = sub.add_parser("promote", help="show, as a diff, the used and approved grants that could become starting grants")
    sp.add_argument("--profile", required=True)
    sp.add_argument("--apply", action="store_true", help="write the diff; for a person who has read it")
    sp.add_argument("--include-unused", action="store_true", help="promote grants with no recorded use")
    sp.add_argument("--min-hits", type=int, default=1)
    sp.set_defaults(fn=cmd_promote)

    sp = sub.add_parser("shrink", help="show, as a diff, the starting grants sessions stopped using")
    sp.add_argument("--profile", required=True)
    sp.add_argument("--apply", action="store_true", help="write the diff; for a person who has read it")
    sp.add_argument("--window-days", type=int)
    sp.add_argument("--min-hits", type=int)
    sp.add_argument("--allow-short-evidence", action="store_true",
                    help="run even if the records do not reach back to the start of the window")
    sp.add_argument("--allow-missing-evidence", action="store_true",
                    help="run even if some sessions in the window left no OCSF records")
    sp.set_defaults(fn=cmd_shrink)

    sp = sub.add_parser("check", help="verify ceilings and prove every profile's grants inside them")
    sp.add_argument("--profile")
    sp.set_defaults(fn=cmd_check)

    sp = sub.add_parser("ceiling", help="create a signing key, print its signers entry, or sign or verify a profile's ceiling")
    sp.add_argument("action", choices=["keygen", "pubkey", "sign", "verify"])
    sp.add_argument("--profile")
    sp.add_argument("--key", help="Ed25519 private key file (PEM)")
    sp.add_argument("--identity", help="who signs, as listed in signers.yaml")
    sp.set_defaults(fn=cmd_ceiling)

    sp = sub.add_parser("status", help="summarize profiles and the ledger")
    sp.add_argument("--profile")
    sp.set_defaults(fn=cmd_status)

    cp = sub.add_parser("agents", help="the demo's Managed Agents sessions (uses your API credentials)")
    csub = cp.add_subparsers(dest="agents_cmd", required=True)
    sp = csub.add_parser("run", help="create a session of the demo agent and send it one message")
    sp.add_argument("--base-url", default=DEFAULT_BASE_URL)
    sp.add_argument("--api-key-file")
    sp.add_argument("--agent")
    sp.add_argument("--environment")
    sp.add_argument("--session-id-file", help="write the new session's id here")
    sp.add_argument("message")
    sp.set_defaults(fn=cmd_agents_run)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return int(args.fn(args) or 0)
    except (PolicyError, config.ConfigMissing) as err:
        print(f"agentpolicy: {err}", file=sys.stderr)
        return 2
    except FileNotFoundError as err:
        print(f"agentpolicy: {err.filename} does not exist", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
