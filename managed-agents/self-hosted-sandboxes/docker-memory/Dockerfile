FROM python:3.12-slim
# Tools the agent's bash sessions expect. Slim images ship almost nothing,
# and agents reach for rg constantly (searching the memory mount, the
# workspace). Add what your agents need here.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ripgrep git curl jq ca-certificates \
 && rm -rf /var/lib/apt/lists/*
# Memory sync for self-hosted sandboxes has been in the SDK since 0.125.0.
RUN pip install --no-cache-dir "anthropic>=1.9.0,<2.0.0"
COPY worker.py /app/worker.py
# /workspace is the agent's working tree (on-work.sh mounts a per-session
# volume over it). Memory stores land at each store's
# mount_path (/mnt/memory/<slug>), on the container's own writable layer:
# that path exists only inside this session's container, which is what keeps
# one session's memories invisible to every other session on the host.
WORKDIR /workspace
# Env contract (worker.py): ANTHROPIC_{SESSION_ID,ENVIRONMENT_ID,WORK_ID,
# WORK_SECRET,BASE_URL}. No environment key: the sessions token inside
# ANTHROPIC_WORK_SECRET is this container's only credential.
ENTRYPOINT ["python", "/app/worker.py"]
