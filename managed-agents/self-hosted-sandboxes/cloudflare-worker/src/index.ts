/**
 * Cloudflare Worker (pure-Worker variant): webhook → drain environment work
 * queue → start a per-session Durable Object running the TS tool dispatcher
 * with an in-isolate fake filesystem. No container, no real shell.
 *
 * The webhook is a wake-up signal only. Each delivery drains *all* pending
 * work items, so a single arriving webhook recovers any earlier missed ones.
 */
import Anthropic from "@anthropic-ai/sdk";
import type { SandboxRunner } from "./runner";

export { SandboxRunner } from "./runner";

export interface Env {
  RUNNER: DurableObjectNamespace<SandboxRunner>;
  ANTHROPIC_BASE_URL: string;
  ANTHROPIC_ENVIRONMENT_ID: string;
  ANTHROPIC_WEBHOOK_SECRET: string;
  ANTHROPIC_ENVIRONMENT_KEY: string;
}

const MAX_DRAIN = 25;
// Anthropic's deliveries are a few hundred bytes. Anything near this is not
// one, and the cap bounds the work an unsigned caller can make us do.
const MAX_BODY_BYTES = 1024 * 1024;

// These become Durable Object names and env values, so check their shape
// before use even though they come from Anthropic's API.
const SESSION_ID = /^sesn_[A-Za-z0-9]+$/;
const WORK_ID = /^work_[A-Za-z0-9]+$/;
const ENVIRONMENT_ID = /^env_[A-Za-z0-9]+$/;

// Best-effort dedupe on the delivery's event id. This is one isolate's memory:
// Cloudflare may serve a retry from another isolate that has never seen the
// id. Correctness does not depend on it, because claiming a work item is
// atomic on the server and a session's runner is get-or-create. It saves a
// redundant drain on a warm isolate. "Handled" and "in flight" are separate so
// a retry that arrives mid-drain is not acked as done before the outcome is
// known.
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

/** Scrub credential shapes before mirroring an error message to the function log. */
function redact(s: string): string {
  return s
    .replace(/sk-ant-[A-Za-z0-9._-]+/g, "sk-ant-[REDACTED]")
    .replace(/whsec_[A-Za-z0-9+/=_-]+/g, "whsec_[REDACTED]")
    .replace(/Bearer\s+\S{8,}/gi, "Bearer [REDACTED]");
}

/**
 * Structured, redacted error detail for log lines. Surfaces the SDK's
 * `status` + `requestID` when present so an API failure is correlatable to a
 * server-side trace, and the message (with credential shapes stripped) for
 * everything else (DO RPC failures, container start errors).
 */
function errDetail(e: unknown): string {
  if (e instanceof Error) {
    const { status, requestID } = e as Error & { status?: number; requestID?: string | null };
    const parts = [e.constructor.name];
    if (status !== undefined) parts.push(`status=${status}`);
    if (requestID) parts.push(`request_id=${requestID}`);
    if (e.message) parts.push(redact(e.message));
    return parts.join(" ");
  }
  return String(e);
}

/**
 * Drain the work queue. The TS `WorkPoller` long-polls and never returns on an
 * empty queue, but a Worker fetch handler must respond, so poll → ack until
 * empty here. The runner DO owns the lease (heartbeat + force-stop), so the
 * webhook never posts `stop`.
 */
async function drainWork(env: Env, client: Anthropic): Promise<{ spawned: object[]; complete: boolean }> {
  const spawned: object[] = [];
  // False when a poll failed and the drain stopped early. The caller then does
  // not remember the delivery as handled, so a retry of it drains again.
  let complete = true;
  for (let i = 0; i < MAX_DRAIN; i++) {
    let work;
    try {
      // The SDK sends `anthropic-beta: managed-agents-2026-04-01` on its own.
      work = await client.beta.environments.work.poll(env.ANTHROPIC_ENVIRONMENT_ID, {
        reclaim_older_than_ms: 2000,
      });
    } catch (e) {
      // /work/poll can 404 ("EnvironmentInstance not found for session …")
      // when it dequeues an entry whose session is gone. The stale entry is
      // consumed server-side, so retrying moves past it. Anything else is a
      // config or transient failure: stop and recover on the next webhook.
      const { status, requestID } = (e ?? {}) as { status?: number; requestID?: string | null };
      console.warn(
        `[webhook] poll failed status=${status ?? "?"} request_id=${requestID ?? "?"}: ${status === 404 ? "skipping" : "stopping drain"}`,
      );
      if (status === 404) continue;
      complete = false;
      break;
    }
    if (!work) break;
    // Log the claimed work item with an explicit allowlist, so `actor` (PII),
    // `metadata` (user-provided), and `secret` never reach the log.
    console.log(
      `[webhook] polled work=${JSON.stringify({
        id: work.id,
        environment_id: work.environment_id,
        data: { type: work.data.type, id: work.data.id },
        created_at: work.created_at,
        acknowledged_at: work.acknowledged_at,
        latest_heartbeat_at: work.latest_heartbeat_at,
      })}`,
    );
    if (work.data.type !== "session") continue;

    const sessionId = work.data.id;
    // The poll is keyed by this environment's id and key, so an item for
    // another environment should be impossible. Check anyway: the cost of
    // being wrong is running someone else's session on this account.
    if (
      work.environment_id !== env.ANTHROPIC_ENVIRONMENT_ID ||
      !SESSION_ID.test(sessionId) ||
      !WORK_ID.test(work.id)
    ) {
      console.warn("[webhook] skipping a work item that is not for this environment or has a malformed id");
      continue;
    }
    try {
      // The client is authed with the environment key, the single credential
      // for poll / ack / stop, so no per-call Authorization header is needed.
      await client.beta.environments.work.ack(work.id, {
        environment_id: env.ANTHROPIC_ENVIRONMENT_ID,
      });

      const stub = env.RUNNER.get(env.RUNNER.idFromName(sessionId));
      const wasLive = await stub.isLive();
      if (!wasLive) {
        await stub.start({
          sessionId,
          environmentKey: env.ANTHROPIC_ENVIRONMENT_KEY,
          workId: work.id,
          environmentId: env.ANTHROPIC_ENVIRONMENT_ID,
        });
      }
      spawned.push({ session_id: sessionId, work_id: work.id, created: !wasLive });
    } catch (e) {
      // Skip and keep draining. The lease lapses and the next webhook reclaims.
      const detail = errDetail(e);
      console.warn(`[webhook] FAILED work=${work.id} session=${sessionId}: ${detail}`);
      spawned.push({ session_id: sessionId, work_id: work.id, error: detail });
    }
  }
  return { spawned, complete };
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    if (req.method !== "POST") return new Response("method not allowed", { status: 405 });
    if (Number(req.headers.get("content-length") ?? 0) > MAX_BODY_BYTES) {
      return new Response("payload too large", { status: 413 });
    }
    if (!ENVIRONMENT_ID.test(env.ANTHROPIC_ENVIRONMENT_ID ?? "")) {
      console.error("[webhook] ANTHROPIC_ENVIRONMENT_ID is not set: put the environment ID from ../webhook-demo/claude-lock.json in wrangler.toml");
      return new Response("not configured", { status: 500 });
    }

    const client = new Anthropic({
      authToken: env.ANTHROPIC_ENVIRONMENT_KEY,
      baseURL: env.ANTHROPIC_BASE_URL,
      // Pass the whsec_ secret as-is: the SDK decodes its URL-safe base64 internally.
      webhookKey: env.ANTHROPIC_WEBHOOK_SECRET,
    });

    const body = await req.text();
    if (body.length > MAX_BODY_BYTES) return new Response("payload too large", { status: 413 });
    let event: ReturnType<typeof client.beta.webhooks.unwrap>;
    try {
      event = client.beta.webhooks.unwrap(body, { headers: Object.fromEntries(req.headers) });
    } catch (e) {
      console.warn(`[webhook] signature reject: ${e instanceof Error ? e.constructor.name : "Error"}`);
      return new Response("signature verification failed", { status: 401 });
    }

    if (event.data.type !== "session.status_run_started") {
      return Response.json({ status: "ignored", event_type: event.data.type });
    }

    if (handledEventIds.has(event.id)) return Response.json({ status: "duplicate" });
    if (inFlightEventIds.has(event.id)) {
      return new Response("still handling this event", { status: 503 });
    }
    inFlightEventIds.add(event.id);
    try {
      const { spawned, complete } = await drainWork(env, client);
      // Only a drain that ran to the end marks the id handled. If a poll
      // failed partway, or the drain threw (a 500), a retry of this delivery
      // is processed from scratch.
      if (complete) rememberHandled(event.id);
      return Response.json({ status: "ok", spawned });
    } finally {
      inFlightEventIds.delete(event.id);
    }
  },
};
