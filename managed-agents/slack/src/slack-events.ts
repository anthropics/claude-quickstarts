import { createHmac, timingSafeEqual } from "crypto";
import { kickoffAgentSession } from "./agent";

const SIGNING_SECRET = process.env.SLACK_SIGNING_SECRET!;
const TOLERANCE_SEC = 5 * 60;

// Dedupe Slack retries. Slack retries unacked events with the same event_id
// and an X-Slack-Retry-Num header.
const seenEventIds = new Set<string>();

// Slack request signing: https://api.slack.com/authentication/verifying-requests-from-slack
// Signature = "v0=" + hex(HMAC-SHA256(signing_secret, "v0:{timestamp}:{body}"))
function verify(rawBody: string, headers: Headers): void {
  const timestamp = headers.get("x-slack-request-timestamp");
  const signature = headers.get("x-slack-signature");
  if (!timestamp || !signature) throw new Error("missing slack headers");

  if (Math.abs(Date.now() / 1000 - parseInt(timestamp, 10)) > TOLERANCE_SEC) {
    throw new Error("timestamp outside tolerance");
  }

  const expected =
    "v0=" +
    createHmac("sha256", SIGNING_SECRET)
      .update(`v0:${timestamp}:${rawBody}`)
      .digest("hex");

  const a = Buffer.from(expected);
  const b = Buffer.from(signature);
  if (a.length !== b.length || !timingSafeEqual(a, b)) {
    throw new Error("signature mismatch");
  }
}

export async function handleSlackEvents(req: Request): Promise<Response> {
  const rawBody = await req.text();

  try {
    verify(rawBody, req.headers);
  } catch (err) {
    console.warn("[slack] signature verification failed:", (err as Error).message);
    return new Response("bad signature", { status: 401 });
  }

  const payload = JSON.parse(rawBody);

  // Slack sends this once when you save the Event Subscriptions URL.
  if (payload.type === "url_verification") {
    return new Response(payload.challenge, {
      headers: { "content-type": "text/plain" },
    });
  }

  if (payload.type !== "event_callback") {
    return new Response(null, { status: 204 });
  }

  if (seenEventIds.has(payload.event_id)) return new Response(null, { status: 204 });
  seenEventIds.add(payload.event_id);

  const ev = payload.event;

  // Handle @mentions in channels and DMs to the bot. Ignore edits, bot echoes,
  // and anything without text.
  const isMention = ev.type === "app_mention";
  const isDM = ev.type === "message" && ev.channel_type === "im" && !ev.subtype;
  if ((!isMention && !isDM) || ev.bot_id || !ev.text) {
    return new Response(null, { status: 204 });
  }

  // Fire-and-forget so we ack Slack within its 3s window.
  kickoffAgentSession({
    channel: ev.channel,
    thread_ts: ev.thread_ts ?? ev.ts,
    user: ev.user,
    text: stripMention(ev.text),
    team: payload.team_id,
  }).catch((err) => console.error("[slack] kickoff error:", err));

  return new Response(null, { status: 204 });
}

function stripMention(text: string): string {
  return text.replace(/<@[A-Z0-9]+>/g, "").trim();
}
