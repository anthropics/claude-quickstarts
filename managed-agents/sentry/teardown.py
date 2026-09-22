"""Archive everything this example created and forget the IDs in .env.

Skip this script to leave the schedule running. `archive` is terminal: it stops
future scheduled triggers, and in-flight sessions keep running.
"""

import os
from pathlib import Path

from dotenv import unset_key

from managed_agents import client

ENV_FILE = Path(__file__).parent / ".env"

# Archiving is idempotent, so a teardown that failed partway can be re-run.
# Each ID leaves .env as soon as its resource is archived, which is what lets
# ./agents/setup.sh and deploy.py start fresh afterwards.
for env_name, archive in [
    ("CLAUDE_DEPLOYMENT_ID", client.beta.deployments.archive),
    ("CLAUDE_ENVIRONMENT_ID", client.beta.environments.archive),
    ("CLAUDE_AGENT_ID", client.beta.agents.archive),
    ("CLAUDE_VAULT_ID", client.beta.vaults.archive),
]:
    resource_id = os.environ.get(env_name, "")
    if resource_id:
        archive(resource_id)
        unset_key(ENV_FILE, env_name)
        print(f"archived {resource_id}")

# The credential went with its vault.
if os.environ.get("CLAUDE_CREDENTIAL_ID"):
    unset_key(ENV_FILE, "CLAUDE_CREDENTIAL_ID")

print("done. The CLAUDE_* IDs are gone from .env, so ./agents/setup.sh creates new ones.")
