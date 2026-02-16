#!/bin/bash
set -euo pipefail

# Only run in remote (Claude Code on the web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

# Install Node.js dependencies for customer-support-agent
if [ -d "$PROJECT_DIR/customer-support-agent" ]; then
  echo "Installing customer-support-agent dependencies..."
  npm install --prefix "$PROJECT_DIR/customer-support-agent"
fi

# Install Node.js dependencies for financial-data-analyst
if [ -d "$PROJECT_DIR/financial-data-analyst" ]; then
  echo "Installing financial-data-analyst dependencies..."
  npm install --prefix "$PROJECT_DIR/financial-data-analyst"
fi

# Install Python dev dependencies for computer-use-demo (includes ruff, pytest, pyright)
if [ -f "$PROJECT_DIR/computer-use-demo/dev-requirements.txt" ]; then
  echo "Installing computer-use-demo Python dev dependencies..."
  pip install -r "$PROJECT_DIR/computer-use-demo/dev-requirements.txt"
fi

# Install Python dependencies for autonomous-coding
if [ -f "$PROJECT_DIR/autonomous-coding/requirements.txt" ]; then
  echo "Installing autonomous-coding Python dependencies..."
  pip install -r "$PROJECT_DIR/autonomous-coding/requirements.txt"
fi

echo "All dependencies installed successfully."
