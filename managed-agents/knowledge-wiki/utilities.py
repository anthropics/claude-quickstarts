"""Shared helpers for the knowledge-graph cookbook notebook.

Two functions the notebook imports:

- `poll_until_end_turn` drives a Managed Agents session by polling
  `events.list` (rather than holding one long SSE stream) until the
  turn ends, printing agent text and file-write progress as it goes.
  Polling makes each request short and independently retryable, which
  matters for the long extraction turns this cookbook runs.

- `wait_for_idle_status` absorbs the small race between the SSE
  `session.status_idle` event and the server-side status field, so an
  `archive()` call issued right after a turn doesn't 400.
"""

import textwrap
import time

from anthropic import Anthropic


def wait_for_idle_status(
    client: Anthropic,
    session_id: str,
    max_wait: float = 30.0,
    max_total_wait: float = 300.0,
) -> None:
    """Poll until the session's server-side status field is `idle`.

    The `session.status_idle` event in the SSE stream can arrive
    slightly before `sessions.retrieve` reports `status == "idle"`,
    which causes an `archive()` call issued immediately after the
    stream exits to 400 with "cannot be archived while its status
    is running." This helper absorbs that race with a short poll.
    Call it after breaking out of a stream/poll loop and before
    `archive()`. Raises `TimeoutError` if the session is still not
    idle after `max_total_wait` seconds.
    """
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        if client.beta.sessions.retrieve(session_id).status == "idle":
            return
        time.sleep(0.25)
    # Still not idle: the stream may have died mid-turn (a transient SSE
    # error leaves the session genuinely running). Keep polling at a gentler
    # cadence until the turn actually finishes - archiving a running session
    # is a 400, and the work it is doing is work you want kept. Bounded so
    # a stuck session doesn't hang forever.
    hard_deadline = time.monotonic() + max_total_wait
    while client.beta.sessions.retrieve(session_id).status != "idle":
        if time.monotonic() >= hard_deadline:
            raise TimeoutError(
                f"session {session_id} still not idle after {max_total_wait}s"
            )
        time.sleep(5.0)


def _store_rel(path: str) -> str:
    """Store-relative path from an absolute /mnt/memory/... tool path."""
    parts = path.split("/")
    for i, seg in enumerate(parts):
        if seg == "memory" and i + 1 < len(parts):
            return "/".join(parts[i + 2 :]) or parts[-1]
    return parts[-1]


def poll_until_end_turn(
    client: Anthropic,
    session_id: str,
    poll_s: float = 5.0,
    timeout_s: float = 3600.0,
    sink: list | None = None,
    stats: dict | None = None,
) -> str:
    """Poll a session's events until the turn ends, printing agent text.

    Streaming a long extraction turn over one connection is fragile —
    proxies reset long-lived streams. Polling `events.list` makes every
    request short and independently retryable, so a network blip costs one
    poll instead of the turn. Sessions can also be RESCHEDULED server-side
    mid-turn (you'll see session.error / session.status_rescheduled events);
    the work still completes — keep polling, which is why the default
    timeout is generous. Prints `agent.message` text and marks tool use.

    Returns the turn outcome: "end_turn" on success, or the stop reason if
    the turn ended abnormally (e.g. repeated server errors) — callers can
    re-send the message to the same session to retry the turn. Pass `sink`
    to collect the agent's message text instead of printing it — useful
    when the reply is markdown you want to render properly. Pass `stats`
    (a dict) to collect token usage and read counts for the turn.
    """
    outcome = "end_turn"
    seen: set[str] = set()
    touched: dict[str, int] = {}
    searches = [0]
    deadline = time.time() + timeout_s
    idle = False
    while time.time() < deadline and not idle:
        try:
            events = list(client.beta.sessions.events.list(session_id=session_id))
        except Exception as e:  # transient network/API blip: retry
            print(f"  [poll retry] {type(e).__name__}")
            time.sleep(poll_s)
            continue
        for ev in events:
            if ev.id in seen:
                continue
            seen.add(ev.id)
            et = getattr(ev, "type", "")
            if et == "agent.message":
                for block in getattr(ev, "content", []) or []:
                    if getattr(block, "type", "") == "text":
                        if sink is not None:
                            sink.append(block.text)  # caller renders (e.g. as Markdown)
                        else:
                            print(textwrap.fill(block.text, width=100))
            elif et == "agent.tool_use":
                # semantic progress: name graph files as they are written,
                # count everything else quietly
                name = getattr(ev, "name", "?")
                inp = getattr(ev, "input", None) or {}
                path = str(inp.get("file_path") or inp.get("path") or "")
                if (
                    name in ("write", "create", "edit", "str_replace", "insert")
                    and path
                ):
                    rel = _store_rel(path)
                    verb = (
                        "+"
                        if name in ("write", "create") and rel not in touched
                        else "~"
                    )
                    if touched.get(rel, 0) == 0 or verb == "+":
                        print(f"  {verb} {rel}")
                    touched[rel] = touched.get(rel, 0) + 1
                else:
                    searches[0] += 1
            elif et == "span.model_request_end" and stats is not None:
                mu = getattr(ev, "model_usage", None)
                if mu is not None:
                    stats["input"] = stats.get("input", 0) + (
                        getattr(mu, "input_tokens", 0) or 0
                    )
                    stats["cache_write"] = stats.get("cache_write", 0) + (
                        getattr(mu, "cache_creation_input_tokens", 0) or 0
                    )
                    stats["cache_read"] = stats.get("cache_read", 0) + (
                        getattr(mu, "cache_read_input_tokens", 0) or 0
                    )
                    stats["output"] = stats.get("output", 0) + (
                        getattr(mu, "output_tokens", 0) or 0
                    )
                    stats["tokens_in"] = (
                        stats["input"] + stats["cache_write"] + stats["cache_read"]
                    )
                    stats["tokens_out"] = stats["output"]
            elif et == "session.status_idle":
                idle = True
                stop = getattr(ev, "stop_reason", None)
                outcome = (
                    getattr(stop, "type", "end_turn")
                    if stop is not None
                    else "end_turn"
                )
        if not idle:
            time.sleep(poll_s)
    if not idle:
        raise TimeoutError(f"session {session_id} did not go idle within {timeout_s}s")
    if stats is not None:
        stats["reads"] = searches[0]
    if touched or searches[0]:
        ents = sum(1 for k in touched if k.startswith("entities/"))
        shared = sorted(k for k in touched if not k.startswith("entities/"))
        bits = []
        if ents:
            bits.append(f"{ents} entity file(s)")
        if shared:
            bits.append(
                "updated " + ", ".join(shared[:4]) + ("…" if len(shared) > 4 else "")
            )
        bits.append(f"{searches[0]} reads/searches")
        print("  done: " + " · ".join(bits))
    if outcome != "end_turn":
        print(f"  [turn ended: {outcome}]")
    return outcome
