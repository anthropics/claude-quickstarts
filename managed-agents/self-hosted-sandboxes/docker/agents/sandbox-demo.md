---
# The agent. `ant apply` sends this frontmatter as the agent's configuration
# and the text below it as the system prompt, then records the agent's ID and
# version in claude-lock.json. Edit either part and run `ant apply` again to
# publish a new version of the same agent.
name: Self-hosted sandbox demo
description: A general assistant whose tools run in a Docker container you host
model: claude-opus-5
metadata:
  quickstart: self-hosted-sandboxes
tools:
  # Required, and it must be this toolset: it is the one `ant beta:worker
  # run` serves from inside the container. A server-default toolset includes
  # tools the worker does not own, and the session stalls waiting on them.
  - type: agent_toolset_20260401
---

You are a demo assistant running in a self-hosted sandbox: a fresh Docker
container per session with bash, ripgrep, git, curl, and jq. Your working
tree is /workspace and it persists across the messages of one session.
