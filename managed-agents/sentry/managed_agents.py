"""Shared client, env loading, and streaming helpers for the triage scripts."""

import os
import re
import sys

from anthropic import Anthropic
from dotenv import load_dotenv

# override=True matches ./agents/setup.sh, which sources .env over whatever the
# shell exports. Without it an ANTHROPIC_API_KEY in your shell would make
# Python talk to a different workspace than the one setup.sh provisioned.
load_dotenv(override=True)

# The SDK adds the managed-agents beta header automatically for agents,
# environments, sessions, vaults, and deployments. The files resource doesn't:
# without it, /v1/files rejects scope_id ("unknown field"), so pass it
# explicitly when listing session-scoped files (run_now.py).
BETAS = ["managed-agents-2026-04-01"]

client = Anthropic()


def require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        sys.exit(f"{name} is not set in .env (run ./agents/setup.sh, see .env.example)")
    return value


# C0 and C1 control characters except tab and newline. The agent reads issue
# titles and stack traces an attacker can write, and its text, tool names, and
# file names are printed to your terminal. Without this an ANSI escape in a
# stack trace could rewrite earlier output or retitle the window.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def printable(text: str) -> str:
    return _CONTROL_CHARS.sub("", text)


def stream_until_end_turn(session_id: str) -> None:
    """Stream a session's events and print until the agent finishes its turn.

    `session.status_idle` is not always terminal: with `stop_reason.type ==
    "requires_action"` the agent is waiting on a client event (a tool
    confirmation or custom tool result), so keep streaming. The terminal stop
    reasons are `end_turn` (normal completion) and `retries_exhausted`
    (failure). Breaking only on `end_turn` would hang forever on a failed run.
    """
    with client.beta.sessions.events.stream(session_id) as stream:
        for ev in stream:
            match ev.type:
                case "agent.message":
                    for block in ev.content:
                        if block.type == "text":
                            print(printable(block.text), end="")
                case "agent.tool_use":
                    print(f"\n[{printable(ev.name)}]")
                case "session.status_idle" if (
                    ev.stop_reason and ev.stop_reason.type != "requires_action"
                ):
                    if ev.stop_reason.type != "end_turn":
                        print(f"\nsession stopped: {ev.stop_reason.type}")
                    return
                case "session.status_terminated":
                    return
