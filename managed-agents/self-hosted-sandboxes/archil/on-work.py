#!/usr/bin/env python3
"""Invoked by `ant beta:worker poll --on-work` once per claimed work item.

The poller passes ANTHROPIC_{WORK_ID,ENVIRONMENT_ID,SESSION_ID,ENVIRONMENT_KEY}
in the environment and the raw work JSON on stdin (unused here). Archil
settings come from the poller's environment too (start.sh exports .env).

Per work item this:
  1. creates an Archil persistent sandbox and installs the `ant` and `archil`
     CLIs in it,
  2. mounts the EDGAR disk at /mnt/edgar in shared mode, so every session
     reads the same data, and checks out /mnt/edgar/reports/<session> so this
     session alone can write there,
  3. runs `ant beta:worker run` until the session idles, streaming its log,
  4. checks the report directory back in, unmounts, and deletes the sandbox.

It stays attached the whole time: the poller stops a work item as soon as
this script returns, so one poller serves one session at a time.
"""

import os
import sys

import sandboxes

session_id = os.environ["ANTHROPIC_SESSION_ID"]
disk, region = os.environ["ARCHIL_DISK"], os.environ["ARCHIL_REGION"]
worker_env = {
    name: os.environ[name]
    for name in (
        "ANTHROPIC_SESSION_ID",
        "ANTHROPIC_ENVIRONMENT_ID",
        "ANTHROPIC_WORK_ID",
        "ANTHROPIC_ENVIRONMENT_KEY",
    )
} | {
    "ANTHROPIC_BASE_URL": os.environ.get(
        "ANTHROPIC_BASE_URL", "https://api.anthropic.com"
    )
}


def log(line: str) -> None:
    print(f"[on-work] session={session_id} {line}", file=sys.stderr, flush=True)


report_dir = f"/mnt/edgar/reports/{session_id}"

log("creating sandbox")
sandbox = sandboxes.create(session_id.replace("_", "-").lower())
try:
    sandboxes.run(sandbox, sandboxes.BOOTSTRAP, stream=False)
    # A shared mount is read-only until a path is checked out; `checkout`
    # gives this sandbox exclusive write access to the session's report dir.
    # A new directory takes a moment to become visible to checkout, so retry.
    sandboxes.run(
        sandbox,
        f"mkdir -p /mnt/edgar && archil -q mount {disk} /mnt/edgar --region {region} --shared >/dev/null"
        f" && mkdir -p {report_dir}"
        f" && for i in 1 2 3 4 5; do archil -q checkout {report_dir} && break; sleep 2; done",
        env={"ARCHIL_MOUNT_TOKEN": os.environ["ARCHIL_MOUNT_TOKEN"]},
    )
    log(f"mounted {disk} at /mnt/edgar, writable at reports/{session_id}")

    # --max-idle: exit 60s after the session goes idle, reset by any new event.
    # The worker's log streams back over the websocket while it runs.
    sandboxes.run(
        sandbox,
        "ant beta:worker run --workdir /mnt/edgar --max-idle 60s --log-format text",
        env=worker_env,
    )
finally:
    # `archil unmount` flushes writes to the disk; `umount` would not.
    sandboxes.run(
        sandbox,
        f"archil checkin {report_dir}; cd / && archil unmount /mnt/edgar; true",
    )
    sandboxes.destroy(sandbox)
    log("sandbox deleted")
