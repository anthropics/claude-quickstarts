# The operator's toolbox, for a host that cannot run the OpenShell and ant
# release binaries (macOS with endpoint protection, for example). scripts/ops runs it on Docker
# Desktop's host network, where the containerized gateway listens
# (stack/openshell), with this repository mounted at its own path.
#
#   make ops-image   (see the pip note below)
#
# It carries the OpenShell CLI and prover (0.1.2, matching the gateway), the
# ant CLI the dispatcher polls with, the docker CLI, and agentpolicy's
# dependencies. agentpolicy itself runs from the mounted source tree.
FROM docker:29-cli AS dockercli

FROM python:3.12-slim

ARG OPENSHELL_VERSION=0.1.2
ARG OPENSHELL_SHA256_ARM64=9880c5776688231d5242deb046cdee361734f94901b9123949a0baf29fdadd9e
ARG OPENSHELL_SHA256_AMD64=7eb6917285331a09e3300266a0558616481a5e9927cae2612ea07c4045b6dd6f
ARG PROVER_SHA256_ARM64=0b6a0ba530b713b4f0afab2850903f6cbb24dd3ec4b4c25b7ee265911444099d
ARG PROVER_SHA256_AMD64=e1c9db66ae459850cab43765d7ad569effe2ac0a338c902a1b895d0cc361fbb0
ARG ANT_VERSION=1.35.0
ARG ANT_SHA256_AMD64=a861a51f62f70f5f6a136dddffc9fe4d9708807a25a24595ce9d640d88361308
ARG ANT_SHA256_ARM64=5e53cb7953a8f92fd5cee47960d520765a532f2bafa7c9ff4c4312045d1f6265

# util-linux for the flock on-work.sh serializes sessions with.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl jq procps util-linux make \
 && rm -rf /var/lib/apt/lists/*

COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker

RUN set -eu; arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      arm64) triple=aarch64; os_sha="$OPENSHELL_SHA256_ARM64"; pv_sha="$PROVER_SHA256_ARM64"; ant_sha="$ANT_SHA256_ARM64" ;; \
      amd64) triple=x86_64;  os_sha="$OPENSHELL_SHA256_AMD64"; pv_sha="$PROVER_SHA256_AMD64"; ant_sha="$ANT_SHA256_AMD64" ;; \
      *) echo "no checksums pinned for $arch" >&2; exit 1 ;; \
    esac; \
    rel="https://github.com/NVIDIA/OpenShell/releases/download/v${OPENSHELL_VERSION}"; \
    curl -fsSL -o /tmp/os.tgz "$rel/openshell-${triple}-unknown-linux-musl.tar.gz"; \
    curl -fsSL -o /tmp/pv.tgz "$rel/openshell-prover-${triple}-unknown-linux-musl.tar.gz"; \
    curl -fsSL -o /tmp/ant.tgz "https://github.com/anthropics/anthropic-cli/releases/download/v${ANT_VERSION}/ant_${ANT_VERSION}_linux_${arch}.tar.gz"; \
    printf '%s  /tmp/os.tgz\n%s  /tmp/pv.tgz\n%s  /tmp/ant.tgz\n' "$os_sha" "$pv_sha" "$ant_sha" | sha256sum -c -; \
    tar -xzf /tmp/os.tgz -C /usr/local/bin openshell; \
    tar -xzf /tmp/pv.tgz -C /usr/local/bin openshell-prover; \
    tar -xzf /tmp/ant.tgz -C /usr/local/bin ant; \
    rm /tmp/*.tgz; \
    openshell --version; openshell-prover --version; ant --version

# agentpolicy's dependencies from requirements.txt: every package, transitive
# ones included, pinned and checked against its hash, wheels only, so whichever
# index serves them can only serve exactly what was locked. `make ops-image`
# passes a pip.conf naming your package mirror as a build secret (its credential
# stays out of every layer), and refuses to build without one unless
# PUBLIC_INDEX=1 allows PyPI deliberately.
COPY requirements.txt /tmp/requirements.txt
RUN --mount=type=secret,id=pipconf,target=/etc/pip.conf,required=false \
    pip install --no-cache-dir --require-hashes --no-deps --only-binary=:all: \
      -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt

COPY agentpolicy /usr/local/bin/agentpolicy
