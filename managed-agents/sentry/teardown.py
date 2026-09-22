"""Archive everything this example created: the deployment named in .env, then
every resource `ant apply` recorded in claude-lock.json, and remove both
records so ./agents/setup.sh and deploy.py start fresh afterwards.

Skip this script to leave the schedule running. `archive` is terminal: it stops
future scheduled triggers, in-flight sessions keep running, and archiving the
vault discards the Sentry token it holds.
"""

import json

from dotenv import dotenv_values, unset_key

from managed_agents import ENV_FILE, LOCKFILE, client, deployment_id

# Archiving is idempotent, so a teardown that failed partway can be re-run.
existing = deployment_id()
if existing:
    client.beta.deployments.archive(existing)
    unset_key(ENV_FILE, "CLAUDE_DEPLOYMENT_ID")
    print(f"archived {existing}")

# `ant apply --prune` archives a resource only once its file is gone, which is
# the wrong tool for tearing down a demo whose files you keep. So archive what
# the lockfile names directly, then delete the lockfile: without it the next
# `ant apply` creates everything again. A vault's credential goes with it.
archivers = {
    "environment": client.beta.environments.archive,
    "agent": client.beta.agents.archive,
    "vault": client.beta.vaults.archive,
    "memory_store": client.beta.memory_stores.archive,
    "skill": client.beta.skills.delete,
}
if LOCKFILE.exists():
    resources = json.loads(LOCKFILE.read_text()).get("resources", {})
    left = []
    for key, entry in resources.items():
        archive = archivers.get(entry["kind"])
        if archive is None:
            left.append(f"{entry['id']}  ({key}, {entry['kind']})")
            continue
        archive(entry["id"])
        print(f"archived {entry['id']}  ({key})")
    if left:
        # Keep the record of anything this script does not know how to remove.
        print("left in place, and claude-lock.json kept for their IDs:")
        for line in left:
            print(f"  {line}")
    else:
        LOCKFILE.unlink()
        print("removed claude-lock.json")

# An older version of this quickstart kept its IDs in .env instead. Archive
# those too (the vault still holds the token) and drop the lines.
legacy = dotenv_values(ENV_FILE)
for name, archive in [
    ("CLAUDE_ENVIRONMENT_ID", client.beta.environments.archive),
    ("CLAUDE_AGENT_ID", client.beta.agents.archive),
    ("CLAUDE_VAULT_ID", client.beta.vaults.archive),
]:
    if legacy.get(name):
        archive(legacy[name])
        unset_key(ENV_FILE, name)
        print(f"archived {legacy[name]}  ({name} from an earlier setup)")
if legacy.get("CLAUDE_CREDENTIAL_ID"):
    unset_key(ENV_FILE, "CLAUDE_CREDENTIAL_ID")  # went with its vault

print("done. ./agents/setup.sh and deploy.py create new resources from here.")
