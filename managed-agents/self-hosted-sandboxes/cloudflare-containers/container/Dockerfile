FROM debian:12-slim
ARG ANT_VERSION=1.23.0
# ca-certificates + curl for the CLI's HTTPS calls at runtime and for agent
# bash sessions. ripgrep, git, and jq because agents expect them and slim
# images ship nothing.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl ripgrep git jq \
 && rm -rf /var/lib/apt/lists/*
# The release asset matching this image's architecture (amd64 or arm64).
RUN curl -fsSL "https://github.com/anthropics/anthropic-cli/releases/download/v${ANT_VERSION}/ant_${ANT_VERSION}_linux_$(dpkg --print-architecture).tar.gz" \
  | tar -xz -C /usr/local/bin ant \
 && ant --version
# The agent runs arbitrary bash. It does not need root to do that, and a
# non-root user keeps a hostile command from rewriting the CLI it runs under.
RUN useradd --create-home --shell /bin/bash sandbox \
 && mkdir -p /workspace && chown sandbox:sandbox /workspace
USER sandbox
# /workspace is the agent's working tree: skills download here and the file
# tools are scoped here unless --unrestricted-paths is set.
WORKDIR /workspace
# Env contract (`ant beta:worker run`): ANTHROPIC_{SESSION_ID,ENVIRONMENT_ID,
# WORK_ID,ENVIRONMENT_KEY,BASE_URL}, all set by src/container.ts.
# --max-idle: exit 60s after session.status_idle/end_turn, reset on any event.
ENTRYPOINT ["ant", "beta:worker", "run", "--workdir", "/workspace", "--unrestricted-paths", "--max-idle", "60s", "--log-format", "json"]
