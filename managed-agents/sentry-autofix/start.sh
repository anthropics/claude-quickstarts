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

exec claude \
  "Walk me through this Sentry autofix quickstart. Read CLAUDE.md and follow its setup steps in order. Use the Sentry plugin to help me select an organization and project, and later to find the demo issue's short ID (tell me to run /mcp if its sentry server needs signing in). Stop for each browser authorization, and get one fix working with npm run fix before setting up webhooks."
