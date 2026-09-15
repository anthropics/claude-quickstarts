"""Create the scheduled deployment: weekday mornings, 9 AM Eastern.

Appends the deployment ID to .env, the same way ./agents/setup.sh saves the
IDs it creates.
"""

import os
import sys
from pathlib import Path

from managed_agents import client, require_env

if os.environ.get("CLAUDE_DEPLOYMENT_ID"):
    sys.exit(
        f"CLAUDE_DEPLOYMENT_ID is already set in .env ({os.environ['CLAUDE_DEPLOYMENT_ID']}). "
        "Re-run ./agents/setup.sh to push changes to it, or teardown.py to remove it."
    )

CLAUDE_AGENT_ID = require_env("CLAUDE_AGENT_ID")
CLAUDE_ENVIRONMENT_ID = require_env("CLAUDE_ENVIRONMENT_ID")
CLAUDE_VAULT_ID = require_env("CLAUDE_VAULT_ID")

# The org and project slugs are in the agent's system prompt, which
# ./agents/setup.sh re-renders on every run. This message is frozen when the
# deployment is created, so naming them here too would let the two drift.
TRIAGE_PROMPT = (
    "Run today's Sentry triage. Pull the last 24 hours of unresolved issues for "
    "the org and project in your instructions, triage them, and write "
    "the report to /mnt/session/outputs/TRIAGE_REPORT.md. "
    "Reply with the Summary section when you're done."
)

# The schedule is a POSIX cron expression plus an IANA timezone, matched on
# wall-clock time (see skill.md for the DST edges). Sessions start themselves
# on Anthropic infra; nothing keeps running on this machine.
deployment = client.beta.deployments.create(
    name="Weekday morning Sentry triage",
    agent=CLAUDE_AGENT_ID,
    environment_id=CLAUDE_ENVIRONMENT_ID,
    vault_ids=[CLAUDE_VAULT_ID],
    initial_events=[
        {
            "type": "user.message",
            "content": [{"type": "text", "text": TRIAGE_PROMPT}],
        }
    ],
    schedule={
        "type": "cron",
        "expression": "0 9 * * 1-5",  # weekday mornings
        "timezone": "America/New_York",
    },
)

print(f"deployment: {deployment.id} ({deployment.status})")
if deployment.schedule:
    print("next runs:")
    for ts in deployment.schedule.upcoming_runs_at or []:
        print(f"  {ts}")
with (Path(__file__).parent / ".env").open("a") as env_file:
    env_file.write(f"\nCLAUDE_DEPLOYMENT_ID={deployment.id}\n")
print("\nsaved CLAUDE_DEPLOYMENT_ID to .env")
