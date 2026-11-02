"""Reading OpenShell's OCSF audit records and measuring which rules were used.

Every network decision a sandbox's supervisor makes is an OCSF record: class
4001 (Network Activity) for a connection, 4002 (HTTP Activity) for one
inspected request. Allowed records name the rule that matched in
``firewall_rule.name``. That is the evidence ``promote`` and ``shrink`` rely
on.

Records live under ``state/ocsf/<profile>/``: the audit collector's
``<session>-gateway.jsonl`` (audit.py), and any OCSF JSON stored with
``ingest-ocsf``, whose lines may be bare JSON (the file in the sandbox) or
carry a prefix up to an ``OCSF-JSON`` marker (the supervisor's stderr).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

NETWORK = 4001
HTTP = 4002
MARKER = "OCSF-JSON"


def parse_line(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line:
        return None
    if not line.startswith("{"):
        idx = line.find(MARKER)
        if idx < 0:
            return None
        line = line[idx + len(MARKER):].strip()
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    return record if isinstance(record, dict) and "class_uid" in record else None


def read(paths: Iterable[Path]) -> Iterator[dict[str, Any]]:
    """Yields each record once, however many files repeat it."""
    seen: set[str] = set()
    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                record = parse_line(line)
                if record is None:
                    continue
                uid = (record.get("metadata") or {}).get("uid")
                if uid:
                    if uid in seen:
                        continue
                    seen.add(uid)
                yield record


def files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.jsonl")) if root.is_dir() else []


def allowed(record: dict[str, Any]) -> bool:
    return record.get("action") == "Allowed" or record.get("action_id") == 1


def rule_name(record: dict[str, Any]) -> str:
    name = (record.get("firewall_rule") or {}).get("name") or ""
    return "" if name == "-" else name


@dataclass
class RuleUse:
    connections: int = 0
    requests: int = 0
    last_seen_ms: int = 0
    binaries: set[str] = field(default_factory=set)
    hits_by_session: dict[str, int] = field(default_factory=dict)

    @property
    def hits(self) -> int:
        return self.connections + self.requests


def usage(records: Iterable[dict[str, Any]], since_ms: int = 0) -> dict[str, RuleUse]:
    """Counts allowed decisions per rule name, from ``since_ms`` on."""
    out: dict[str, RuleUse] = {}
    for r in records:
        if r.get("class_uid") not in (NETWORK, HTTP) or not allowed(r):
            continue
        t = int(r.get("time") or 0)
        if t < since_ms:
            continue
        name = rule_name(r)
        if not name:
            continue
        u = out.setdefault(name, RuleUse())
        u.last_seen_ms = max(u.last_seen_ms, t)
        proc = ((r.get("actor") or {}).get("process") or {}).get("name")
        if proc:
            u.binaries.add(proc)
        session = session_of(r)
        if session:
            u.hits_by_session[session] = u.hits_by_session.get(session, 0) + 1
        if r.get("class_uid") == HTTP:
            u.requests += 1
        else:
            u.connections += 1
    return out


def session_of(record: dict[str, Any]) -> str:
    return str((record.get("unmapped") or {}).get("managed_agents_session_id") or "")


def tag(record: dict[str, Any], session_id: str, profile: str,
        agent_id: str = "", agent_version: str = "") -> dict[str, Any]:
    """Adds the Managed Agents session, agent and profile to a record from a sandbox.

    OCSF's ``unmapped`` object is the place the schema reserves for fields it
    has no attribute for.
    """
    unmapped = dict(record.get("unmapped") or {})
    unmapped["managed_agents_session_id"] = session_id
    unmapped["policy_profile"] = profile
    if agent_id:
        unmapped["managed_agents_agent_id"] = agent_id
    if agent_version:
        unmapped["managed_agents_agent_version"] = agent_version
    return {**record, "unmapped": unmapped}
