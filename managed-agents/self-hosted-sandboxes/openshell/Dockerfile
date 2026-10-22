FROM debian:12-slim
# `ant beta:worker run` takes the per-session token from a file
# (--work-secret-file) and runs without the environment key.
ARG ANT_VERSION=2.0.0
ARG ANT_SHA256_AMD64=1cce993c19c9b8e37acca52cee7671b0cf4112fac34f5adf8c3f8d91c92a735d
ARG ANT_SHA256_ARM64=265d325816566f001ef109a10702e9782ec1d9bb1b3a05931e105d4db508dbf6
# ca-certificates and curl for HTTPS from agent bash sessions. ripgrep, git,
# and jq because agents expect them and slim images ship nothing. procps for
# the pgrep that on-work.sh uses to spot a session that already has a worker.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl ripgrep git jq procps \
 && rm -rf /var/lib/apt/lists/*
# The release asset matching this image's architecture (amd64 or arm64),
# checked against the hash from that release's checksums file. To move to
# another version, change all three ARGs.
RUN arch="$(dpkg --print-architecture)" \
 && case "$arch" in \
      amd64) sha="$ANT_SHA256_AMD64" ;; \
      arm64) sha="$ANT_SHA256_ARM64" ;; \
      *) echo "no ant checksum pinned for $arch" >&2; exit 1 ;; \
    esac \
 && curl -fsSL -o /tmp/ant.tar.gz "https://github.com/anthropics/anthropic-cli/releases/download/v${ANT_VERSION}/ant_${ANT_VERSION}_linux_${arch}.tar.gz" \
 && echo "${sha}  /tmp/ant.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/ant.tar.gz -C /usr/local/bin ant \
 && rm /tmp/ant.tar.gz \
 && ant --version
# OpenShell refuses to run a workload as root and never chowns the working
# directory. Declare a user (with none, OpenShell runs as 1000:1000 with no
# passwd entry) and hand it /workspace.
RUN useradd --uid 1000 --no-create-home --home-dir /workspace --shell /bin/bash sandbox \
 && install -d -o sandbox -g sandbox /workspace
USER sandbox
# /workspace is the agent's working tree, and the file tools are scoped to it.
# OpenShell also makes the image's WORKDIR the workload's $HOME.
WORKDIR /workspace
# No ENTRYPOINT: OpenShell ignores it. on-work.sh names the command to run.
