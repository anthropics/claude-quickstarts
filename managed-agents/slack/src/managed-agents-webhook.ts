import Anthropic from "@anthropic-ai/sdk";
import { ErrorCode, WebClient } from "@slack/web-api";

const client = new Anthropic();
const slack = new WebClient(process.env.SLACK_BOT_TOKEN);

// Dedupe retries (same event.id across retries). Swap for Redis/DB in prod.
const seenEventIds = new Set<string>();

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

  if (seenEventIds.has(event.id)) return new Response(null, { status: 204 });
  seenEventIds.add(event.id);

  // A throw becomes a 500 and Anthropic retries with the same event.id, so
  // forget the id on failure or the retry is deduped and the reply is lost.
  try {
    return await postReply(event);
  } catch (err) {
    seenEventIds.delete(event.id);
    throw err;
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

  const channel = session.metadata?.slack_channel;
  const thread_ts = session.metadata?.slack_thread_ts;
  if (!channel || !thread_ts) {
    return new Response(null, { status: 204 });
  }

  if (event.data.type === "session.status_terminated") {
    await slack.chat.postMessage({
      channel,
      thread_ts,
      text: ":warning: Agent session terminated unexpectedly.",
    });
    return new Response(null, { status: 204 });
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

  try {
    await slack.chat.postMessage({ channel, thread_ts, text: responseText });
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
