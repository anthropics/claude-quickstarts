// `npm run sentry-login`: sign in to the Sentry MCP server and store the
// tokens in this quickstart's vault.
//
// The hosted Sentry MCP server authenticates with MCP OAuth, so the vault
// credential is `mcp_oauth`, not a pasted API token. This script is the whole
// flow: register a public client, send you to Sentry to approve it, exchange
// the code (PKCE), and hand the access and refresh tokens to the vault. From
// then on the platform refreshes them, and they are injected outside the
// sandbox whenever a session calls a Sentry tool. Nothing is written to disk.

import Anthropic from "@anthropic-ai/sdk";
import { createHash, randomBytes } from "node:crypto";
import { createServer } from "node:http";
import { createInterface } from "node:readline/promises";

// Must equal mcp_servers[].url in agents/issue-fixer/agent.yaml: the platform
// picks the credential for a server by matching this URL.
const MCP_SERVER_URL = "https://mcp.sentry.dev/mcp";
const ISSUER = "https://mcp.sentry.dev";
// Read access for the issue tools, and event:write because starting a Seer
// analysis is a write in Sentry's API. The agent's tool allow-list, not this
// scope, is what keeps it from resolving issues (see agent.yaml).
const SCOPE = "org:read project:write event:write";
const PORT = Number(process.env.SENTRY_LOGIN_PORT ?? 8976);
const REDIRECT_URI = `http://localhost:${PORT}/callback`;

const client = new Anthropic();

type Metadata = { authorization_endpoint: string; token_endpoint: string; registration_endpoint: string };
type Tokens = { access_token: string; refresh_token?: string; expires_in?: number };

async function postJson<T>(url: string, body: Record<string, unknown> | URLSearchParams): Promise<T> {
  const form = body instanceof URLSearchParams;
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": form ? "application/x-www-form-urlencoded" : "application/json", accept: "application/json" },
    body: form ? body : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${url} -> ${response.status} ${await response.text()}`);
  return (await response.json()) as T;
}

// Resolves with the `code` Sentry sends back. It arrives either at the local
// listener (browser on this machine) or as a pasted URL (browser somewhere
// else, e.g. you are on a remote dev box and localhost did not resolve).
async function waitForCode(state: string): Promise<string> {
  const codeFrom = (url: URL): string => {
    if (url.searchParams.get("state") !== state) throw new Error("state mismatch: start over");
    const code = url.searchParams.get("code");
    if (!code) throw new Error(url.searchParams.get("error_description") ?? "no code in the redirect");
    return code;
  };
  const server = createServer();
  const prompt = createInterface({ input: process.stdin, output: process.stdout });
  try {
    // The listener only ever resolves. A busy port or a stale tab replaying an
    // old redirect must not end the sign-in, because the paste path below
    // exists for exactly the case where the listener is no use.
    const viaBrowser = new Promise<string>((resolve) => {
      server.on("request", (request, response) => {
        const url = new URL(request.url ?? "/", REDIRECT_URI);
        if (url.pathname !== "/callback") return void response.writeHead(404).end();
        try {
          resolve(codeFrom(url));
          response.end("Signed in. You can close this tab.");
        } catch (err) {
          console.warn(`ignored a callback: ${err instanceof Error ? err.message : err}`);
          response.writeHead(400).end("That redirect does not belong to this sign-in. Use the newest URL from the terminal.");
        }
      });
      server.on("error", (err) => console.warn(`not listening on port ${PORT} (${err.message}). Paste the URL instead.`));
      server.listen(PORT, "127.0.0.1");
    });
    const viaPaste = (async () => {
      for (;;) {
        const pasted = await prompt.question("\nIf the browser ends on a page that will not load, paste its full URL here:\n");
        try {
          return codeFrom(new URL(pasted.trim()));
        } catch (err) {
          console.warn(`that URL did not work: ${err instanceof Error ? err.message : err}`);
        }
      }
    })();
    return await Promise.race([viaBrowser, viaPaste]);
  } finally {
    prompt.close();
    server.close();
  }
}

async function main() {
  const vaultId = process.env.CLAUDE_VAULT_ID;
  if (!vaultId) throw new Error("CLAUDE_VAULT_ID is not in .env: run ./agents/setup.sh first");

  const metadata = (await (await fetch(`${ISSUER}/.well-known/oauth-authorization-server`)).json()) as Metadata;
  const registration = await postJson<{ client_id: string }>(metadata.registration_endpoint, {
    client_name: "Sentry autofix quickstart (Claude Managed Agents)",
    redirect_uris: [REDIRECT_URI],
    grant_types: ["authorization_code", "refresh_token"],
    response_types: ["code"],
    token_endpoint_auth_method: "none",
  });

  const verifier = randomBytes(32).toString("base64url");
  const state = randomBytes(16).toString("base64url");
  const authorize = new URL(metadata.authorization_endpoint);
  authorize.search = new URLSearchParams({
    response_type: "code",
    client_id: registration.client_id,
    redirect_uri: REDIRECT_URI,
    scope: SCOPE,
    state,
    code_challenge: createHash("sha256").update(verifier).digest("base64url"),
    code_challenge_method: "S256",
    resource: MCP_SERVER_URL,
  }).toString();
  console.log(`Open this URL and approve access for the organization whose issues you want fixed:\n\n${authorize}`);

  const code = await waitForCode(state);
  const tokens = await postJson<Tokens>(
    metadata.token_endpoint,
    new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: REDIRECT_URI,
      client_id: registration.client_id,
      code_verifier: verifier,
      resource: MCP_SERVER_URL,
    }),
  );

  await storeCredential(vaultId, registration.client_id, metadata.token_endpoint, tokens);
  console.log(`\nStored the Sentry credential in vault ${vaultId}. Sessions can call the Sentry tools now.`);
}

// A vault holds one active credential per MCP server URL, so signing in again
// replaces the old one.
async function storeCredential(vaultId: string, clientId: string, tokenEndpoint: string, tokens: Tokens) {
  for await (const credential of client.beta.vaults.credentials.list(vaultId)) {
    const { auth } = credential;
    if (auth.type !== "environment_variable" && auth.mcp_server_url === MCP_SERVER_URL && !credential.archived_at) {
      await client.beta.vaults.credentials.archive(credential.id, { vault_id: vaultId });
    }
  }
  await client.beta.vaults.credentials.create(vaultId, {
    display_name: "Sentry MCP (OAuth)",
    metadata: { quickstart: "sentry-autofix" },
    auth: {
      type: "mcp_oauth",
      mcp_server_url: MCP_SERVER_URL,
      access_token: tokens.access_token,
      ...(tokens.expires_in ? { expires_at: new Date(Date.now() + tokens.expires_in * 1000).toISOString() } : {}),
      // Without a refresh block the credential works until the access token
      // expires and then the agent silently loses Sentry.
      ...(tokens.refresh_token
        ? {
            refresh: {
              refresh_token: tokens.refresh_token,
              client_id: clientId,
              token_endpoint: tokenEndpoint,
              token_endpoint_auth: { type: "none" as const },
              resource: MCP_SERVER_URL,
              scope: SCOPE,
            },
          }
        : {}),
    },
  });
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exit(1);
});
