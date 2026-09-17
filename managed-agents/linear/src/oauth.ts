import { randomBytes } from "crypto";
import { chmodSync, readFileSync, renameSync, writeFileSync } from "fs";
import { join } from "path";

const LINEAR_CLIENT_ID = process.env.LINEAR_CLIENT_ID!;
const LINEAR_CLIENT_SECRET = process.env.LINEAR_CLIENT_SECRET!;
const BASE_URL = process.env.BASE_URL || `http://localhost:${process.env.PORT || 3000}`;
const REDIRECT_URI = `${BASE_URL}/oauth/callback`;

// /oauth/authorize has no login in front of it, and every mention from an
// installed workspace spends your Anthropic budget. So the gate fails closed:
//   - LINEAR_ALLOWED_ORG_IDS set: only those Linear organizations.
//   - unset: the first workspace to install owns the bridge. After that only
//     workspaces already in the token store pass, and adding another means
//     listing both in LINEAR_ALLOWED_ORG_IDS.
const ALLOWED_ORG_IDS = new Set(
  (process.env.LINEAR_ALLOWED_ORG_IDS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
);

export function isAllowedOrg(orgId: string): boolean {
  if (ALLOWED_ORG_IDS.size > 0) return ALLOWED_ORG_IDS.has(orgId);
  return tokens.size === 0 || tokens.has(orgId);
}

type TokenEntry = { accessToken: string; refreshToken: string; expiresAt: number };
const TOKEN_FILE = join(import.meta.dir, "..", ".linear-tokens.json");

// Only a missing file means "no installs yet". The install gate treats an
// empty store as "nobody owns this bridge, the next install may", so reading a
// corrupt or unreadable file as empty would reopen installs to everyone.
function load(): Map<string, TokenEntry> {
  let raw: string;
  try {
    raw = readFileSync(TOKEN_FILE, "utf-8");
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return new Map();
    console.error(`FATAL: cannot read ${TOKEN_FILE}: ${(err as Error).message}`);
    process.exit(1);
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("not a JSON object");
    return new Map(Object.entries(parsed as Record<string, TokenEntry>));
  } catch (err) {
    console.error(
      `FATAL: ${TOKEN_FILE} is not valid (${(err as Error).message}). Fix it, or delete it and reinstall at /oauth/authorize.`,
    );
    process.exit(1);
  }
}
// The file holds live access and refresh tokens, so keep it owner-only, and
// replace it in one step: a crash halfway through a plain write would leave a
// truncated file, which load() refuses to start on.
function save(m: Map<string, TokenEntry>) {
  const tmp = `${TOKEN_FILE}.tmp`;
  writeFileSync(tmp, JSON.stringify(Object.fromEntries(m), null, 2), { mode: 0o600 });
  chmodSync(tmp, 0o600);
  renameSync(tmp, TOKEN_FILE);
}
const tokens = load();

// OAuth `state`: a single-use random value that ties the callback to an
// authorize request this server started. Without it anyone can hand the
// callback a `code` of their choosing.
const STATE_TTL_MS = 10 * 60 * 1000;
const pendingStates = new Map<string, number>();

function newState(): string {
  const now = Date.now();
  for (const [s, expiresAt] of pendingStates) {
    if (expiresAt < now) pendingStates.delete(s);
  }
  const state = randomBytes(32).toString("hex");
  pendingStates.set(state, now + STATE_TTL_MS);
  return state;
}

function consumeState(state: string | null): boolean {
  if (!state) return false;
  const expiresAt = pendingStates.get(state);
  pendingStates.delete(state);
  return expiresAt !== undefined && expiresAt >= Date.now();
}

export function handleOAuthAuthorize(): Response {
  const params = new URLSearchParams({
    client_id: LINEAR_CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    response_type: "code",
    scope: "read,write,app:assignable,app:mentionable",
    actor: "app",
    state: newState(),
  });
  return Response.redirect(`https://linear.app/oauth/authorize?${params}`);
}

export async function handleOAuthCallback(url: URL): Promise<Response> {
  if (!consumeState(url.searchParams.get("state"))) {
    return new Response("Unknown or expired state. Start again at /oauth/authorize.", { status: 400 });
  }
  const code = url.searchParams.get("code");
  if (!code) return new Response("Missing code", { status: 400 });

  let tok: OAuthToken;
  let org: { id: string; name: string };
  try {
    tok = await exchange({ grant_type: "authorization_code", code, redirect_uri: REDIRECT_URI });
    org = await fetchOrganization(tok.access_token);
  } catch (err) {
    // The upstream body can echo the client secret's validity or the code, so
    // it goes to the server log, not the browser.
    console.error("[oauth] install failed:", (err as Error).message);
    return new Response("Linear rejected the install. Check the server log.", { status: 502 });
  }

  if (!isAllowedOrg(org.id)) {
    console.warn(`[oauth] refused install for org ${org.id} (see LINEAR_ALLOWED_ORG_IDS)`);
    // Linear installed the app the moment the user approved. Revoke the token
    // so the agent leaves that workspace's @-picker instead of sitting there
    // ignoring every mention.
    await revoke(tok.access_token);
    return new Response("This Linear workspace is not allowed to install this agent.", { status: 403 });
  }

  tokens.set(org.id, {
    accessToken: tok.access_token,
    refreshToken: tok.refresh_token,
    expiresAt: Date.now() + tok.expires_in * 1000,
  });
  save(tokens);

  // The workspace name is whatever its admin typed. JSON.stringify keeps
  // control characters out of the terminal, and escapeHtml out of the page.
  console.log(`[oauth] installed in ${JSON.stringify(org.name)} (${org.id})`);
  return new Response(
    `<h1>Agent installed in ${escapeHtml(org.name)}</h1><p>You can now @mention it in Linear.</p>`,
    { headers: { "Content-Type": "text/html; charset=utf-8" } },
  );
}

// One refresh per org at a time. Linear rotates the refresh token on every
// use, so two deliveries refreshing at once would race: the loser presents an
// already-used token, gets invalid_grant, and looks exactly like a revoked
// install. Concurrent callers share the in-progress promise instead.
const refreshing = new Map<string, Promise<TokenEntry>>();

export async function getAccessToken(orgId: string): Promise<string> {
  const entry = tokens.get(orgId);
  if (!entry) throw new NoLinearTokenError(orgId);
  if (entry.expiresAt - Date.now() >= 5 * 60 * 1000) return entry.accessToken;

  let pending = refreshing.get(orgId);
  if (!pending) {
    pending = refresh(orgId, entry).finally(() => refreshing.delete(orgId));
    refreshing.set(orgId, pending);
  }
  return (await pending).accessToken;
}

async function refresh(orgId: string, entry: TokenEntry): Promise<TokenEntry> {
  const presented = entry.refreshToken;
  let tok: OAuthToken;
  try {
    tok = await exchange({ grant_type: "refresh_token", refresh_token: presented });
  } catch (err) {
    // Only invalid_grant, for the refresh token still on file, means the grant
    // is gone (the workspace uninstalled the app). invalid_client is a wrong
    // LINEAR_CLIENT_SECRET, and a token that changed underneath us means
    // another refresh won. Both should be retried, not written off.
    const current = tokens.get(orgId);
    if (
      err instanceof OAuthExchangeError &&
      err.oauthError === "invalid_grant" &&
      current?.refreshToken === presented
    ) {
      throw new LinearInstallRevokedError(orgId);
    }
    throw err;
  }
  entry.accessToken = tok.access_token;
  entry.refreshToken = tok.refresh_token;
  entry.expiresAt = Date.now() + tok.expires_in * 1000;
  save(tokens);
  return entry;
}

// Thrown when Linear refuses to refresh an org's token. Retrying cannot fix
// that either. The fix is a reinstall at /oauth/authorize.
export class LinearInstallRevokedError extends Error {
  constructor(orgId: string) {
    super(`Linear refused to refresh the token for org ${orgId}. Reinstall at /oauth/authorize.`);
  }
}

class OAuthExchangeError extends Error {
  // The `error` field of the OAuth error body (invalid_grant, invalid_client).
  readonly oauthError: string | undefined;
  constructor(
    readonly status: number,
    body: string,
  ) {
    super(`Linear OAuth token exchange failed: ${status} ${body}`);
    try {
      this.oauthError = (JSON.parse(body) as { error?: string }).error;
    } catch {
      this.oauthError = undefined;
    }
  }
}

// Thrown when the bridge has no token for an org: it was never installed
// there, or .linear-tokens.json was deleted. Retrying cannot fix that.
export class NoLinearTokenError extends Error {
  constructor(orgId: string) {
    super(`No Linear token for org ${orgId}`);
  }
}

type OAuthToken = { access_token: string; refresh_token: string; expires_in: number };

async function exchange(params: Record<string, string>): Promise<OAuthToken> {
  const res = await fetch("https://api.linear.app/oauth/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: LINEAR_CLIENT_ID,
      client_secret: LINEAR_CLIENT_SECRET,
      ...params,
    }),
  });
  if (!res.ok) throw new OAuthExchangeError(res.status, await res.text());
  return (await res.json()) as OAuthToken;
}

async function revoke(accessToken: string): Promise<void> {
  try {
    const res = await fetch("https://api.linear.app/oauth/revoke", {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) console.warn(`[oauth] revoke returned ${res.status}`);
  } catch (err) {
    console.warn("[oauth] revoke failed:", (err as Error).message);
  }
}

async function fetchOrganization(accessToken: string): Promise<{ id: string; name: string }> {
  const res = await fetch("https://api.linear.app/graphql", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ query: "{ organization { id name } }" }),
  });
  if (!res.ok) throw new Error(`Linear organization lookup failed: ${res.status}`);
  const body = (await res.json()) as { data?: { organization?: { id?: string; name?: string } } };
  const org = body.data?.organization;
  if (!org?.id || !org.name) throw new Error("Linear organization lookup returned no organization");
  return { id: org.id, name: org.name };
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
