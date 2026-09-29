"""Runs inside the sandbox (Modal and Daytona use the same file).

``client.beta.environments.work.worker(...).handle_item()`` is the whole runner:
it builds the per-session ``AgentToolContext`` at ``workdir`` and downloads the
agent's skills into ``{workdir}/skills/<name>/``, then runs a
``SessionToolRunner`` (heartbeat + reconcile + event stream + tool dispatch +
result posting) for the session, and force-stops the work item on exit. It
reads the same ``ANTHROPIC_*`` env vars ``ant beta:worker poll --on-work`` sets,
which the webhook injects when it creates the sandbox.

Idle policy is the SDK default: the runner stays alive for as long as the
session has activity and exits ``DEFAULT_MAX_IDLE`` (60s) after
``session.status_idle`` with ``stop_reason: end_turn``. Any other event resets
the clock, including a ``requires_action`` idle, where the agent is blocked on
the sandbox.

Credentials. The agent in this sandbox runs arbitrary bash, so it can read
every env var here. The webhook therefore prefers to hand over only the work
item's per-session ``secret``: the sessions token inside it is scoped to this
one session. The environment key, which can claim any session's work in the
environment, arrives only when the webhook was deployed with
``ALLOW_ENVIRONMENT_KEY_IN_SANDBOX=true`` and the work item carried no secret.
The cost of the token: the skills API only accepts the environment key, so a
token-only runner logs ``failed to download skill`` and carries on without them.

Env vars (injected by the webhook when it creates the sandbox):
  ANTHROPIC_BASE_URL        - API base URL
  ANTHROPIC_SESSION_ID      - session id
  ANTHROPIC_ENVIRONMENT_ID  - environment id
  ANTHROPIC_WORK_ID         - work item id
  ANTHROPIC_WORK_SECRET     - the work item's secret payload (base64url JSON
                              carrying ``sessions_token``), when it had one
  ANTHROPIC_ENVIRONMENT_KEY - the environment key, only in the fallback above
"""

import asyncio
import base64
import json
import logging
import os
import sys

from anthropic import AsyncAnthropic

# EnvironmentWorker reports lifecycle (start, idle-out, heartbeat shutdown,
# stream reconnects, tool dispatch) at INFO via stdlib logging. Without a
# handler that is all dropped, and the exit reason is the only diagnostic this
# process emits, so route it to stdout for the provider's log view.
logging.basicConfig(
    level=logging.INFO,
    format="[runner] %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)

WORKDIR = "/workspace"


def sessions_token(secret: str) -> str | None:
    """Extract the sessions token from a work item's secret payload, or None."""
    try:
        payload = json.loads(base64.urlsafe_b64decode(secret + "=" * (-len(secret) % 4)))
    except ValueError:
        return None
    token = payload.get("sessions_token") if isinstance(payload, dict) else None
    return token if isinstance(token, str) and token else None


async def main() -> None:
    secret = os.environ.get("ANTHROPIC_WORK_SECRET", "")
    token = sessions_token(secret) if secret else None
    # handle_item() prefers the token inside work_secret for every call it
    # makes. `environment_key` is its required fallback credential: passing the
    # token there too keeps any standing key out of this process. Left unset,
    # the SDK would read ANTHROPIC_ENVIRONMENT_KEY from the environment.
    credential = token or os.environ.get("ANTHROPIC_ENVIRONMENT_KEY", "")
    if not credential:
        raise SystemExit(
            "runner: no credential. Expected ANTHROPIC_WORK_SECRET (or, in the opt-in "
            "fallback, ANTHROPIC_ENVIRONMENT_KEY) from the webhook that started this sandbox."
        )
    print(f"[runner] credential={'per-session token' if token else 'ENVIRONMENT KEY'}", flush=True)

    async with AsyncAnthropic(auth_token=credential) as client:
        await client.beta.environments.work.worker(
            environment_key=credential,
            workdir=WORKDIR,
            unrestricted_paths=True,
        ).handle_item(work_secret=secret or None)


if __name__ == "__main__":
    asyncio.run(main())
