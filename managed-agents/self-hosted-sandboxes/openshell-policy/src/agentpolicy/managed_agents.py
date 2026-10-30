"""The Claude Managed Agents side: sessions, agents, and the worker's credentials.

Two kinds of caller use this module, with different credentials:

* the dispatcher, on the sandbox host, holds only one session's worker token
  (from the work item's secret) and uses it to read that session;
* the operator's tools hold your API key and create agents and sessions.

The dispatcher never holds your API key.
"""

from __future__ import annotations

import base64
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from .policyfile import AGENT_RE

BETA = "managed-agents-2026-04-01"
VERSION_RE = re.compile(r"^[A-Za-z0-9._-]{1,63}$")



def headers(token: str) -> dict[str, str]:
    return {
        "authorization": f"Bearer {token}",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": BETA,
    }


def worker_token(work_secret_b64: str) -> str:
    """The session token inside a work item's ``secret``.

    The secret is URL-safe base64 of a JSON object that bundles the session
    token with others the worker does not use.
    """
    raw = work_secret_b64.strip()
    raw += "=" * (-len(raw) % 4)
    try:
        bundle = json.loads(base64.urlsafe_b64decode(raw))
    except (ValueError, json.JSONDecodeError) as err:
        raise ValueError("work secret is not base64 JSON") from err
    token = bundle.get("sessions_token") if isinstance(bundle, dict) else None
    if not token:
        raise ValueError("work secret carries no sessions_token")
    return str(token)


WEB_TOOLS = ("web_fetch", "web_search")


def outside_routes(agent: dict[str, Any]) -> list[str]:
    """The ways a session's agent reaches the network without passing its sandbox.

    Web tools and MCP servers run on Anthropic's side, where no sandbox policy
    applies. ``agent`` is the session's resolved agent, so what the session's
    creator overrode for this one session shows here too.
    """
    out = [f"MCP server {m.get('name') or m.get('url')!r}" for m in agent.get("mcp_servers") or [] if isinstance(m, dict)]
    for tool in agent.get("tools") or []:
        kind = str(tool.get("type") or "") if isinstance(tool, dict) else ""
        if kind.startswith("agent_toolset"):
            on = {name: bool((tool.get("default_config") or {}).get("enabled", True)) for name in WEB_TOOLS}
            for c in tool.get("configs") or []:
                if isinstance(c, dict) and c.get("name") in on:
                    on[c["name"]] = bool(c.get("enabled", True))
            out += [name for name in WEB_TOOLS if on[name]]
        elif kind != "custom":  # a custom tool runs in the caller's own code
            out.append(f"tool of type {kind or 'unknown'!r}")
    if agent.get("multiagent"):
        out.append("other agents it coordinates, whose tools are not checked")
    return out


def session_identity(base_url: str, session_id: str, token: str) -> dict[str, Any]:
    """The agent a session runs, read with the session's own token.

    The dispatcher puts the agent's id and version on the sandbox, and from
    there on every ledger entry and audit record, so each line can be joined
    to the agent that made it. The profile is not read here: it belongs to
    the environment, which the operator maps (``agentpolicy environment``).
    """
    for wait in (1, 3, None):  # a work item that fails here is not queued again, so one bad answer is not enough
        try:
            resp = httpx.get(f"{base_url.rstrip('/')}/v1/sessions/{session_id}", headers=headers(token), timeout=30)
            resp.raise_for_status()
            break
        except httpx.HTTPError:
            if wait is None:
                raise
            time.sleep(wait)
    agent = resp.json().get("agent") or {}
    agent_id = str(agent.get("id") or "")
    version = str(agent.get("version") if agent.get("version") is not None else "")
    if not AGENT_RE.match(agent_id):
        raise ValueError(f"session {session_id} names no well-formed agent id (got {agent_id!r})")
    if version and not VERSION_RE.match(version):
        raise ValueError(f"session {session_id}: malformed agent version {version!r}")
    return {"agent_id": agent_id, "agent_version": version, "outside_routes": outside_routes(agent)}


# ---------------------------------------------------------------------------
# Operator side: needs your API key.


def client(base_url: str, api_key: str = "") -> Any:
    """With no key, the SDK's own credential chain (ANTHROPIC_API_KEY, or the
    `ant auth login` profile)."""
    import anthropic

    return anthropic.Anthropic(base_url=base_url, api_key=api_key) if api_key else anthropic.Anthropic(base_url=base_url)



def interrupt(client: Any, session_id: str) -> None:
    """Asks the Managed Agents API to stop the session's current turn (``user.interrupt``)."""
    client.beta.sessions.events.send(session_id, events=[{"type": "user.interrupt"}])


def release_work(client: Any, environment_id: str, session_id: str) -> str:
    """Frees a session's work item that a refused worker left behind; returns what was done.

    When the dispatcher refuses a stopped session, the poller asks for a
    graceful stop that no worker is left to finish, and an item in ``stopping``
    is not released on any timer (observed on the Managed Agents API): the
    session would never be dispatched again. Force-stopping it lets the work
    queue take it afresh. An item in any other state is left as it is. See
    https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes-operations#stop-a-session-gracefully
    """
    state = str(client.beta.environments.work.retrieve(session_id, environment_id=environment_id).state)
    if state != "stopping":
        return state
    client.beta.environments.work.stop(session_id, environment_id=environment_id, force=True)
    return "force_stopped"


# The demo's resources, by the file `ant apply` creates each from: the key
# claude-lock.json records it under.
RESOURCES = {
    "agent_id": "./agents/hello.md",
    "reviewer_agent_id": "./agents/reviewer.md",
    "worker_environment_id": "./environments/worker.yaml",
    "reviewer_environment_id": "./environments/reviewer.yaml",
}


def resource_ids(project_dir: Path) -> dict[str, str]:
    """The demo's agents and environments, from the claude-lock.json `ant apply` writes."""
    lock = project_dir / "claude-lock.json"
    if not lock.exists():
        raise SystemExit(f"no {lock}: run `make apply`")
    resources = json.loads(lock.read_text()).get("resources", {})
    return {key: resources[f]["id"] for key, f in RESOURCES.items() if f in resources}


def run_session(client: Any, agent_id: str, environment_id: str, text: str) -> str:
    """Creates a session, sends one message, and prints the agent's replies.

    The session's policy profile is its environment's, as the operator mapped
    it on the sandbox host; nothing set here can choose it.
    """
    session = client.beta.sessions.create(agent=agent_id, environment_id=environment_id)
    print(f"session {session.id}", file=sys.stderr)
    events = client.beta.sessions.events
    with events.stream(session.id) as stream:
        events.send(session.id, events=[{"type": "user.message", "content": [{"type": "text", "text": text}]}])
        for event in stream:
            etype = getattr(event, "type", "")
            if etype == "agent.message":
                for block in getattr(event, "content", []) or []:
                    if getattr(block, "type", "") == "text":
                        print(block.text)
            elif etype == "agent.tool_use":
                print(f"  [tool] {getattr(event, 'name', '')}", file=sys.stderr)
            elif etype == "session.status_idle":
                stop = getattr(event, "stop_reason", None)
                if getattr(stop, "type", "") == "end_turn":
                    break
            elif etype in ("session.status_terminated", "session.error"):
                print(f"  [{etype}]", file=sys.stderr)
                break
    return session.id
