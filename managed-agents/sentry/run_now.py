"""Trigger a manual deployment run, stream it, and download the report.

Starts a session immediately, exactly as the schedule would, and records a
deployment run with `trigger_context.type: "manual"`. Use it to smoke-test
the deployment without waiting for the next cron tick.
"""

import sys
import time
from pathlib import Path

from managed_agents import BETAS, client, printable, require_env, stream_until_end_turn

CLAUDE_DEPLOYMENT_ID = require_env("CLAUDE_DEPLOYMENT_ID")

manual_run = client.beta.deployments.run(CLAUDE_DEPLOYMENT_ID)
print(f"run: {manual_run.id}")
if not manual_run.session_id:
    reason = f"{manual_run.error.type} ({manual_run.error.message})" if manual_run.error else "?"
    sys.exit(f"the run did not start a session: {reason}")
print(f"session: {manual_run.session_id}")

# The run created a real session. Stream it like any other.
stream_until_end_turn(manual_run.session_id)

# The agent wrote to /mnt/session/outputs/, which the Files API captures
# automatically. Indexing can lag 1-3 seconds after the session goes idle,
# so retry an empty list a few times.
report_files = []
for _ in range(5):
    report_files = client.beta.files.list(
        scope_id=manual_run.session_id,
        betas=BETAS,
    ).data
    if report_files:
        break
    time.sleep(1)

if not report_files:
    print("\nno files found; check the transcript above for whether the agent wrote the report")

# The agent picked these filenames, and the agent reads attacker-controlled
# input (issue titles, stack traces). So a filename is untrusted: write into a
# fresh per-session directory, never the working directory (a report named
# managed_agents.py would replace this project's code), drop path components,
# refuse dotfiles, and never overwrite.
out_dir = Path("reports") / manual_run.session_id
for f in report_files:
    local_name = Path(f.filename).name
    print(f"\n{printable(f.filename)}  ({f.size_bytes} bytes)")
    if not local_name or local_name.startswith("."):
        print("skipped: not a plain file name")
        continue
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / local_name
    try:
        with target.open("xb") as fh:
            fh.write(client.beta.files.download(f.id).read())
    except FileExistsError:
        print(f"skipped: {printable(str(target))} already exists")
        continue
    print(f"downloaded to ./{printable(str(target))}")
