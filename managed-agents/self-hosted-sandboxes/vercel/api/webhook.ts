/**
 * Vercel Function: Anthropic session webhook → drain environment work queue →
 * start a Vercel Sandbox per item.
 *
 * The webhook is a wake-up signal only. Each delivery drains *all* pending
 * work items (not only the one that triggered it), so a single arriving
 * webhook recovers any earlier missed deliveries. A bad work item is logged
 * and skipped. Its lease lapses and it reclaims on the next webhook, so it
 * can't wedge the rest of the queue.
 *
 * Flow per webhook delivery:
 *   1. Verify the Standard Webhooks signature via `client.beta.webhooks.unwrap()`.
 *   2. Only act on data.type == "session.status_run_started".
 *   3. Loop work.poll() until empty; per item: ack, then create a Vercel
 *      Sandbox running runner/runner.mjs.
 *
 * Env (vercel env add ...):
 *   ANTHROPIC_WEBHOOK_SECRET   - issued by Anthropic at webhook registration
 *   ANTHROPIC_ENVIRONMENT_ID   - the self-hosted environment id
 *   ANTHROPIC_ENVIRONMENT_KEY  - the environment key: Bearer auth for the work
 *                                poll/ack/stop. It stays in this function.
 *   ANTHROPIC_BASE_URL         - optional, default https://api.anthropic.com
 *   ALLOW_ENVIRONMENT_KEY_IN_SANDBOX - optional, see sandboxCredentials()
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import Anthropic from "@anthropic-ai/sdk";
import { Sandbox } from "@vercel/sandbox";

// 0.124.0 is the first release whose handleItem() accepts the per-session
// work secret.
const SDK_VERSION = ">=0.124.0 <1.0.0";
const SANDBOX_TIMEOUT_MS = 30 * 60 * 1000;
const MAX_DRAIN = 25;
// Anthropic's deliveries are a few hundred bytes. The cap bounds the work an
// unsigned caller can make this function do.
const MAX_BODY_BYTES = 1024 * 1024;

// These become KV keys and sandbox env values, so check their shape before use
// even though they come from Anthropic's API.
const SESSION_ID = /^sesn_[A-Za-z0-9]+$/;
const WORK_ID = /^work_[A-Za-z0-9]+$/;

// Best-effort dedupe on the delivery's event id. This is one function
// instance's memory: Vercel may serve a retry from another instance that has
// never seen the id. Correctness does not depend on it, because claiming a
// work item is atomic on the server, and `SessionToolRunner` dedups tool calls
// so a duplicate runner is wasteful, not wrong. "Handled" and "in flight" are
// separate so a retry that arrives mid-drain is not acked as done before the
// outcome is known.
const MAX_REMEMBERED_EVENTS = 1000;
const handledEventIds = new Set<string>();
const inFlightEventIds = new Set<string>();

function rememberHandled(id: string): void {
  handledEventIds.add(id);
  if (handledEventIds.size > MAX_REMEMBERED_EVENTS) {
    // Sets iterate in insertion order, so the first value is the oldest.
    const oldest = handledEventIds.values().next().value;
    if (oldest !== undefined) handledEventIds.delete(oldest);
  }
}
// Where the runner's package.json + runner.mjs live and where `npm install` runs.
const RUNNER_DIR = "/vercel/sandbox/runner";
// The agent's working tree. Created at sandbox start; matches the workdir the
// other variants use (Modal mounts a volume at /workspace, the Cloudflare
// container runs `ant beta:worker run --workdir /workspace`). Vercel Sandboxes
// have no persistent volumes, so these are fresh per sandbox.
const AGENT_DIRS = ["/mnt/session", "/workspace"];
const WORKDIR = "/workspace";

// Read at module load so Vercel's file tracer bundles it. vercel.json
// includeFiles is a second line of defense for builds where tracing misses
// the readFileSync.
const RUNNER_SOURCE = readFileSync(
  fileURLToPath(new URL("../runner/runner.mjs", import.meta.url)),
  "utf-8",
);

// The runner's package.json, installed inside the sandbox at spawn time. Same
// SDK range as the webhook handler so the worker API surface matches.
const RUNNER_PACKAGE_JSON = JSON.stringify(
  {
    name: "self-hosted-sandbox-runner",
    private: true,
    type: "module",
    dependencies: { "@anthropic-ai/sdk": SDK_VERSION, minimatch: "^9.0.5" },
  },
  null,
  2,
);

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`${name} is not set`);
  return v;
}

function baseURL(): string {
  return process.env.ANTHROPIC_BASE_URL ?? "https://api.anthropic.com";
}

/** Scrub credential shapes before mirroring sandbox output to the function log. */
function redact(s: string): string {
  return s
    .replace(/sk-ant-[A-Za-z0-9._-]+/g, "sk-ant-[REDACTED]")
    .replace(/whsec_[A-Za-z0-9+/=_-]+/g, "whsec_[REDACTED]")
    .replace(/Bearer\s+\S{8,}/gi, "Bearer [REDACTED]");
}

interface ProcessedItem {
  session_id: string;
  work_id: string;
  sandbox_id?: string;
  reused?: boolean;
  error?: string;
}

/**
 * session_id → sandbox_id mapping, optional. Vercel Sandbox has no native
 * tag/label/get-by-name API and `Sandbox.list()` returns no per-sandbox
 * metadata, so reuse needs external state. Uses Vercel KV when configured;
 * falls back to fresh-per-run otherwise so the demo works without provisioning.
 */
type KVLike = {
  get<T>(key: string): Promise<T | null>;
  set(key: string, value: unknown, opts?: { px?: number }): Promise<unknown>;
  del(key: string): Promise<unknown>;
};
let _kv: KVLike | null | undefined;
async function kvStore(): Promise<KVLike | null> {
  if (_kv !== undefined) return _kv;
  if (!process.env.KV_REST_API_URL || !process.env.KV_REST_API_TOKEN) return (_kv = null);
  try {
    const { kv } = await import("@vercel/kv");
    return (_kv = kv as unknown as KVLike);
  } catch {
    return (_kv = null);
  }
}

const sandboxKey = (sessionId: string) => `shs:sandbox:${sessionId}`;

/**
 * Find an existing running sandbox for this session and renew its lifetime.
 * Returns `null` when there's no mapping, the mapped sandbox is no longer
 * running, or KV isn't configured.
 */
async function findLiveSandbox(sessionId: string): Promise<Sandbox | null> {
  const kv = await kvStore();
  if (!kv) return null;
  const sandboxId = await kv.get<string>(sandboxKey(sessionId));
  if (!sandboxId) return null;
  try {
    const sb = await Sandbox.get({ sandboxId });
    if (sb.status !== "running") {
      await kv.del(sandboxKey(sessionId));
      return null;
    }
    // The sandbox VM has its own clock independent of the runner. Renew it on
    // each new run so an active session doesn't get killed mid-turn. Once the
    // runner exits (60s after end_turn idle) renewals stop and the sandbox
    // dies at the next timeout boundary.
    await sb.extendTimeout(SANDBOX_TIMEOUT_MS).catch(() => {});
    return sb;
  } catch {
    await kv.del(sandboxKey(sessionId)).catch(() => {});
    return null;
  }
}

/** Diagnostics we author and control: safe to show in logs and the webhook
 * response (key names, never values). */
class WorkError extends Error {}

/**
 * Pick what the sandbox authenticates with, or null to refuse the item.
 *
 * The agent in the sandbox runs arbitrary bash, so it can read its env. The
 * work item's per-session `secret` carries a token scoped to that one session,
 * so that is what goes in. The environment key can claim any session's work in
 * this environment, so it only goes in when the operator opted in with
 * ALLOW_ENVIRONMENT_KEY_IN_SANDBOX=true, which is reasonable only when every
 * session in the environment trusts every other.
 */
function sandboxCredentials(
  secret: string | null | undefined,
  environmentKey: string,
): Record<string, string> | null {
  if (secret) return { ANTHROPIC_WORK_SECRET: secret };
  if ((process.env.ALLOW_ENVIRONMENT_KEY_IN_SANDBOX ?? "").toLowerCase() === "true") {
    return { ANTHROPIC_ENVIRONMENT_KEY: environmentKey };
  }
  return null;
}

/** Ack and create a sandbox for one work item.
 * Raises on ack failure or Vercel API errors. The caller treats any raise as
 * "skip this item and keep draining".
 */
async function processWorkItem(
  client: Anthropic,
  work: { id: string; secret?: string | null; data: { id: string } },
  environmentId: string,
  environmentKey: string,
): Promise<ProcessedItem> {
  const sessionId = work.data.id;

  // `client` is authed with the environment key, the single credential for
  // poll / ack / stop, so no per-call Authorization header is needed.
  await client.beta.environments.work.ack(work.id, { environment_id: environmentId });

  // Reuse a live sandbox for the same session if KV has a mapping for it. The
  // runner inside is still streaming and dispatching; it just needs the
  // already-extended VM timeout. Without KV every delivery creates a fresh
  // sandbox. SessionToolRunner dedups via seen/answered, so a duplicate runner
  // is wasteful, not wrong.
  const existing = await findLiveSandbox(sessionId);
  if (existing) {
    console.log(`[webhook] work=${work.id} session=${sessionId} sandbox=${existing.sandboxId} (reused)`);
    return { session_id: sessionId, work_id: work.id, sandbox_id: existing.sandboxId, reused: true };
  }

  const credentials = sandboxCredentials(work.secret, environmentKey);
  if (credentials === null) {
    // The item is ack'd. Force-stop it so it does not sit on its lease and
    // come back on every webhook.
    await client.beta.environments.work.stop(work.id, { environment_id: environmentId, force: true });
    console.warn(
      `[webhook] REFUSED work=${work.id} session=${sessionId}: the work item carried no per-session secret, and this deploy does not put the environment key in sandboxes. Set ALLOW_ENVIRONMENT_KEY_IN_SANDBOX=true only if every session in this environment trusts every other.`,
    );
    throw new WorkError("no_session_secret");
  }
  if ("ANTHROPIC_ENVIRONMENT_KEY" in credentials) {
    console.warn(`[webhook] session=${sessionId}: the sandbox receives the ENVIRONMENT KEY (opt-in fallback)`);
  }

  const sandbox = await Sandbox.create({
    runtime: "node24",
    timeout: SANDBOX_TIMEOUT_MS,
    networkPolicy: {
      // npm install + Anthropic API. Add github.com etc. if your tools need it.
      allow: [new URL(baseURL()).hostname, "registry.npmjs.org"],
    },
  });
  // Record session_id → sandbox_id with a TTL matching the VM timeout so stale
  // mappings self-evict. Best effort: a failed write means the next delivery
  // creates a duplicate sandbox.
  await (await kvStore())?.set(sandboxKey(sessionId), sandbox.sandboxId, { px: SANDBOX_TIMEOUT_MS }).catch(() => {});

  await sandbox.writeFiles([
    { path: `${RUNNER_DIR}/runner.mjs`, content: Buffer.from(RUNNER_SOURCE) },
    { path: `${RUNNER_DIR}/package.json`, content: Buffer.from(RUNNER_PACKAGE_JSON) },
  ]);

  // Root-owned paths: create them as root, then chown to the sandbox user so
  // the runner (which runs unprivileged) can write the agent's working tree.
  // The command string is built from constants only.
  const mkdirs = await sandbox.runCommand({
    cmd: "sh",
    args: ["-c", `mkdir -p ${AGENT_DIRS.join(" ")} && chown -R "$(stat -c %u:%g ${RUNNER_DIR})" ${AGENT_DIRS.join(" ")}`],
    sudo: true,
  });
  if (mkdirs.exitCode !== 0) {
    console.warn(`[webhook] sandbox=${sandbox.sandboxId} mkdir rc=${mkdirs.exitCode}: ${redact((await mkdirs.output("both")).trim())}`);
  }

  // Install runner deps and surface the result in the *function* logs
  // (`vercel logs <project>`). Sandbox stdout isn't visible without the
  // Sandboxes observability tab, which not every plan has.
  const install = await sandbox.runCommand({
    cmd: "sh",
    args: ["-c", `cd ${RUNNER_DIR} && npm install --no-audit --no-fund 2>&1`],
  });
  const installOut = await install.output("both");
  console.log(
    `[webhook] sandbox=${sandbox.sandboxId} npm install rc=${install.exitCode}: ${redact(installOut.slice(-500).trim())}`,
  );
  if (install.exitCode !== 0) throw new WorkError(`npm install failed rc=${install.exitCode}`);

  // Runner detached: its heartbeat must outlive this function invocation.
  const runner = await sandbox.runCommand({
    cmd: "node",
    args: ["runner.mjs"],
    cwd: RUNNER_DIR,
    // Same env contract as `ant beta:worker poll --on-work`: runner.mjs reads these
    // to build the client and run EnvironmentWorker.handleItem(). The credential
    // is whatever sandboxCredentials() picked above.
    env: {
      ANTHROPIC_BASE_URL: baseURL(),
      ...credentials,
      ANTHROPIC_SESSION_ID: sessionId,
      ANTHROPIC_ENVIRONMENT_ID: environmentId,
      ANTHROPIC_WORK_ID: work.id,
      WORKDIR,
    },
    detached: true,
  });

  // Mirror the runner's first ~30s of stdout/stderr into the function log so
  // crash-on-start (bad import, 401, missing env) and the first tool dispatch
  // are debuggable from `vercel logs` alone. The runner keeps going after we
  // stop listening.
  const tail: string[] = [];
  const tailAbort = new AbortController();
  const tailTimeout = setTimeout(() => tailAbort.abort(), 30_000);
  try {
    for await (const log of runner.logs({ signal: tailAbort.signal })) {
      tail.push(log.data);
      if (tail.join("").length > 8_000) break;
    }
  } catch {
    // aborted by timeout, as expected
  } finally {
    clearTimeout(tailTimeout);
  }
  console.log(`[webhook] sandbox=${sandbox.sandboxId} runner head:\n${redact(tail.join("").trim()) || "(no output yet)"}`);

  console.log(`[webhook] acked work=${work.id} session=${sessionId} sandbox=${sandbox.sandboxId} (created)`);
  return { session_id: sessionId, work_id: work.id, sandbox_id: sandbox.sandboxId };
}

/**
 * Drain the work queue. The TS `WorkPoller` long-polls and never returns on
 * an empty queue, but a serverless handler must respond, so poll → ack until
 * empty here. The runner sandbox owns the lease (heartbeat + force-stop), so
 * the webhook never posts `stop`.
 */
async function drainWork(
  client: Anthropic,
  environmentId: string,
  environmentKey: string,
): Promise<{ results: ProcessedItem[]; complete: boolean }> {
  const results: ProcessedItem[] = [];
  // False when a poll failed and the drain stopped early. The caller then does
  // not remember the delivery as handled, so a retry of it drains again.
  let complete = true;
  for (let i = 0; i < MAX_DRAIN; i++) {
    let work;
    try {
      // The SDK sends `anthropic-beta: managed-agents-2026-04-01` on its own.
      work = await client.beta.environments.work.poll(environmentId, {
        reclaim_older_than_ms: 2000,
      });
    } catch (e) {
      // /work/poll can 404 when it dequeues an entry whose session is gone.
      // The stale entry is consumed server-side, so retrying moves past it.
      // Anything else is a config or transient failure: stop and recover on
      // the next webhook.
      const { status, requestID } = (e ?? {}) as { status?: number; requestID?: string | null };
      console.warn(
        `[webhook] poll failed status=${status ?? "?"} request_id=${requestID ?? "?"}: ${status === 404 ? "skipping" : "stopping drain"}`,
      );
      if (status === 404) continue;
      complete = false;
      break;
    }
    if (!work) break;
    if (work.data.type !== "session") {
      console.log(`[webhook] skipping work=${work.id} type=${work.data.type}`);
      continue;
    }
    // The poll is keyed by this environment's id and key, so an item for
    // another environment should be impossible. Check anyway: the cost of
    // being wrong is running someone else's session on this account.
    if (work.environment_id !== environmentId || !SESSION_ID.test(work.data.id) || !WORK_ID.test(work.id)) {
      console.warn("[webhook] skipping a work item that is not for this environment or has a malformed id");
      continue;
    }
    try {
      results.push(await processWorkItem(client, work, environmentId, environmentKey));
    } catch (e) {
      // Only WorkError carries our own controlled diagnostic text. SDK / Vercel
      // exceptions can embed request context, so log type only.
      const detail = e instanceof WorkError ? e.message : e?.constructor?.name ?? "unknown";
      console.error(`[webhook] FAILED work=${work.id} session=${work.data.id}: ${detail}`);
      results.push({ session_id: work.data.id, work_id: work.id, error: detail });
    }
  }
  return { results, complete };
}

// Vercel only hands Node.js `api/` functions the Web Standard `Request` when the
// handler is exported as a named HTTP method. `export default` gets the legacy
// `(req: IncomingMessage, res: ServerResponse)` shape, where `req.text()` doesn't
// exist. Only POST is exported, so every other method is a 405.
export async function POST(req: Request): Promise<Response> {
  if (Number(req.headers.get("content-length") ?? 0) > MAX_BODY_BYTES) {
    return new Response("payload too large", { status: 413 });
  }
  const client = new Anthropic({
    authToken: requireEnv("ANTHROPIC_ENVIRONMENT_KEY"),
    baseURL: baseURL(),
    // Pass the whsec_ secret as-is: the SDK decodes its URL-safe base64 internally.
    webhookKey: requireEnv("ANTHROPIC_WEBHOOK_SECRET"),
  });

  const body = await req.text();
  if (body.length > MAX_BODY_BYTES) return new Response("payload too large", { status: 413 });
  let event: ReturnType<typeof client.beta.webhooks.unwrap>;
  try {
    event = client.beta.webhooks.unwrap(body, { headers: Object.fromEntries(req.headers) });
  } catch (e) {
    console.error(`[webhook] signature reject: ${e instanceof Error ? e.constructor.name : "Error"}`);
    return new Response("signature verification failed", { status: 401 });
  }

  console.log(`[webhook] event=${event.data.type} session_id=${event.data.id}`);
  if (event.data.type !== "session.status_run_started") {
    return Response.json({ status: "ignored", event_type: event.data.type });
  }

  if (handledEventIds.has(event.id)) return Response.json({ status: "duplicate" });
  if (inFlightEventIds.has(event.id)) {
    return new Response("still handling this event", { status: 503 });
  }
  inFlightEventIds.add(event.id);
  try {
    const { results: spawned, complete } = await drainWork(
      client,
      requireEnv("ANTHROPIC_ENVIRONMENT_ID"),
      requireEnv("ANTHROPIC_ENVIRONMENT_KEY"),
    );
    // Only a drain that ran to the end marks the id handled. If a poll failed
    // partway, or the drain threw (a 500), a retry of this delivery is
    // processed from scratch.
    if (complete) rememberHandled(event.id);
    return Response.json({ status: "ok", event_type: event.data.type, spawned });
  } finally {
    inFlightEventIds.delete(event.id);
  }
}
