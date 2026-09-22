# Deploys the HTTP entrypoint (Fly, Railway, Render, Cloud Run).
# Pinned by digest, because this container holds your Anthropic key and the
# bearer token. To move to a newer Bun, change the tag and the digest together:
#   docker buildx imagetools inspect oven/bun:<tag>-slim
FROM oven/bun:1.3.13-slim@sha256:7e8ed3961db1cdedf17d516dda87948cfedbd294f53bf16462e5b57ed3fff0f1
WORKDIR /app
# bun.lock is committed for the same reason: the build installs exactly the
# versions that were tested, not whatever the semver ranges resolve to today.
COPY package.json bun.lock ./
RUN bun install --production --frozen-lockfile
COPY src ./src
# The image's unprivileged user. The server needs no write access.
USER bun
ENV PORT=3000
# Listen on the container's interface. The server refuses to start on a
# non-loopback HOST until ALLOWED_HOSTS names the public hostname, so set
# ALLOWED_HOSTS, MANAGED_AGENTS_MCP_TOKEN, ANTHROPIC_API_KEY, and
# CLAUDE_ENVIRONMENT_ID as secrets on the platform. Nothing secret is baked in.
ENV HOST=0.0.0.0
EXPOSE 3000
CMD ["bun", "run", "src/server-http.ts"]
