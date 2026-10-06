#!/usr/bin/env python3
"""Container entrypoint: run one already-claimed work item to completion.

`EnvironmentWorker.handle_item()` does the whole per-session lifecycle:
memory-store download to each store's `mount_path`, tool dispatch against
the session's event stream, memory sync (a reconcile with the store every
`memory_sync_interval`, default 30s, checked after each tool call, plus a
final one at a clean end and a bounded push-only flush on any exit), the
work-item lease heartbeat, and the force-stop on exit. The file tools are
confined to /workspace plus the memory mounts, and a store attached
read-only refuses writes.

The only credential in this container is the per-session token carried
inside `ANTHROPIC_WORK_SECRET`. The environment key never enters a
container: the agent in here runs arbitrary bash, and a leaked environment
key could claim other sessions' work items. The sessions token is scoped to
this one session, and it is also the only credential the memory endpoints
accept.

Env (set by on-work.sh via `docker run -e`):
  ANTHROPIC_WORK_ID, ANTHROPIC_ENVIRONMENT_ID, ANTHROPIC_SESSION_ID
  ANTHROPIC_WORK_SECRET  - the work item's secret payload (base64url JSON
                           carrying `sessions_token`)
  ANTHROPIC_BASE_URL     - optional, default https://api.anthropic.com
"""

import os
import json
import base64
import signal
import asyncio
import logging

from anthropic import AsyncAnthropic
from anthropic.lib.environments import EnvironmentWorker


def sessions_token(secret: str) -> str | None:
    """Extract the sessions token from a work item's secret payload, or None."""
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(secret + "=" * (-len(secret) % 4))
        )
    except ValueError:
        return None
    token = payload.get("sessions_token") if isinstance(payload, dict) else None
    return token if isinstance(token, str) and token else None


async def main() -> None:
    secret = os.environ.get("ANTHROPIC_WORK_SECRET", "")
    token = sessions_token(secret)
    if token is None:
        # on-work.sh only starts a container for items that carry a secret, so
        # this means the image was run by hand or the payload shape changed.
        raise SystemExit(
            "worker: ANTHROPIC_WORK_SECRET carries no sessions token; run this image through on-work.sh"
        )

    # `docker stop` sends SIGTERM: turn it into a cancellation so the worker's
    # teardown (final memory flush, force-stop of the work item) still runs.
    task = asyncio.current_task()
    assert task is not None
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, task.cancel)

    client = AsyncAnthropic(auth_token=token)
    worker = EnvironmentWorker(client, workdir="/workspace")
    # handle_item reads ANTHROPIC_{WORK_ID,ENVIRONMENT_ID,SESSION_ID} from the
    # environment and uses the token inside work_secret for every call it
    # makes, so this process needs no environment key.
    await worker.handle_item(work_secret=secret)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(main())
