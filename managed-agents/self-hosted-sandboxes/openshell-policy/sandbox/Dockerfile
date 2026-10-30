# The sandbox image: ../openshell's image, built first by start.sh (or
# `make image`) as shs-openshell, plus OpenShell's policy advisor guide.
#
# Add what your agents need in ../openshell/Dockerfile or here. Keep that
# image's non-root user: OpenShell refuses to run a workload as root, and
# never changes the owner of /workspace.
ARG BASE_IMAGE=shs-openshell
FROM ${BASE_IMAGE}

# OpenShell's policy advisor guide (from v0.1.2, Apache-2.0). Its supervisor
# installs this into the sandbox itself, but the docker driver's workload runs
# non-root with no capabilities and cannot write /etc, so it never arrives.
# The agent's instructions send it here when a request is blocked.
COPY openshell-skills/ /etc/openshell/skills/
