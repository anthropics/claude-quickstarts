"""Collecting each worker sandbox's network decisions from the gateway.

The evidence promote and shrink need is which rules sandboxes actually used.
OpenShell's supervisor streams every decision to the gateway as it makes it;
this collector follows that stream for every worker sandbox and keeps the
allowed decisions under ``state/ocsf/<profile>/<session>-gateway.jsonl``, the
files ``ocsf.read`` takes. It runs beside the sandboxes, not in them, so
nothing the agent does can delete or rewrite what was collected, and nothing
depends on copying a file out before a sandbox stops.

A line counts only if it parses strictly (shorthand.py) and names a rule of
that sandbox's current policy, with, for a connection, a binary that rule
lists. Whatever the gateway says it skipped, or could not resume, is recorded
as an ``audit_gap``; shrink treats a gap like a session with no records, as
use it cannot see.

Denied decisions are kept too, as they arrive, under
``state/denied/<profile>/<session>.jsonl``. They are a record for people: the
gateway's own copy is an in-memory buffer that a restart or a deleted sandbox
loses. They are never evidence, so they live outside ``state/ocsf`` and are
stored unparsed, up to a size per session. Treat the text of each as partly
the agent's.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable

from . import ocsf, shorthand
from .gateway import CursorLost, LogEvent, SandboxRef
from .store import Store

Log = Callable[[str], None]

# The verdict sits where the supervisor writes it, before any text the agent chose.
_DENIED = re.compile(r"[A-Z]{1,16}:[A-Z]{1,16} \[[A-Z]{1,8}\] DENIED ")
# A denied line carries a path or URL the agent chose, then the supervisor's
# reason. A long one keeps both ends.
MAX_DENIED_CHARS = 2000
# Denials cost an agent nothing to make, and this shares a disk with the ledger.
MAX_DENIED_BYTES = 5_000_000


class Collector:
    def __init__(self, settings: Any, store: Store, gateway: Any, log: Log = print) -> None:
        self.s = settings
        self.store = store
        self.gateway = gateway
        self.log = log
        self.cursor_file = settings.state_dir / "audit" / "cursors.json"
        self._lock = threading.Lock()
        self._cursors: dict[str, dict[str, Any]] = self._load()
        self._threads: dict[str, threading.Thread] = {}
        self._full: set[Path] = set()

    # ---- the loop ----------------------------------------------------------

    def run(self, interval: float = 5.0, stop: threading.Event | None = None) -> None:
        stop = stop or threading.Event()
        while not stop.is_set():
            try:
                sandboxes = self.gateway.list_sandboxes(self.s.sandbox_label)
            except Exception as err:  # a gateway restart is routine; the cursors record what it cost
                self.log(f"could not list sandboxes, trying again: {err}")
                sandboxes = []
            for sb in sandboxes:
                t = self._threads.get(sb.name)
                if t is None or not t.is_alive():
                    t = threading.Thread(target=self._follow_forever, args=(sb,), daemon=True, name=sb.name)
                    self._threads[sb.name] = t
                    t.start()
            stop.wait(interval)

    def _follow_forever(self, sb: SandboxRef) -> None:
        try:
            self.follow(sb)
        except Exception as err:  # one sandbox's trouble must not stop the rest
            self.log(f"{sb.name}: log watch ended: {err}")

    def follow(self, sb: SandboxRef) -> int:
        """Follows one sandbox's stream until it ends. Returns records kept."""
        if not (sb.profile and sb.session_id):
            self.log(f"skip {sb.name}: missing profile or session label")
            return 0
        rules = self.gateway.policy_rules(sb.name)
        kept = 0
        cursor = self._cursors.get(sb.name, {}).get("cursor", "")
        while True:
            try:
                for ev in self.gateway.watch_logs(sb.name, cursor):
                    if ev.kind == "gap":
                        self._gap(sb, f"the gateway skipped log lines: {ev.message}")
                        continue
                    if ev.level.strip().upper() == "OCSF":
                        self._denied(sb, ev)
                        record, rules = self._evidence(sb, ev, rules)
                        if record is not None:
                            self._append(sb, record)
                            kept += 1
                    if ev.cursor:
                        cursor = ev.cursor
                        self._save(sb.name, cursor)
                return kept
            except CursorLost as err:
                # The buffer moved on or the gateway restarted: what happened
                # in between is unknown. Start over from what it still holds.
                self._gap(sb, f"could not resume the log watch: {err}")
                cursor = ""
                self._save(sb.name, "")

    # ---- one line -----------------------------------------------------------

    def _evidence(self, sb: SandboxRef, ev: LogEvent, rules: dict[str, list[str]]):
        if " ALLOWED " not in ev.message:
            return None, rules
        uid = f"openshell:{ev.sandbox_id or sb.id}:{ev.cursor}" if ev.cursor else ""
        record = shorthand.parse(ev.message, ev.time_ms, uid)
        if record is None:
            self.log(f"{sb.name}: dropped an allowed line that does not parse strictly: {ev.message[:200]!r}")
            return None, rules
        rule = record["firewall_rule"]["name"]
        if rule not in rules:
            rules = self.gateway.policy_rules(sb.name)  # a grant approved since
        if rule not in rules:
            self.log(f"{sb.name}: dropped a line naming {rule!r}, which is not a rule of its policy")
            return None, rules
        binary = ((record.get("actor") or {}).get("process") or {}).get("name")
        if binary and rules[rule] and binary not in rules[rule]:
            self.log(f"{sb.name}: dropped a line where {binary!r} used {rule!r}, which does not list it")
            return None, rules
        return ocsf.tag(record, sb.session_id, sb.profile, sb.agent_id, sb.agent_version), rules

    def _denied(self, sb: SandboxRef, ev: LogEvent) -> None:
        if not _DENIED.match(ev.message):
            return
        out = self.s.denied_dir / sb.profile / f"{sb.session_id}.jsonl"
        record = {"time": ev.time_ms, "cursor": ev.cursor, "session_id": sb.session_id, "profile": sb.profile,
                  "agent_id": sb.agent_id, "agent_version": sb.agent_version, "sandbox": sb.name, "message": ev.message}
        if len(ev.message) > MAX_DENIED_CHARS:
            half = MAX_DENIED_CHARS // 2
            record.update(message=ev.message[:half] + ev.message[-half:], truncated=True)
        if out.exists() and out.stat().st_size > MAX_DENIED_BYTES:
            if out not in self._full:
                self._full.add(out)
                self.log(f"{sb.name}: {out} is full; keeping no more of this session's denials")
                self._write(out, {**record, "message": "", "full": True})
            return
        self._write(out, record)

    # ---- storage ---------------------------------------------------------------

    def _append(self, sb: SandboxRef, record: dict[str, Any]) -> None:
        self._write(self.s.ocsf_dir / sb.profile / f"{sb.session_id}-gateway.jsonl", record)

    def _write(self, out: Path, record: dict[str, Any]) -> None:
        out.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, open(out, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    def _gap(self, sb: SandboxRef, reason: str) -> None:
        self.log(f"{sb.name}: audit gap: {reason}")
        self.store.record("audit_gap", profile=sb.profile, session_id=sb.session_id, agent_id=sb.agent_id,
                          sandbox=sb.name, reason=reason)

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            return json.loads(self.cursor_file.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save(self, sandbox: str, cursor: str) -> None:
        with self._lock:
            self._cursors[sandbox] = {"cursor": cursor, "at": int(time.time())}
            self.cursor_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = Path(f"{self.cursor_file}.tmp")
            tmp.write_text(json.dumps(self._cursors, sort_keys=True))
            os.replace(tmp, self.cursor_file)
