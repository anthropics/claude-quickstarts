"""Create the scheduled deployment (weekday mornings, 9 AM Eastern), or bring an
existing one up to date.

The agent, environment, and vault IDs come from claude-lock.json, which
`ant apply` wrote; the Sentry org and project come from .env and go into the
message that starts each run. The first run appends CLAUDE_DEPLOYMENT_ID to
.env. After that, running this again (./agents/setup.sh does) re-pins the
deployment to the latest agent version and re-sends the environment, vault,
and message, because a deployment keeps whatever it was created with.
"""

import os
from pathlib import Path

from managed_agents import client, lockfile_id, require_env

agent_id = lockfile_id("./agents/sentry-triage.md")
environment_id = lockfile_id("./environments/sentry-triage.yaml")
vault_id = lockfile_id("./vaults/sentry-triage.yaml")
org = require_env("SENTRY_ORG")
project = require_env("SENTRY_PROJECT")

# The org and project are settings, not secrets, so they travel in the run's
# first message rather than in the vault. The system prompt tells the agent to
# use exactly these slugs.
TRIAGE_PROMPT = (
    f"Run today's Sentry triage for org `{org}`, project `{project}`. "
    "Pull the last 24 hours of unresolved issues, triage them, and write "
    "the report to /mnt/session/outputs/TRIAGE_REPORT.md. "
    "Reply with the Summary section when you're done."
)

config = dict(
    # The bare agent ID means "latest version".
    agent=agent_id,
    environment_id=environment_id,
    vault_ids=[vault_id],
    initial_events=[
        {
            "type": "user.message",
            "content": [{"type": "text", "text": TRIAGE_PROMPT}],
        }
    ],
)

deployment_id = os.environ.get("CLAUDE_DEPLOYMENT_ID")
if deployment_id:
    deployment = client.beta.deployments.update(deployment_id, **config)
    print(f"deployment: {deployment.id} updated (agent version {deployment.agent.version})")
else:
    # The schedule is a POSIX cron expression plus an IANA timezone, matched on
    # wall-clock time (see skill.md for the DST edges). Sessions start themselves
    # on Anthropic infra; nothing keeps running on this machine.
    deployment = client.beta.deployments.create(
        name="Weekday morning Sentry triage",
        schedule={
            "type": "cron",
            "expression": "0 9 * * 1-5",  # weekday mornings
            "timezone": "America/New_York",
        },
        **config,
    )
    print(f"deployment: {deployment.id} ({deployment.status})")
    if deployment.schedule:
        print("next runs:")
        for ts in deployment.schedule.upcoming_runs_at or []:
            print(f"  {ts}")
    with (Path(__file__).parent / ".env").open("a") as env_file:
        env_file.write(f"\nCLAUDE_DEPLOYMENT_ID={deployment.id}\n")
    print("\nsaved CLAUDE_DEPLOYMENT_ID to .env")
