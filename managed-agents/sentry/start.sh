#!/usr/bin/env bash
# Install or update Sentry's Claude Code plugin, then launch the guided setup.
set -euo pipefail
cd "$(dirname "$0")"

command -v claude >/dev/null || {
  echo "Claude Code is required: https://docs.claude.com/en/docs/claude-code" >&2
  exit 1
}

# Update succeeds when the project-scoped plugin is already present. The first
# run falls back to install. Starting a fresh Claude process afterward is what
# makes the newly installed plugin and its Sentry MCP server available.
if ! claude plugin update sentry@claude-plugins-official --scope project >/dev/null 2>&1; then
  claude plugin install sentry@claude-plugins-official --scope project
fi

# run_now.py triggers the deployment, so deploy.py has to create the schedule
# before the smoke test; the guide asks afterwards whether to keep it.
exec claude \
  "Walk me through this Sentry triage quickstart. Read CLAUDE.md and skill.md, use the Sentry plugin to help me select an organization and project (tell me to run /mcp if its sentry server needs signing in), then provision, deploy, and smoke-test the Managed Agent. Stop for each browser authorization, and after I have seen the manual report, ask me before leaving the schedule active."
