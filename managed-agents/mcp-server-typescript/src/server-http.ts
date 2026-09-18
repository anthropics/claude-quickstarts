#!/usr/bin/env bun
// Streamable HTTP transport, for claude.ai custom connectors or any remote MCP
// client. Web-standard Request/Response, so the handler also runs on Node 18+,
// Deno, and (with env plumbing) Cloudflare Workers.
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";
import { createHash, timingSafeEqual } from "node:crypto";
import { allowedAgentIds } from "./scope";
import { registerTools } from "./tools";

const MIN_TOKEN_CHARS = 32;
const MAX_BODY_BYTES = 1024 * 1024;

const TOKEN = process.env.MANAGED_AGENTS_MCP_TOKEN ?? "";
if (TOKEN.length < MIN_TOKEN_CHARS) {
  console.error(
    `FATAL: MANAGED_AGENTS_MCP_TOKEN must be set and at least ${MIN_TOKEN_CHARS} characters. Generate one with: openssl rand -hex 32`,
  );
  process.exit(1);
}
const PORT = Number(process.env.PORT) || 3000;
// Loopback by default. This token is all that stands between a caller and
// every agent your credentials can reach, so exposing the port is opt-in.
const HOST = process.env.HOST || "127.0.0.1";
const LOOPBACK = new Set(["127.0.0.1", "localhost", "::1"]);

function list(raw: string | undefined): string[] {
  return (raw ?? "")
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
}

// Host header allowlist. A browser tricked by DNS rebinding sends the
// attacker's hostname here, and so does a request meant for another vhost.
let allowedHosts = list(process.env.ALLOWED_HOSTS);
if (allowedHosts.length === 0) {
  if (!LOOPBACK.has(HOST)) {
    console.error(
      `FATAL: HOST=${HOST} is not loopback, so ALLOWED_HOSTS is required. Set it to the public hostname clients will use, e.g. ALLOWED_HOSTS=agents.example.com`,
    );
    process.exit(1);
  }
  allowedHosts = [`127.0.0.1:${PORT}`, `localhost:${PORT}`, `[::1]:${PORT}`];
}
// Server-to-server MCP clients (claude.ai connectors, Claude Code) send no
// Origin. A browser always does, so an Origin that is not listed is refused.
const allowedOrigins = list(process.env.ALLOWED_ORIGINS);

const expectedDigest = createHash("sha256").update(`Bearer ${TOKEN}`).digest();

// Compare fixed-length digests so neither the length nor the content of the
// token leaks through timing.
function authorized(req: Request): boolean {
  const provided = req.headers.get("authorization") ?? "";
  return timingSafeEqual(createHash("sha256").update(provided).digest(), expectedDigest);
}

// wait_for_idle can hold a request open for minutes while the agent works, and
// nothing is written in that time. Bun closes a connection that has been
// silent for idleTimeout seconds (10 by default), and proxies do the same. The
// transport's SSE keep-alive comment has to arrive more often than that.
const KEEP_ALIVE_MS = 5_000;
const IDLE_TIMEOUT_SEC = 30;

// Stateless mode (no sessionIdGenerator): each HTTP request gets its own
// McpServer + transport. Fine because the tools themselves are stateless.
// The calling model holds the session_id across turns.
async function newTransport() {
  const server = new McpServer({ name: "managed-agents-mcp", version: "0.1.0" });
  registerTools(server);
  const transport = new WebStandardStreamableHTTPServerTransport({ keepAliveMs: KEEP_ALIVE_MS });
  await server.connect(transport);
  return transport;
}

Bun.serve({
  port: PORT,
  hostname: HOST,
  // Enforced by the runtime, so it also covers chunked bodies with no Content-Length.
  maxRequestBodySize: MAX_BODY_BYTES,
  idleTimeout: IDLE_TIMEOUT_SEC,
  async fetch(req) {
    const url = new URL(req.url);

    if (url.pathname === "/health" && req.method === "GET") {
      return new Response("ok");
    }
    if (url.pathname !== "/mcp") {
      return new Response("Not Found", { status: 404 });
    }
    if (!["POST", "GET", "DELETE"].includes(req.method)) {
      return new Response("Method Not Allowed", { status: 405, headers: { allow: "POST, GET, DELETE" } });
    }

    const host = (req.headers.get("host") ?? "").toLowerCase();
    if (!allowedHosts.includes(host)) {
      return new Response("Misdirected Request", { status: 421 });
    }
    const origin = req.headers.get("origin");
    if (origin !== null && !allowedOrigins.includes(origin.toLowerCase())) {
      return new Response("Forbidden", { status: 403 });
    }

    // The only thing standing between the network and every agent your
    // Anthropic credentials can reach. Do not remove.
    if (!authorized(req)) {
      return new Response("Unauthorized", { status: 401, headers: { "www-authenticate": "Bearer" } });
    }

    return (await newTransport()).handleRequest(req);
  },
});

console.error(`[managed-agents-mcp] HTTP server on http://${HOST}:${PORT}/mcp`);
console.error(`[managed-agents-mcp] accepting Host: ${allowedHosts.join(", ")}`);
console.error(
  allowedAgentIds
    ? `[managed-agents-mcp] limited to ${allowedAgentIds.size} agent(s) by ALLOWED_AGENT_IDS`
    : "[managed-agents-mcp] ALLOWED_AGENT_IDS is not set: every agent in the workspace is reachable",
);
