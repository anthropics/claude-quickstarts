import Anthropic from "@anthropic-ai/sdk";
import { ErrorCode, WebClient } from "@slack/web-api";

const client = new Anthropic();
const slack = new WebClient(process.env.SLACK_BOT_TOKEN);

// Dedupe retries (same event.id across retries). Swap for Redis/DB in prod.
// "Handled" and "being handled" are separate: if a slow first delivery times
// out and Anthropic redelivers while it is still running, acking the duplicate
// would mark the event delivered, and a later throw from the first attempt
// would lose the reply with no retry left.
const handledEventIds = new Set<string>();
const inFlightEventIds = new Set<string>();

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

  // Metadata alone is not proof the session is ours: anyone who can create a
  // session in this Anthropic workspace can set these two keys, and we would
  // post their text into a Slack channel with the bot token. Only sessions
  // started by this bridge's agent count.
  if (
    session.agent.id !== process.env.CLAUDE_AGENT_ID ||
    session.environment_id !== process.env.CLAUDE_ENVIRONMENT_ID
  ) {
    return new Response(null, { status: 204 });
  }
  const channel = session.metadata?.slack_channel;
  const thread_ts = session.metadata?.slack_thread_ts;
  if (!channel || !thread_ts) {
    return new Response(null, { status: 204 });
  }

  if (event.data.type === "session.status_terminated") {
    return post(channel, thread_ts, claudeSessionId, ":warning: Agent session terminated unexpectedly.");
  }

  // Pull the agent's reply text and the reason it stopped from the event
  // history. Iterating the page object auto-paginates. The types filter skips
  // the tool calls and results.
  const parts: string[] = [];
  let stopReason: string | undefined;
  for await (const e of client.beta.sessions.events.list(claudeSessionId, {
    types: ["agent.message", "session.status_idle"],
  })) {
    if (e.type === "session.status_idle") {
      stopReason = e.stop_reason?.type;
      continue;
    }
    if (e.type !== "agent.message") continue;
    let text = "";
    for (const block of e.content ?? []) {
      if (block.type === "text") text += block.text;
    }
    if (text) parts.push(text);
  }
  const responseText = parts.join("\n\n").trim();

  // Idle is not always "reply ready". Only end_turn means the agent finished.
  // The others would otherwise post nothing, or post a half-finished preamble
  // as if it were the answer.
  if (stopReason && stopReason !== "end_turn") {
    const why =
      stopReason === "requires_action"
        ? "it is waiting for a tool approval this bridge has no way to give (see skill.md, \"No approval surface\")"
        : stopReason === "budget_reached"
          ? "the session hit its budget"
          : "it ran out of retries";
    return post(channel, thread_ts, claudeSessionId, `:warning: The agent stopped before finishing: ${why}.`);
  }

  if (!responseText) return new Response(null, { status: 204 });
  return post(channel, thread_ts, claudeSessionId, responseText);
}

async function post(
  channel: string,
  thread_ts: string,
  claudeSessionId: string,
  text: string,
): Promise<Response> {
  try {
    await slack.chat.postMessage({ channel, thread_ts, text });
  } catch (err) {
    // Slack rejected the call (not_in_channel, invalid_auth). A retry gets the
    // same answer, so log it and ack instead of failing the delivery.
    if ((err as { code?: string }).code !== ErrorCode.PlatformError) throw err;
    console.error(
      `[managed-agents-webhook] chat.postMessage failed slack=${channel}/${thread_ts}:`,
      (err as { data?: { error?: string } }).data?.error,
    );
    return new Response(null, { status: 204 });
  }
  console.log(
    `[managed-agents-webhook] posted reply slack=${channel}/${thread_ts} claude=${claudeSessionId}`,
  );
  return new Response(null, { status: 204 });
}
