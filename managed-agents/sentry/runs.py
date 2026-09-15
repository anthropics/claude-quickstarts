"""List run history for the deployment, failures last.

Every scheduled or manual trigger writes a deployment run record, whether or
not it produced a session. `error.type` distinguishes rate-limited, archived
environment, missing vault, and backend errors. Permanent failures
(`vault_not_found_error`, `agent_archived_error`, `environment_archived_error`)
auto-pause the deployment and set `paused_reason`.
"""

from managed_agents import client, require_env

CLAUDE_DEPLOYMENT_ID = require_env("CLAUDE_DEPLOYMENT_ID")

runs = client.beta.deployment_runs.list(deployment_id=CLAUDE_DEPLOYMENT_ID)
for run in runs:
    outcome = run.session_id or (run.error.type if run.error else "?")
    print(f"{run.created_at}  [{run.trigger_context.type}]  {outcome}")

failed = client.beta.deployment_runs.list(deployment_id=CLAUDE_DEPLOYMENT_ID, has_error=True)
for run in failed:
    if run.error:
        print(f"FAILED {run.created_at}: {run.error.type} ({run.error.message})")
