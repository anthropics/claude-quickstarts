// `npm run sentry-login`: sign in to the Sentry MCP server and store the
// tokens in this quickstart's vault.
//
// The hosted Sentry MCP server authenticates with MCP OAuth, so the vault
// credential is `mcp_oauth`, not a pasted API token. This script is the whole
// flow: register a public client, send you to Sentry to approve it, exchange
// the code (PKCE), and hand the access and refresh tokens to the vault. From
// then on the platform refreshes them, and they are injected outside the
// sandbox whenever a session calls a Sentry tool. Nothing is written to disk.
//
// This is deliberately a separate grant from the Sentry plugin's in Claude
// Code (./start.sh). Claude Code keeps its own tokens private, and sessions a
// webhook starts need a credential of their own.

import { createHash, randomBytes } from "node:crypto";
import { createServer } from "node:http";
import { createInterface } from "node:readline/promises";
import { client, lockedId, SENTRY_MCP_URL as MCP_SERVER_URL } from "./fixer";

// What the issue tools need, plus event:write because starting a Seer analysis
// is a write in Sentry's API. The server also advertises team:write and
// alerts:write. Nothing here needs them, so the request leaves them out, and
// main() refuses a token that reports a scope outside this list.
const SCOPES = ["org:read", "project:write", "event:write"];
const PORT = Number(process.env.SENTRY_LOGIN_PORT ?? 8976);
const REDIRECT_URI = `http://localhost:${PORT}/callback`;

type Resource = { resource?: string; authorization_servers?: string[]; scopes_supported?: string[] };
type Metadata = { authorization_endpoint: string; token_endpoint: string; registration_endpoint: string };
type Tokens = { access_token: string; refresh_token?: string; expires_in?: number; scope?: string };

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { headers: { accept: "application/json" } });
  if (!response.ok) throw new Error(`${url} -> ${response.status}`);
  return (await response.json()) as T;
}

// Where to sign in is the server's to say: its protected-resource metadata
// (RFC 9728) names the authorization server, whose own metadata (RFC 8414)
// names the endpoints. Tokens are sent to those endpoints, so each must be
// https.
async function discover(): Promise<{ resource: Resource; metadata: Metadata }> {
  const server = new URL(MCP_SERVER_URL);
  const resource = await getJson<Resource>(`${server.origin}/.well-known/oauth-protected-resource${server.pathname}`);
  const issuer = resource.authorization_servers?.[0];
  if (!issuer) throw new Error("the Sentry MCP server did not advertise an OAuth authorization server");
  const { origin, pathname } = new URL(issuer);
  const metadata = await getJson<Metadata>(`${origin}/.well-known/oauth-authorization-server${pathname === "/" ? "" : pathname}`);
  for (const field of ["authorization_endpoint", "token_endpoint", "registration_endpoint"] as const) {
    if (!metadata[field]?.startsWith("https://")) throw new Error(`Sentry's OAuth metadata has no https ${field}`);
  }
  return { resource, metadata };
}

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
  const vaultId = lockedId("vault");

  const { resource, metadata } = await discover();
  const advertised = resource.scopes_supported;
  const scope = SCOPES.filter((name) => !advertised || advertised.includes(name)).join(" ");
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
    scope,
    state,
    code_challenge: createHash("sha256").update(verifier).digest("base64url"),
    code_challenge_method: "S256",
    resource: MCP_SERVER_URL,
  }).toString();
  console.log(
    "Open this URL and approve access for the organization whose issues you want fixed. On the approval screen, leave only\n" +
      `"Inspect Issues & Events" and "Seer" checked, and untick the rest. The token carries only what you approve.\n\n${authorize}`,
  );

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

  // Both checks come before the old credential is archived, so a sign-in that
  // fails them leaves a working credential in place.
  if (!tokens.access_token || !tokens.refresh_token) {
    throw new Error("Sentry did not return both an access and a refresh token. Not storing a credential the platform cannot refresh.");
  }
  const extra = (tokens.scope ?? "").split(" ").filter((name) => name && !SCOPES.includes(name));
  if (extra.length) throw new Error(`Sentry granted more than this quickstart asked for (${extra.join(", ")}). Not storing it.`);

  const credentialId = await storeCredential(vaultId, registration.client_id, metadata.token_endpoint, tokens, tokens.refresh_token);
  console.log(`\ncredential: stored ${credentialId} in ${vaultId}`);
  await validate(vaultId, credentialId);
}

// Probes the stored credential against the MCP server (`initialize` and
// `tools/list`). The vault always presents it as `Authorization: Bearer`, so
// an organization that rejects that fails here and not in the first session a
// webhook starts. Advisory: it reports, and `npm run fix` is the real test.
async function validate(vaultId: string, credentialId: string) {
  const status = await client.beta.vaults.credentials
    .mcpOAuthValidate(credentialId, { vault_id: vaultId })
    .then((validation) => validation.status)
    .catch(() => null);
  if (!status) return console.log("credential: validation probe did not run. Try it with `npm run fix -- <SHORT-ID>`.");
  console.log(`credential: validation status ${status}`);
  if (status === "invalid") {
    console.log(
      "The MCP server rejected the stored token. If your Sentry organization enforces SSO or otherwise rejects\n" +
        'user-bound OAuth tokens, signing in again will not help: see "Known limitations" in the README.',
    );
  }
}

// A vault holds one active credential per MCP server URL, so signing in again
// replaces the old one.
async function storeCredential(vaultId: string, clientId: string, tokenEndpoint: string, tokens: Tokens, refreshToken: string): Promise<string> {
  for await (const credential of client.beta.vaults.credentials.list(vaultId)) {
    const { auth } = credential;
    if (auth.type !== "environment_variable" && auth.mcp_server_url === MCP_SERVER_URL && !credential.archived_at) {
      await client.beta.vaults.credentials.archive(credential.id, { vault_id: vaultId });
    }
  }
  const credential = await client.beta.vaults.credentials.create(vaultId, {
    display_name: "Sentry MCP (OAuth)",
    metadata: { quickstart: "sentry-autofix" },
    auth: {
      type: "mcp_oauth",
      mcp_server_url: MCP_SERVER_URL,
      access_token: tokens.access_token,
      ...(tokens.expires_in ? { expires_at: new Date(Date.now() + tokens.expires_in * 1000).toISOString() } : {}),
      refresh: {
        refresh_token: refreshToken,
        client_id: clientId,
        token_endpoint: tokenEndpoint,
        token_endpoint_auth: { type: "none" },
        resource: MCP_SERVER_URL,
        // The scope Sentry reported for this grant.
        ...(tokens.scope ? { scope: tokens.scope } : {}),
      },
    },
  });
  return credential.id;
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exit(1);
});
