"""Reading OpenShell's shorthand OCSF lines as evidence of use.

Where a sandbox's supervisor cannot write its OCSF JSON file (the 0.1.2
docker driver runs it as nobody on a read-only root), the only record of its
network decisions is the shorthand it streams to the gateway:

    NET:OPEN [INFO] ALLOWED /usr/bin/curl(58) -> example.com:443 [policy:r engine:opa]
    HTTP:GET [INFO] ALLOWED GET http://example.com/ [policy:r engine:l7]

Parts of these lines are chosen by the agent: the binary's path, the host and
the request path. They feed promote and shrink, so a line is read only if it
has exactly the shape above: one event, no control characters, one policy
token and it last (the supervisor writes it after everything the agent
chooses), and nothing with spaces or brackets where the agent's text goes.
Anything else is dropped, and a dropped line never counts as use. The rule a
line names must also be a rule of that sandbox's policy; that is the
collector's check (audit.py), since only it knows the policy.

Only allowed decisions are read: denials are not evidence of use. The
collector keeps those unparsed, in a file of their own.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from .ocsf import HTTP, NETWORK

_RULE = r"(?P<rule>[A-Za-z0-9_.-]{1,128})"
_TAIL = rf" \[policy:{_RULE}(?: engine:(?P<engine>opa|l7))?\]"
_SEV = r"\[[A-Z]{1,8}\]"
_HOST = r"(?P<host>[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?)"

_NET = re.compile(
    rf"NET:OPEN {_SEV} ALLOWED (?P<binary>/[^\s()\[\]]{{1,4096}})\((?P<pid>\d{{1,10}})\)"
    rf" -> {_HOST}:(?P<port>\d{{1,5}}){_TAIL}"
)
_HTTP = re.compile(
    rf"HTTP:(?P<verb>[A-Z]{{1,16}}) {_SEV} ALLOWED (?P<method>[A-Z]{{1,16}})"
    rf" (?P<url>https?://[^\s\[\]]{{1,8192}}){_TAIL}"
)


def _clean(message: str) -> bool:
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in message):
        return False
    return message.count("[policy:") == 1 and message.count(" -> ") <= 1


def parse(message: str, time_ms: int, uid: str) -> dict[str, Any] | None:
    """One shorthand line as an OCSF-shaped record ``ocsf.usage`` reads, or None."""
    if not _clean(message):
        return None
    if m := _NET.fullmatch(message):
        port = int(m["port"])
        if not 0 < port < 65536:
            return None
        return _record(NETWORK, m["rule"], time_ms, uid, {
            "actor": {"process": {"name": m["binary"]}},
            "dst_endpoint": {"domain": m["host"], "port": port},
        })
    if m := _HTTP.fullmatch(message):
        if m["verb"] != m["method"]:
            return None
        try:
            url = urlsplit(m["url"])
            port = url.port
        except ValueError:
            return None
        host = url.hostname or ""
        if not re.fullmatch(_HOST, host) or not url.path.startswith("/"):
            return None
        endpoint: dict[str, Any] = {"domain": host}
        if port:
            endpoint["port"] = port
        return _record(HTTP, m["rule"], time_ms, uid, {
            "dst_endpoint": endpoint,
            "http_request": {"http_method": m["method"], "url": {"hostname": host, "path": url.path}},
        })
    return None


def _record(class_uid: int, rule: str, time_ms: int, uid: str, extra: dict[str, Any]) -> dict[str, Any]:
    return {
        "class_uid": class_uid,
        "action": "Allowed",
        "action_id": 1,
        "time": time_ms,
        "firewall_rule": {"name": rule},
        "metadata": {"uid": uid, "product": {"name": "agentpolicy audit collector (OpenShell shorthand)"}},
        **extra,
    }
