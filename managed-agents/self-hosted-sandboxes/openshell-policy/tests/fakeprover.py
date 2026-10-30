"""A test double for openshell-prover.

It decides containment with a simple structural comparison that agrees with
the real prover on the shapes these tests use: exact hosts and binaries,
REST endpoints in enforce mode, access presets and method/path rules with
``*`` and ``/**`` globs. It is not a prover and nothing outside tests/ uses
it. Real proofs come from the openshell-prover binary.

Run as a script, it takes the real prover's arguments and prints its JSON
envelope, so command-line tests can point AGENTPOLICY_PROVER at it.
"""

from __future__ import annotations

import fnmatch
import json
import sys
from typing import Any

import yaml

PRESETS = {
    "read-only": ["GET", "HEAD", "OPTIONS"],
    "read-write": ["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH"],
    "full": ["*"],
}


def _requests(ep: dict[str, Any]) -> list[tuple[str, str]]:
    if "access" in ep:
        return [(m, "/**") for m in PRESETS[ep["access"]]]
    return [(r["allow"]["method"], r["allow"]["path"]) for r in ep.get("rules") or []]


def _path_covers(bp: str, p: str) -> bool:
    if bp == p or bp == "/**":
        return True
    if bp.endswith("/**"):
        prefix = bp[:-3]
        return p == prefix or p.startswith(prefix + "/")
    if "**" in p:
        return False
    if "*" in bp:
        b_parts, p_parts = bp.split("/"), p.split("/")
        return len(b_parts) == len(p_parts) and all(fnmatch.fnmatchcase(x, y) for y, x in zip(b_parts, p_parts))
    return False


def _req_covered(req: tuple[str, str], allowed: list[tuple[str, str]]) -> bool:
    m, p = req
    return any((bm == "*" or bm == m) and _path_covers(bp, p) for bm, bp in allowed)


class Result(Exception):
    def __init__(self, result: str, counterexample: dict[str, Any] | None = None, reason: str | None = None):
        self.result, self.counterexample, self.reason = result, counterexample, reason


def check(candidate: dict[str, Any], boundary: dict[str, Any]) -> dict[str, Any]:
    try:
        _check(candidate, boundary)
        result, ce, reason = "within_boundary", None, None
    except Result as r:
        result, ce, reason = r.result, r.counterexample, r.reason
    code = {"within_boundary": 0, "exceeds_boundary": 1, "error": 2}.get(result, 3)
    return {
        "schema_version": 1,
        "prover_version": "fake",
        "check": "boundary",
        "coverage": {"domains": ["filesystem", "network_l4", "network_rest", "process", "landlock"]},
        "result": result,
        "exit_code": code,
        "inputs": {"candidate": "candidate", "boundary": "boundary"},
        "counterexample": ce,
        "reason_code": None if code < 2 else "unsupported_policy_shape",
        "reason": reason,
    }


def _check(c: dict[str, Any], b: dict[str, Any]) -> None:
    if (b.get("landlock") or {}).get("compatibility") == "hard_requirement":
        if (c.get("landlock") or {}).get("compatibility") != "hard_requirement":
            raise Result("exceeds_boundary", {"domain": "landlock", "boundary": "hard_requirement",
                                              "candidate": (c.get("landlock") or {}).get("compatibility", "best_effort")})
    cfs, bfs = c.get("filesystem_policy") or {}, b.get("filesystem_policy") or {}
    b_rw, b_ro = set(bfs.get("read_write") or []), set(bfs.get("read_only") or [])
    for path in cfs.get("read_write") or []:
        if path not in b_rw:
            raise Result("exceeds_boundary", {"domain": "filesystem", "access": "read_write", "path": path})
    for path in cfs.get("read_only") or []:
        if path not in b_ro | b_rw:
            raise Result("exceeds_boundary", {"domain": "filesystem", "access": "read_only", "path": path})

    b_rules = list((b.get("network_policies") or {}).values())
    for rule in (c.get("network_policies") or {}).values():
        for bin_ in rule.get("binaries") or []:
            for ep in rule.get("endpoints") or []:
                _endpoint_covered(bin_["path"], ep, b_rules)


def _endpoint_covered(binary: str, ep: dict[str, Any], b_rules: list[dict[str, Any]]) -> None:
    host, port = ep.get("host"), ep.get("port")
    if ep.get("protocol") == "rest" and ep.get("enforcement") != "enforce":
        raise Result("unsupported", reason=f"REST endpoint {host}:{port} is in audit mode")
    allowed: list[tuple[str, str]] = []
    l4_ok = False
    for br in b_rules:
        if binary not in [x["path"] for x in br.get("binaries") or []]:
            continue
        for bep in br.get("endpoints") or []:
            if bep.get("host") != host or bep.get("port") != port:
                continue
            if bep.get("protocol") != "rest":
                l4_ok = True
            elif bep.get("enforcement") == "enforce":
                allowed.extend(_requests(bep))
    if l4_ok:
        return
    ce = {"domain": "network", "binary": binary, "ancestor_binary": None, "binary_identity_required": True,
          "host": host, "destination_ip": "203.0.113.1", "trusted_gateway": False, "port": port,
          "protocol": "rest", "method": None, "path": None}
    if ep.get("protocol") != "rest":
        ce["protocol"] = "tcp"
        raise Result("exceeds_boundary", ce)
    for req in _requests(ep):
        if not _req_covered(req, allowed):
            ce["method"], ce["path"] = req
            raise Result("exceeds_boundary", ce)


def main(argv: list[str]) -> int:
    # openshell-prover check CANDIDATE --boundary BOUNDARY [--output json] [--timeout T]
    args = argv[1:]
    if not args or args[0] != "check":
        print("usage: fakeprover check CANDIDATE --boundary BOUNDARY", file=sys.stderr)
        return 2
    candidate = args[1]
    boundary = args[args.index("--boundary") + 1]
    with open(candidate) as fh:
        c = yaml.safe_load(fh)
    with open(boundary) as fh:
        b = yaml.safe_load(fh)
    env = check(c, b)
    print(json.dumps(env))
    return env["exit_code"]


if __name__ == "__main__":
    sys.exit(main(sys.argv))
