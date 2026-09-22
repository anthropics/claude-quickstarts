import Anthropic from "@anthropic-ai/sdk";
import {
  AuthenticationLinearError,
  ForbiddenLinearError,
  InvalidInputLinearError,
  LinearClient,
  UserLinearError,
} from "@linear/sdk";
import { forgetRun, wasStopped } from "./agent";
import { verifyRoute } from "./route-signature";
import { getAccessToken, isAllowedOrg, LinearInstallRevokedError, NoLinearTokenError } from "./oauth";

const client = new Anthropic();

// Dedupe retries (same event.id across retries). Swap for Redis/DB in prod.
// "Handled" and "being handled" are separate: if a slow first delivery times
// out and Anthropic redelivers while it is still running, acking the duplicate
// would mark the event delivered, and a later throw from the first attempt
// would lose the reply with no retry left.
const handledEventIds = new Set<string>();
const inFlightEventIds = new Set<string>();

// One delivery per Claude session, enforced here as well as by deleting the
// signature remotely. The remote delete can fail, and two idle events for one
// session carry different event ids, so both could verify before either
// consumes. These are in memory: the remote delete is what survives a restart.
const deliveredSessions = new Set<string>();
const deliveringSessions = new Set<string>();

export async function handleManagedAgentsWebhook(req: Request): Promise<Response> {
  const rawBody = await req.text();

  // Verify HMAC + timestamp and parse. Reads ANTHROPIC_WEBHOOK_SIGNING_KEY
  // from env. unwrap() needs a plain header map, not a fetch Headers object.
  let event: Anthropic.Beta.BetaWebhookEvent;
  try {
    event = client.beta.webhooks.unwrap(rawBody, {
      headers: Object.fromEntries(req.headers),
    });
  } catch (err) {
    console.warn("[managed-agents-webhook] signature verification failed");
    return new Response("bad signature", { status: 401 });
  }

  if (handledEventIds.has(event.id)) return new Response(null, { status: 204 });
  if (inFlightEventIds.has(event.id)) {
    return new Response("still handling this event", { status: 503 });
  }

  // A throw becomes a 500 and Anthropic retries with the same event.id. Only
  // a finished attempt marks the id handled, so that retry is processed.
  inFlightEventIds.add(event.id);
  try {
    const res = await postReply(event);
    handledEventIds.add(event.id);
    return res;
  } finally {
    inFlightEventIds.delete(event.id);
  }
}

async function postReply(event: Anthropic.Beta.BetaWebhookEvent): Promise<Response> {
  if (
    event.data.type !== "session.status_idled" &&
    event.data.type !== "session.status_terminated"
  ) {
    return new Response(null, { status: 204 });
  }

  const claudeSessionId = event.data.id;

  // Workspace webhooks fire for EVERY session in the workspace. Fetch the
  // session and filter by our metadata FIRST; ignore anything that isn't ours
  // (including sessions our key can't read).
  let session;
  try {
    session = await client.beta.sessions.retrieve(claudeSessionId);
  } catch (err) {
    // Only "not ours" is safe to ignore. A 429 or 5xx should fail the delivery
    // so Anthropic retries it.
    if (err instanceof Anthropic.NotFoundError || err instanceof Anthropic.PermissionDeniedError) {
      return new Response(null, { status: 204 });
    }
    throw err;
  }

  // Cheap first filter: a session on some other agent is never ours.
  if (
    session.agent.id !== process.env.CLAUDE_AGENT_ID ||
    session.environment_id !== process.env.CLAUDE_ENVIRONMENT_ID
  ) {
    return new Response(null, { status: 204 });
  }
  const linearSessionId = session.metadata?.linear_session_id;
  const linearOrgId = session.metadata?.linear_org_id;
  if (!linearSessionId || !linearOrgId || !isAllowedOrg(linearOrgId)) {
    return new Response(null, { status: 204 });
  }
  // The real ownership check. Matching agent and environment IDs is not proof:
  // anyone with workspace credentials can start a session on this same agent
  // with metadata of their choosing, and we would post their text into a
  // Linear issue with the installed org's token. Only a route this bridge
  // signed is trusted.
  if (!verifyRoute(
      claudeSessionId,
      linearSessionId,
      linearOrgId,
      session.metadata?.linear_route_iat,
      session.metadata?.linear_route_sig,
    )) {
    console.warn(`[managed-agents-webhook] ignored claude=${claudeSessionId}: route signature missing, invalid, or expired`);
    return new Response(null, { status: 204 });
  }

  // The route is good for one delivery. A signed session is still a session
  // anyone with workspace credentials can send another message to, and its
  // next idle would post their text here. So once this bridge has delivered,
  // or decided it never will, the route is spent: remembered here, and the
  // signature deleted remotely. deliver() throwing means "retry me", and then
  // neither happens, so the retry can verify.
  if (deliveredSessions.has(claudeSessionId)) return new Response(null, { status: 204 });
  if (deliveringSessions.has(claudeSessionId)) {
    return new Response("still delivering for this session", { status: 503 });
  }
  deliveringSessions.add(claudeSessionId);
  try {
    const res = await deliver(event, claudeSessionId, linearSessionId, linearOrgId);
    deliveredSessions.add(claudeSessionId);
    await consumeRoute(claudeSessionId);
    return res;
  } finally {
    deliveringSessions.delete(claudeSessionId);
  }
}

async function consumeRoute(claudeSessionId: string): Promise<void> {
  try {
    // Metadata is a patch, and null deletes the key.
    await client.beta.sessions.update(claudeSessionId, { metadata: { linear_route_sig: null, linear_route_iat: null } });
  } catch (err) {
    console.warn(
      `[managed-agents-webhook] could not clear the route signature on claude=${claudeSessionId} (this process still refuses it):`,
      (err as Error).message,
    );
  }
}

async function deliver(
  event: Anthropic.Beta.BetaWebhookEvent,
  claudeSessionId: string,
  linearSessionId: string,
  linearOrgId: string,
): Promise<Response> {
  // The run is over either way, so Stop has nothing left to interrupt.
  forgetRun(linearSessionId, claudeSessionId);

  // Stop interrupted this run and already told Linear so. Its half-finished
  // text is not the answer.
  if (wasStopped(claudeSessionId)) return new Response(null, { status: 204 });

  if (event.data.type === "session.status_terminated") {
    return postActivity(linearOrgId, linearSessionId, claudeSessionId, {
      type: "error",
      body: "Agent session terminated unexpectedly.",
    });
  }

  // Pull the agent's reply text from the event history. Iterating the page
  // object auto-paginates. The types filter skips the tool calls and results.
  const parts: string[] = [];
  for await (const e of client.beta.sessions.events.list(claudeSessionId, {
    types: ["agent.message"],
  })) {
    if (e.type !== "agent.message") continue;
    let text = "";
    for (const block of e.content ?? []) {
      if (block.type === "text") text += block.text;
    }
    if (text) parts.push(text);
  }
  const responseText = parts.join("\n\n").trim();
  if (!responseText) return new Response(null, { status: 204 });

  return postActivity(linearOrgId, linearSessionId, claudeSessionId, {
    type: "response",
    body: responseText,
  });
}

async function postActivity(
  linearOrgId: string,
  linearSessionId: string,
  claudeSessionId: string,
  content: { type: "response" | "error"; body: string },
): Promise<Response> {
  try {
    const linear = new LinearClient({ accessToken: await getAccessToken(linearOrgId) });
    await linear.createAgentActivity({ agentSessionId: linearSessionId, content });
  } catch (err) {
    // No token for the org, a revoked install, or an agent session Linear no
    // longer accepts activity on. A retry gets the same answer, so log it and
    // ack instead of failing the delivery.
    if (!isPermanentLinearFailure(err)) throw err;
    console.error(
      `[managed-agents-webhook] could not post to linear=${linearSessionId}:`,
      (err as Error).message,
    );
    return new Response(null, { status: 204 });
  }
  console.log(
    `[managed-agents-webhook] posted ${content.type} linear=${linearSessionId} claude=${claudeSessionId}`,
  );
  return new Response(null, { status: 204 });
}

function isPermanentLinearFailure(err: unknown): boolean {
  return (
    err instanceof NoLinearTokenError ||
    err instanceof LinearInstallRevokedError ||
    err instanceof AuthenticationLinearError ||
    err instanceof ForbiddenLinearError ||
    err instanceof InvalidInputLinearError ||
    err instanceof UserLinearError
  );
}
