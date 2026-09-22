"""Archive everything this example created: the deployment named in .env, then
every resource `ant apply` recorded in claude-lock.json, and remove both
records so ./agents/setup.sh and deploy.py start fresh afterwards.

Skip this script to leave the schedule running. `archive` is terminal: it stops
future scheduled triggers, in-flight sessions keep running, and archiving the
vault discards the Sentry token it holds.
"""

import json
import os
from pathlib import Path

from dotenv import unset_key

from managed_agents import LOCKFILE, client

ENV_FILE = Path(__file__).parent / ".env"

# Archiving is idempotent, so a teardown that failed partway can be re-run.
deployment_id = os.environ.get("CLAUDE_DEPLOYMENT_ID", "")
if deployment_id:
    client.beta.deployments.archive(deployment_id)
    unset_key(ENV_FILE, "CLAUDE_DEPLOYMENT_ID")
    print(f"archived {deployment_id}")

# `ant apply --prune` archives a resource only once its file is gone, which is
# the wrong tool for tearing down a demo whose files you keep. So archive what
# the lockfile names directly, then delete the lockfile: without it the next
# `ant apply` creates everything again.
archivers = {
    "environment": client.beta.environments.archive,
    "agent": client.beta.agents.archive,
    "vault": client.beta.vaults.archive,  # the credential goes with it
}
if LOCKFILE.exists():
    resources = json.loads(LOCKFILE.read_text()).get("resources", {})
    for key, entry in resources.items():
        archive = archivers.get(entry["kind"])
        if archive:
            archive(entry["id"])
            print(f"archived {entry['id']}  ({key})")
    LOCKFILE.unlink()
    print("removed claude-lock.json")

# IDs an older version of this quickstart kept in .env.
for stale in (
    "CLAUDE_CREDENTIAL_ID",
    "CLAUDE_VAULT_ID",
    "CLAUDE_ENVIRONMENT_ID",
    "CLAUDE_AGENT_ID",
):
    if os.environ.get(stale):
        unset_key(ENV_FILE, stale)

print("done. ./agents/setup.sh and deploy.py create new resources from here.")
